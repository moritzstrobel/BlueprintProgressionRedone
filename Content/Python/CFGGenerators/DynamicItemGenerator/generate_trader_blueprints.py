#!/usr/bin/env python3
"""
Generate STALKER 2 trader blueprint bpatch config from blueprint_traders.json.

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
         ├─ blueprint_traders.json
         └─ generate_trader_blueprints.py

The JSON is trader-centric:
{
  "traders": {
    "Zalissya": {
      "generator": "TraderZalesie_TradeItemGenerator",
      "blueprints": [
        "PM_Upgrades_Tier_1"
      ]
    }
  }
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# =============================================================================
# Paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# Content/Python/CFGGenerators/DynamicItemGenerator -> Content
CONTENT_DIR = SCRIPT_DIR.parents[2]

CONFIG_PATH = SCRIPT_DIR / "blueprint_traders.json"

OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemGeneratorPrototypes"
    / "DynamicItemGenerator"
    / "DynamicItemGenerator_patch_BPR.cfg"
)


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


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict) -> None:
    if "traders" not in config:
        raise ValueError("Missing required top-level key: 'traders'")

    traders = config["traders"]

    if not isinstance(traders, dict) or not traders:
        raise ValueError("'traders' must contain at least one trader.")

    seen_generators: set[str] = set()

    for trader_name, trader in traders.items():
        if not isinstance(trader, dict):
            raise ValueError(
                f"Trader '{trader_name}' must be an object."
            )

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

        blueprints = trader.get("blueprints", [])

        if not isinstance(blueprints, list):
            raise ValueError(
                f"'blueprints' for trader '{trader_name}' must be a list."
            )

        duplicates = {
            sid
            for sid in blueprints
            if blueprints.count(sid) > 1
        }

        if duplicates:
            raise ValueError(
                f"Duplicate blueprint(s) for trader '{trader_name}': "
                + ", ".join(sorted(duplicates))
            )


# =============================================================================
# CFG generation
# =============================================================================

def render_item(
    index: int,
    blueprint_sid: str,
    defaults: dict
) -> list[str]:

    chance = defaults.get("chance", 1)
    min_count = defaults.get("min_count", 1)
    max_count = defaults.get("max_count", 1)
    min_durability = defaults.get("min_durability", 1)
    max_durability = defaults.get("max_durability", 1)

    return [
        f"                [{index}] : struct.begin",
        f"                    ItemPrototypeSID = {blueprint_sid}",
        f"                    Chance = {fmt_number(chance)}",
        f"                    MinCount = {fmt_number(min_count)}",
        f"                    MaxCount = {fmt_number(max_count)}",
        f"                    MinDurability = {fmt_number(min_durability)}",
        f"                    MaxDurability = {fmt_number(max_durability)}",
        f"                struct.end",
    ]


def render_trader(
    trader_name: str,
    trader: dict,
    defaults: dict
) -> str:

    trader_sid = trader["generator"]
    blueprints = trader.get("blueprints", [])

    category = trader.get(
        "category",
        defaults.get(
            "category",
            "EItemGenerationCategory::Attach"
        )
    )

    ranks = trader.get(
        "player_ranks",
        defaults.get(
            "player_ranks",
            [
                "ERank::Newbie",
                "ERank::Experienced",
                "ERank::Veteran",
                "ERank::Master"
            ]
        )
    )

    ranks_text = ", ".join(ranks)

    allow_same = trader.get(
        "allow_same_category_generation",
        defaults.get(
            "allow_same_category_generation",
            True
        )
    )

    allow_same_text = "true" if allow_same else "false"

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

    for index, blueprint_sid in enumerate(blueprints):
        if index > 0:
            lines.append("")

        lines.extend(
            render_item(
                index,
                blueprint_sid,
                defaults
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
    print(f"Config: {CONFIG_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file not found:\n{CONFIG_PATH}"
        )

    config = load_config(CONFIG_PATH)
    validate_config(config)

    defaults = config.get("defaults", {})
    traders = config["traders"]

    header = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        f"// Source: Python/CFGGenerators/DynamicItemGenerator/{CONFIG_PATH.name}",
        "// Generated by: generate_trader_blueprints.py",
        "// -----------------------------------------------------------------------------",
        "",
    ]

    blocks = []
    total_blueprints = 0
    active_traders = 0

    for trader_name, trader in traders.items():
        blueprints = trader.get("blueprints", [])

        # Empty trader entries are allowed in JSON,
        # but do not generate useless CFG blocks.
        if not blueprints:
            continue

        active_traders += 1
        total_blueprints += len(blueprints)

        blocks.append(
            render_trader(
                trader_name,
                trader,
                defaults
            )
        )

    if not blocks:
        raise ValueError(
            "No blueprint assignments found. "
            "All configured traders have empty blueprint lists."
        )

    output = (
        "\n".join(header)
        + "\n".join(blocks if len(blocks) == 1 else ["\n\n".join(blocks)])
        + "\n"
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_PATH.write_text(
        output,
        encoding="utf-8"
    )

    print("Generation successful.")
    print()
    print(f"Configured traders: {len(traders)}")
    print(f"Active traders:     {active_traders}")
    print(f"Blueprint entries:  {total_blueprints}")
    print()

    for trader_name, trader in traders.items():
        blueprints = trader.get("blueprints", [])

        if not blueprints:
            continue

        print(
            f"  {trader_name} "
            f"({trader['generator']}): "
            f"{len(blueprints)} blueprint(s)"
        )

    print()
    print(f"Written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
