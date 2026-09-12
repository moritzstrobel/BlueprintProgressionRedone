#!/usr/bin/env python3
"""Run all standard-library BPR CFG generators in a deterministic order."""

from __future__ import annotations

import runpy
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parent

GENERATORS = (
    "CFGGenerators/BlueprintPrototypes/generate_blueprint_prototypes.py",
    "CFGGenerators/UpgradeKits/generate_upgrade_kit_items.py",
    "CFGGenerators/CameraShakes/generate_camera_shakes.py",
    "CFGGenerators/CameraEffects/generate_camera_effects.py",
    "CFGGenerators/Distribution/generate_stash_blueprints.py",
    "CFGGenerators/Distribution/generate_npc_loot.py",
    "CFGGenerators/Distribution/generate_trader_blueprints.py",
    "CFGGenerators/Upgrades/generate_upgrade_blueprint_tiers.py",
)


def main() -> None:
    print("BPR CFG Generator Suite")
    print("=======================")

    for relative_path in GENERATORS:
        script_path = PYTHON_ROOT / relative_path
        if not script_path.exists():
            raise FileNotFoundError(f"Generator not found:\n{script_path}")

        print()
        print(f">>> {relative_path}")
        print("-" * (4 + len(relative_path)))
        runpy.run_path(str(script_path), run_name="__main__")

    print()
    print("All CFG generators completed successfully.")


if __name__ == "__main__":
    main()
