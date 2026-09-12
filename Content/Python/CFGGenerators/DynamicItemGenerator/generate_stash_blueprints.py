#!/usr/bin/env python3
"""
Generate BPR stash loot configuration.

Expected location:
    Content/Python/CFGGenerators/DynamicItemGenerator/generate_stash_blueprints.py

Config:
    Content/Python/CFGGenerators/DynamicItemGenerator/weapon_progression.json

Generated files:
    Content/GameLite/ModGameData/Testmod/ItemGeneratorPrototypes/
        BPR_Stashes_ItemGeneratorPrototypes.cfg

    Content/GameLite/GameData/ItemGeneratorPrototypes/DynamicItemGenerator/
        GamePassItemGeneratorPrototypes_patch_BPR.cfg

Design:
  * Weapon pools are cumulative:
      Newbie
      Newbie + Experienced
      Newbie + Experienced + Veteran
  * Vanilla Master reuses the Veteran pool.
  * Tier I / II / III blueprint rolls are independent.
  * Upgrade Kits are a separate, very rare independent roll.
  * Upgrade Kits use SID: BPR_<family>_UpgradeKit
  * Dynamic arrays use [*] wherever possible.
"""

from __future__ import annotations

import json
from pathlib import Path


# =============================================================================
# Paths
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "weapon_progression.json"

# SCRIPT_DIR:
# Content/Python/CFGGenerators/DynamicItemGenerator
#
# parents[2]:
# Content
CONTENT_DIR = SCRIPT_DIR.parents[2]

BASEGAME_ITEM_GENERATOR_DIR = (
    CONTENT_DIR
    / "GameLite"
    / "GameData"
    / "ItemGeneratorPrototypes"
)

MOD_ITEM_GENERATOR_DIR = (
    CONTENT_DIR
    / "GameLite"
    / "ModGameData"
    / "Testmod"
    / "ItemGeneratorPrototypes"
)

DYNAMIC_ITEM_GENERATOR_DIR = (
    BASEGAME_ITEM_GENERATOR_DIR
    / "DynamicItemGenerator"
)

GENERATORS_OUTPUT = (
    MOD_ITEM_GENERATOR_DIR
    / "BPR_Stashes_ItemGeneratorPrototypes.cfg"
)

PATCH_OUTPUT = (
    DYNAMIC_ITEM_GENERATOR_DIR
    / "GamePassItemGeneratorPrototypes_patch_BPR.cfg"
)


# =============================================================================
# Constants
# =============================================================================

RANK_ORDER = (
    "Newbie",
    "Experienced",
    "Veteran",
)

VANILLA_RANKS = (
    "Newbie",
    "Experienced",
    "Veteran",
    "Master",
)

TIER_KEYS = (
    ("tier_1", 1),
    ("tier_2", 2),
    ("tier_3", 3),
)

STASH_GENERATORS = (
    "GamePass_Stash_ItemGenerator_Cheap",
    "GamePass_Stash_ItemGenerator_Rare",
    "GamePass_Stash_ItemGenerator_Common_Var1",
    "GamePass_Stash_ItemGenerator_Common_Var2",
)


# =============================================================================
# Config
# =============================================================================

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config not found:\n{CONFIG_FILE}"
        )

    data = json.loads(
        CONFIG_FILE.read_text(
            encoding="utf-8"
        )
    )

    required = (
        "drop_chances",
        "rank_behavior",
        "weapon_progression",
        "item_sid_patterns",
    )

    for key in required:
        if key not in data:
            raise ValueError(
                f"Missing required JSON key: {key}"
            )

    for rank in RANK_ORDER:
        if rank not in data[
            "weapon_progression"
        ]:
            raise ValueError(
                f"Missing weapon progression rank: {rank}"
            )

    for chance_key in (
        "tier_1",
        "tier_2",
        "tier_3",
        "upgrade_kit",
    ):
        if chance_key not in data[
            "drop_chances"
        ]:
            raise ValueError(
                f"Missing drop chance: {chance_key}"
            )

        chance = float(
            data[
                "drop_chances"
            ][
                chance_key
            ]
        )

        if not 0.0 <= chance <= 1.0:
            raise ValueError(
                f"{chance_key} must be between "
                f"0.0 and 1.0, got {chance}"
            )

    mapping = data[
        "rank_behavior"
    ].get(
        "vanilla_rank_mapping",
        {},
    )

    for vanilla_rank in VANILLA_RANKS:
        if vanilla_rank not in mapping:
            raise ValueError(
                f"Missing vanilla rank mapping: "
                f"{vanilla_rank}"
            )

        logical_rank = mapping[
            vanilla_rank
        ]

        if logical_rank not in RANK_ORDER:
            raise ValueError(
                f"Invalid logical rank mapping for "
                f"{vanilla_rank}: {logical_rank}"
            )

    return data


