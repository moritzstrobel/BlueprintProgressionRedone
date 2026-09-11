#!/usr/bin/env python3
"""
Generate BPR NPC blueprint loot.

Expected location:
    Content/Python/CFGGenerators/DynamicItemGenerator/generate_npc_loot.py

Configs in the same directory:
    weapon_progression.json
    npc_loot.json

Generated:
    Content/GameLite/GameData/ItemGeneratorPrototypes/
        BPR_NPC_ItemGeneratorPrototypes.cfg

    Content/GameLite/GameData/ItemGeneratorPrototypes/DynamicItemGenerator/
        NPCInventoryPatch_patch_BPR.cfg

Pool rule:
    effective families =
        families unlocked by PlayerRank
        ∩ families allowed for NPC role
        ∩ families available up to faction_max_rank

Vanilla Master maps to logical Veteran, matching the stash progression.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
WEAPON_CONFIG_FILE = SCRIPT_DIR / "weapon_progression.json"
NPC_CONFIG_FILE = SCRIPT_DIR / "npc_loot.json"

CONTENT_DIR = SCRIPT_DIR.parents[2]
ITEM_GENERATOR_DIR = CONTENT_DIR / "GameLite" / "GameData" / "ItemGeneratorPrototypes"
DYNAMIC_DIR = ITEM_GENERATOR_DIR / "DynamicItemGenerator"

POOLS_OUTPUT = ITEM_GENERATOR_DIR / "BPR_NPC_ItemGeneratorPrototypes.cfg"
PATCH_OUTPUT = DYNAMIC_DIR / "NPCInventoryPatch_patch_BPR.cfg"

RANK_ORDER = ("Newbie", "Experienced", "Veteran")
VANILLA_RANKS = ("Newbie", "Experienced", "Veteran", "Master")
TIER_KEYS = (("tier_1", 1), ("tier_2", 2), ("tier_3", 3))

TARGET_RE = re.compile(
    r"^GeneralNPC_(?P<faction>[^_]+)_(?P<role>CloseCombat|Recon|Stormtrooper|Sniper|Heavy)_ItemGenerator$"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config:\n{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(weapon: dict, npc: dict) -> None:
    for rank in RANK_ORDER:
        if rank not in weapon["weapon_progression"]:
            raise ValueError(f"Missing weapon rank: {rank}")

    for target in npc["targets"]:
        match = TARGET_RE.match(target)
        if not match:
            raise ValueError(f"Unsupported NPC target name: {target}")

        faction = match.group("faction")
        role = match.group("role")

        if faction not in npc["faction_max_rank"]:
            raise ValueError(f"No faction_max_rank for {faction}")

        if role not in npc["role_allowed_families"]:
            raise ValueError(f"No role allowlist for {role}")


def cumulative_families(weapon: dict, rank: str) -> list[str]:
    result: list[str] = []
    for current in RANK_ORDER:
        result.extend(weapon["weapon_progression"][current])
        if current == rank:
            break
    return list(dict.fromkeys(result))


def rank_index(rank: str) -> int:
    return RANK_ORDER.index(rank)


def lower_rank(a: str, b: str) -> str:
    return RANK_ORDER[min(rank_index(a), rank_index(b))]


def parse_target(target: str) -> tuple[str, str]:
    match = TARGET_RE.match(target)
    if not match:
        raise ValueError(target)
    return match.group("faction"), match.group("role")


def logical_rank_for_vanilla(weapon: dict, vanilla_rank: str) -> str:
    return weapon["rank_behavior"]["vanilla_rank_mapping"][vanilla_rank]


def effective_families(
    weapon: dict,
    npc: dict,
    faction: str,
    role: str,
    logical_player_rank: str,
) -> list[str]:
    faction_ceiling = npc["faction_max_rank"][faction]
    effective_rank = lower_rank(logical_player_rank, faction_ceiling)

    unlocked = set(cumulative_families(weapon, effective_rank))
    role_allowed = set(npc["role_allowed_families"][role])

    # Keep the global progression order.
    return [
        family
        for family in cumulative_families(weapon, effective_rank)
        if family in unlocked and family in role_allowed
    ]


def safe_sid_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def pool_prefix(faction: str, role: str, rank: str) -> str:
    return f"BPR_NPC_{safe_sid_part(faction)}_{safe_sid_part(role)}_{rank}"


def tier_sid(weapon: dict, family: str, tier: int) -> str:
    return weapon["item_sid_patterns"]["tier_blueprint"].format(
        family=family, tier=tier
    )


def kit_sid(weapon: dict, family: str) -> str:
    return weapon["item_sid_patterns"]["upgrade_kit"].format(family=family)


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
        lines += [
            "            [*] : struct.begin",
            f"               ItemPrototypeSID = {item_sid}",
            "               Weight = 1",
            "               MinCount = 1",
            "               MaxCount = 1",
            "            struct.end",
        ]

    lines += [
        "         struct.end",
        "      struct.end",
        "   struct.end",
        "struct.end",
        "",
    ]
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
        lines += render_roll_entry(
            f"{prefix}_Tier_{tier}",
            float(npc["drop_chances"][chance_key]),
        )

    lines += render_roll_entry(
        f"{prefix}_UpgradeKit",
        float(npc["drop_chances"]["upgrade_kit"]),
    )

    lines += [
        "   struct.end",
        "struct.end",
        "",
    ]
    return lines


def generate_pools(weapon: dict, npc: dict) -> str:
    lines = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "// Source: weapon_progression.json + npc_loot.json",
        "// Generated by: generate_npc_loot.py",
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

            families = effective_families(
                weapon, npc, faction, role, rank
            )

            prefix = pool_prefix(faction, role, rank)

            lines += [
                "// -----------------------------------------------------------------------------",
                f"// {faction} / {role} / {rank}",
                f"// Families: {', '.join(families) if families else '(none)'}",
                "// -----------------------------------------------------------------------------",
                "",
            ]

            # If a combination contains no possible families, do not emit pools.
            # The patch generator will also skip it.
            if not families:
                continue

            for _, tier in TIER_KEYS:
                lines += render_item_pool(
                    f"{prefix}_Tier_{tier}",
                    [tier_sid(weapon, family, tier) for family in families],
                )

            lines += render_item_pool(
                f"{prefix}_UpgradeKit",
                [kit_sid(weapon, family) for family in families],
            )

            lines += render_roll_generator(prefix, npc)

    return "\n".join(lines).rstrip() + "\n"


def generate_patch(weapon: dict, npc: dict) -> str:
    lines = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "// Source: weapon_progression.json + npc_loot.json",
        "// Generated by: generate_npc_loot.py",
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
            families = effective_families(
                weapon, npc, faction, role, logical_rank
            )

            if not families:
                continue

            prefix = pool_prefix(faction, role, logical_rank)

            entries += [
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
            ]

        if not entries:
            continue

        lines += [
            f"{target} : struct.begin {{bpatch}}",
            "   ItemGenerator : struct.begin {bpatch}",
            *entries,
            "   struct.end",
            "struct.end",
            "",
        ]

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    weapon = load_json(WEAPON_CONFIG_FILE)
    npc = load_json(NPC_CONFIG_FILE)
    validate(weapon, npc)

    ITEM_GENERATOR_DIR.mkdir(parents=True, exist_ok=True)
    DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)

    POOLS_OUTPUT.write_text(generate_pools(weapon, npc), encoding="utf-8")
    PATCH_OUTPUT.write_text(generate_patch(weapon, npc), encoding="utf-8")

    print("BPR NPC Loot Generator")
    print("----------------------")
    print(f"Weapon config: {WEAPON_CONFIG_FILE}")
    print(f"NPC config:    {NPC_CONFIG_FILE}")
    print()
    print(f"Generated: {POOLS_OUTPUT}")
    print(f"Generated: {PATCH_OUTPUT}")
    print()
    print(f"NPC targets: {len(npc['targets'])}")
    print("Drop chances:")
    print(f"  Tier I:      {npc['drop_chances']['tier_1']:.2%}")
    print(f"  Tier II:     {npc['drop_chances']['tier_2']:.2%}")
    print(f"  Tier III:    {npc['drop_chances']['tier_3']:.2%}")
    print(f"  Upgrade Kit: {npc['drop_chances']['upgrade_kit']:.2%}")


if __name__ == "__main__":
    main()
