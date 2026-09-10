import json
import os
import unreal


# ============================================================
# CONFIG
# ============================================================

ASSET_PATH = "/Testmod/Localization/L_Testmod"

# JSON lies in the same directory as this Python script.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALIZATION_FILE = os.path.join(
    SCRIPT_DIR,
    "Blueprint_Localization.json"
)


# ============================================================
# HELPERS
# ============================================================

def log(message):
    unreal.log(f"[BlueprintLocalization] {message}")


def warn(message):
    unreal.log_warning(f"[BlueprintLocalization] {message}")


def escape_unreal_string(value):
    """
    Escape a Python string so it can safely be used inside
    Unreal's Struct import_text representation.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def read_localization_file(path):
    """
    Expected JSON format:

    {
      "entries": [
        {
          "sid": "sid_items_PM_Upgrades_Tier_1_name",
          "languages": {
            "English": "PM Upgrade Blueprint - Tier I"
          }
        }
      ]
    }
    """
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    entries = data.get("entries")

    if not isinstance(entries, list):
        raise RuntimeError(
            "Localization JSON must contain an 'entries' array."
        )

    normalized = []

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise RuntimeError(
                f"Entry #{index} is not an object."
            )

        sid = str(entry.get("sid", "")).strip()
        languages = entry.get("languages")

        if not sid:
            raise RuntimeError(
                f"Entry #{index} has an empty SID."
            )

        if not isinstance(languages, dict) or not languages:
            raise RuntimeError(
                f"Entry '{sid}' has no valid 'languages' object."
            )

        normalized_languages = {}

        for language, text in languages.items():
            language = str(language).strip()

            if not language:
                raise RuntimeError(
                    f"Entry '{sid}' contains an empty language key."
                )

            normalized_languages[language] = str(text)

        normalized.append(
            {
                "sid": sid,
                "languages": normalized_languages
            }
        )

    return normalized


def make_struct_text(sid, languages):
    """
    Build the Struct import_text representation:

    (SID="...",
     LanguagesToLocalizedStrings=((English, "...")))
    """
    safe_sid = escape_unreal_string(sid)

    language_parts = []

    for language, text in languages.items():
        safe_text = escape_unreal_string(text)
        language_parts.append(
            f'({language}, "{safe_text}")'
        )

    languages_text = ",".join(language_parts)

    return (
        f'(SID="{safe_sid}",'
        f'LanguagesToLocalizedStrings=({languages_text}))'
    )


def get_sid(localized_entry):
    """
    Read SID from an existing ModTextToolLocalizedText struct.
    """
    sid = localized_entry.get_editor_property("SID")
    return str(sid)


# ============================================================
# START
# ============================================================

log("========================================")
log("Starting localization UPSERT")
log("========================================")


# ============================================================
# CHECK INPUT FILE
# ============================================================

if not os.path.isfile(LOCALIZATION_FILE):
    raise RuntimeError(
        f"Localization file does not exist:\n{LOCALIZATION_FILE}"
    )

log(f"Localization file: {LOCALIZATION_FILE}")


# ============================================================
# LOAD LOCALIZATION DATA
# ============================================================

entries = read_localization_file(LOCALIZATION_FILE)

if len(entries) == 0:
    raise RuntimeError(
        "Localization JSON contains no usable entries."
    )

log(f"Read {len(entries)} localization entries")


# Detect duplicate SIDs in JSON before touching the asset.
seen_input_sids = set()
input_duplicates = []

for entry in entries:
    sid = entry["sid"]

    if sid in seen_input_sids:
        input_duplicates.append(sid)

    seen_input_sids.add(sid)

if input_duplicates:
    raise RuntimeError(
        "Duplicate localization SIDs found in JSON:\n"
        + "\n".join(sorted(set(input_duplicates)))
    )

log("No duplicate SIDs found in JSON")


# ============================================================
# LOAD ASSET
# ============================================================

asset = unreal.load_asset(ASSET_PATH)

if asset is None:
    raise RuntimeError(
        f"Could not load localization asset: {ASSET_PATH}"
    )

log(f"Loaded asset: {asset}")


# ============================================================
# GET EXISTING LOCALIZED TEXT ARRAY
# ============================================================

localized_texts = asset.get_editor_property("LocalizedTexts")

existing_count_before = len(localized_texts)

log(
    f"Existing LocalizedTexts entries: "
    f"{existing_count_before}"
)

if existing_count_before == 0:
    raise RuntimeError(
        "LocalizedTexts is empty.\n\n"
        "The current Zone Kit Python API does not expose a constructor "
        "for ModTextToolLocalizedText.\n"
        "Create ONE temporary localization entry manually inside "
        "L_Testmod first, then run this script again."
    )


# ============================================================
# BUILD INDEX OF EXISTING ENTRIES
# ============================================================

existing_by_sid = {}
asset_duplicates = []

for index, localized_entry in enumerate(localized_texts):
    sid = get_sid(localized_entry)

    if sid in existing_by_sid:
        asset_duplicates.append(sid)
    else:
        existing_by_sid[sid] = localized_entry

if asset_duplicates:
    raise RuntimeError(
        "Duplicate localization SIDs already exist in L_Testmod.\n"
        "Resolve these before running the importer:\n"
        + "\n".join(sorted(set(asset_duplicates)))
    )

log(
    f"Indexed {len(existing_by_sid)} existing unique SIDs"
)


# ============================================================
# UPDATE EXISTING ENTRIES
# ============================================================

updated = 0
to_add = []

for entry in entries:
    sid = entry["sid"]
    struct_text = make_struct_text(
        sid,
        entry["languages"]
    )

    existing = existing_by_sid.get(sid)

    if existing is None:
        to_add.append(entry)
        continue

    existing.import_text(struct_text)
    updated += 1

log(f"Updated existing entries: {updated}")
log(f"New entries to append:    {len(to_add)}")


# ============================================================
# APPEND NEW ENTRIES
# ============================================================

added = 0

if to_add:
    # Python cannot directly instantiate ModTextToolLocalizedText.
    # Reuse one existing struct as a temporary working object.
    #
    # IMPORTANT:
    # Array.append() copies Unreal structs BY VALUE.
    # We therefore:
    #   1. save the working struct's current state,
    #   2. mutate it for each new SID,
    #   3. append a copied value,
    #   4. restore the working struct afterwards.
    template = localized_texts[0]
    template_backup = template.export_text()

    try:
        for index, entry in enumerate(to_add, start=1):
            struct_text = make_struct_text(
                entry["sid"],
                entry["languages"]
            )

            template.import_text(struct_text)
            localized_texts.append(template)
            added += 1

            if index % 25 == 0 or index == len(to_add):
                log(
                    f"Appended {index}/{len(to_add)} new entries"
                )

    finally:
        # Always restore the original value of element [0],
        # even if generation fails part-way through.
        template.import_text(template_backup)

log(f"Added new entries: {added}")


# ============================================================
# VALIDATION
# ============================================================

expected_final_count = existing_count_before + added
actual_final_count = len(localized_texts)

if actual_final_count != expected_final_count:
    raise RuntimeError(
        "Entry count mismatch!\n"
        f"Expected: {expected_final_count}\n"
        f"Actual:   {actual_final_count}"
    )

# Ensure every SID from JSON now exists exactly once.
final_sids = set()
final_duplicates = []

for localized_entry in localized_texts:
    sid = get_sid(localized_entry)

    if sid in final_sids:
        final_duplicates.append(sid)

    final_sids.add(sid)

if final_duplicates:
    raise RuntimeError(
        "Duplicate SIDs detected after UPSERT:\n"
        + "\n".join(sorted(set(final_duplicates)))
    )

missing_after_upsert = sorted(
    seen_input_sids - final_sids
)

if missing_after_upsert:
    raise RuntimeError(
        "Some JSON SIDs are still missing after UPSERT:\n"
        + "\n".join(missing_after_upsert)
    )

untouched = existing_count_before - updated

log("Validation successful")
log(f"Untouched old entries: {untouched}")
log(f"Final entry count:     {actual_final_count}")


# ============================================================
# WRITE PROPERTY TO ASSET
# ============================================================

asset.modify()

asset.set_editor_property(
    "LocalizedTexts",
    localized_texts
)

log("LocalizedTexts written to asset")


# ============================================================
# SAVE
# ============================================================

saved = unreal.EditorAssetLibrary.save_asset(
    ASSET_PATH,
    only_if_is_dirty=False
)

if not saved:
    raise RuntimeError(
        f"Failed to save asset: {ASSET_PATH}"
    )

log("Asset saved successfully")


# ============================================================
# DONE
# ============================================================

log("========================================")
log("SUCCESS - localization UPSERT complete")
log(f"Input entries:    {len(entries)}")
log(f"Updated:          {updated}")
log(f"Added:            {added}")
log(f"Untouched old:    {untouched}")
log(f"Final asset size: {actual_final_count}")
log(f"Asset: {ASSET_PATH}")
log("========================================")
