import os
import re
import csv
import sys

# Add core_tools directory to sys.path to resolve scryfall_core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core_tools")))
import scryfall_core

# --- CONFIGURATION ---
INPUT_FILE = "input.txt"
COLLECTION_FILE = "collection.csv"
OUTPUT_FILE = "output.txt"
IGNORE_DIR = "ignore"

def parse_line(line):
    line = line.strip()
    if not line:
        return None
        
    # Strip trailing foil indicators if present (*F*, *f*, etc.)
    foil = False
    foil_match = re.search(r'\s*\*F\*\s*$', line, re.IGNORECASE)
    if foil_match:
        foil = True
        line = line[:foil_match.start()].strip()
        
    # 1. Standard format: Quantity Name (Set) CollectorNumber
    match = re.match(r"^(\d+)\s+(.*?)\s+\(([^)]+)\)[^()]*\s+(\S+)$", line)
    if match:
        return {
            'quantity': int(match.group(1)),
            'name': match.group(2).strip(),
            'set': match.group(3).strip(),
            'collector_number': match.group(4).strip(),
            'foil': foil,
            'raw': line
        }
        
    # 2. Fallback: Quantity Name (Set)
    match = re.match(r"^(\d+)\s+(.*?)\s+\(([^)]+)\)$", line)
    if match:
        return {
            'quantity': int(match.group(1)),
            'name': match.group(2).strip(),
            'set': match.group(3).strip(),
            'collector_number': None,
            'foil': foil,
            'raw': line
        }
        
    # 3. Fallback: Quantity Name
    match = re.match(r"^(\d+)\s+(.*)$", line)
    if match:
        return {
            'quantity': int(match.group(1)),
            'name': match.group(2).strip(),
            'set': None,
            'collector_number': None,
            'foil': foil,
            'raw': line
        }
        
    # 4. Fallback: Just Name
    return {
        'quantity': 1,
        'name': line,
        'set': None,
        'collector_number': None,
        'foil': foil,
        'raw': line
    }

def is_golgari_legal(color_identity):
    # Golgari color identity is a subset of {B, G} (Black and Green).
    # Colorless/empty is allowed. No White (W), Blue (U), or Red (R) is allowed.
    for color in color_identity:
        if color.upper() not in ('B', 'G'):
            return False
    return True

def main():
    print("=" * 60)
    print("                      GOLGARI DECK HELPER")
    print("=" * 60)
    
    # 1. Load Exclusions from input.txt
    excluded_names = set()
    if os.path.exists(INPUT_FILE):
        print(f"Reading exclusions from: {INPUT_FILE}...")
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                parsed = parse_line(line)
                if parsed:
                    excluded_names.add(parsed['name'].lower())
        print(f"Loaded {len(excluded_names)} excluded card name(s) from {INPUT_FILE}.")
    else:
        print(f"Info: Exclusions file '{INPUT_FILE}' not found.")

    # 1b. Load Exclusions from CSVs in ignore/ directory
    if os.path.exists(IGNORE_DIR) and os.path.isdir(IGNORE_DIR):
        print(f"Checking for ignore CSV files in: {IGNORE_DIR}...")
        for filename in os.listdir(IGNORE_DIR):
            if filename.lower().endswith('.csv'):
                csv_path = os.path.join(IGNORE_DIR, filename)
                print(f"Reading ignore exclusions from: {csv_path}...")
                try:
                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        count_file_exclusions = 0
                        for row in reader:
                            name = row.get('Name')
                            if name:
                                name_stripped = name.strip()
                                if name_stripped:
                                    excluded_names.add(name_stripped.lower())
                                    count_file_exclusions += 1
                        print(f"  -> Loaded {count_file_exclusions} name(s) from {filename}")
                except Exception as e:
                    print(f"Error reading ignore CSV '{filename}': {e}", file=sys.stderr)
        print(f"Total active exclusions: {len(excluded_names)} card name(s).")

    # 2. Load Collection from collection.csv
    if not os.path.exists(COLLECTION_FILE):
        print(f"Error: Collection file '{COLLECTION_FILE}' not found.")
        print("Please export your Moxfield collection to CSV and save it as 'collection.csv'.")
        input()
        return

    print(f"Reading collection from: {COLLECTION_FILE}...")
    collection_rows = []
    try:
        with open(COLLECTION_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Name'):
                    collection_rows.append(row)
    except Exception as e:
        print(f"Error reading collection file: {e}", file=sys.stderr)
        input()
        return

    print(f"Parsed {len(collection_rows)} card entries from collection.")

    # 3. Filter out excluded cards and prepare list for resolving
    cards_to_resolve = []
    seen_names = set()
    
    for row in collection_rows:
        name = row['Name'].strip()
        name_lower = name.lower()
        
        # Skip if in input.txt exclusions
        if name_lower in excluded_names:
            continue
            
        # Skip if already added (prevents duplicate API lookups for duplicates in collection)
        if name_lower in seen_names:
            continue
            
        seen_names.add(name_lower)
        cards_to_resolve.append({
            'name': name,
            'set': row.get('Edition', '').strip(),
            'collector_number': row.get('Collector Number', '').strip()
        })
        
    print(f"After exclusions, {len(cards_to_resolve)} unique card(s) will be resolved.")

    # 4. Resolve details via core Scryfall API & caching system
    scryfall_core.resolve_cards(cards_to_resolve)

    # 5. Process and filter for Golgari-legal color identity
    golgari_cards = []
    unresolved_cards = []
    
    for card in cards_to_resolve:
        scryfall_data, cache_file = scryfall_core.load_from_cache(card)
        if not scryfall_data:
            unresolved_cards.append(card['name'])
            continue
            
        color_identity = scryfall_data.get('color_identity', [])
        if is_golgari_legal(color_identity):
            golgari_cards.append(scryfall_data['name'])

    # Sort results alphabetically for readability
    golgari_cards.sort()

    # 6. Write results to output.txt
    print(f"Writing {len(golgari_cards)} Golgari-legal cards to: {OUTPUT_FILE}...")
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for name in golgari_cards:
                f.write(f"{name}\n")
        print("Successfully generated output list.")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)

    if unresolved_cards:
        print("\n" + "!" * 50)
        print("WARNING: The following cards could not be resolved:")
        for name in unresolved_cards:
            print(f"  - {name}")

    print("\n" + "=" * 60)
    print("Press Enter to close this window...")
    input()

if __name__ == "__main__":
    main()
