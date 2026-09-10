#!/usr/bin/env python3
"""
Generate STALKER 2 Upgrade Kit ItemPrototypes from upgrade_kits.json.

Expected project layout:

Content/
├─ GameLite/
│  └─ GameData/
│     └─ ItemPrototypes/
│        └─ ItemPrototypes_patch_BPR_UpgradeKits.cfg
│
└─ Python/
   └─ CFGGenerators/
      └─ ItemGenerator/
         ├─ upgrade_kits.json
         └─ generate_upgrade_kit_items.py

Expected JSON structure:

{
  "settings": {
    "mod_root": "Testmod",
    "icon_path": "GameLite/FPS_Game/UIRemaster/UITextures/Inventory/Quest",
    "mesh_prototype_sid": "QuestItem_Case_X11",
    "item_grid_width": 2,
    "item_grid_height": 2,
    "cost": 1000,
    "weight": 0.1,
    "sort_group": "ESortGroup::None",
    "consumable_type": "EConsumableType::None",
    "ui_use_sound": "EUISound::WearEquipment"
  },

  "weapon_families": [
    "AK74",
    "AKU",
    "PM"
  ]
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

# Content/Python/CFGGenerators/ItemGenerator -> Content
CONTENT_DIR = SCRIPT_DIR.parents[2]

CONFIG_FILE = SCRIPT_DIR / "upgrade_kits.json"

OUTPUT_FILE = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemPrototypes"
    / "ItemPrototypes_patch_BPR_UpgradeKits.cfg"
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
    if "settings" not in config:
        raise ValueError(
            "Missing required top-level key: 'settings'"
        )

    if "weapon_families" not in config:
        raise ValueError(
            "Missing required top-level key: 'weapon_families'"
        )

    settings = config["settings"]
    families = config["weapon_families"]

    if not isinstance(settings, dict):
        raise ValueError(
            "'settings' must be an object."
        )

    if not isinstance(families, list) or not families:
        raise ValueError(
            "'weapon_families' must contain at least one weapon family."
        )

    required_settings = [
        "mod_root",
        "icon_path",
        "mesh_prototype_sid",
        "item_grid_width",
        "item_grid_height",
        "cost",
        "weight",
        "sort_group",
        "consumable_type",
        "ui_use_sound",
    ]

    for key in required_settings:
        if key not in settings:
            raise ValueError(
                f"Missing required setting: '{key}'"
            )

    duplicates = {
        family
        for family in families
        if families.count(family) > 1
    }

    if duplicates:
        raise ValueError(
            "Duplicate weapon family/families: "
            + ", ".join(sorted(duplicates))
        )


# =============================================================================
# CFG generation
# =============================================================================

def render_upgrade_kit(
    family: str,
    settings: dict
) -> str:

    item_sid = f"BPR_{family}_UpgradeKit"
    effect_sid = f"BPR_{family}_UpgradeKit_ShakeEffect"

    icon_name = f"T_UpgradeKit_{family}"

    mod_root = settings["mod_root"]
    icon_path = settings["icon_path"]

    icon_reference = (
        f"Texture2D'/{mod_root}/{icon_path}/"
        f"{icon_name}.{icon_name}'"
    )

    mesh_prototype_sid = settings["mesh_prototype_sid"]
    item_grid_width = settings["item_grid_width"]
    item_grid_height = settings["item_grid_height"]
    cost = settings["cost"]
    weight = settings["weight"]
    sort_group = settings["sort_group"]
    consumable_type = settings["consumable_type"]
    ui_use_sound = settings["ui_use_sound"]

    lines = [
        f"{item_sid} : struct.begin "
        "{refurl=@BaseGame/ItemPrototypes/ConsumablePrototypes.cfg;refkey=Bread}",

        f"    SID = {item_sid}",
        f"    Icon = {icon_reference}",
        f"    MeshPrototypeSID = {mesh_prototype_sid}",
        f"    ItemGridWidth = {fmt_number(item_grid_width)}",
        f"    ItemGridHeight = {fmt_number(item_grid_height)}",
        f"    Cost = {fmt_number(cost)}",
        f"    Weight = {fmt_number(weight)}",
        f"    SortGroup = {sort_group}",
        f"    ConsumableType = {consumable_type}",
        f"    UIUseSound = {ui_use_sound}",
        "    AnimBlueprint = AnimBlueprint''",
        "",
        "    EffectPrototypeSIDs : struct.begin",
        f"        [0] = {effect_sid}",
        "        [1] = None",
        "        [2] = None",
        "        [3] = None",
        "        [4] = None",
        "    struct.end",
        "",
        "    ShouldShowEffects : struct.begin",
        "        [0] = false",
        "        [1] = false",
        "        [2] = false",
        "        [3] = false",
        "        [4] = false",
        "    struct.end",
        "",
        "    EffectsDisplayTypes : struct.begin",
        "        [0] = EEffectDisplayType::Value",
        "        [1] = EEffectDisplayType::Value",
        "        [2] = EEffectDisplayType::Value",
        "        [3] = EEffectDisplayType::Value",
        "        [4] = EEffectDisplayType::Value",
        "    struct.end",
        "struct.end",
    ]

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print("Upgrade Kit ItemPrototype CFG Generator")
    print("---------------------------------------")
    print(f"Config: {CONFIG_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config file not found:\n{CONFIG_FILE}"
        )

    config = load_config(CONFIG_FILE)
    validate_config(config)

    settings = config["settings"]
    families = config["weapon_families"]

    header = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        f"// Source: Python/CFGGenerators/ItemGenerator/{CONFIG_FILE.name}",
        "// Generated by: generate_upgrade_kit_items.py",
        "// -----------------------------------------------------------------------------",
        "",
    ]

    blocks = []

    for family in families:
        blocks.append(
            render_upgrade_kit(
                family,
                settings
            )
        )

    if not blocks:
        raise ValueError(
            "No Upgrade Kit ItemPrototypes were generated."
        )

    output = (
        "\n".join(header)
        + "\n\n".join(blocks)
        + "\n"
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        output,
        encoding="utf-8"
    )

    print("Generation successful.")
    print()
    print(f"Upgrade kits generated: {len(families)}")
    print()

    for family in families:
        print(
            f"  {family}: "
            f"BPR_{family}_UpgradeKit "
            f"-> BPR_{family}_UpgradeKit_ShakeEffect"
        )

    print()
    print(f"Written to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()