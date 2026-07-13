import csv
import datetime
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Adjust sys.path to import _core_tools
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

from _core_tools import scryfall_core
from _core_tools.sorting_logic import get_card_wubrg_sort_key

# --- Set Codes for ALKOO Case ---
DEFAULT_ALKOO_SETS = {
    "DFT", "TLA", "DSK", "EOE", "FDN", "J25",
    "ECL", "SPM", "MH3", "ONE", "SOS", "TDM", "MSH"
}

def load_alkoo_sets(file_path: Optional[Path] = None, fallback_to_base: bool = True) -> Set[str]:
    """
    Loads ALKOO set codes from a file.
    If the specified file_path doesn't exist, we load from alkoo_base.txt and initialize the file_path with it.
    """
    if file_path is None:
        file_path = SCRIPT_DIR / "alkoo.txt"
    
    if file_path.is_file():
        try:
            with file_path.open('r', encoding='utf-8') as f:
                content = f.read()
            sets = set()
            for token in content.replace(',', ' ').split():
                token_clean = token.strip().upper()
                if token_clean:
                    sets.add(token_clean)
            return sets
        except Exception:
            pass

    # If active file doesn't exist, try alkoo_base.txt
    base_path = SCRIPT_DIR / "alkoo_base.txt"
    base_sets = set()
    if fallback_to_base and base_path.is_file():
        try:
            with base_path.open('r', encoding='utf-8') as f:
                content = f.read()
            for token in content.replace(',', ' ').split():
                token_clean = token.strip().upper()
                if token_clean:
                    base_sets.add(token_clean)
        except Exception:
            pass

    if not base_sets:
        base_sets = set(DEFAULT_ALKOO_SETS)

    # Initialize alkoo.txt with the base set
    try:
        write_alkoo_sets(base_sets, file_path)
    except Exception:
        pass

    return base_sets

def write_alkoo_sets(sets: Set[str], file_path: Optional[Path] = None):
    """Writes the set codes (one per line) to the specified file."""
    if file_path is None:
        file_path = SCRIPT_DIR / "alkoo.txt"
    sorted_sets = sorted(list(sets))
    with file_path.open('w', encoding='utf-8') as f:
        f.write("\n".join(sorted_sets) + "\n")

# Default ALKOO_SETS is loaded from the files
ALKOO_SETS = load_alkoo_sets()


def is_foil(row: Dict) -> bool:
    """Returns True if the card row is a foil or etched version."""
    raw = row.get('Foil', '').strip().lower()
    return bool(raw and raw != 'false')

