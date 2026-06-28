import os
import re
import sys

# Add core_tools directory to sys.path to resolve scryfall_core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core_tools")))
import scryfall_core

# --- CONFIGURATION ---
INPUT_FILE = "input.txt"

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
    # Supports parenthesis in names by matching the last parenthesis block
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
        
    # 4. Fallback: Just Name (Implicit Quantity of 1)
    return {
        'quantity': 1,
        'name': line,
        'set': None,
        'collector_number': None,
        'foil': foil,
        'raw': line
    }

def format_color_identity(ci_list):
    wubrg_order = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
    valid_colors = [c.upper() for c in ci_list if c.upper() in wubrg_order]
    sorted_colors = sorted(valid_colors, key=lambda c: wubrg_order[c])
    if not sorted_colors:
        return "Colorless"
    return "".join(sorted_colors)

def main():
    print("=" * 60)
    print("                MTG CARD COLOR IDENTITY COUNTER")
    print("=" * 60)
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file '{INPUT_FILE}' not found in the current directory.")
        print("Please create the file and add your cards list (one per line).")
        input()
        return

    print(f"Reading cards from: {INPUT_FILE}...")
    cards = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parsed = parse_line(line)
            if parsed:
                cards.append(parsed)
                
    if not cards:
        print("No cards found in input file.")
        input()
        return
        
    print(f"Parsed {len(cards)} entries. Resolving cards (cache & API)...")
    scryfall_core.resolve_cards(cards)
            
    # Second Pass: Load all resolved card details from cache and aggregate counts
    tally_1 = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0}
    tally_2 = {}
    colorless_count_tally_1 = 0
    
    unresolved_cards = []
    
    for i, card in enumerate(cards, 1):
        name = card['name']
        qty = card['quantity']
        
        scryfall_data, cache_file = scryfall_core.load_from_cache(card)
        if not scryfall_data:
            print(f"!! Error: Could not resolve card details for '{name}'")
            unresolved_cards.append(card)
            continue
            
        color_identity = scryfall_data.get('color_identity', [])
        
        # Tally 1: Ignore multicolour, just +qty for each constituent identity
        if not color_identity:
            colorless_count_tally_1 += qty
        else:
            for color in color_identity:
                c_upper = color.upper()
                if c_upper in tally_1:
                    tally_1[c_upper] += qty
                    
        # Tally 2: Group by exact color identity combo
        identity_key = format_color_identity(color_identity)
        tally_2[identity_key] = tally_2.get(identity_key, 0) + qty

    # --- PRINT RESULTS ---
    print("\n" + "=" * 60)
    print("                           RESULTS")
    print("=" * 60)
    
    # 1. Result Tally 1
    print("\n1. Constituent Color Identity Counts (Ignoring Multicolour Groupings):")
    print("-" * 50)
    print(f"  White (W): {tally_1['W']}")
    print(f"  Blue (U) : {tally_1['U']}")
    print(f"  Black (B): {tally_1['B']}")
    print(f"  Red (R)  : {tally_1['R']}")
    print(f"  Green (G): {tally_1['G']}")
    print(f"  (Colorless cards: {colorless_count_tally_1})")
    
    # 2. Result Tally 2
    print("\n2. Distinct Color Identity Groupings:")
    print("-" * 50)
    def sorting_key(item):
        key = item[0]
        if key == "Colorless":
            return (0, "")
        return (len(key), key)
        
    sorted_tally_2 = sorted(tally_2.items(), key=sorting_key)
    for group, count in sorted_tally_2:
        print(f"  {group:<15} : {count}")
        
    if unresolved_cards:
        print("\n" + "!" * 50)
        print("WARNING: The following cards could not be resolved:")
        for card in unresolved_cards:
            print(f"  - {card['quantity']}x {card['name']} (raw: '{card['raw']}')")
            
    print("\n" + "=" * 60)
    print("Press Enter to close this window...")
    input()

if __name__ == "__main__":
    main()
