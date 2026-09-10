#!/usr/bin/env python3
"""
Generate BlueprintPrototypes_patch_BPR.cfg from blueprint_prototypes.json.

Expected project layout:

Content/
├─ GameLite/
│  └─ GameData/
│     └─ ItemPrototypes/
│        └─ BlueprintPrototypes/
│           └─ BlueprintPrototypes_patch_BPR.cfg
│
└─ Python/
   └─ CFGGenerators/
      └─ BlueprintPrototypes/
         ├─ blueprint_prototypes.json
         └─ generate_blueprint_prototypes.py
"""

from __future__ import annotations

import json
from pathlib import Path


# =============================================================================
# Paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# Content/Python/CFGGenerators/BlueprintPrototypes -> Content
CONTENT_DIR = SCRIPT_DIR.parents[2]

CONFIG_PATH = SCRIPT_DIR / "blueprint_prototypes.json"

OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemPrototypes"
    / "BlueprintPrototypes"
    / "BlueprintPrototypes_patch_BPR.cfg"
)


# =============================================================================
# Helpers
# =============================================================================

def bool_cfg(value: bool) -> str:
    return "true" if value else "false"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict) -> None:
    templates = config.get("templates")
    blueprints = config.get("blueprints")
    costs = config.get("costs")
    icon_base_path = config.get("icon_base_path")
    debug_icon_name = config.get("debug_icon_name")
    icon_names = config.get("icon_names")

    if not isinstance(costs, dict):
        raise ValueError("Missing or invalid 'costs' object.")

    for weapon_tier in ("1", "2", "3", "4"):
        if weapon_tier not in costs or not isinstance(costs[weapon_tier], dict):
            raise ValueError(f"Missing cost table for weapon tier {weapon_tier}.")
        for blueprint_tier in ("1", "2", "3"):
            value = costs[weapon_tier].get(blueprint_tier)
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"Invalid cost for weapon tier {weapon_tier}, "
                    f"blueprint tier {blueprint_tier}: {value}"
                )

    if not isinstance(icon_base_path, str) or not icon_base_path:
        raise ValueError("Missing or invalid 'icon_base_path'.")

    if not isinstance(debug_icon_name, str) or not debug_icon_name:
        raise ValueError("Missing or invalid 'debug_icon_name'.")

    if not isinstance(icon_names, dict) or not icon_names:
        raise ValueError("Missing or invalid 'icon_names' object.")

    if not isinstance(templates, dict):
        raise ValueError("Missing or invalid 'templates' object.")

    for tier in ("1", "2", "3"):
        if tier not in templates:
            raise ValueError(f"Missing template for tier {tier}.")

        template = templates[tier]

        for required in (
            "sid",
            "parent_refurl",
            "parent_refkey",
            "icon",
            "item_grid_width",
            "item_grid_height",
            "invisible_in_player_inventory",
        ):
            if required not in template:
                raise ValueError(
                    f"Template tier {tier} is missing '{required}'."
                )

    if not isinstance(blueprints, list):
        raise ValueError("Missing or invalid 'blueprints' list.")

    seen_sids: set[str] = set()

    template_sids = {
        template["sid"]
        for template in templates.values()
    }

    for blueprint in blueprints:
        sid = blueprint.get("sid")
        tier = blueprint.get("tier")
        fitting = blueprint.get("fitting_weapons")
        weapon_tier = blueprint.get("weapon_tier")

        if weapon_tier not in (1, 2, 3, 4):
            raise ValueError(
                f"Blueprint '{sid}' has invalid/missing weapon_tier: {weapon_tier}"
            )

        if not sid:
            raise ValueError("Blueprint without SID found.")

        if sid in seen_sids:
            raise ValueError(f"Duplicate blueprint SID: {sid}")

        if sid in template_sids:
            raise ValueError(
                f"Blueprint SID collides with template SID: {sid}"
            )

        if tier not in (1, 2, 3):
            raise ValueError(
                f"Blueprint '{sid}' has invalid tier: {tier}"
            )

        if not isinstance(fitting, list) or not fitting:
            raise ValueError(
                f"Blueprint '{sid}' has no fitting_weapons."
            )

        if len(fitting) != len(set(fitting)):
            raise ValueError(
                f"Blueprint '{sid}' contains duplicate fitting weapons."
            )

        family = sid.split("_Upgrades_Tier_")[0]
        if family not in icon_names:
            raise ValueError(
                f"No icon mapping found for blueprint family '{family}'."
            )

        seen_sids.add(sid)

    for debug in config.get("debug_items", []):
        sid = debug.get("sid")

        if not sid:
            raise ValueError("Debug item without SID found.")

        if sid in seen_sids or sid in template_sids:
            raise ValueError(f"Duplicate/colliding SID: {sid}")

        if debug.get("tier") not in (1, 2, 3):
            raise ValueError(
                f"Debug item '{sid}' has invalid tier."
            )

        seen_sids.add(sid)


# =============================================================================
# Rendering
# =============================================================================

