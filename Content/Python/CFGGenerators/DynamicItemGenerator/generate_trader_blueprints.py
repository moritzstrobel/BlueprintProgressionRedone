#!/usr/bin/env python3
"""
Generate STALKER 2 trader blueprint bpatch config.

Expected project layout:

Content/
├─ GameLite/
│  └─ GameData/
│     └─ ItemGeneratorPrototypes/
│        └─ DynamicItemGenerator/
│           └─ DynamicItemGenerator_patch_BPR.cfg
│
└─ Python/
   └─ CFGGenerators/
      └─ DynamicItemGenerator/
         ├─ weapon_progression.json
         ├─ blueprint_traders.json
         └─ generate_trader_blueprints.py

The trader JSON no longer stores large explicit blueprint lists.
Blueprint availability is derived from weapon_progression.json plus trader stage/focus.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# =============================================================================
# Paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CONTENT_DIR = SCRIPT_DIR.parents[2]

WEAPON_CONFIG_PATH = SCRIPT_DIR / "weapon_progression.json"
TRADER_CONFIG_PATH = SCRIPT_DIR / "blueprint_traders.json"

OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemGeneratorPrototypes"
    / "DynamicItemGenerator"
    / "DynamicItemGenerator_patch_BPR.cfg"
)


# =============================================================================
# Constants
# =============================================================================

RANK_ORDER = ("Newbie", "Experienced", "Veteran")


# =============================================================================
# Helpers
# =============================================================================

def fmt_number(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found:\n{path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def cumulative_families(weapon_config: dict, rank: str) -> list[str]:
    families: list[str] = []

    for current_rank in RANK_ORDER:
        families.extend(
            weapon_config["weapon_progression"][current_rank]
        )

        if current_rank == rank:
            break

    return list(dict.fromkeys(families))


def validate_config(
    weapon_config: dict,
    trader_config: dict,
) -> None:
    if "weapon_progression" not in weapon_config:
        raise ValueError(
            "weapon_progression.json is missing 'weapon_progression'."
        )

    for rank in RANK_ORDER:
        if rank not in weapon_config["weapon_progression"]:
            raise ValueError(
                f"weapon_progression.json is missing rank '{rank}'."
            )

    if "item_sid_patterns" not in weapon_config:
        raise ValueError(
            "weapon_progression.json is missing 'item_sid_patterns'."
        )

    if "traders" not in trader_config:
        raise ValueError(
            "blueprint_traders.json is missing 'traders'."
        )

    if "stage_rules" not in trader_config:
        raise ValueError(
            "blueprint_traders.json is missing 'stage_rules'."
        )

    traders = trader_config["traders"]

    if not isinstance(traders, dict) or not traders:
        raise ValueError(
            "'traders' must contain at least one trader."
        )

    seen_generators: set[str] = set()

    for trader_name, trader in traders.items():
        generator = trader.get("generator")

        if not generator:
            raise ValueError(
                f"Trader '{trader_name}' is missing 'generator'."
            )

        if generator in seen_generators:
            raise ValueError(
                f"Generator '{generator}' is assigned more than once."
            )

        seen_generators.add(generator)

        stage = str(trader.get("progression_stage", ""))

        if stage not in trader_config["stage_rules"]:
            raise ValueError(
                f"Trader '{trader_name}' references unknown "
                f"progression_stage '{stage}'."
            )

        focus = trader.get("focus")

        if focus is not None:
            focus_groups = trader_config.get("focus_groups", {})

            if focus not in focus_groups:
                raise ValueError(
                    f"Trader '{trader_name}' references unknown "
                    f"focus group '{focus}'."
                )


def blueprint_sid(
    weapon_config: dict,
    family: str,
    tier: int,
) -> str:
    pattern = weapon_config[
        "item_sid_patterns"
    ]["tier_blueprint"]

    return pattern.format(
        family=family,
        tier=tier,
    )


def build_trader_blueprints(
    weapon_config: dict,
    trader_config: dict,
    trader: dict,
) -> list[str]:
    stage_id = str(trader["progression_stage"])
    stage_rule = trader_config["stage_rules"][stage_id]

    max_weapon_rank = stage_rule["max_weapon_rank"]
    max_blueprint_tier = int(
        stage_rule["max_blueprint_tier"]
    )

    families = cumulative_families(
        weapon_config,
        max_weapon_rank,
    )

    focus = trader.get("focus")

    if focus:
        allowed = set(
            trader_config["focus_groups"][focus]
        )
        families = [
            family
            for family in families
            if family in allowed
        ]

    blueprints: list[str] = []

    for family in families:
        for tier in range(1, max_blueprint_tier + 1):
            blueprints.append(
                blueprint_sid(
                    weapon_config,
                    family,
                    tier,
                )
            )

    return blueprints


# =============================================================================
# CFG generation
# =============================================================================

def render_item(
    blueprint_sid_value: str,
    defaults: dict,
) -> list[str]:

    chance = defaults.get("chance", 1)
    min_count = defaults.get("min_count", 1)
    max_count = defaults.get("max_count", 1)
    min_durability = defaults.get("min_durability", 1)
    max_durability = defaults.get("max_durability", 1)

    return [
        "                [*] : struct.begin",
        f"                    ItemPrototypeSID = {blueprint_sid_value}",
        f"                    Chance = {fmt_number(chance)}",
        f"                    MinCount = {fmt_number(min_count)}",
        f"                    MaxCount = {fmt_number(max_count)}",
        f"                    MinDurability = {fmt_number(min_durability)}",
        f"                    MaxDurability = {fmt_number(max_durability)}",
        "                struct.end",
    ]


def render_trader(
    trader_name: str,
    trader: dict,
    blueprints: list[str],
    defaults: dict,
) -> str:

    trader_sid = trader["generator"]

    category = trader.get(
        "category",
        defaults.get(
            "category",
            "EItemGenerationCategory::Attach",
        ),
    )

    ranks = trader.get(
        "player_ranks",
        defaults.get(
            "player_ranks",
            [
                "ERank::Newbie",
                "ERank::Experienced",
                "ERank::Veteran",
                "ERank::Master",
            ],
        ),
    )

    ranks_text = ", ".join(ranks)

    allow_same = trader.get(
        "allow_same_category_generation",
        defaults.get(
            "allow_same_category_generation",
            True,
        ),
    )

    allow_same_text = (
        "true" if allow_same else "false"
    )

    lines = [
        f"// {trader_name}",
        f"{trader_sid} : struct.begin {{bpatch}}",
        f"    SID = {trader_sid}",
        "",
        "    ItemGenerator : struct.begin {bpatch}",
        "",
        "        [*] : struct.begin {bpatch}",
        f"            Category = {category}",
        f"            PlayerRank = {ranks_text}",
        f"            bAllowSameCategoryGeneration = {allow_same_text}",
        "",
        "            PossibleItems : struct.begin",
    ]

    for blueprint in blueprints:
        lines.extend(
            render_item(
                blueprint,
                defaults,
            )
        )

    lines += [
        "            struct.end",
        "",
        "        struct.end",
        "",
        "    struct.end",
        "struct.end",
    ]

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print("Blueprint Trader CFG Generator")
    print("------------------------------")
    print(f"Weapon config: {WEAPON_CONFIG_PATH}")
    print(f"Trader config: {TRADER_CONFIG_PATH}")
    print(f"Output:        {OUTPUT_PATH}")
    print()

    weapon_config = load_json(
        WEAPON_CONFIG_PATH
    )

    trader_config = load_json(
        TRADER_CONFIG_PATH
    )

    validate_config(
        weapon_config,
        trader_config,
    )

    defaults = trader_config.get(
        "defaults",
        {},
    )

    traders = trader_config["traders"]

    header = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        "// Sources:",
        "//   Python/CFGGenerators/DynamicItemGenerator/weapon_progression.json",
        "//   Python/CFGGenerators/DynamicItemGenerator/blueprint_traders.json",
        "// Generated by: generate_trader_blueprints.py",
        "// -----------------------------------------------------------------------------",
        "",
    ]

    blocks: list[str] = []
    total_blueprints = 0

    for trader_name, trader in traders.items():
        blueprints = build_trader_blueprints(
            weapon_config,
            trader_config,
            trader,
        )

        if not blueprints:
            continue

        total_blueprints += len(blueprints)

        blocks.append(
            render_trader(
                trader_name,
                trader,
                blueprints,
                defaults,
            )
        )

    if not blocks:
        raise ValueError(
            "No trader blueprint assignments generated."
        )

    output = (
        "\n".join(header)
        + "\n\n".join(blocks)
        + "\n"
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        output,
        encoding="utf-8",
    )

    print("Generation successful.")
    print()
    print(f"Configured traders: {len(traders)}")
    print(f"Blueprint entries:  {total_blueprints}")
    print()

    for trader_name, trader in traders.items():
        blueprints = build_trader_blueprints(
            weapon_config,
            trader_config,
            trader,
        )

        if not blueprints:
            continue

        focus = trader.get("focus")
        focus_text = (
            f", focus={focus}"
            if focus
            else ""
        )

        print(
            f"  {trader_name} "
            f"(stage {trader['progression_stage']}{focus_text}): "
            f"{len(blueprints)} blueprint(s)"
        )

    print()
    print(f"Written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
