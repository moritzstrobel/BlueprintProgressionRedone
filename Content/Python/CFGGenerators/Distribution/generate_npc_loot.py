#!/usr/bin/env python3
"""Generate BPR NPC blueprint loot pools and vanilla NPC inventory patches."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = SCRIPT_DIR.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Common.bpr_common import (
    RANK_ORDER,
    VANILLA_RANKS,
    cumulative_families,
    get_weapon_families,
    load_json,
    load_weapon_progression,
    logical_rank_for_vanilla,
    tier_blueprint_sid,
    upgrade_kit_sid,
)

CONTENT_DIR = PYTHON_ROOT.parent
NPC_CONFIG_FILE = SCRIPT_DIR / "npc_loot.json"
BASEGAME_ITEM_GENERATOR_DIR = CONTENT_DIR / "GameLite" / "GameData" / "ItemGeneratorPrototypes"
MOD_ITEM_GENERATOR_DIR = CONTENT_DIR / "GameLite" / "ModGameData" / "Testmod" / "ItemGeneratorPrototypes"
DYNAMIC_DIR = BASEGAME_ITEM_GENERATOR_DIR / "DynamicItemGenerator"
POOLS_OUTPUT = MOD_ITEM_GENERATOR_DIR / "BPR_NPC_ItemGeneratorPrototypes.cfg"
PATCH_OUTPUT = DYNAMIC_DIR / "NPCInventoryPatch_patch_BPR.cfg"
TIER_KEYS = (("tier_1", 1), ("tier_2", 2), ("tier_3", 3))
TARGET_RE = re.compile(r"^GeneralNPC_(?P<faction>[^_]+)_(?P<role>CloseCombat|Recon|Stormtrooper|Sniper|Heavy)_ItemGenerator$")


def validate(weapon: dict, npc: dict) -> None:
    known_families = set(get_weapon_families(weapon))
    for key, _ in TIER_KEYS + (("upgrade_kit", 0),):
        chance = npc.get("drop_chances", {}).get(key)
        if chance is None or not 0.0 <= float(chance) <= 1.0:
            raise ValueError(f"Invalid/missing NPC drop chance '{key}': {chance}")

    for faction, rank in npc.get("faction_max_rank", {}).items():
        if rank not in RANK_ORDER:
            raise ValueError(f"Faction '{faction}' has invalid max rank '{rank}'.")

    for role, families in npc.get("role_allowed_families", {}).items():
        unknown = sorted(set(families) - known_families)
        if unknown:
            raise ValueError(f"Role '{role}' contains unknown families: {', '.join(unknown)}")

    for target in npc.get("targets", []):
        match = TARGET_RE.match(target)
        if not match:
            raise ValueError(f"Unsupported NPC target name: {target}")
        faction = match.group("faction")
        role = match.group("role")
        if faction not in npc["faction_max_rank"]:
            raise ValueError(f"No faction_max_rank for {faction}")
        if role not in npc["role_allowed_families"]:
            raise ValueError(f"No role allowlist for {role}")


def rank_index(rank: str) -> int:
    return RANK_ORDER.index(rank)


def lower_rank(a: str, b: str) -> str:
    return RANK_ORDER[min(rank_index(a), rank_index(b))]


def parse_target(target: str) -> tuple[str, str]:
    match = TARGET_RE.match(target)
    if not match:
        raise ValueError(target)
    return match.group("faction"), match.group("role")


def effective_families(weapon: dict, npc: dict, faction: str, role: str, logical_player_rank: str) -> list[str]:
    effective_rank = lower_rank(logical_player_rank, npc["faction_max_rank"][faction])
    role_allowed = set(npc["role_allowed_families"][role])
    return [family for family in cumulative_families(weapon, effective_rank) if family in role_allowed]


def safe_sid_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def pool_prefix(faction: str, role: str, rank: str) -> str:
    return f"BPR_NPC_{safe_sid_part(faction)}_{safe_sid_part(role)}_{rank}"


def render_item_pool(sid: str, item_sids: list[str]) -> list[str]:
    lines = [
        f"{sid} : struct.begin {{refurl=@BaseGame/ItemGeneratorPrototypes.cfg;refkey=[0]}}",
        f"   SID = {sid}",
        "   ItemGenerator : struct.begin",
        "      [*] : struct.begin",
        "         Category = EItemGenerationCategory::Junk",
        "         bAllowSameCategoryGeneration = true",
        "         PossibleItems : struct.begin",
    ]
    for item_sid in item_sids:
        lines.extend([
            "            [*] : struct.begin",
            f"               ItemPrototypeSID = {item_sid}",
            "               Weight = 1",
            "               MinCount = 1",
            "               MaxCount = 1",
            "            struct.end",
        ])
    lines.extend(["         struct.end", "      struct.end", "   struct.end", "struct.end", ""])
    return lines


def render_roll_entry(pool_sid: str, chance: float) -> list[str]:
    return [
        "      [*] : struct.begin",
        "         Category = EItemGenerationCategory::SubItemGenerator",
        "         bAllowSameCategoryGeneration = true",
        "         PossibleItems : struct.begin",
        "            [*] : struct.begin",
        f"               ItemGeneratorPrototypeSID = {pool_sid}",
        f"               Chance = {chance:g}",
        "               MinCount = 1",
        "               MaxCount = 1",
        "            struct.end",
        "         struct.end",
        "      struct.end",
    ]


def render_roll_generator(prefix: str, npc: dict) -> list[str]:
    sid = f"{prefix}_Rolls"
    lines = [
        f"{sid} : struct.begin {{refurl=@BaseGame/ItemGeneratorPrototypes.cfg;refkey=[0]}}",
        f"   SID = {sid}",
        "   ItemGenerator : struct.begin",
    ]
    for chance_key, tier in TIER_KEYS:
        lines.extend(render_roll_entry(f"{prefix}_Tier_{tier}", float(npc["drop_chances"][chance_key])))
    lines.extend(render_roll_entry(f"{prefix}_UpgradeKit", float(npc["drop_chances"]["upgrade_kit"])))
    lines.extend(["   struct.end", "struct.end", ""])
    return lines


def generate_pools(weapon: dict, npc: dict) -> str:
    lines = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "// Sources: Python/Config/weapon_progression.json + Python/CFGGenerators/Distribution/npc_loot.json",
        "// Generated by: generate_npc_loot.py",
        f"// Output: Content/{POOLS_OUTPUT.relative_to(CONTENT_DIR).as_posix()}",
        "// -----------------------------------------------------------------------------",
        "",
    ]
    generated: set[tuple[str, str, str]] = set()
    for target in npc["targets"]:
        faction, role = parse_target(target)
        for rank in RANK_ORDER:
            key = (faction, role, rank)
            if key in generated:
                continue
            generated.add(key)
            families = effective_families(weapon, npc, faction, role, rank)
            if not families:
                continue
            prefix = pool_prefix(faction, role, rank)
            lines.extend([
                "// -----------------------------------------------------------------------------",
                f"// {faction} / {role} / {rank}",
                f"// Families: {', '.join(families)}",
                "// -----------------------------------------------------------------------------",
                "",
            ])
            for _, tier in TIER_KEYS:
                lines.extend(render_item_pool(
                    f"{prefix}_Tier_{tier}",
                    [tier_blueprint_sid(weapon, family, tier) for family in families],
                ))
            lines.extend(render_item_pool(
                f"{prefix}_UpgradeKit",
                [upgrade_kit_sid(weapon, family) for family in families],
            ))
            lines.extend(render_roll_generator(prefix, npc))
    return "\n".join(lines).rstrip() + "\n"


def generate_patch(weapon: dict, npc: dict) -> str:
    lines = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "// Sources: Python/Config/weapon_progression.json + Python/CFGGenerators/Distribution/npc_loot.json",
        "// Generated by: generate_npc_loot.py",
        f"// Output: Content/{PATCH_OUTPUT.relative_to(CONTENT_DIR).as_posix()}",
        "// -----------------------------------------------------------------------------",
        "",
        "// Entries use [*] so this patch does not depend on fixed array positions.",
        "",
    ]
    for target in npc["targets"]:
        faction, role = parse_target(target)
        entries: list[str] = []
        for vanilla_rank in VANILLA_RANKS:
            logical_rank = logical_rank_for_vanilla(weapon, vanilla_rank)
            families = effective_families(weapon, npc, faction, role, logical_rank)
            if not families:
                continue
            prefix = pool_prefix(faction, role, logical_rank)
            entries.extend([
                "      [*] : struct.begin",
                "         Category = EItemGenerationCategory::SubItemGenerator",
                "         bAllowSameCategoryGeneration = true",
                f"         PlayerRank = ERank::{vanilla_rank}",
                "         PossibleItems : struct.begin",
                "            [*] : struct.begin",
                f"               ItemGeneratorPrototypeSID = {prefix}_Rolls",
                "               Weight = 1",
                "            struct.end",
                "         struct.end",
                "      struct.end",
            ])
        if entries:
            lines.extend([
                f"{target} : struct.begin {{bpatch}}",
                "   ItemGenerator : struct.begin {bpatch}",
                *entries,
                "   struct.end",
                "struct.end",
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    weapon = load_weapon_progression()
    npc = load_json(NPC_CONFIG_FILE)
    validate(weapon, npc)

    MOD_ITEM_GENERATOR_DIR.mkdir(parents=True, exist_ok=True)
    DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
    POOLS_OUTPUT.write_text(generate_pools(weapon, npc), encoding="utf-8")
    PATCH_OUTPUT.write_text(generate_patch(weapon, npc), encoding="utf-8")

    print("BPR NPC Loot Generator")
    print("----------------------")
    print(f"NPC targets: {len(npc['targets'])}")
    print(f"Generated: {POOLS_OUTPUT}")
    print(f"Generated: {PATCH_OUTPUT}")


if __name__ == "__main__":
    main()