def cumulative_families(
    data: dict,
    rank: str,
) -> list[str]:
    families: list[str] = []

    for current_rank in RANK_ORDER:
        families.extend(
            data[
                "weapon_progression"
            ][
                current_rank
            ]
        )

        if current_rank == rank:
            break

    # Preserve configured order and remove duplicates.
    return list(
        dict.fromkeys(families)
    )


def tier_item_sid(
    data: dict,
    family: str,
    tier: int,
) -> str:
    pattern = data[
        "item_sid_patterns"
    ][
        "tier_blueprint"
    ]

    return pattern.format(
        family=family,
        tier=tier,
    )


def upgrade_kit_sid(
    data: dict,
    family: str,
) -> str:
    pattern = data[
        "item_sid_patterns"
    ][
        "upgrade_kit"
    ]

    return pattern.format(
        family=family,
    )


# =============================================================================
# Common rendering helpers
# =============================================================================

def render_header(
    output_path: Path,
) -> list[str]:
    relative_path = (
        output_path.relative_to(
            CONTENT_DIR
        )
    )

    return [
        "// -----------------------------------------------------------------------------",
        "// AUTO-GENERATED FILE - DO NOT EDIT BY HAND",
        "//",
        "// Source: Python/CFGGenerators/DynamicItemGenerator/weapon_progression.json",
        "// Generated by: generate_stash_blueprints.py",
        f"// Output: Content/{relative_path.as_posix()}",
        "// -----------------------------------------------------------------------------",
        "",
    ]


# =============================================================================
# BPR custom generator CFG
# =============================================================================

