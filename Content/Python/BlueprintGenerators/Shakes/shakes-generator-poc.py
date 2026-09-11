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

TEMPLATE_FAMILY = "PM"


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


def build_commands(family: str) -> dict[str, str]:
    return {
        "CMD_TIER_I": (
            f"XCreateItemInInventoryByID "
            f"{family}_Upgrades_Tier_1 0 1 1"
        ),
        "CMD_TIER_II": (
            f"XCreateItemInInventoryByID "
            f"{family}_Upgrades_Tier_2 0 1 1"
        ),
        "CMD_TIER_III": (
            f"XCreateItemInInventoryByID "
            f"{family}_Upgrades_Tier_3 0 1 1"
        ),
    }


def build_target_asset(family: str) -> str:
    return f"{OUTPUT_FOLDER}/BPR_{family}_UpgradeKit"


# =============================================================================
# Blueprint generation
# =============================================================================

def generate_blueprint(family: str) -> None:
    target_asset = build_target_asset(family)
    commands = build_commands(family)

    log("----------------------------------------")
    log(f"Generating family: {family}")
    log(f"Target: {target_asset}")

    # -------------------------------------------------------------------------
    # Existing asset
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
    # Load Blueprint
    # -------------------------------------------------------------------------

    blueprint = unreal.load_asset(target_asset)

    if blueprint is None:
        raise RuntimeError(
            f"Could not load Blueprint:\n{target_asset}"
        )

    log(f"Loaded Blueprint: {blueprint.get_name()}")

    # -------------------------------------------------------------------------
    # Compile before accessing GeneratedClass
    # -------------------------------------------------------------------------

    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)

    generated_class = blueprint.generated_class()

    if generated_class is None:
        raise RuntimeError(
            f"Blueprint has no GeneratedClass:\n{target_asset}"
        )

    cdo = unreal.get_default_object(generated_class)

    if cdo is None:
        raise RuntimeError(
            f"Could not get Class Default Object:\n{target_asset}"
        )

    # -------------------------------------------------------------------------
    # Set variable defaults
    # -------------------------------------------------------------------------

    for variable_name, command in commands.items():
        log(f"{variable_name} = {command}")

        try:
            cdo.set_editor_property(
                variable_name,
                command,
            )

        except Exception as exc:
            raise RuntimeError(
                f"Could not set Blueprint variable "
                f"'{variable_name}' for family '{family}'.\n"
                f"Command: {command}\n"
                f"Error: {exc}"
            )

    # -------------------------------------------------------------------------
    # Compile again after modifying defaults
    # -------------------------------------------------------------------------

    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)

    # -------------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------------

    saved = unreal.EditorAssetLibrary.save_asset(
        target_asset,
        only_if_is_dirty=False,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save Blueprint:\n{target_asset}"
        )

    log(f"Generated successfully: {target_asset}")


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

    generated_count = 0
    skipped_count = 0

    for family in families:

        # PM currently already exists as the manually created/original asset.
        # The _Base Blueprint is only the generator template.
        if family == TEMPLATE_FAMILY:
            log("----------------------------------------")
            log(
                f"Skipping template family '{family}'. "
                f"Existing BPR_{family}_UpgradeKit will not be overwritten."
            )
            skipped_count += 1
            continue

        generate_blueprint(family)
        generated_count += 1

    log("")
    log("========================================")
    log("Generation complete")
    log("========================================")
    log(f"Families in config: {len(families)}")
    log(f"Generated:          {generated_count}")
    log(f"Skipped:            {skipped_count}")


if __name__ == "__main__":
    main()