def parse_price(val) -> float:
    """Safely converts price strings to floats."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace('$', '').replace('€', '').strip())
    except ValueError:
        return 0.0

def is_basic_land(type_line: str) -> bool:
    """Checks if the card is a basic land."""
    t_lower = type_line.lower()
    return "basic" in t_lower and "land" in t_lower

def load_existing_inventory(csv_path: Path) -> Dict[str, Dict[str, bool]]:
    """
    Loads cards from an existing collection CSV to track presence of foils vs non-foils.
    Returns dict: {card_name.lower(): {"has_foil": bool, "has_non_foil": bool}}
    """
    inventory = {}
    if not csv_path or not csv_path.exists():
        return inventory

    with csv_path.open(mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'Name' not in row:
                continue
            name_key = row['Name'].strip().lower()
            foil_status = is_foil(row)
            
            if name_key not in inventory:
                inventory[name_key] = {"has_foil": False, "has_non_foil": False}
                
            if foil_status:
                inventory[name_key]["has_foil"] = True
            else:
                inventory[name_key]["has_non_foil"] = True
    return inventory

def assign_cards_to_binders(
    input_csv: Path,
    alkoo_inventory_csv: Path,
    pleather_inventory_csv: Path,
    output_dir: Path,
    logger: logging.Logger,
    alkoo_sets: Optional[Set[str]] = None
) -> Tuple[Dict[str, int], List[str], Dict[str, List[str]]]:
    """
    Categorizes the incoming CSV card list into 6 binders based on the rule flow.
    Returns: (counts_dict, swap_action_strings, card_names_per_binder_dict)
    """
    if alkoo_sets is None:
        alkoo_sets = load_alkoo_sets()

    logger.info("Loading existing collection inventories...")
    alkoo_inv = load_existing_inventory(alkoo_inventory_csv)
    pleather_inv = load_existing_inventory(pleather_inventory_csv)
    
    logger.info(f"Loaded {len(alkoo_inv)} card entries from ALKOO Case.")
    logger.info(f"Loaded {len(pleather_inv)} card entries from Small Pleather.")

    # Read incoming card file
    incoming_rows: List[Dict] = []
    fieldnames: List[str] = []
    
    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")
        
    with input_csv.open(mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames if reader.fieldnames else []
        for row in reader:
            if 'Name' in row and row['Name'].strip():
                qty = int(row.get("Count", "1") or 1)
                for _ in range(qty):
                    new_row = row.copy()
                    new_row["Count"] = "1"
                    incoming_rows.append(new_row)

    logger.info(f"Read {len(incoming_rows)} rows from incoming CSV.")

    # --- Internal Input Deduplication ---
    logger.info("Detecting duplicates within incoming cards list...")
    grouped_incoming: Dict[str, List[Dict]] = {}
    for row in incoming_rows:
        name_key = row["Name"].strip().lower()
        grouped_incoming.setdefault(name_key, []).append(row)

    best_incoming: List[Dict] = []
    internal_duplicates: List[Dict] = []

    for name_key, rows in grouped_incoming.items():
        # Sort so foil is first (prioritizing foil)
        sorted_rows = sorted(rows, key=lambda r: is_foil(r), reverse=True)
        best_row = sorted_rows[0]
        best_incoming.append(best_row)
        
        # Remaining entries for the same card name are duplicates
        for extra_row in sorted_rows[1:]:
            internal_duplicates.append(extra_row)
            logger.info(
                f"[Internal Duplicate] '{extra_row['Name']}' (Foil: {is_foil(extra_row)}) "
                f"routed directly to Duplicates/Unwanted (Best version '{best_row['Name']}' Foil: {is_foil(best_row)} retained)"
            )

    logger.info(f"Selected {len(best_incoming)} unique best card(s). Identified {len(internal_duplicates)} duplicate(s) within the input.")

    # Resolve details against Scryfall cache/API in batch
    scryfall_queries = []
    for row in best_incoming:
        scryfall_queries.append({
            "name": row.get("Name", "").strip(),
            "set": row.get("Edition", "").strip(),
            "collector_number": row.get("Collector Number", "").strip()
        })
        
    logger.info("Resolving card details (prices, type_line, full_art) against Scryfall...")
    scryfall_core.resolve_cards(scryfall_queries)

    # Binder Categories lists
    binders: Dict[str, List[Dict]] = {
        "Binder - Yellow": [],
        "Binder - ALKOO Case": [],
        "Binder - Basics": [],
        "Binder - Fancy Basics": [],
        "ABinder - Small Pleather": [],
        "Binder - Duplicates and Unwanted": []
    }
    
    # Send internal duplicates directly to Duplicates/Unwanted
    binders["Binder - Duplicates and Unwanted"].extend(internal_duplicates)
    
    swap_notes: List[str] = []

    for row in best_incoming:
        name = row["Name"].strip()
        name_key = name.lower()
        set_code = row.get("Edition", "").strip().upper()
        card_is_foil = is_foil(row)

        # Lookup Scryfall Data from Cache
        query_card = {
            "name": name,
            "set": row.get("Edition", "").strip(),
            "collector_number": row.get("Collector Number", "").strip()
        }
        scry_data, _ = scryfall_core.load_from_cache(query_card)
        if not scry_data:
            scry_data = {
                "name": name,
                "type_line": "",
                "prices": {},
                "full_art": False
            }

        type_line = scry_data.get("type_line", "")
        full_art = scry_data.get("full_art", False)
        prices = scry_data.get("prices", {})
        
        usd = parse_price(prices.get("usd"))
        eur = parse_price(prices.get("eur"))
        card_is_basic = is_basic_land(type_line)

        # Rule 1: Worth > $1.00 USD and/or > €1.00 EUR (except basic lands). Ignores dupes.
        if (usd > 1.0 or eur > 1.0) and not card_is_basic:
            binders["Binder - Yellow"].append(row)
            logger.info(f"[Rule 1] Assigned '{name}' to Yellow Binder (Valued: ${usd:.2f} USD / €{eur:.2f} EUR)")
            continue

        # Rule 2: Non-land in ALKOO Set Codes
        card_is_land = "land" in type_line.lower()
        if not card_is_land and set_code in alkoo_sets:
            if name_key in alkoo_inv:
                has_foil_existing = alkoo_inv[name_key]["has_foil"]
                if not has_foil_existing and card_is_foil:
                    binders["Binder - ALKOO Case"].append(row)
                    swap_notes.append(f"ALKOO Case: Swap out non-foil '{name}' with incoming foil")
                    logger.info(f"[Rule 2] Assigned '{name}' to ALKOO Case as Foil Upgrade (Set: {set_code})")
                else:
                    binders["Binder - Duplicates and Unwanted"].append(row)
                    logger.info(f"[Rule 2] Routed '{name}' to Duplicates and Unwanted (Already exists in ALKOO Case)")
            else:
                binders["Binder - ALKOO Case"].append(row)
                logger.info(f"[Rule 2] Assigned '{name}' to ALKOO Case (New card, Set: {set_code})")
            continue

        # Rule 3: Basic Land
        if card_is_basic:
            # 3.1 does it have full_art = False and is it non-foil?
            if (not full_art) and (not card_is_foil):
                binders["Binder - Basics"].append(row)
                logger.info(f"[Rule 3] Assigned '{name}' to Basics Binder (Standard Non-foil)")
            else:
                binders["Binder - Fancy Basics"].append(row)
                logger.info(f"[Rule 3] Assigned '{name}' to Fancy Basics Binder (Foil/Full-Art: {full_art})")
            continue

        # Rule 4: Small Pleather check
        if name_key in pleather_inv:
            has_foil_existing = pleather_inv[name_key]["has_foil"]
            if not has_foil_existing and card_is_foil:
                binders["ABinder - Small Pleather"].append(row)
                swap_notes.append(f"Small Pleather: Swap out non-foil '{name}' with incoming foil")
                logger.info(f"[Rule 4] Assigned '{name}' to Small Pleather as Foil Upgrade")
            else:
                binders["Binder - Duplicates and Unwanted"].append(row)
                logger.info(f"[Rule 4] Routed '{name}' to Duplicates and Unwanted (Already exists in Small Pleather)")
        else:
            binders["ABinder - Small Pleather"].append(row)
            logger.info(f"[Rule 4] Assigned '{name}' to Small Pleather (New card)")

    # Sort card_rows in place using WUBRG sorting rules before exporting
    for binder_name, card_rows in binders.items():
        def sort_key_fn(row):
            name = row.get("Name", "").strip()
            query_card = {
                "name": name,
                "set": row.get("Edition", "").strip(),
                "collector_number": row.get("Collector Number", "").strip()
            }
            scry_data, _ = scryfall_core.load_from_cache(query_card)
            if scry_data:
                type_line = scry_data.get("type_line", "")
                color_identity = scry_data.get("color_identity", [])
            else:
                type_line = ""
                color_identity = []
            return get_card_wubrg_sort_key(name, type_line, color_identity)
            
        card_rows.sort(key=sort_key_fn)

    # Generate timestamp for output files
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write files
    output_dir.mkdir(exist_ok=True, parents=True)
    counts = {}
    
    for binder_name, card_rows in binders.items():
        counts[binder_name] = len(card_rows)
        
        # Convert folder name to safe filename
        safe_fn = f"{timestamp}_{binder_name.replace(' - ', '_').replace(' ', '_').lower()}.csv"
        out_path = output_dir / safe_fn
        
        with out_path.open(mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(card_rows)
            
    # Write Swap recommendations
    swap_file = output_dir / f"{timestamp}_swap_recommendations.txt"
    with swap_file.open(mode='w', encoding='utf-8') as f:
        f.write("--- MTG Physical Card Swap Recommendations ---\n")
        f.write(f"Generated at: {timestamp}\n\n")
        if swap_notes:
            for note in swap_notes:
                f.write(f"- {note}\n")
        else:
            f.write("No physical card swaps recommended.\n")

    return counts, swap_notes, binders
