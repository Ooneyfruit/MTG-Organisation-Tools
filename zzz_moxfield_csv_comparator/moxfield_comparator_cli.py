import logging
import sys
from pathlib import Path
from typing import Tuple, Optional

# Add path/imports
from moxfield_comparator_logic import compare_csv_files

# --- Configuration ---
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("outputs")
OUTPUT_CSV = OUTPUT_DIR / "new_cards_to_import.csv"
OUTPUT_LOG = OUTPUT_DIR / "comparison_summary.txt"
RUNTIME_LOG = OUTPUT_DIR / "runtime.log"

def setup_logging() -> logging.Logger:
    """Configures runtime and output logging."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger("MTGComparatorCLI")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    
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
        user_input = user_input.strip('"').strip("'") 
        
        if not user_input:
            logger.warning("Input cannot be empty. Please try again.")
            continue
            
        path = Path(user_input)
        
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

def main():
    logger.info("Starting MTG CSV Comparator CLI Programme...")
    
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
    try:
        compare_csv_files(dest_file, input_file, OUTPUT_CSV, OUTPUT_LOG, logger)
    except Exception as e:
        logger.error(f"Failed comparison: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nProgramme terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
