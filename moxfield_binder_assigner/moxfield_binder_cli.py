import logging
import sys
import datetime
from pathlib import Path
from typing import Optional

from moxfield_binder_logic import assign_cards_to_binders, is_foil

# --- Configurations ---
SCRIPT_DIR = Path(__file__).parent
INPUTS_DIR = SCRIPT_DIR / "inputs"
LOGS_DIR = SCRIPT_DIR / "logs"

def get_default_path(filename: str) -> Optional[Path]:
    p = INPUTS_DIR / filename
    return p if p.is_file() else None

DEFAULT_INPUT = get_default_path("20260628_184333-regular-cards.csv")
DEFAULT_ALKOO = get_default_path("ALKOO_moxfield_haves_2026-06-28-1818Z.csv")
DEFAULT_PLEATHER = get_default_path("SmallPleather_moxfield_haves_2026-06-28-1818Z.csv")
OUTPUT_DIR = SCRIPT_DIR / "outputs"

def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"assigner_cli_{timestamp}.log"
    
    logger = logging.getLogger("BinderAssignerCLI")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

def prompt_file(description: str, default_path: Optional[Path]) -> Path:
    print(f"\nSelect {description}:")
    if default_path:
        print(f"Default: {default_path}")
        val = input("Enter path (or press Enter to use default): ").strip().strip('"').strip("'")
        if not val:
            return default_path
        return Path(val)
    else:
        while True:
            val = input("Enter path (no default available): ").strip().strip('"').strip("'")
            if val:
                return Path(val)
            print("Path cannot be empty. Please try again.")

def main():
    logger.info("=" * 60)
    logger.info("         MOXFIELD BINDER ASSIGNER CLI")
    logger.info("=" * 60)
    
    input_csv = prompt_file("Incoming Card List CSV", DEFAULT_INPUT)
    alkoo_csv = prompt_file("Existing ALKOO Case CSV", DEFAULT_ALKOO)
    pleather_csv = prompt_file("Existing Small Pleather CSV", DEFAULT_PLEATHER)
    
    logger.info("\nStarting classification...")
    try:
        counts, swaps, binders = assign_cards_to_binders(
            input_csv=input_csv,
            alkoo_inventory_csv=alkoo_csv,
            pleather_inventory_csv=pleather_csv,
            output_dir=OUTPUT_DIR,
            logger=logger
        )
        
        logger.info("\n" + "="*70)
        logger.info("      DETAILED BINDER CLASSIFICATION REPORT")
        logger.info("="*70)
        
        for binder, rows in binders.items():
            logger.info(f"\n📁 {binder} ({len(rows)} entry/entries):")
            if rows:
                ordered_keys = []
                tallied = {}
                for r in rows:
                    name = r.get("Name", "").strip()
                    edition = r.get("Edition", "").strip().upper()
                    cn = r.get("Collector Number", "").strip()
                    foil_str = "Foil" if is_foil(r) else "Non-Foil"
                    cond = r.get("Condition", "").strip()
                    qty = int(r.get("Count", "1") or 1)
                    
                    key = (name, edition, cn, foil_str, cond)
                    if key not in tallied:
                        ordered_keys.append(key)
                    tallied[key] = tallied.get(key, 0) + qty
                    
                for key in ordered_keys:
                    name, edition, cn, foil, cond = key
                    count = tallied[key]
                    details = f"{name} (Edition: {edition}, CN: {cn}, Foil: {foil}, Condition: {cond})"
                    qty_str = f" [{count}x]"
                    logger.info(f"   - {details}{qty_str}")
            else:
                logger.info("   (Empty)")
                
        logger.info("\n" + "="*70)
        logger.info("      SUMMARY TABLE")
        logger.info("="*70)
        for binder, count in counts.items():
            logger.info(f"  {binder.ljust(35)}: {count} card(s)")
        logger.info("="*70)
        
        if swaps:
            logger.info("\nSwap Recommendations:")
            for swap in swaps:
                logger.info(f"  - {swap}")
        else:
            logger.info("\nNo card swaps recommended.")
            
        logger.info(f"\nOutputs written to: {OUTPUT_DIR.resolve()}")
        
    except Exception as e:
        logger.error(f"Failed to execute binder assignment: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCancelled by user.")
        sys.exit(0)
