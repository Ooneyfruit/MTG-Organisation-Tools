import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust sys.path to import core_tools and yellow binder checker logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent

if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

YELLOW_BINDER_DIR = PARENT_DIR / "moxfield_yellow_binder_checker"
if str(YELLOW_BINDER_DIR) not in sys.path:
    sys.path.append(str(YELLOW_BINDER_DIR))

import moxfield_yellow_binder_logic as logic
import _core_tools.yellow_binder_logic as core_logic
core_logic.USD_TO_GBP = 0.77
core_logic.EUR_TO_GBP = 0.85
logic.USD_TO_GBP = 0.77
logic.EUR_TO_GBP = 0.85

class TestYellowBinderChecker(unittest.TestCase):
    def test_parse_price(self):
        self.assertEqual(logic.parse_price("1.50"), 1.50)
        self.assertEqual(logic.parse_price("$2.99"), 2.99)
        self.assertEqual(logic.parse_price("€0.85"), 0.85)
        self.assertEqual(logic.parse_price("£1.20"), 1.20)
        self.assertEqual(logic.parse_price(None), 0.0)
        self.assertEqual(logic.parse_price("invalid"), 0.0)

    def test_is_foil(self):
        self.assertTrue(logic.is_foil({"Foil": "foil"}))
        self.assertTrue(logic.is_foil({"Foil": "true"}))
        self.assertFalse(logic.is_foil({"Foil": ""}))
        self.assertFalse(logic.is_foil({"Foil": "false"}))
        self.assertFalse(logic.is_foil({}))

    def test_get_card_prices(self):
        scry_data = {
            "prices": {
                "usd": "0.50",
                "usd_foil": "2.50",
                "eur": "0.45",
                "eur_foil": "2.20"
            }
        }
        
        # Test non-foil prices
        usd, eur, gbp = logic.get_card_prices(scry_data, foil=False)
        self.assertEqual(usd, 0.50)
        self.assertEqual(eur, 0.45)
        # 0.50 * 0.77 = 0.385; 0.45 * 0.85 = 0.3825. Max is 0.385.
        self.assertAlmostEqual(gbp, 0.385)

        # Test foil prices
        usd, eur, gbp = logic.get_card_prices(scry_data, foil=True)
        self.assertEqual(usd, 2.50)
        self.assertEqual(eur, 2.20)
        # 2.50 * 0.77 = 1.925; 2.20 * 0.85 = 1.87. Max is 1.925.
        self.assertAlmostEqual(gbp, 1.925)

    def test_meets_threshold(self):
        # USD meets GBP threshold: 1.30 * 0.77 = 1.001 (and low EUR is >= 0.88 to meet the 75p requirement)
        self.assertTrue(logic.meets_threshold(1.30, 1.0, 1.0))
        # EUR meets GBP threshold: 1.18 * 0.85 = 1.003
        self.assertTrue(logic.meets_threshold(0.5, 1.18, 0.5))
        # Neither meets threshold
        self.assertFalse(logic.meets_threshold(1.20, 1.10, 0.9))

    @patch('_core_tools.yellow_binder_logic.get_other_cache_prices')
    def test_market_manipulation(self, mock_get_other):
        # 1. Autarch Mammoth (0.12, 3.46) -> low=0.12 (<0.55), diff=3.34 (>=1.30). No other printings. -> Manipulated.
        mock_get_other.return_value = []
        self.assertTrue(logic.is_manipulated(0.12, 3.46, "Autarch Mammoth"))
        self.assertFalse(logic.meets_threshold(0.12, 3.46, 3.46 * 0.85, "Autarch Mammoth"))
        
        # 2. Ezuri (1.11, 0.37) -> low=0.37, diff=0.74 (<1.30) -> Not manipulated, but USD 1.11 is £0.85 (< £1.00)
        self.assertFalse(logic.is_manipulated(1.11, 0.37, "Ezuri, Stalker of Spheres"))
        self.assertFalse(logic.meets_threshold(1.11, 0.37, 0.37 * 0.85, "Ezuri, Stalker of Spheres"))
        
        # 3. Kona (2.37, 0.76) -> low=0.76 (>=0.55) -> Not manipulated
        self.assertFalse(logic.is_manipulated(2.37, 0.76, "Kona, Rescue Beastie"))
        
        # 4. Corpsejack Menace (1.78, 0.48) with only cheap other printings in cache
        mock_get_other.return_value = [(0.86, 0.64), (0.59, 0.35)]
        self.assertTrue(logic.is_manipulated(1.78, 0.48, "Corpsejack Menace"))
        
        # 5. Dragon Sniper (1.95, 0.48) but with a valuable other printing in the cache -> Not manipulated
        mock_get_other.return_value = [(1.03, 0.85)]
        self.assertFalse(logic.is_manipulated(1.95, 0.48, "Dragon Sniper"))



    @patch('moxfield_yellow_binder_logic.scryfall_core')
    def test_check_binders_logic(self, mock_scryfall):
        # Setup mock cache lookup
        def mock_load_from_cache(query):
            if query['name'] == 'Cheap Card':
                return {
                    "prices": {
                        "usd": "0.20",
                        "eur": "0.15"
                    },
                    "type_line": "Creature",
                    "color_identity": ["W"]
                }, "mock_path"
            elif query['name'] == 'Expensive Card':
                return {
                    "prices": {
                        "usd": "5.00",
                        "eur": "4.50"
                    },
                    "type_line": "Instant",
                    "color_identity": ["W"]
                }, "mock_path"
            elif query['name'] == 'Borderline Card':
                # Meets GBP threshold only (USD=1.20 -> GBP=0.924, EUR=1.20 -> GBP=1.02)
                return {
                    "prices": {
                        "usd": "0.95",
                        "eur": "1.20"
                    },
                    "type_line": "Sorcery",
                    "color_identity": ["G"]
                }, "mock_path"
            elif query['name'] == 'Manipulated Card':
                # USD=0.12, EUR=3.46 (manipulated)
                return {
                    "prices": {
                        "usd": "0.12",
                        "eur": "3.46"
                    },
                    "type_line": "Enchantment",
                    "color_identity": ["B"]
                }, "mock_path"
            elif query['name'] == 'Glitch Card':
                return {
                    "prices": {
                        "usd": "0.00",
                        "eur": "0.00"
                    },
                    "type_line": "Instant",
                    "color_identity": ["R"]
                }, "mock_path"
            return None, None

        mock_scryfall.load_from_cache.side_effect = mock_load_from_cache
        mock_scryfall.resolve_cards = MagicMock()

        # Mock loader functions
        with patch('moxfield_yellow_binder_logic.load_moxfield_csv') as mock_load_csv:
            yellow_rows = [
                {'Name': 'Cheap Card', 'Edition': 'SET', 'Collector Number': '1', 'Foil': '', 'Count': '1'},
                {'Name': 'Expensive Card', 'Edition': 'SET', 'Collector Number': '2', 'Foil': '', 'Count': '1'},
                {'Name': 'Manipulated Card', 'Edition': 'SET', 'Collector Number': '4', 'Foil': '', 'Count': '1'},
                {'Name': 'Glitch Card', 'Edition': 'SET', 'Collector Number': '5', 'Foil': '', 'Count': '1'}
            ]
            other_rows = [
                {'Name': 'Cheap Card', 'Edition': 'SET', 'Collector Number': '1', 'Foil': '', 'Count': '2'},
                {'Name': 'Expensive Card', 'Edition': 'SET', 'Collector Number': '2', 'Foil': '', 'Count': '1'},
                {'Name': 'Borderline Card', 'Edition': 'SET', 'Collector Number': '3', 'Foil': '', 'Count': '1'},
                {'Name': 'Glitch Card', 'Edition': 'SET', 'Collector Number': '5', 'Foil': '', 'Count': '1'}
            ]

            def side_effect(filepath):
                if "yellow" in str(filepath):
                    return yellow_rows
                return other_rows

            mock_load_csv.side_effect = side_effect

            yellow_path = Path("yellow_binder.csv")
            other_paths = [Path("other_binder.csv")]

            move, remove = logic.check_binders(yellow_path, other_paths)

            # Assert Cheap Card and Manipulated Card in yellow should be removed
            self.assertEqual(len(remove), 2)
            self.assertEqual(remove[0]['Name'], 'Cheap Card')
            self.assertEqual(remove[1]['Name'], 'Manipulated Card')

            # Assert Expensive Card and Borderline Card should be moved into yellow
            # Cheap Card is below threshold, so it shouldn't move
            self.assertEqual(len(move), 2)
            self.assertEqual(move[0]['Tags'], 'From other_binder (£3.85)')
            self.assertEqual(move[1]['Name'], 'Borderline Card')
            self.assertEqual(move[1]['Tags'], 'From other_binder (£1.02)')

if __name__ == '__main__':
    unittest.main()
