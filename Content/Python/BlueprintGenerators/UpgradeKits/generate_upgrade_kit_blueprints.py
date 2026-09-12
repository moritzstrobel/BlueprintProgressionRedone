from __future__ import annotations

import sys
from pathlib import Path

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_ROOT = SCRIPT_DIR.parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from Common.bpr_common import get_weapon_families

TEMPLATE_ASSET = "/Testmod/Shakes/BPR_PM_UpgradeKit_Base"
OUTPUT_FOLDER = "/Testmod/Shakes"


def log(message: str) -> None:
    unreal.log(f"[BPR Upgrade Kit Generator] {message}")


def build_target_asset(family: str) -> str:
    return f"{OUTPUT_FOLDER}/BPR_{family}_UpgradeKit"


def generate_blueprint(family: str) -> None:
    target_asset = build_target_asset(family)
    log(f"Generating {family}: {target_asset}")

    if unreal.EditorAssetLibrary.does_asset_exist(target_asset):
        if not unreal.EditorAssetLibrary.delete_asset(target_asset):
            raise RuntimeError(f"Could not delete existing asset:\n{target_asset}")

    if not unreal.EditorAssetLibrary.duplicate_asset(TEMPLATE_ASSET, target_asset):
        raise RuntimeError(f"Could not duplicate Blueprint:\n{TEMPLATE_ASSET}\n-> {target_asset}")

    blueprint = unreal.load_asset(target_asset)
    if blueprint is None:
        raise RuntimeError(f"Could not load Blueprint:\n{target_asset}")

    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    if not unreal.EditorAssetLibrary.save_asset(target_asset, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save Blueprint:\n{target_asset}")

    log(f"Generated: {target_asset}")
    log(f"Manual commands: {family}_Upgrades_Tier_1 / Tier_2 / Tier_3")


def main() -> None:
    if not unreal.EditorAssetLibrary.does_asset_exist(TEMPLATE_ASSET):
        raise RuntimeError(f"Template Blueprint does not exist:\n{TEMPLATE_ASSET}")

    families = get_weapon_families()
    log(f"Generating {len(families)} Upgrade Kit Blueprints")

    for family in families:
        generate_blueprint(family)

    log(f"Generation complete: {len(families)} Blueprints")
    log("Console command values still require manual editing in each generated Blueprint.")


if __name__ == "__main__":
    main()
