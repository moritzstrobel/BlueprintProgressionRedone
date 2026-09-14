#!/usr/bin/env python3
"""Generate BPR trader stock pools and vanilla trader patches."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = SCRIPT_DIR.parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Common.bpr_common import RANK_ORDER, VANILLA_RANKS, get_weapon_families, load_json, load_weapon_progression, tier_blueprint_sid

CONTENT_DIR = PYTHON_ROOT.parent
TRADER_CONFIG_PATH = SCRIPT_DIR / "blueprint_traders.json"
PATCH_OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemGeneratorPrototypes"
    / "DynamicItemGenerator"
    / "DynamicItemGenerator_patch_BPR.cfg"
)
POOL_OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "ModGameData"
    / "Testmod"
    / "ItemGeneratorPrototypes"
    / "BPR_Traders_ItemGeneratorPrototypes.cfg"
)


def fmt_number(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def sid_fragment(value: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_")
    if not fragment:
        raise ValueError(f"Cannot create SID fragment from trader name: {value!r}")
    return fragment


def pool_group_key(trader: dict) -> str:
    stage = str(trader["progression_stage"])
    focus = trader.get("focus")
    focus_part = sid_fragment(focus) if focus else "All"
    return f"Stage{stage}_{focus_part}"


def pool_sid(trader: dict) -> str:
    return f"BPR_TraderPool_{pool_group_key(trader)}"


def validate_tier_chances(tier_chances: dict, context: str) -> None:
    for tier in (1, 2, 3):
        chance = tier_chances.get(str(tier))
        if not isinstance(chance, (int, float)) or chance < 0:
            raise ValueError(f"Missing/invalid chance for blueprint tier {tier} in {context}: {chance}")


def validate_config(weapon_config: dict, trader_config: dict) -> None:
    traders = trader_config.get("traders")
    stage_rules = trader_config.get("stage_rules")
    defaults = trader_config.get("defaults", {})
    if not isinstance(traders, dict) or not traders:
        raise ValueError("'traders' must contain at least one trader.")
    if not isinstance(stage_rules, dict):
        raise ValueError("Missing or invalid 'stage_rules'.")

    default_tier_chances = defaults.get("tier_chance_by_tier", {})
    validate_tier_chances(default_tier_chances, "defaults.tier_chance_by_tier")

    stock_counts = defaults.get("stock_count_by_player_rank", {})
    for vanilla_rank in VANILLA_RANKS:
        stock = stock_counts.get(vanilla_rank)
        if not isinstance(stock, dict):
            raise ValueError(f"Missing stock count for player rank '{vanilla_rank}'.")
        minimum = stock.get("min")
        maximum = stock.get("max")
        if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum < 1 or maximum < minimum:
            raise ValueError(f"Invalid stock count for player rank '{vanilla_rank}': {stock}")

    for stage, rule in stage_rules.items():
        if stage.startswith("_"):
            continue
        ranks = rule.get("weapon_ranks")
        if not isinstance(ranks, list) or not ranks:
            raise ValueError(f"Stage {stage} must define non-empty 'weapon_ranks'.")
        invalid = [rank for rank in ranks if rank not in RANK_ORDER]
        if invalid:
            raise ValueError(f"Stage {stage} has invalid weapon ranks: {', '.join(invalid)}")

        stage_tier_chances = rule.get("blueprint_tier_chance_by_tier", default_tier_chances)
        if not isinstance(stage_tier_chances, dict):
            raise ValueError(f"Stage {stage} has invalid blueprint tier chances.")
        validate_tier_chances(stage_tier_chances, f"stage {stage}")
        if not any(stage_tier_chances[str(tier)] > 0 for tier in (1, 2, 3)):
            raise ValueError(f"Stage {stage} disables every blueprint tier.")

    known_families = set(get_weapon_families(weapon_config))
    focus_groups = trader_config.get("focus_groups", {})
    for focus_name, families in focus_groups.items():
        if focus_name.startswith("_"):
            continue
        unknown = sorted(set(families) - known_families)
        if unknown:
            raise ValueError(f"Focus group '{focus_name}' contains unknown families: {', '.join(unknown)}")

    seen_generators: set[str] = set()
    for trader_name, trader in traders.items():
        generator = trader.get("generator")
        if not generator:
            raise ValueError(f"Trader '{trader_name}' is missing 'generator'.")
        if generator in seen_generators:
            raise ValueError(f"Generator '{generator}' is assigned more than once.")
        seen_generators.add(generator)

        stage = str(trader.get("progression_stage", ""))
        if stage not in stage_rules:
            raise ValueError(f"Trader '{trader_name}' references unknown stage '{stage}'.")

        focus = trader.get("focus")
        if focus is not None and focus not in focus_groups:
            raise ValueError(f"Trader '{trader_name}' references unknown focus '{focus}'.")

        sid_fragment(trader_name)


def build_trader_families(weapon_config: dict, trader_config: dict, trader: dict) -> list[str]:
    stage_rule = trader_config["stage_rules"][str(trader["progression_stage"])]
    families = [
        family
        for rank in stage_rule["weapon_ranks"]
        for family in weapon_config["weapon_progression"][rank]
    ]

    focus = trader.get("focus")
    if focus:
        allowed = set(trader_config["focus_groups"][focus])
        families = [family for family in families if family in allowed]

    return families


def build_pool_blueprints(
    weapon_config: dict,
    families: list[str],
    tier_chances: dict[str, int | float],
) -> list[tuple[str, int | float]]:
    return [
        (tier_blueprint_sid(weapon_config, family, tier), tier_chances[str(tier)])
        for family in families
        for tier in (1, 2, 3)
        if tier_chances[str(tier)] > 0
    ]


def render_pool_template() -> str:
    return "\n".join([
        "BPR_TraderPool_Template : struct.begin {refurl=@BaseGame/ItemGeneratorPrototypes.cfg;refkey=[0]}",
        "    SID = BPR_TraderPool_Template",
        "    SpecificRewardSound = EUISound::SystemNotificationNews",
        "    ItemGenerator : struct.begin",
        "        [0] : struct.begin",
        "            Category = EItemGenerationCategory::Junk",
        "            PossibleItems : struct.begin",
        "                [0] : struct.begin",
        "                    ItemPrototypeSID = Bread",
        "                    Chance = 0",
        "                    MinCount = 0",
        "                    MaxCount = 0",
        "                struct.end",
        "            struct.end",
        "        struct.end",
        "    struct.end",
        "struct.end",
    ])


def render_pool(
    pool_group: str,
    blueprints: list[tuple[str, int | float]],
    defaults: dict,
) -> str:
    sid = f"BPR_TraderPool_{pool_group}"
    category = defaults.get("pool_category", "EItemGenerationCategory::Attach")
    allow_same = bool(defaults.get("allow_same_category_generation", True))

    lines = [
        f"// {pool_group}",
        f"{sid} : struct.begin {{refkey=BPR_TraderPool_Template}}",
        f"    SID = {sid}",
        "    ItemGenerator : struct.begin",
        "        [*] : struct.begin",
        f"            Category = {category}",
        f"            bAllowSameCategoryGeneration = {'true' if allow_same else 'false'}",
        "            PossibleItems : struct.begin",
    ]

    for blueprint_sid, chance in blueprints:
        lines.extend([
            "                [*] : struct.begin",
            f"                    ItemPrototypeSID = {blueprint_sid}",
            f"                    Chance = {fmt_number(chance)}",
            "                    MinCount = 1",
            "                    MaxCount = 1",
            "                struct.end",
        ])

    lines.extend([
        "            struct.end",
        "        struct.end",
        "    struct.end",
        "struct.end",
    ])
    return "\n".join(lines)


def render_trader_patch(
    trader_name: str,
    trader: dict,
    defaults: dict,
) -> str:
    trader_sid = trader["generator"]
    start_index = int(trader.get("start_index", defaults.get("start_index", 86)))
    category = defaults.get("trader_category", "EItemGenerationCategory::SubItemGenerator")
    allow_same = bool(defaults.get("allow_same_category_generation", True))
    chance = defaults.get("subgenerator_chance", 1)
    stock_counts = defaults["stock_count_by_player_rank"]
    sid = pool_sid(trader)

    lines = [
        f"// {trader_name}",
        f"{trader_sid} : struct.begin {{bpatch}}",
        f"    SID = {trader_sid}",
        "    ItemGenerator : struct.begin {bpatch}",
    ]

    for offset, vanilla_rank in enumerate(VANILLA_RANKS):
        stock = stock_counts[vanilla_rank]
        lines.extend([
            f"        [{start_index + offset}] : struct.begin",
            f"            Category = {category}",
            f"            PlayerRank = ERank::{vanilla_rank}",
            f"            bAllowSameCategoryGeneration = {'true' if allow_same else 'false'}",
            "            PossibleItems : struct.begin",
            "                [0] : struct.begin",
            f"                    ItemGeneratorPrototypeSID = {sid}",
            f"                    Chance = {fmt_number(chance)}",
            f"                    MinCount = {stock['min']}",
            f"                    MaxCount = {stock['max']}",
            "                struct.end",
            "            struct.end",
            "        struct.end",
        ])

    lines.extend([
        "    struct.end",
        "struct.end",
    ])
    return "\n".join(lines)


def header(kind: str) -> str:
    return "\n".join([
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        "// Sources:",
        "//   Python/Config/weapon_progression.json",
        "//   Python/CFGGenerators/Distribution/blueprint_traders.json",
        "// Generated by: generate_trader_blueprints.py",
        f"// Output: {kind}",
        "// -----------------------------------------------------------------------------",
        "",
    ])


def main() -> None:
    weapon_config = load_weapon_progression()
    trader_config = load_json(TRADER_CONFIG_PATH)
    validate_config(weapon_config, trader_config)

    defaults = trader_config["defaults"]
    default_tier_chances = defaults["tier_chance_by_tier"]
    pool_blocks = [render_pool_template()]
    patch_blocks: list[str] = []
    pool_count = 0
    blueprint_entries = 0
    generated_groups: set[str] = set()

    for trader_name, trader in trader_config["traders"].items():
        families = build_trader_families(weapon_config, trader_config, trader)
        if not families:
            raise ValueError(f"Trader '{trader_name}' has an empty family pool.")

        group = pool_group_key(trader)
        if group not in generated_groups:
            stage_rule = trader_config["stage_rules"][str(trader["progression_stage"])]
            tier_chances = stage_rule.get("blueprint_tier_chance_by_tier", default_tier_chances)
            blueprints = build_pool_blueprints(
                weapon_config,
                families,
                tier_chances,
            )
            pool_blocks.append(render_pool(group, blueprints, defaults))
            pool_count += 1
            blueprint_entries += len(blueprints)
            generated_groups.add(group)

        patch_blocks.append(render_trader_patch(trader_name, trader, defaults))

    POOL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PATCH_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    POOL_OUTPUT_PATH.write_text(header("BPR trader stock pools") + "\n\n".join(pool_blocks) + "\n", encoding="utf-8")
    PATCH_OUTPUT_PATH.write_text(header("vanilla trader references to BPR pools") + "\n\n".join(patch_blocks) + "\n", encoding="utf-8")

    print("Blueprint Trader Pool Generator")
    print("------------------------------")
    print(f"Configured traders: {len(trader_config['traders'])}")
    print(f"Generated pools:    {pool_count}")
    print(f"Blueprint entries:  {blueprint_entries}")
    print(f"Pool output:\n{POOL_OUTPUT_PATH}")
    print(f"Patch output:\n{PATCH_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
