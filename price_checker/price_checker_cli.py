import os
import sys
import csv
import logging
import datetime
from pathlib import Path

# Set up sys.path to import _core_tools
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from _core_tools import scryfall_core
except ImportError as e:
    print(f"Error: Failed to import scryfall_core. Make sure _core_tools is in the parent directory. Detail: {e}")
    sys.exit(1)

# Configuration
OUTPUT_DIR = ROOT_DIR / "price_checker" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUTPUT_DIR / "price_checker.log"

# Setup Logging
logger = logging.getLogger("PriceCheckerCLI")
logger.setLevel(logging.INFO)

# Clear existing handlers
if logger.hasHandlers():
    logger.handlers.clear()

# File handler
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(ch)

def parse_price(val) -> float:
    """Safely converts price strings or None to floats."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace('$', '').replace('€', '').strip())
    except ValueError:
        return 0.0

def is_foil(row: dict) -> bool:
    """Returns True if the card row is a foil or etched version."""
    raw = row.get('Foil', '').strip().lower()
    return bool(raw and raw != 'false')

def check_prices(csv_path: Path):
    if not csv_path.exists():
        logger.error(f"Input file not found at: {csv_path}")
        return

    logger.info(f"Loading cards from CSV: {csv_path}")
    cards = []
    
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            name = row.get('Name', '').strip()
            edition = row.get('Edition', '').strip()
            collector_num = row.get('Collector Number', '').strip()
            count_str = row.get('Count', '1').strip()
            
            try:
                count = int(count_str) if count_str else 1
            except ValueError:
                count = 1

            if not name:
                logger.warning(f"Row {idx + 2} has missing Card Name, skipping.")
                continue

            cards.append({
                'name': name,
                'set': edition,
                'collector_number': collector_num,
                'foil': is_foil(row),
                'count': count,
                'original_row': row
            })

    if not cards:
        logger.warning("No valid cards found in the CSV.")
        return

    logger.info(f"Found {len(cards)} card entries. Resolving metadata from Scryfall cache/API...")
    
    # Batch query resolving
    scryfall_queries = []
    for card in cards:
        scryfall_queries.append({
            'name': card['name'],
            'set': card['set'],
            'collector_number': card['collector_number']
        })
        
    scryfall_core.resolve_cards(scryfall_queries)
    logger.info("Metadata resolution completed. Extracting prices...")

    processed_cards = []
    total_count = 0
    grand_total_usd = 0.0
    grand_total_eur = 0.0

    for card in cards:
        query = {
            'name': card['name'],
            'set': card['set'],
            'collector_number': card['collector_number']
        }
        scry_data, _ = scryfall_core.load_from_cache(query)
        
        usd_unit = 0.0
        eur_unit = 0.0
        
        if scry_data:
            prices = scry_data.get('prices', {})
            if card['foil']:
                usd_unit = parse_price(prices.get('usd_foil'))
                if usd_unit == 0.0:
                    usd_unit = parse_price(prices.get('usd'))
                
                eur_unit = parse_price(prices.get('eur_foil'))
                if eur_unit == 0.0:
                    eur_unit = parse_price(prices.get('eur'))
            else:
                usd_unit = parse_price(prices.get('usd'))
                if usd_unit == 0.0:
                    usd_unit = parse_price(prices.get('usd_foil'))
                
                eur_unit = parse_price(prices.get('eur'))
                if eur_unit == 0.0:
                    eur_unit = parse_price(prices.get('eur_foil'))
        else:
            logger.warning(f"Metadata not found for card: {card['name']} ({card['set']})")

        total_usd = usd_unit * card['count']
        total_eur = eur_unit * card['count']

        processed_cards.append({
            'name': card['name'],
            'set': card['set'],
            'collector_number': card['collector_number'],
            'foil': card['foil'],
            'count': card['count'],
            'usd_unit': usd_unit,
            'eur_unit': eur_unit,
            'usd_total': total_usd,
            'eur_total': total_eur,
            'original_row': card['original_row']
        })

        total_count += card['count']
        grand_total_usd += total_usd
        grand_total_eur += total_eur

    # Sort in price order (USD total price descending, then name)
    processed_cards.sort(key=lambda x: (-x['usd_total'], x['name'].lower()))

    # Print Table
    logger.info("\n" + "="*95)
    logger.info(f"{'Card Name':<35} | {'Set':<6} | {'CN':<5} | {'Foil':<4} | {'Qty':<3} | {'Unit USD':<8} | {'Total USD':<9} | {'Unit EUR':<8} | {'Total EUR':<9}")
    logger.info("="*95)
    for c in processed_cards:
        foil_str = "Yes" if c['foil'] else "No"
        logger.info(f"{c['name'][:35]:<35} | {c['set'].upper():<6} | {c['collector_number']:<5} | {foil_str:<4} | {c['count']:<3} | ${c['usd_unit']:<7.2f} | ${c['usd_total']:<8.2f} | €{c['eur_unit']:<7.2f} | €{c['eur_total']:<8.2f}")
    logger.info("="*95)
    logger.info(f"{'GRAND TOTALS':<35} | {'':<6} | {'':<5} | {'':<4} | {total_count:<3} | {'':<8} | ${grand_total_usd:<8.2f} | {'':<8} | €{grand_total_eur:<8.2f}")
    logger.info("="*95 + "\n")

    # Save to output CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv_path = OUTPUT_DIR / f"price_check_result_{timestamp}.csv"
    
    try:
        # We will keep original headers and append new price details
        with open(output_csv_path, mode='w', encoding='utf-8', newline='') as out_f:
            if processed_cards:
                fieldnames = list(processed_cards[0]['original_row'].keys()) + [
                    'Unit USD', 'Total USD', 'Unit EUR', 'Total EUR'
                ]
                writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                writer.writeheader()
                for c in processed_cards:
                    row_data = c['original_row'].copy()
                    row_data['Unit USD'] = f"{c['usd_unit']:.2f}"
                    row_data['Total USD'] = f"{c['usd_total']:.2f}"
                    row_data['Unit EUR'] = f"{c['eur_unit']:.2f}"
                    row_data['Total EUR'] = f"{c['eur_total']:.2f}"
                    writer.writerow(row_data)
        logger.info(f"Saved results CSV to: {output_csv_path}")
    except Exception as e:
        logger.error(f"Failed to write results CSV: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default fallback to the user's specific CSV file
        default_csv = ROOT_DIR / "moxfield_binder_assigner" / "inputs" / "20260628_184333-regular-cards.csv"
        if default_csv.exists():
            check_prices(default_csv)
        else:
            print("Usage: python price_checker_cli.py <path_to_csv>")
    else:
        check_prices(Path(sys.argv[1]))
