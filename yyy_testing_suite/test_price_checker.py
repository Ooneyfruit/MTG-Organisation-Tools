import unittest
import sys
import csv
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust sys.path to import core_tools and price checker logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent

if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

PRICE_CHECKER_DIR = PARENT_DIR / "price_checker"
if str(PRICE_CHECKER_DIR) not in sys.path:
    sys.path.append(str(PRICE_CHECKER_DIR))

import price_checker_cli as pc

class TestPriceChecker(unittest.TestCase):
    def test_parse_price(self):
        self.assertEqual(pc.parse_price("5.96"), 5.96)
        self.assertEqual(pc.parse_price("$10.03"), 10.03)
        self.assertEqual(pc.parse_price("€12.33"), 12.33)
        self.assertEqual(pc.parse_price(None), 0.0)
        self.assertEqual(pc.parse_price("invalid"), 0.0)

    def test_is_foil(self):
        self.assertTrue(pc.is_foil({"Foil": "foil"}))
        self.assertTrue(pc.is_foil({"Foil": "true"}))
        self.assertFalse(pc.is_foil({"Foil": ""}))
        self.assertFalse(pc.is_foil({"Foil": "false"}))
        self.assertFalse(pc.is_foil({}))

    @patch('price_checker_cli.scryfall_core')
    def test_pricing_and_sorting_logic(self, mock_scryfall):
        # Setup mock cache loading
        def mock_load_from_cache(query):
            if query['name'] == 'Card A':
                return {
                    "prices": {
                        "usd": "2.00",
                        "usd_foil": "5.00",
                        "eur": "1.80",
                        "eur_foil": "4.50"
                    }
                }, "mock_path"
            elif query['name'] == 'Card B':
                return {
                    "prices": {
                        "usd": "10.00",
                        "usd_foil": "20.00",
                        "eur": "9.00",
                        "eur_foil": "18.00"
                    }
                }, "mock_path"
            return None, None

        mock_scryfall.load_from_cache.side_effect = mock_load_from_cache
        mock_scryfall.resolve_cards = MagicMock()

        # Build some mock CSV data
        test_rows = [
            {'Name': 'Card A', 'Edition': 'SET', 'Collector Number': '1', 'Foil': '', 'Count': '3'},
            {'Name': 'Card B', 'Edition': 'SET', 'Collector Number': '2', 'Foil': 'foil', 'Count': '1'}
        ]

        processed_cards = []
        for row in test_rows:
            query = {
                'name': row['Name'],
                'set': row['Edition'],
                'collector_number': row['Collector Number']
            }
            scry_data, _ = mock_scryfall.load_from_cache(query)
            
            usd_unit = 0.0
            eur_unit = 0.0
            count = int(row['Count'])
            foil_status = pc.is_foil(row)
            
            if scry_data:
                prices = scry_data.get('prices', {})
                if foil_status:
                    usd_unit = pc.parse_price(prices.get('usd_foil'))
                    eur_unit = pc.parse_price(prices.get('eur_foil'))
                else:
                    usd_unit = pc.parse_price(prices.get('usd'))
                    eur_unit = pc.parse_price(prices.get('eur'))

            processed_cards.append({
                'name': row['Name'],
                'usd_unit': usd_unit,
                'eur_unit': eur_unit,
                'usd_total': usd_unit * count,
                'eur_total': eur_unit * count,
                'count': count
            })

        # Sort the processed cards
        processed_cards.sort(key=lambda x: (-x['usd_total'], x['name'].lower()))

        # Card B total USD = 20.00 (1 x 20.00)
        # Card A total USD = 6.00 (3 x 2.00)
        # Card B should be first
        self.assertEqual(processed_cards[0]['name'], 'Card B')
        self.assertEqual(processed_cards[0]['usd_total'], 20.00)
        self.assertEqual(processed_cards[0]['eur_total'], 18.00)
        
        # Card A should be second
        self.assertEqual(processed_cards[1]['name'], 'Card A')
        self.assertEqual(processed_cards[1]['usd_total'], 6.00)
        self.assertEqual(processed_cards[1]['eur_total'], 5.40)

if __name__ == "__main__":
    unittest.main()
