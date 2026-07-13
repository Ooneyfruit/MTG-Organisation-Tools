import os
import sys
import logging
import datetime

# Add SCRIPT_DIR to path to allow importing local modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from moxfield_importer_logic import MoxfieldImporter, format_report_as_ascii

# --- FILE PATHS ---
INPUT_FILE = os.path.join(SCRIPT_DIR, "input.txt")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# --- GLOBAL LOGGER SETUP ---
def setup_logging():
    if not os.path.exists(LOG_DIR): 
        os.makedirs(LOG_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"import_cli_log_{timestamp}.log")
    
    logger = logging.getLogger("MoxfieldToolCli")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): 
        logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
    
    # Console stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)
    
    return logger, log_file

def format_table_to_ascii(headers, rows):
    if not rows:
        return "  No data resolved.\n"
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i in range(len(headers)):
            col_widths[i] = max(col_widths[i], len(str(row[i])))
            
    separator = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+\n"
    
    out = separator
    out += "| " + " | ".join(f"{str(h).ljust(col_widths[i])}" for i, h in enumerate(headers)) + " |\n"
    out += separator
    for row in rows:
        out += "| " + " | ".join(f"{str(row[i]).ljust(col_widths[i])}" for i in range(len(headers))) + " |\n"
    out += separator
    return out

def print_help_banner():
    print("="*80)
    print("      MOXFIELD UNIFIED IMPORT TOOL (CLI - Anti-Block & Smart Tokens)")
    print("="*80)
    print("OVERVIEW:")
    print("1. Enter strings separated by slashes '/'.")
    print("2. Normal input is treated as Tokens (with automatic deduplication).")
    print("3. Prepend '@' to treat a block as Regular Cards (Comma-separated).")
    print("4. Foils are automatically prioritised over Non-Foils in Tokens.")
    print("5. Distinct CSVs are generated in the /outputs folder.")
    print("-" * 80)
    print("TOKEN SYNTAX (Default Mode):")
    print("  7pip22        -> Double-Sided Same Set (TPIP #7 & #22)")
    print("  snc15ncc26    -> Double-Sided Diff Set")
    print("  dft14*d       -> Double-Sided Single Entry (e.g. DFC Token)")
    print("  one5 OR 5one  -> Single-Sided (Set+CN or CN+Set both work)")
    print("  !mh3          -> Use '!' to force a set code if it contains numbers.")
    print("                   (e.g., 21!mh327 will parse as TMH3 21 and 27).")
    print("-" * 80)
    print("TOKEN MODIFIERS & CONDITIONS:")
    print("  one5sp*f      -> 1x TONE #5 (Lightly Played, Foil)")
    print("  dft14*df3     -> 3x Double-Sided Single Entry (Foil)")
    print("-" * 80)
    print("REGULAR CARD SYNTAX (Starts with @):")
    print("  @sld7094,2452 -> SLD #7094 and SLD #2452 (Both Near Mint)")
    print("  @nem115sp,42f -> NEM #115 (Lightly Played) and NEM #42 (Foil)")
    print("="*80)

def main():
    logger, log_filename = setup_logging()
    print_help_banner()
    
    raw_input_strings = []
    if os.path.exists(INPUT_FILE):
        choice = input(f"Found '{INPUT_FILE}'. Use it? (Y/n): ").strip().lower()
        if choice != 'n':
            try:
                with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                    raw_input_text = f.read().strip()
                logger.info(f"Loaded import string from {INPUT_FILE}")
            except Exception as e:
                logger.error(f"Failed to read {INPUT_FILE}: {e}")
                print(f"Error reading {INPUT_FILE}: {e}")
                sys.exit(1)
    
    if not os.path.exists(INPUT_FILE) or choice == 'n':
        raw_input_text = input("\nInput string: ").strip()
        logger.info("Loaded manual console input string")
        
    if not raw_input_text:
        print("No input provided. Exiting.")
        sys.exit(0)
        
    logger.info("Initializing Moxfield Importer CLI session...")
    
    # CLI runs with scryfall API enabled, WUBRG sorting enabled, and dry_run=False by default
    importer = MoxfieldImporter(enable_lookup=True, enable_wubrg=True, dry_run=False, logger=logger)
    results = importer.run_import_session(raw_input_text)
    
    if results is None:
        print("No valid cards resolved. Exiting.")
        sys.exit(0)
        
    headers = ["Set", "CN", "Qty", "Name", "Type", "Foil", "Condition", "Note"]
    report = format_report_as_ascii(
        results_dict=results, 
        headers=headers, 
        append_table_callback=format_table_to_ascii,
        enable_wubrg=True
    )
    
    print("\n" + report)
    logger.info("CLI session completed successfully.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
