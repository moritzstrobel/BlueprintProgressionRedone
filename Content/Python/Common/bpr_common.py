from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PYTHON_ROOT = Path(__file__).resolve().parents[1]
WEAPON_PROGRESSION_PATH = PYTHON_ROOT / "Config" / "weapon_progression.json"

RANK_ORDER = ("Newbie", "Experienced", "Veteran")
VANILLA_RANKS = ("Newbie", "Experienced", "Veteran", "Master")


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object and fail with a useful path if it is missing."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found:\n{path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in:\n{path}")

    return data


def validate_weapon_progression(config: dict[str, Any]) -> None:
    required = (
        "rank_behavior",
        "weapon_progression",
        "item_sid_patterns",
    )

    for key in required:
        if key not in config:
            raise ValueError(
                f"weapon_progression.json is missing '{key}'."
            )

    progression = config["weapon_progression"]

    if not isinstance(progression, dict):
        raise ValueError("'weapon_progression' must be an object.")

    families: list[str] = []

    for rank in RANK_ORDER:
        rank_families = progression.get(rank)

        if not isinstance(rank_families, list) or not rank_families:
            raise ValueError(
                f"weapon_progression.json is missing/invalid rank '{rank}'."
            )

        if any(
            not isinstance(family, str) or not family.strip()
            for family in rank_families
        ):
            raise ValueError(
                f"Rank '{rank}' contains an invalid weapon family."
            )

        families.extend(rank_families)

    duplicates = sorted({
        family
        for family in families
        if families.count(family) > 1
    })

    if duplicates:
        raise ValueError(
            "Weapon families must occur in exactly one progression rank: "
            + ", ".join(duplicates)
        )

    mapping = config["rank_behavior"].get(
        "vanilla_rank_mapping",
        {},
    )

    for vanilla_rank in VANILLA_RANKS:
        logical_rank = mapping.get(vanilla_rank)

        if logical_rank not in RANK_ORDER:
            raise ValueError(
                f"Invalid/missing rank mapping for {vanilla_rank}: "
                f"{logical_rank}"
            )

    patterns = config["item_sid_patterns"]

    for key in ("tier_blueprint", "upgrade_kit"):
        if not isinstance(patterns.get(key), str) or not patterns[key]:
            raise ValueError(
                f"Missing/invalid item SID pattern '{key}'."
            )


def load_weapon_progression() -> dict[str, Any]:
    config = load_json(WEAPON_PROGRESSION_PATH)
    validate_weapon_progression(config)
    return config


def get_weapon_families(
    config: dict[str, Any] | None = None,
) -> list[str]:
    if config is None:
        config = load_weapon_progression()

    families: list[str] = []

    for rank in RANK_ORDER:
        families.extend(config["weapon_progression"][rank])

    return families


def cumulative_families(
    config: dict[str, Any],
    rank: str,
) -> list[str]:
    if rank not in RANK_ORDER:
        raise ValueError(f"Unknown logical rank: {rank}")

    families: list[str] = []

    for current_rank in RANK_ORDER:
        families.extend(config["weapon_progression"][current_rank])

        if current_rank == rank:
            break

    return families


def logical_rank_for_vanilla(
    config: dict[str, Any],
    vanilla_rank: str,
) -> str:
    try:
        return config["rank_behavior"]["vanilla_rank_mapping"][vanilla_rank]
    except KeyError as exc:
        raise ValueError(
            f"No logical rank mapping for vanilla rank '{vanilla_rank}'."
        ) from exc


def tier_blueprint_sid(
    config: dict[str, Any],
    family: str,
    tier: int,
) -> str:
    return config["item_sid_patterns"]["tier_blueprint"].format(
        family=family,
        tier=tier,
    )


def upgrade_kit_sid(
    config: dict[str, Any],
    family: str,
) -> str:
    return config["item_sid_patterns"]["upgrade_kit"].format(
        family=family,
    )
