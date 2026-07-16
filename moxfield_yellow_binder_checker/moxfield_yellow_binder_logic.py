import csv
import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Adjust sys.path to import _core_tools
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

from _core_tools import scryfall_core
from _core_tools.sorting_logic import get_card_wubrg_sort_key

from _core_tools.yellow_binder_logic import (
    USD_TO_GBP,
    EUR_TO_GBP,
    parse_price,
    is_foil,
    get_card_prices,
    get_other_cache_prices,
    is_manipulated,
    meets_threshold,
)

def load_moxfield_csv(filepath: Path) -> List[Dict[str, str]]:
    """Loads a Moxfield CSV file, returning a list of rows."""
    rows = []
    if not filepath.exists():
        return rows
    with filepath.open(mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'Name' in row and row['Name'].strip():
                rows.append(row)
    return rows

def check_binders(
    yellow_path: Path,
    other_paths: List[Path],
    progress_callback=None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compares the yellow binder CSV with other binder CSVs.
    Returns:
        move_to_yellow: List of cards from other binders that should move.
        remove_from_yellow: List of cards in yellow binder that should be removed.
    """
    if progress_callback:
        progress_callback("Loading files...")

    yellow_rows = load_moxfield_csv(yellow_path)
    
    others_data: List[Tuple[Path, List[Dict[str, str]]]] = []
    for path in other_paths:
        others_data.append((path, load_moxfield_csv(path)))

    # Compile queries for scryfall resolving
    scryfall_queries = []
    
    # Yellow binder cards
    for row in yellow_rows:
        scryfall_queries.append({
            'name': row['Name'].strip(),
            'set': row.get('Edition', '').strip(),
            'collector_number': row.get('Collector Number', '').strip()
        })
        
    # Other binders cards
    for _, rows in others_data:
        for row in rows:
            scryfall_queries.append({
                'name': row['Name'].strip(),
                'set': row.get('Edition', '').strip(),
                'collector_number': row.get('Collector Number', '').strip()
            })

    # Deduplicate queries to optimize Scryfall requests
    unique_queries = {}
    for q in scryfall_queries:
        key = (q['name'].lower(), q['set'].lower(), q['collector_number'].lower())
        unique_queries[key] = q
    
    unique_queries_list = list(unique_queries.values())

    # Check cache to separate uncached cards
    uncached = []
    cached_count = 0
    for q in unique_queries_list:
        data, _ = scryfall_core.load_from_cache(q)
        if data:
            cached_count += 1
        else:
            uncached.append(q)

    if progress_callback:
        progress_callback(f"Cache status: {cached_count} card(s) found in cache, {len(uncached)} to fetch.")

    if uncached:
        BATCH_SIZE = 75
        total_batches = (len(uncached) - 1) // BATCH_SIZE + 1
        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i:i+BATCH_SIZE]
            current_batch_num = i // BATCH_SIZE + 1
            if progress_callback:
                progress_callback(f"Resolving Scryfall: batch {current_batch_num}/{total_batches} ({i}/{len(uncached)} cards)...")
            scryfall_core.fetch_cards_batch_from_scryfall(batch)

    if progress_callback:
        progress_callback("Analysing prices and processing yellow binder...")

    # Process yellow binder
    remove_from_yellow = []
    for row in yellow_rows:
        query = {
            'name': row['Name'].strip(),
            'set': row.get('Edition', '').strip(),
            'collector_number': row.get('Collector Number', '').strip()
        }
        scry_data, _ = scryfall_core.load_from_cache(query)
        if scry_data:
            usd, eur, gbp = get_card_prices(scry_data, is_foil(row))
        else:
            usd, eur, gbp = 0.0, 0.0, 0.0

        if usd <= 0.0 and eur <= 0.0:
            continue

        card_name = row['Name'].strip()
        if not meets_threshold(usd, eur, gbp, card_name):
            # No longer worth that much - keep original row info
            remove_from_yellow.append(row.copy())

    if progress_callback:
        progress_callback("Analysing prices and processing other binders...")

    # Process other binders
    move_to_yellow = []
    for path, rows in others_data:
        binder_name = path.stem
        for row in rows:
            query = {
                'name': row['Name'].strip(),
                'set': row.get('Edition', '').strip(),
                'collector_number': row.get('Collector Number', '').strip()
            }
            scry_data, _ = scryfall_core.load_from_cache(query)
            if scry_data:
                usd, eur, gbp = get_card_prices(scry_data, is_foil(row))
            else:
                usd, eur, gbp = 0.0, 0.0, 0.0

            if usd <= 0.0 and eur <= 0.0:
                continue

            if meets_threshold(usd, eur, gbp, row['Name'].strip()):
                new_row = row.copy()
                
                # Determine the converted pounds value that caused the card to be flagged
                usd_gbp = usd * USD_TO_GBP
                eur_gbp = eur * EUR_TO_GBP
                flagged_price = f"£{max(usd_gbp, eur_gbp):.2f}"
                    
                # Store the source binder in the tags field to keep moxfield CSV compliance
                tag_to_add = f"From {binder_name} ({flagged_price})"
                orig_tags = new_row.get('Tags', '')
                if orig_tags:
                    new_row['Tags'] = f"{orig_tags}, {tag_to_add}"
                else:
                    new_row['Tags'] = tag_to_add
                move_to_yellow.append(new_row)

    # Sort lists using the color ordering tool
    def sort_key(row):
        q = {
            'name': row['Name'].strip(),
            'set': row.get('Edition', '').strip(),
            'collector_number': row.get('Collector Number', '').strip()
        }
        data, _ = scryfall_core.load_from_cache(q)
        if data:
            return get_card_wubrg_sort_key(row['Name'].strip(), data.get('type_line', ''), data.get('color_identity', []))
        return (0, (5,), row['Name'].strip().lower().replace("-", ""))

    move_to_yellow = sorted(move_to_yellow, key=sort_key)
    remove_from_yellow = sorted(remove_from_yellow, key=sort_key)

    if progress_callback:
        progress_callback("Done processing.")

    return move_to_yellow, remove_from_yellow

def write_output_csv(filepath: Path, data: List[Dict[str, Any]], fieldnames: List[str] = None):
    """Writes the results to a CSV file matching standard Moxfield headers."""
    if fieldnames is None:
        fieldnames = [
            "Count", "Tradelist Count", "Name", "Edition", "Condition",
            "Language", "Foil", "Tags", "Last Modified", "Collector Number",
            "Alter", "Proxy", "Purchase Price"
        ]
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open(mode='w', encoding='utf-8', newline='') as f:
        # Filter data to only write keys that are in fieldnames
        clean_rows = []
        for r in data:
            clean_row = {}
            for field in fieldnames:
                clean_row[field] = r.get(field, "")
            clean_rows.append(clean_row)
            
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(clean_rows)
