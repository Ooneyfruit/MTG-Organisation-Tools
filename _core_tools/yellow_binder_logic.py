import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any

logger = logging.getLogger("moxfield_yellow_binder")

# Conversion rates
try:
    from currency_converter import CurrencyConverter
    c_conv = CurrencyConverter()
    USD_TO_GBP = c_conv.convert(1.0, 'USD', 'GBP')
    EUR_TO_GBP = c_conv.convert(1.0, 'EUR', 'GBP')
except Exception:
    USD_TO_GBP = 0.77
    EUR_TO_GBP = 0.85

CORE_DIR = Path(__file__).parent
PARENT_DIR = CORE_DIR.parent

def parse_price(val: Any) -> float:
    """Safely converts price strings to floats."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace('$', '').replace('€', '').replace('£', '').strip())
    except ValueError:
        return 0.0

def is_foil(row: Dict[str, str]) -> bool:
    """Checks if the row specifies a foil card."""
    foil_val = row.get("Foil", "").strip().lower()
    return bool(foil_val and foil_val != "false")

def get_card_prices(scry_data: Dict[str, Any], foil: bool) -> Tuple[float, float, float]:
    """
    Returns (usd, eur, gbp) prices for a card based on its foil status.
    Uses fallback logic if preferred foil/non-foil prices are missing.
    """
    prices = scry_data.get("prices", {})
    usd_unit = 0.0
    eur_unit = 0.0

    if foil:
        usd_unit = parse_price(prices.get("usd_foil"))
        if usd_unit == 0.0:
            usd_unit = parse_price(prices.get("usd"))
            
        eur_unit = parse_price(prices.get("eur_foil"))
        if eur_unit == 0.0:
            eur_unit = parse_price(prices.get("eur"))
    else:
        usd_unit = parse_price(prices.get("usd"))
        if usd_unit == 0.0:
            usd_unit = parse_price(prices.get("usd_foil"))
            
        eur_unit = parse_price(prices.get("eur"))
        if eur_unit == 0.0:
            eur_unit = parse_price(prices.get("eur_foil"))

    # Estimate GBP
    gbp_unit = max(usd_unit * USD_TO_GBP, eur_unit * EUR_TO_GBP)
    return usd_unit, eur_unit, gbp_unit

def get_other_cache_prices(card_name: str) -> List[Tuple[float, float]]:
    """Scans the local cache directory for any other cached printings of this card name."""
    prices_found = []
    if not card_name:
        return prices_found
        
    # Sanitize the card name to match cache filenames
    s_name = card_name.strip().lower()
    s_name = re.sub(r'[^a-z0-9_]', '_', s_name)
    s_name = re.sub(r'_+', '_', s_name).strip('_')
    if not s_name:
        return prices_found

    cache_path = PARENT_DIR / "cache"
    if not cache_path.exists():
        return prices_found

    for root, dirs, files in os.walk(cache_path):
        for file in files:
            if file.endswith(".json") and s_name in file:
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        scry = data.get("scryfall_data", {})
                        if scry:
                            cached_name = scry.get("name", "").strip().lower()
                            if cached_name == card_name.strip().lower():
                                pr = scry.get("prices", {})
                                pr_usd = parse_price(pr.get("usd"))
                                pr_eur = parse_price(pr.get("eur"))
                                if pr_usd > 0.0 or pr_eur > 0.0:
                                    prices_found.append((pr_usd, pr_eur))
                except Exception:
                    pass
    return prices_found

def is_manipulated(usd: float, eur: float, card_name: str = "") -> bool:
    """
    Checks for potential market manipulation or pricing errors.
    """
    if usd <= 0.0 or eur <= 0.0:
        return False
    
    # Check if there is disagreement on whether it meets the threshold
    one_below = (usd < 1.0) or (eur < 1.0)
    one_above = (usd >= 1.0) or (eur >= 1.0)
    
    if not (one_below and one_above):
        return False
        
    high = max(usd, eur)
    low = min(usd, eur)
    diff = high - low
    
    # European market bias: if USD is inflated compared to EUR,
    # we raise the threshold for the low (EUR) price to be considered safe (0.70 instead of 0.55)
    # and lower the diff threshold to 0.80 (instead of 1.30) to catch smaller spreads.
    if usd > eur:
        low_threshold = 0.70
        diff_threshold = 0.80
        bias_str = " (European market bias active: USD > EUR)"
    else:
        low_threshold = 0.55
        diff_threshold = 1.30
        bias_str = ""
    
    if low >= low_threshold:
        return False
        
    if diff < diff_threshold:
        return False
        
    # Potential manipulation! Check other printings in the cache.
    logger.info(f"Checking potential manipulation for '{card_name}' (USD: ${usd:.2f}, EUR: €{eur:.2f}){bias_str}")
    other_prices = get_other_cache_prices(card_name)
    if other_prices:
        has_valuable_printing = False
        for pr_usd, pr_eur in other_prices:
            # Skip this exact printing to ensure we are comparing against others
            if abs(pr_usd - usd) < 0.01 and abs(pr_eur - eur) < 0.01:
                continue
            if pr_usd >= 1.0 or pr_eur >= 1.0:
                has_valuable_printing = True
                break
        if has_valuable_printing:
            logger.info(f"Legit card '{card_name}': other cached printings support the price.")
            return False  # Legit card, other printings support the price
        else:
            logger.warning(f"Confirmed manipulation/outlier for '{card_name}': all other cached printings are cheap (< 1.0).")
    else:
        logger.warning(f"Confirmed manipulation/outlier for '{card_name}': no other printings cached to verify.")
            
    return True

def meets_threshold(usd: float, eur: float, gbp: float, card_name: str = "") -> bool:
    """
    Returns True if the card converted to GBP meets or exceeds £1.00
    on either data point (USD or EUR) and is not manipulated.
    We also require the EUR price converted to GBP to be at least £0.75.
    """
    if is_manipulated(usd, eur, card_name):
        return False
    usd_gbp = usd * USD_TO_GBP
    eur_gbp = eur * EUR_TO_GBP
    if eur_gbp < 0.75:
        logger.info(f"Card '{card_name}' EUR price converted to GBP (£{eur_gbp:.2f}) is below 75p limit. Skipping.")
        return False
    meets = usd_gbp >= 1.0 or eur_gbp >= 1.0
    if not meets:
        logger.info(f"Card '{card_name}' does not meet £1.00 threshold (USD GBP: £{usd_gbp:.2f}, EUR GBP: £{eur_gbp:.2f}).")
    return meets
