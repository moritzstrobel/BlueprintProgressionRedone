import json
from pathlib import Path

import unreal


# =============================================================================
# Paths / Config
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "shakes.json"

TEMPLATE_ASSET = "/Testmod/Shakes/BPR_PM_UpgradeKit_Base"
OUTPUT_FOLDER = "/Testmod/Shakes"


# =============================================================================
# Helpers
# =============================================================================

def log(message: str) -> None:
    unreal.log(f"[BPR Shake Generator] {message}")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict) -> None:
    families = config.get("weapon_families")

    if not isinstance(families, list) or not families:
        raise ValueError(
            "'weapon_families' must contain at least one weapon family."
        )

    if any(
        not isinstance(family, str) or not family.strip()
        for family in families
    ):
        raise ValueError(
            "Every weapon family must be a non-empty string."
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


def build_target_asset(family: str) -> str:
    return f"{OUTPUT_FOLDER}/BPR_{family}_UpgradeKit"


# =============================================================================
# Blueprint generation
# =============================================================================

def generate_blueprint(family: str) -> None:
    """
    Duplicate the base UpgradeKit Blueprint for one weapon family.

    Important:
    - The complete EventGraph is copied from BPR_PM_UpgradeKit_Base.
    - Literal Execute Console Command values are NOT modified here.
    - The template values/placeholders remain unchanged and can be edited
      manually in the generated Blueprint afterwards.
    """
    target_asset = build_target_asset(family)

    log("----------------------------------------")
    log(f"Generating family: {family}")
    log(f"Target: {target_asset}")

    # -------------------------------------------------------------------------
    # Delete existing generated asset
    # -------------------------------------------------------------------------

    if unreal.EditorAssetLibrary.does_asset_exist(target_asset):
        log(f"Target already exists, deleting: {target_asset}")

        deleted = unreal.EditorAssetLibrary.delete_asset(target_asset)

        if not deleted:
            raise RuntimeError(
                f"Could not delete existing asset:\n{target_asset}"
            )

    # -------------------------------------------------------------------------
    # Duplicate template
    #
    # The duplicated Blueprint keeps the complete EventGraph, including the
    # three Execute Console Command nodes and all existing connections.
    # -------------------------------------------------------------------------

    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        TEMPLATE_ASSET,
        target_asset,
    )

    if not duplicated:
        raise RuntimeError(
            f"Could not duplicate Blueprint:\n"
            f"{TEMPLATE_ASSET}\n"
            f"-> {target_asset}"
        )

    # -------------------------------------------------------------------------
    # Load / compile / save
    # -------------------------------------------------------------------------

    blueprint = unreal.load_asset(target_asset)

    if blueprint is None:
        raise RuntimeError(
            f"Could not load Blueprint:\n{target_asset}"
        )

    log(f"Loaded Blueprint: {blueprint.get_name()}")

    # No graph manipulation is performed here.
    # Compiling verifies that the duplicated graph is still valid.
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)

    saved = unreal.EditorAssetLibrary.save_asset(
        target_asset,
        only_if_is_dirty=False,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save Blueprint:\n{target_asset}"
        )

    log(f"Generated successfully: {target_asset}")
    log(
        f"Manual commands still required for {family}: "
        f"{family}_Upgrades_Tier_1 / Tier_2 / Tier_3"
    )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    log("========================================")
    log("BPR Shake Blueprint Generator")
    log("========================================")
    log(f"Config:   {CONFIG_FILE}")
    log(f"Template: {TEMPLATE_ASSET}")
    log(f"Output:   {OUTPUT_FOLDER}")
    log("")

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config file not found:\n{CONFIG_FILE}"
        )

    if not unreal.EditorAssetLibrary.does_asset_exist(TEMPLATE_ASSET):
        raise RuntimeError(
            f"Template Blueprint does not exist:\n{TEMPLATE_ASSET}"
        )

    config = load_config(CONFIG_FILE)
    validate_config(config)

    families = config["weapon_families"]

    log(f"Weapon families: {len(families)}")
    log(
        "Mode: duplicate template only; "
        "console commands are kept from the template."
    )

    generated_count = 0

    for family in families:
        generate_blueprint(family)
        generated_count += 1

    log("")
    log("========================================")
    log("Generation complete")
    log("========================================")
    log(f"Families in config: {len(families)}")
    log(f"Generated:          {generated_count}")
    log("")
    log(
        "Next step: edit the three Execute Console Command values "
        "manually in each generated Blueprint."
    )


if __name__ == "__main__":
    main()
