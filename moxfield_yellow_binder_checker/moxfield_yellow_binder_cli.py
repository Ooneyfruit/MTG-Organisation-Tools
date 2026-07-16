import argparse
import sys
import logging
from pathlib import Path

# Adjust sys.path to import logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

import moxfield_yellow_binder_logic as logic

# Setup logging
logger = logging.getLogger("YellowBinderCLI")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(ch)

def main():
    parser = argparse.ArgumentParser(
        description="Moxfield Yellow Binder Checker. Evaluates card values and recommends movements."
    )
    parser.add_argument(
        "--yellow",
        required=True,
        help="Path to the yellow binder CSV file."
    )
    parser.add_argument(
        "--others",
        nargs="+",
        required=True,
        help="One or more paths to other binder CSV files to check."
    )
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR / "outputs"),
        help="Directory to save output CSV lists."
    )

    args = parser.parse_args()
    
    yellow_path = Path(args.yellow)
    other_paths = [Path(p) for p in args.others]
    output_dir = Path(args.output_dir)

    if not yellow_path.is_file():
        logger.error(f"Yellow binder file not found: {yellow_path}")
        sys.exit(1)

    valid_others = []
    for p in other_paths:
        if p.is_file():
            valid_others.append(p)
        else:
            logger.warning(f"Other binder file not found, skipping: {p}")

    if not valid_others:
        logger.error("No valid other binder CSV files were provided.")
        sys.exit(1)

    logger.info("Starting Yellow Binder Checker analysis...")
    logger.info("NOTE: Threshold is strictly >= 1.00 GBP when converted from USD (x0.77) or EUR (x0.85). Cards with large USD/EUR discrepancies (diff >= 1.30, low < 0.70 for USD-high or < 0.55 for EUR-high) are checked against other cached printings; if unsupported, they are flagged as manipulated & ignored.")
    
    def log_progress(msg: str):
        logger.info(msg)

    move_to_yellow, remove_from_yellow = logic.check_binders(
        yellow_path,
        valid_others,
        progress_callback=log_progress
    )

    # Output paths
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    move_csv_path = output_dir / f"{timestamp}_move_to_yellow.csv"
    remove_csv_path = output_dir / f"{timestamp}_remove_from_yellow.csv"

    logger.info(f"Writing move list to: {move_csv_path}")
    logic.write_output_csv(move_csv_path, move_to_yellow)

    logger.info(f"Writing remove list to: {remove_csv_path}")
    logic.write_output_csv(remove_csv_path, remove_from_yellow)

    logger.info(f"Analysis complete. Found {len(move_to_yellow)} cards to move to yellow binder, and {len(remove_from_yellow)} to remove.")

if __name__ == "__main__":
    main()