def render_item_pool(
    sid: str,
    item_sids: list[str],
) -> list[str]:
    lines = [
        f"{sid} : struct.begin "
        "{refurl=@BaseGame/ItemGeneratorPrototypes.cfg;refkey=[0]}",
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

    lines.extend([
        "         struct.end",
        "      struct.end",
        "   struct.end",
        "struct.end",
        "",
    ])

    return lines


def render_roll_entry(
    pool_sid: str,
    chance: float,
) -> list[str]:
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


def render_rank_roll_generator(
    rank: str,
    data: dict,
) -> list[str]:
    sid = (
        f"BPR_StashRolls_{rank}"
    )

    lines = [
        f"{sid} : struct.begin "
        "{refurl=@BaseGame/ItemGeneratorPrototypes.cfg;refkey=[0]}",
        f"   SID = {sid}",
        "   ItemGenerator : struct.begin",
    ]

    # Independent rolls for the three normal blueprint tiers.
    for chance_key, tier in TIER_KEYS:
        pool_sid = (
            f"BPR_StashBlueprint_"
            f"{rank}_Tier_{tier}"
        )

        chance = float(
            data[
                "drop_chances"
            ][
                chance_key
            ]
        )

        lines.extend(
            render_roll_entry(
                pool_sid,
                chance,
            )
        )

    # Independent rare Upgrade Kit roll.
    kit_pool_sid = (
        f"BPR_StashUpgradeKit_{rank}"
    )

    kit_chance = float(
        data[
            "drop_chances"
        ][
            "upgrade_kit"
        ]
    )

    lines.extend(
        render_roll_entry(
            kit_pool_sid,
            kit_chance,
        )
    )

    lines.extend([
        "   struct.end",
        "struct.end",
        "",
    ])

    return lines


def generate_generators(
    data: dict,
) -> str:
    lines = render_header(
        GENERATORS_OUTPUT
    )

    lines.extend([
        "//",
        "// This file contains all BPR-owned stash loot pools.",
        "// It replaces the previous flat 108-item blueprint pool.",
        "//",
        "",
    ])

    for rank in RANK_ORDER:
        families = cumulative_families(
            data,
            rank,
        )

        lines.extend([
            "// -----------------------------------------------------------------------------",
            f"// {rank} - {len(families)} cumulative weapon families",
            "// -----------------------------------------------------------------------------",
            "",
        ])

        # ---------------------------------------------------------
        # Tier blueprint pools
        # ---------------------------------------------------------

        for _, tier in TIER_KEYS:
            item_sids = [
                tier_item_sid(
                    data,
                    family,
                    tier,
                )
                for family in families
            ]

            lines.extend(
                render_item_pool(
                    (
                        f"BPR_StashBlueprint_"
                        f"{rank}_Tier_{tier}"
                    ),
                    item_sids,
                )
            )

        # ---------------------------------------------------------
        # Upgrade Kit pool
        # ---------------------------------------------------------

        kit_sids = [
            upgrade_kit_sid(
                data,
                family,
            )
            for family in families
        ]

        lines.extend(
            render_item_pool(
                f"BPR_StashUpgradeKit_{rank}",
                kit_sids,
            )
        )

        # ---------------------------------------------------------
        # Combined independent rolls
        # ---------------------------------------------------------

        lines.extend(
            render_rank_roll_generator(
                rank,
                data,
            )
        )

    return (
        "\n".join(lines).rstrip()
        + "\n"
    )


# =============================================================================
# GamePass stash patch
# =============================================================================

def generate_patch(
    data: dict,
) -> str:
    mapping = data[
        "rank_behavior"
    ][
        "vanilla_rank_mapping"
    ]

    lines = render_header(
        PATCH_OUTPUT
    )

    lines.extend([
        "// [*] is intentional.",
        "//",
        "// We append BPR entries instead of relying on fixed array indices.",
        "// This avoids assumptions about whether vanilla or another mod",
        "// has already appended entries before this patch is processed.",
        "",
    ])

    for stash_sid in STASH_GENERATORS:
        lines.extend([
            f"{stash_sid} : struct.begin {{bpatch}}",
            "   ItemGenerator : struct.begin {bpatch}",
        ])

        for vanilla_rank in VANILLA_RANKS:
            logical_rank = mapping[
                vanilla_rank
            ]

            lines.extend([
                "      [*] : struct.begin",
                "         Category = EItemGenerationCategory::SubItemGenerator",
                "         bAllowSameCategoryGeneration = true",
                f"         PlayerRank = ERank::{vanilla_rank}",
                "         PossibleItems : struct.begin",
                "            [*] : struct.begin",
                (
                    "               "
                    "ItemGeneratorPrototypeSID = "
                    f"BPR_StashRolls_{logical_rank}"
                ),
                "               Chance = 1",
                "               MinCount = 1",
                "               MaxCount = 1",
                "            struct.end",
                "         struct.end",
                "      struct.end",
            ])

        lines.extend([
            "   struct.end",
            "struct.end",
            "",
        ])

    return (
        "\n".join(lines).rstrip()
        + "\n"
    )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    data = load_config()

    MOD_ITEM_GENERATOR_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    DYNAMIC_ITEM_GENERATOR_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    GENERATORS_OUTPUT.write_text(
        generate_generators(
            data
        ),
        encoding="utf-8",
    )

    PATCH_OUTPUT.write_text(
        generate_patch(
            data
        ),
        encoding="utf-8",
    )

    print(
        "BPR Dynamic Item Generator"
    )
    print(
        "--------------------------"
    )

    print("Config:")
    print(
        f"  {CONFIG_FILE}"
    )

    print()

    print("Generated:")
    print(
        f"  {GENERATORS_OUTPUT}"
    )
    print(
        f"  {PATCH_OUTPUT}"
    )

    print()

    print("Drop chances:")
    print(
        f"  Tier I:      "
        f"{data['drop_chances']['tier_1']:.2%}"
    )
    print(
        f"  Tier II:     "
        f"{data['drop_chances']['tier_2']:.2%}"
    )
    print(
        f"  Tier III:    "
        f"{data['drop_chances']['tier_3']:.2%}"
    )
    print(
        f"  Upgrade Kit: "
        f"{data['drop_chances']['upgrade_kit']:.2%}"
    )


if __name__ == "__main__":
    main()