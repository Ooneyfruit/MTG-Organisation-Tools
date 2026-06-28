import csv
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Optional

def load_destination_names(filepath: Path) -> set:
    """Loads card names from the destination CSV into a set."""
    names = set()
    with filepath.open(mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'Name' in row:
                names.add(row['Name'].strip().lower())
    return names

def is_foil(row: Dict) -> bool:
    """Helper to determine if a card row is foil."""
    raw_foil = row.get('Foil', '').strip().lower()
    return bool(raw_foil and raw_foil != 'false')

def compare_csv_files(
    dest_path: Path,
    input_path: Path,
    output_csv_path: Path,
    output_log_path: Path,
    logger: logging.Logger
) -> Tuple[int, int, int, List[Dict]]:
    """
    Compares the input CSV against the destination CSV.
    Writes outputs to output_csv_path and output_log_path.
    Returns (new_count, dest_dupes_count, internal_dupes_count, new_cards).
    """
    logger.info(f"Loading destination file: {dest_path.name}")
    destination_names = load_destination_names(dest_path)

    unique_input_cards: Dict[str, Dict] = {}
    fieldnames = []
    internal_duplicates = 0

    logger.info(f"Scanning and deduping input file: {input_path.name}")
    with input_path.open(mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames if reader.fieldnames else []
        
        for row in reader:
            if 'Name' not in row:
                continue
            
            card_name = row['Name'].strip()
            name_key = card_name.lower()
            
            # Check for duplicates *within* the input file itself
            if name_key in unique_input_cards:
                internal_duplicates += 1
                existing_card = unique_input_cards[name_key]
                
                # If the new one is foil and the saved one is not, overwrite it.
                if is_foil(row) and not is_foil(existing_card):
                    unique_input_cards[name_key] = row
            else:
                unique_input_cards[name_key] = row

    if internal_duplicates > 0:
        logger.info(f"Resolved {internal_duplicates} internal duplicate(s) in the input file (prioritising foils).")

    new_cards: List[Dict] = []
    duplicate_cards: List[Dict] = []
    
    for row in unique_input_cards.values():
        card_name = row['Name'].strip()
        if card_name.lower() in destination_names:
            duplicate_cards.append(row)
        else:
            new_cards.append(row)

    logger.info("--- Comparison Complete ---")
    logger.info(f"New unique cards found: {len(new_cards)}")
    logger.info(f"Duplicates in destination ignored: {len(duplicate_cards)}")
    if internal_duplicates > 0:
        logger.info(f"Internal input duplicates ignored: {internal_duplicates}")

    # Generate Output Summary File
    output_log_path.parent.mkdir(parents=True, exist_ok=True)
    with output_log_path.open(mode='w', encoding='utf-8') as f:
        f.write(f"--- MTG Comparison Summary ---\n")
        f.write(f"New Cards: {len(new_cards)} | Dest Duplicates: {len(duplicate_cards)} | Input Duplicates: {internal_duplicates}\n\n")
        
        f.write("--- NEW CARDS (Safe to move) ---\n")
        for card in new_cards:
            f.write(f"[{card.get('Count', '1')}x] {card.get('Name', 'Unknown')} ({card.get('Edition', 'N/A')})\n")
            
        f.write("\n--- DUPLICATE CARDS ---\n")
        for card in duplicate_cards:
            f.write(f"[-] {card.get('Name', 'Unknown')} matches an existing entry.\n")
            
    logger.info(f"A detailed text summary has been saved to '{output_log_path}'.")

    # Generate clean CSV for importing using Moxfield formatting (QUOTE_ALL)
    if new_cards and fieldnames:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        with output_csv_path.open(mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(new_cards)
        logger.info(f"Success: '{output_csv_path}' has been created and is ready for Moxfield import.")
    
    return len(new_cards), len(duplicate_cards), internal_duplicates, new_cards
