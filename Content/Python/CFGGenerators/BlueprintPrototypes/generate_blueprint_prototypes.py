#!/usr/bin/env python3
"""Generate BPR blueprint ItemPrototypes from blueprint_prototypes.json."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = SCRIPT_DIR.parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Common.bpr_common import get_weapon_families, load_json, load_weapon_progression, tier_blueprint_sid

CONTENT_DIR = PYTHON_ROOT.parent
CONFIG_PATH = SCRIPT_DIR / "blueprint_prototypes.json"
OUTPUT_PATH = (
    CONTENT_DIR
    / "GameLite"
    / "ModGameData"
    / "Testmod"
    / "ItemPrototypes"
    / "BlueprintPrototypes"
    / "BPR_BlueprintPrototypes.cfg"
)


def bool_cfg(value: bool) -> str:
    return "true" if value else "false"


def validate_config(config: dict, weapon_config: dict) -> None:
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
                    f"Invalid cost for weapon tier {weapon_tier}, blueprint tier {blueprint_tier}: {value}"
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
        for required in (
            "sid", "parent_refurl", "parent_refkey", "icon",
            "item_grid_width", "item_grid_height", "invisible_in_player_inventory",
        ):
            if required not in templates[tier]:
                raise ValueError(f"Template tier {tier} is missing '{required}'.")

    if not isinstance(blueprints, list):
        raise ValueError("Missing or invalid 'blueprints' list.")

    expected_families = get_weapon_families(weapon_config)
    expected_family_set = set(expected_families)
    unknown_icons = sorted(set(icon_names) - expected_family_set)
    missing_icons = sorted(expected_family_set - set(icon_names))
    if unknown_icons:
        raise ValueError("Icon mappings contain unknown families: " + ", ".join(unknown_icons))
    if missing_icons:
        raise ValueError("Missing icon mappings for families: " + ", ".join(missing_icons))

    template_sids = {template["sid"] for template in templates.values()}
    seen_sids: set[str] = set()
    tiers_by_family: dict[str, set[int]] = {family: set() for family in expected_families}

    for blueprint in blueprints:
        sid = blueprint.get("sid")
        tier = blueprint.get("tier")
        fitting = blueprint.get("fitting_weapons")
        weapon_tier = blueprint.get("weapon_tier")

        if not sid:
            raise ValueError("Blueprint without SID found.")
        if sid in seen_sids:
            raise ValueError(f"Duplicate blueprint SID: {sid}")
        if sid in template_sids:
            raise ValueError(f"Blueprint SID collides with template SID: {sid}")
        if tier not in (1, 2, 3):
            raise ValueError(f"Blueprint '{sid}' has invalid tier: {tier}")
        if weapon_tier not in (1, 2, 3, 4):
            raise ValueError(f"Blueprint '{sid}' has invalid/missing weapon_tier: {weapon_tier}")
        if not isinstance(fitting, list) or not fitting:
            raise ValueError(f"Blueprint '{sid}' has no fitting_weapons.")
        if len(fitting) != len(set(fitting)):
            raise ValueError(f"Blueprint '{sid}' contains duplicate fitting weapons.")

        marker = "_Upgrades_Tier_"
        if marker not in sid:
            raise ValueError(f"Blueprint SID does not follow the family/tier pattern: {sid}")
        family = sid.split(marker)[0]
        if family not in expected_family_set:
            raise ValueError(f"Blueprint '{sid}' references unknown family '{family}'.")

        expected_sid = tier_blueprint_sid(weapon_config, family, tier)
        if sid != expected_sid:
            raise ValueError(f"Blueprint SID '{sid}' does not match expected SID '{expected_sid}'.")

        tiers_by_family[family].add(tier)
        seen_sids.add(sid)

    incomplete = [
        family for family, tiers in tiers_by_family.items()
        if tiers != {1, 2, 3}
    ]
    if incomplete:
        raise ValueError(
            "Every weapon family must define Tier 1, 2 and 3 blueprints. Incomplete: "
            + ", ".join(incomplete)
        )

    for debug in config.get("debug_items", []):
        sid = debug.get("sid")
        if not sid:
            raise ValueError("Debug item without SID found.")
        if sid in seen_sids or sid in template_sids:
            raise ValueError(f"Duplicate/colliding SID: {sid}")
        if debug.get("tier") not in (1, 2, 3):
            raise ValueError(f"Debug item '{sid}' has invalid tier.")
        seen_sids.add(sid)


def render_fitting_weapons(weapons: list[str]) -> list[str]:
    lines = ["   FittingWeaponsSIDs : struct.begin"]
    for index, weapon_sid in enumerate(weapons):
        lines.append(f"      [{index}] = {weapon_sid}")
    lines.append("   struct.end")
    return lines


def render_template(template: dict) -> str:
    sid = template["sid"]
    return "\n".join([
        f"{sid} : struct.begin {{refurl={template['parent_refurl']};refkey={template['parent_refkey']}}}",
        f"   SID = {sid}",
        f"   Icon = {template['icon']}",
        f"   ItemGridWidth = {template['item_grid_width']}",
        f"   ItemGridHeight = {template['item_grid_height']}",
        f"   InvisibleInPlayerInventory = {bool_cfg(template['invisible_in_player_inventory'])}",
        "struct.end",
    ])


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
    icon_name = debug_icon_name if debug else icon_names[sid.split("_Upgrades_Tier_")[0]]
    icon_asset = f"T_{icon_name}_Tier{tier}"
    icon = f"Texture2D'{icon_base_path}/{icon_asset}.{icon_asset}'"

    lines = [
        f"{sid} : struct.begin {{refkey={template_sid}}}",
        f"   SID = {sid}",
        f"   LocalizationSID = {item.get('localization_sid', sid)}",
        f"   Cost = {cost}",
        f"   Icon = {icon}",
    ]
    lines.extend(render_fitting_weapons(item["fitting_weapons"]))
    if "invisible_in_player_inventory" in item:
        lines.append(
            f"   InvisibleInPlayerInventory = {bool_cfg(item['invisible_in_player_inventory'])}"
        )
    lines.append("struct.end")
    return "\n".join(lines)


def main() -> None:
    config = load_json(CONFIG_PATH)
    weapon_config = load_weapon_progression()
    validate_config(config, weapon_config)

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
        "// Sources:",
        "//   Python/Config/weapon_progression.json",
        "//   Python/CFGGenerators/BlueprintPrototypes/blueprint_prototypes.json",
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
        lines.append(render_template(templates[str(tier)]))

    if debug_items:
        lines.extend([
            "", "",
            "// ------------------------------------------------------------",
            "// Debug Items - visible in inventory",
            "// ------------------------------------------------------------",
        ])
        for index, item in enumerate(debug_items):
            if index > 0:
                lines.append("")
            lines.append(render_item(
                item, templates, costs, icon_base_path, icon_names, debug_icon_name, debug=True
            ))

    current_family = None
    for item in blueprints:
        family = item["sid"].split("_Upgrades_Tier_")[0]
        if family != current_family:
            lines.extend([
                "", "",
                "// ------------------------------------------------------------",
                f"// {family}",
                "// ------------------------------------------------------------",
            ])
            current_family = family
        else:
            lines.append("")
        lines.append(render_item(
            item, templates, costs, icon_base_path, icon_names, debug_icon_name
        ))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Blueprint Prototype CFG Generator")
    print("---------------------------------")
    print(f"Templates:       {len(templates)}")
    print(f"Debug items:     {len(debug_items)}")
    print(f"Blueprint items: {len(blueprints)}")
    print(f"Weapon families: {len(get_weapon_families(weapon_config))}")
    print(f"Written to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
