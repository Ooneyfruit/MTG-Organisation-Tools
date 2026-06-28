import csv
import logging
import sys
from pathlib import Path
from typing import Tuple, List, Dict, Optional

# --- Configuration ---
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("outputs")

# Route all outputs to the /outputs/ directory
OUTPUT_CSV = OUTPUT_DIR / "new_cards_to_import.csv"
OUTPUT_LOG = OUTPUT_DIR / "comparison_summary.txt"
RUNTIME_LOG = OUTPUT_DIR / "runtime.log"

def setup_logging() -> logging.Logger:
    """Configures runtime and output logging."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger("MTGComparator")
    logger.setLevel(logging.INFO)
    
    # File handler for runtime debugging/logs
    fh = logging.FileHandler(RUNTIME_LOG, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Stream handler for console output
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(message)s'))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

def get_most_recent_files() -> Tuple[Optional[Path], Optional[Path]]:
    """Finds the two most recent CSVs in the input directory based on file metadata."""
    if not INPUT_DIR.exists():
        INPUT_DIR.mkdir(exist_ok=True)
        logger.warning(f"Created missing '{INPUT_DIR}' directory.")
        return None, None

    csv_files = list(INPUT_DIR.glob("*.csv"))
    
    if len(csv_files) < 2:
        return None, None

    # Sort descending (newest first) using the OS file creation metadata (st_ctime)
    sorted_files = sorted(csv_files, key=lambda p: p.stat().st_ctime, reverse=True)
    
    # The absolute newest is the input (awaiting cards), the second newest is the destination
    input_file = sorted_files[0]
    destination_file = sorted_files[1]
    
    return destination_file, input_file

def prompt_for_file(file_type: str) -> Path:
    """Prompts the user for a valid file path, defaulting to /input/ if only a name is given."""
    while True:
        user_input = input(f"Please provide the path or filename for the {file_type} CSV: ").strip()
        # Remove quotes if copied directly from Windows Explorer
        user_input = user_input.strip('"').strip("'") 
        
        if not user_input:
            logger.warning("Input cannot be empty. Please try again.")
            continue
            
        path = Path(user_input)
        
        # If it's just a filename without directories, assume it's in the input folder
        if len(path.parts) == 1:
            path = INPUT_DIR / path
            
        if path.is_file():
            return path
        else:
            logger.warning(f"File not found: '{path}'. Ensure the file exists and try again.")

def get_user_confirmation(dest: Path, inp: Path) -> Tuple[Path, Path]:
    """Asks the user to confirm default files, swap them, or provide custom ones."""
    while True:
        logger.info(f"\nCurrent File Selection:")
        logger.info(f"  Destination (Base Collection): {dest.name}")
        logger.info(f"  Input (Awaiting/New Cards):    {inp.name}")
        
        choice = input("\nWould you like to use these files? [Y/n/s (swap)]: ").strip().lower()
        
        if choice in ["", "y", "yes"]:
            return dest, inp
        elif choice in ["s", "swap"]:
            logger.info("\nSwapping files...")
            dest, inp = inp, dest
        elif choice in ["n", "no"]:
            logger.info("\nManual override selected.")
            custom_dest = prompt_for_file("Destination (Base Collection)")
            custom_inp = prompt_for_file("Input (Awaiting/New Cards)")
            return custom_dest, custom_inp
        else:
            logger.warning("Invalid input. Please type 'y', 'n', or 's'.")

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
    # Moxfield usually leaves non-foils empty, or says 'false'. Foils say 'foil' or 'etched'.
    raw_foil = row.get('Foil', '').strip().lower()
    return bool(raw_foil and raw_foil != 'false')

def compare_csvs(dest_path: Path, input_path: Path):
    """Compares the input CSV against the destination CSV and logs the behaviour."""
    logger.info(f"\nStarting comparison...")
    logger.info(f"Loading destination file: {dest_path.name}")
    
    try:
        destination_names = load_destination_names(dest_path)
    except Exception as e:
        logger.error(f"Failed to read destination file: {e}", exc_info=True)
        return

    unique_input_cards: Dict[str, Dict] = {}
    fieldnames = []
    internal_duplicates = 0

    logger.info(f"Scanning and deduping input file: {input_path.name}")
    try:
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
                    
    except Exception as e:
        logger.error(f"Failed to read input file: {e}", exc_info=True)
        return

    if internal_duplicates > 0:
        logger.info(f"Resolved {internal_duplicates} internal duplicate(s) in the input file (prioritising foils).")

    # Now compare the cleaned input against the destination collection
    new_cards: List[Dict] = []
    duplicate_cards: List[Dict] = []
    
    for row in unique_input_cards.values():
        card_name = row['Name'].strip()
        if card_name.lower() in destination_names:
            duplicate_cards.append(row)
        else:
            new_cards.append(row)

    write_outputs(new_cards, duplicate_cards, fieldnames, internal_duplicates)

def write_outputs(new_cards: List[Dict], duplicate_cards: List[Dict], fieldnames: List[str], internal_dupes: int):
    """Handles generating the output logs and the final CSV in the outputs folder."""
    logger.info("\n--- Comparison Complete ---")
    logger.info(f"New unique cards found: {len(new_cards)}")
    logger.info(f"Duplicates in destination ignored: {len(duplicate_cards)}")
    if internal_dupes > 0:
        logger.info(f"Internal input duplicates ignored: {internal_dupes}")
    logger.info("")

    # Generate Output Summary File
    with OUTPUT_LOG.open(mode='w', encoding='utf-8') as f:
        f.write(f"--- MTG Comparison Summary ---\n")
        f.write(f"New Cards: {len(new_cards)} | Dest Duplicates: {len(duplicate_cards)} | Input Duplicates: {internal_dupes}\n\n")
        
        f.write("--- NEW CARDS (Safe to move) ---\n")
        for card in new_cards:
            f.write(f"[{card.get('Count', '1')}x] {card.get('Name', 'Unknown')} ({card.get('Edition', 'N/A')})\n")
            
        f.write("\n--- DUPLICATE CARDS ---\n")
        for card in duplicate_cards:
            f.write(f"[-] {card.get('Name', 'Unknown')} matches an existing entry.\n")
            
    logger.info(f"A detailed text summary has been saved to '{OUTPUT_LOG}'.")

    # Generate clean CSV for importing using Moxfield formatting (QUOTE_ALL)
    if new_cards and fieldnames:
        try:
            with OUTPUT_CSV.open(mode='w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(new_cards)
            logger.info(f"Success: '{OUTPUT_CSV}' has been created and is ready for Moxfield import.")
        except Exception as e:
            logger.error(f"Failed to write new cards CSV: {e}", exc_info=True)

def main():
    logger.info("Starting MTG CSV Comparator Programme...")
    
    # 1. Attempt to find default files
    dest_file, input_file = get_most_recent_files()
    
    if dest_file and input_file:
        # 2. Prompt user using found defaults, allowing them to swap or manually override
        dest_file, input_file = get_user_confirmation(dest_file, input_file)
    else:
        logger.info("\nCould not find two CSV files in the 'input' folder. Proceeding to manual entry.")
        dest_file = prompt_for_file("Destination (Base Collection)")
        input_file = prompt_for_file("Input (Awaiting/New Cards)")
        
    # 3. Execute core logic
    compare_csvs(dest_file, input_file)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nProgramme terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)