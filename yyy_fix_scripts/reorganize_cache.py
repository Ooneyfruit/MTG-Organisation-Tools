import os
import re
import sys
import json
import shutil

# Ensure we can import from _core_tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from _core_tools.scryfall_core import CACHE_DIR, sanitize_filename

def reorganize_cache():
    if not os.path.exists(CACHE_DIR):
        print(f"Cache directory {CACHE_DIR} does not exist. Nothing to reorganize.")
        return

    print(f"Scanning cache directory: {CACHE_DIR}")
    files = [f for f in os.listdir(CACHE_DIR) if os.path.isfile(os.path.join(CACHE_DIR, f))]
    
    moved_count = 0
    skipped_count = 0
    errors_count = 0

    for filename in files:
        if filename.lower() == "readme.md":
            print(f"Skipping documentation file: {filename}")
            skipped_count += 1
            continue

        if not filename.endswith(".json"):
            print(f"Skipping non-JSON file: {filename}")
            skipped_count += 1
            continue

        src_path = os.path.join(CACHE_DIR, filename)
        target_dir_name = None
        target_filename = filename

        # Try to parse the file to help resolve/verify set
        file_data = None
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse {filename}: {e}")

        # Rule 1: Set Metadata files
        if filename.startswith("set_metadata_"):
            match = re.match(r"^set_metadata_(.+)\.json$", filename)
            if match:
                set_code = match.group(1)
                target_dir_name = sanitize_filename(set_code)
            else:
                # Fallback to content check
                if file_data and isinstance(file_data, dict) and file_data.get("code"):
                    target_dir_name = sanitize_filename(file_data["code"])

        # Rule 2: Set and collector number card cache
        elif filename.startswith("set_"):
            # Try to get set from file content first
            if file_data and isinstance(file_data, dict):
                params = file_data.get("query_metadata", {}).get("query_params", {})
                if params.get("set"):
                    target_dir_name = sanitize_filename(params["set"])
            
            # Fallback to parsing filename set_setcode_collector.json
            if not target_dir_name:
                match = re.match(r"^set_(.+)_[^_]+\.json$", filename)
                if match:
                    target_dir_name = sanitize_filename(match.group(1))

        # Rule 3: Name and set card cache
        elif filename.startswith("name_set_"):
            # Try to get set from file content first
            if file_data and isinstance(file_data, dict):
                params = file_data.get("query_metadata", {}).get("query_params", {})
                if params.get("set"):
                    target_dir_name = sanitize_filename(params["set"])
            
            # Fallback to parsing filename name_set_cardname_setcode.json
            if not target_dir_name:
                # Greedy match on first part, capturing the last segment after the last underscore
                match = re.match(r"^name_set_(.+)_([^_]+)\.json$", filename)
                if match:
                    target_dir_name = sanitize_filename(match.group(2))

        # Rule 4: Name only card cache
        elif filename.startswith("name_"):
            target_dir_name = "_general"

        # Check if we successfully resolved a target directory
        if target_dir_name:
            dest_dir = os.path.join(CACHE_DIR, target_dir_name)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, target_filename)

            try:
                # Check for conflicts
                if os.path.exists(dest_path):
                    # If target already exists, delete the source to avoid duplicates
                    os.remove(src_path)
                    print(f"Removed duplicate file: {filename} (already exists in {target_dir_name}/)")
                else:
                    shutil.move(src_path, dest_path)
                    print(f"Moved: {filename} -> {target_dir_name}/{target_filename}")
                moved_count += 1
            except Exception as e:
                print(f"Error moving {filename} to {dest_dir}: {e}")
                errors_count += 1
        else:
            print(f"Could not determine target directory for: {filename}")
            skipped_count += 1

    print("\nReorganization complete:")
    print(f"  Moved/Resolved: {moved_count}")
    print(f"  Skipped:        {skipped_count}")
    print(f"  Errors:         {errors_count}")

if __name__ == "__main__":
    reorganize_cache()