def render_fitting_weapons(weapons: list[str]) -> list[str]:
    lines = ["   FittingWeaponsSIDs : struct.begin"]

    for index, weapon_sid in enumerate(weapons):
        lines.append(f"      [{index}] = {weapon_sid}")

    lines.append("   struct.end")
    return lines


def render_template(tier: int, template: dict) -> str:
    sid = template["sid"]

    lines = [
        f"{sid} : struct.begin "
        f"{{refurl={template['parent_refurl']};"
        f"refkey={template['parent_refkey']}}}",
        f"   SID = {sid}",
        f"   Icon = {template['icon']}",
        f"   ItemGridWidth = {template['item_grid_width']}",
        f"   ItemGridHeight = {template['item_grid_height']}",
        "   InvisibleInPlayerInventory = "
        f"{bool_cfg(template['invisible_in_player_inventory'])}",
        "struct.end",
    ]

    return "\n".join(lines)


def render_item(
    item: dict,
    templates: dict,
    costs: dict,
    icon_base_path: str,
    icon_names: dict[str, str],
    debug_icon_name: str,
    *,
    debug: bool = False,
) -> str:
    tier = item["tier"]
    sid = item["sid"]
    template_sid = templates[str(tier)]["sid"]
    weapon_tier = item.get("weapon_tier", 1)
    cost = costs[str(weapon_tier)][str(tier)]

    if debug:
        icon_name = debug_icon_name
    else:
        family = sid.split("_Upgrades_Tier_")[0]
        icon_name = icon_names[family]

    icon_asset = f"T_{icon_name}_Tier{tier}"
    icon = f"Texture2D'{icon_base_path}/{icon_asset}.{icon_asset}'"

    # Same-file inheritance: refkey alone is valid and is widely used
    # by vanilla STALKER 2 configs.
    lines = [
        f"{sid} : struct.begin {{refkey={template_sid}}}",
        f"   SID = {sid}",
        f"   LocalizationSID = {item.get('localization_sid', sid)}",
        f"   Cost = {cost}",
        f"   Icon = {icon}",
    ]

    lines.extend(
        render_fitting_weapons(item["fitting_weapons"])
    )

    # Real items inherit InvisibleInPlayerInventory=true from the
    # tier template. Debug items explicitly override it to false.
    if "invisible_in_player_inventory" in item:
        lines.append(
            "   InvisibleInPlayerInventory = "
            f"{bool_cfg(item['invisible_in_player_inventory'])}"
        )

    lines.append("struct.end")
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print("Blueprint Prototype CFG Generator")
    print("---------------------------------")
    print(f"Config: {CONFIG_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file not found:\n{CONFIG_PATH}"
        )

    config = load_config(CONFIG_PATH)
    validate_config(config)

    templates = config["templates"]
    blueprints = config["blueprints"]
    debug_items = config.get("debug_items", [])
    costs = config["costs"]
    icon_base_path = config["icon_base_path"]
    debug_icon_name = config["debug_icon_name"]
    icon_names = config["icon_names"]

    lines = [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        "// Source: Python/CFGGenerators/BlueprintPrototypes/blueprint_prototypes.json",
        "// Generated by: generate_blueprint_prototypes.py",
        "// -----------------------------------------------------------------------------",
        "",
        "// ------------------------------------------------------------",
        "// BPR Tier Templates",
        "// ------------------------------------------------------------",
    ]

    for tier in (1, 2, 3):
        if tier > 1:
            lines.append("")
        lines.append(
            render_template(
                tier,
                templates[str(tier)]
            )
        )

    if debug_items:
        lines.extend([
            "",
            "",
            "// ------------------------------------------------------------",
            "// Debug Items - visible in inventory",
            "// ------------------------------------------------------------",
        ])

        for index, item in enumerate(debug_items):
            if index > 0:
                lines.append("")
            lines.append(
                render_item(
                    item,
                    templates,
                    costs,
                    icon_base_path,
                    icon_names,
                    debug_icon_name,
                    debug=True
                )
            )

    # Group by weapon family for readability.
    current_family = None

    for item in blueprints:
        family = item["sid"].split("_Upgrades_Tier_")[0]

        if family != current_family:
            lines.extend([
                "",
                "",
                "// ------------------------------------------------------------",
                f"// {family}",
                "// ------------------------------------------------------------",
            ])
            current_family = family
        else:
            lines.append("")

        lines.append(
            render_item(
                item,
                templates,
                costs,
                icon_base_path,
                icon_names,
                debug_icon_name
            )
        )

    output = "\n".join(lines) + "\n"

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_PATH.write_text(
        output,
        encoding="utf-8"
    )

    all_sids = {
        item["sid"]
        for item in blueprints
    }

    print("Generation successful.")
    print()
    print(f"Templates:       {len(templates)}")
    print(f"Debug items:     {len(debug_items)}")
    print(f"Blueprint items: {len(blueprints)}")
    print(f"Icon mappings:   {len(icon_names)}")
    print(f"Unique BPs:      {len(all_sids)}")
    print()
    print(f"Written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
