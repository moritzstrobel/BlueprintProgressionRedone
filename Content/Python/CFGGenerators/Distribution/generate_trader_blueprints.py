#!/usr/bin/env python3
"""Generate vanilla trader patches for BPR blueprint distribution."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = SCRIPT_DIR.parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Common.bpr_common import RANK_ORDER, cumulative_families, get_weapon_families, load_json, load_weapon_progression, tier_blueprint_sid

CONTENT_DIR = PYTHON_ROOT.parent
TRADER_CONFIG_PATH = SCRIPT_DIR / "blueprint_traders.json"
OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemGeneratorPrototypes"
    / "DynamicItemGenerator"
    / "DynamicItemGenerator_patch_BPR.cfg"
)


def fmt_number(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def validate_config(weapon_config: dict, trader_config: dict) -> None:
    traders = trader_config.get("traders")
    stage_rules = trader_config.get("stage_rules")
    if not isinstance(traders, dict) or not traders:
        raise ValueError("'traders' must contain at least one trader.")
    if not isinstance(stage_rules, dict):
        raise ValueError("Missing or invalid 'stage_rules'.")

    known_families = set(get_weapon_families(weapon_config))
    focus_groups = trader_config.get("focus_groups", {})
    for focus_name, families in focus_groups.items():
        if focus_name.startswith("_"):
            continue
        unknown = sorted(set(families) - known_families)
        if unknown:
            raise ValueError(f"Focus group '{focus_name}' contains unknown families: {', '.join(unknown)}")

    for stage, rule in stage_rules.items():
        if stage.startswith("_"):
            continue
        if rule.get("max_weapon_rank") not in RANK_ORDER:
            raise ValueError(f"Stage {stage} has invalid max_weapon_rank: {rule.get('max_weapon_rank')}")
        max_tier = rule.get("max_blueprint_tier")
        if max_tier not in (1, 2, 3):
            raise ValueError(f"Stage {stage} has invalid max_blueprint_tier: {max_tier}")

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


def build_trader_blueprints(weapon_config: dict, trader_config: dict, trader: dict) -> list[str]:
    stage_rule = trader_config["stage_rules"][str(trader["progression_stage"])]
    families = cumulative_families(weapon_config, stage_rule["max_weapon_rank"])
    focus = trader.get("focus")
    if focus:
        allowed = set(trader_config["focus_groups"][focus])
        families = [family for family in families if family in allowed]

    max_tier = int(stage_rule["max_blueprint_tier"])
    return [
        tier_blueprint_sid(weapon_config, family, tier)
        for family in families
        for tier in range(1, max_tier + 1)
    ]


def render_item(blueprint_sid: str, defaults: dict) -> list[str]:
    return [
        "                [*] : struct.begin",
        f"                    ItemPrototypeSID = {blueprint_sid}",
        f"                    Chance = {fmt_number(defaults.get('chance', 1))}",
        f"                    MinCount = {fmt_number(defaults.get('min_count', 1))}",
        f"                    MaxCount = {fmt_number(defaults.get('max_count', 1))}",
        f"                    MinDurability = {fmt_number(defaults.get('min_durability', 1))}",
        f"                    MaxDurability = {fmt_number(defaults.get('max_durability', 1))}",
        "                struct.end",
    ]


def render_trader(trader_name: str, trader: dict, blueprints: list[str], defaults: dict) -> str:
    trader_sid = trader["generator"]
    category = trader.get("category", defaults.get("category", "EItemGenerationCategory::Attach"))
    ranks = trader.get("player_ranks", defaults.get("player_ranks", [
        "ERank::Newbie", "ERank::Experienced", "ERank::Veteran", "ERank::Master"
    ]))
    allow_same = trader.get("allow_same_category_generation", defaults.get("allow_same_category_generation", True))

    lines = [
        f"// {trader_name}",
        f"{trader_sid} : struct.begin {{bpatch}}",
        f"    SID = {trader_sid}",
        "",
        "    ItemGenerator : struct.begin {bpatch}",
        "",
        "        [*] : struct.begin",
        f"            Category = {category}",
        f"            PlayerRank = {', '.join(ranks)}",
        f"            bAllowSameCategoryGeneration = {'true' if allow_same else 'false'}",
        "",
        "            PossibleItems : struct.begin",
    ]
    for blueprint in blueprints:
        lines.extend(render_item(blueprint, defaults))
    lines.extend([
        "            struct.end", "", "        struct.end", "", "    struct.end", "struct.end",
    ])
    return "\n".join(lines)


def main() -> None:
    weapon_config = load_weapon_progression()
    trader_config = load_json(TRADER_CONFIG_PATH)
    validate_config(weapon_config, trader_config)

    defaults = trader_config.get("defaults", {})
    blocks: list[str] = []
    total_blueprints = 0
    for trader_name, trader in trader_config["traders"].items():
        blueprints = build_trader_blueprints(weapon_config, trader_config, trader)
        if not blueprints:
            continue
        total_blueprints += len(blueprints)
        blocks.append(render_trader(trader_name, trader, blueprints, defaults))

    if not blocks:
        raise ValueError("No trader blueprint assignments generated.")

    header = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        "// Sources:",
        "//   Python/Config/weapon_progression.json",
        "//   Python/CFGGenerators/Distribution/blueprint_traders.json",
        "// Generated by: generate_trader_blueprints.py",
        "// -----------------------------------------------------------------------------",
        "",
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(header) + "\n\n".join(blocks) + "\n", encoding="utf-8")

    print("Blueprint Trader CFG Generator")
    print("------------------------------")
    print(f"Configured traders: {len(trader_config['traders'])}")
    print(f"Blueprint entries:  {total_blueprints}")
    print(f"Written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
