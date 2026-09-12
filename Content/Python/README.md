# BPR Python tooling

The Python tooling is split by responsibility so generated game data and Unreal asset generation stay easy to reason about.

## Structure

- `Common/` - shared Python helpers used by multiple generators.
- `Config/` - global configuration shared across generator groups. `weapon_progression.json` is the single source of truth for weapon families and rank progression.
- `CFGGenerators/BlueprintPrototypes/` - blueprint item prototype generation.
- `CFGGenerators/UpgradeKits/` - Upgrade Kit consumable prototype generation.
- `CFGGenerators/CameraShakes/` - Upgrade Kit camera shake prototype generation.
- `CFGGenerators/CameraEffects/` - Upgrade Kit camera effect prototype generation.
- `CFGGenerators/Distribution/` - stash, NPC and trader distribution generation.
- `CFGGenerators/Upgrades/` - vanilla weapon upgrade patches that require blueprint tiers.
- `BlueprintGenerators/UpgradeKits/` - Unreal Python tooling that duplicates Upgrade Kit Blueprint assets.
- `Localization/` - localization generation/upsert tooling.

## Shared configuration

Weapon families must only be added or removed in `Config/weapon_progression.json`. Other generators derive their family list from that file instead of maintaining local copies.

Distribution-specific settings remain close to their generators:

- `Distribution/stash_loot.json`
- `Distribution/npc_loot.json`
- `Distribution/blueprint_traders.json`

Item-specific settings remain in `UpgradeKits/upgrade_kits.json`.
