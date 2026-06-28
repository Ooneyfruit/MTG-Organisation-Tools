import requests
import csv
import sys
import datetime
import os
import json

# Configuration
CACHE_DIR = "scryfall_cache"

def load_set_data(set_code):
    """
    Logic:
    1. Check if {set_code}.json exists in CACHE_DIR.
    2. If yes, load and return it.
    3. If no, fetch from Scryfall, save to disk, then return.
    """
    
    # Ensure cache directory exists
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        
    cache_file = os.path.join(CACHE_DIR, f"{set_code}.json")
    
    # 1. Try loading from cache
    if os.path.exists(cache_file):
        print(f"--> Found cached data for '{set_code}'. Loading from file...", file=sys.stderr)
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("--> Cache file corrupted. Re-downloading...", file=sys.stderr)

    # 2. Fetch from API if not cached
    print(f"--> downloading data for set '{set_code}' from Scryfall...", file=sys.stderr)
    
    url = f"https://api.scryfall.com/cards/search?q=set:{set_code}&unique=prints&page=1"
    card_map = {}
    has_more = True
    
    while has_more:
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            for card in data.get('data', []):
                cn = card.get('collector_number')
                name = card.get('name')
                card_map[cn] = name
            
            has_more = data.get('has_more', False)
            url = data.get('next_page')
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}", file=sys.stderr)
            sys.exit(1)

    # 3. Save to cache
    print(f"--> Saving {len(card_map)} cards to {cache_file}...", file=sys.stderr)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(card_map, f, ensure_ascii=False, indent=2)
        
    return card_map

def main():
    # 1. Ask for Set Code
    set_code = input("Enter the Set Code (e.g., 'lea', 'mh2'): ").strip().lower()
    
    # 2. Load data (Cache or API)
    card_map = load_set_data(set_code)
    
    # 3. Ask for the Collector Number string
    print("\nEnter collector numbers separated by slashes (e.g., 111/222/333/444f/555).")
    input_str = input("Input: ").strip()
    
    raw_entries = input_str.split('/')
    
    # 4. Generate Filename with Timestamp
    # Format: moxfield_import_mh2_20231027_153000.csv
    file_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"moxfield_import_{set_code}_{file_timestamp}.csv"
    
    missing_cards = []
    processed_count = 0
    
    try:
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Force quoting to match Moxfield's style exactly
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            
            # Headers
            headers = [
                "Count", "Tradelist Count", "Name", "Edition", "Condition", 
                "Language", "Foil", "Tags", "Last Modified", "Collector Number", 
                "Alter", "Proxy", "Purchase Price"
            ]
            writer.writerow(headers)
            
            for entry in raw_entries:
                entry = entry.strip()
                if not entry:
                    continue
                    
                is_foil = False
                collector_number = entry
                
                # Check for foil flag
                if entry.lower().endswith('f'):
                    is_foil = True
                    collector_number = entry[:-1]
                    
                # Lookup Name
                card_name = card_map.get(collector_number)
                
                if not card_name:
                    missing_cards.append(entry)
                    print(f"Warning: Card #{collector_number} not found in set {set_code}")
                    continue
                    
                # Calculate Fields for CSV content
                row_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                foil_val = "foil" if is_foil else ""
                
                writer.writerow([
                    "1",                # Count
                    "1",                # Tradelist Count
                    card_name,          # Name
                    set_code,           # Edition
                    "Near Mint",        # Condition
                    "English",          # Language
                    foil_val,           # Foil
                    "",                 # Tags
                    row_time,           # Last Modified
                    collector_number,   # Collector Number
                    "False",            # Alter
                    "False",            # Proxy
                    ""                  # Purchase Price
                ])
                processed_count += 1
                
        print(f"\nSUCCESS! Generated '{output_filename}' with {processed_count} cards.")
        
        if missing_cards:
            print(f"Skipped {len(missing_cards)} items (names not found): {missing_cards}")

    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    main()
