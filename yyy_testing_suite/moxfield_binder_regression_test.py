import unittest
import sys
import os
import json
import logging
from pathlib import Path
from unittest.mock import patch

# Adjust sys.path to import core_tools and binder logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent

if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))
    
BINDER_DIR = PARENT_DIR / "moxfield_binder_assigner"
if str(BINDER_DIR) not in sys.path:
    sys.path.append(str(BINDER_DIR))

from _core_tools import scryfall_core
from moxfield_binder_logic import (
    parse_price,
    is_basic_land,
    load_existing_inventory,
    assign_cards_to_binders,
    is_foil
)

# Test Data Paths (pointing to directory under yyy_testing_suite)
TEST_DATA_DIR = SCRIPT_DIR / "moxfield_binder_assigner" / "test_data"
TEST_INPUT = TEST_DATA_DIR / "test_input_cards.csv"
TEST_ALKOO = TEST_DATA_DIR / "test_alkoo_inventory.csv"
TEST_PLEATHER = TEST_DATA_DIR / "test_pleather_inventory.csv"
TEST_OUTPUT_DIR = TEST_DATA_DIR / "outputs"

class TestScryfallCacheHealing(unittest.TestCase):
    def setUp(self):
        scryfall_core.ensure_cache_dir()
        self.test_card = {
            "name": "Test Card Name",
            "set": "TST",
            "collector_number": "99"
        }
        paths = scryfall_core.get_cache_paths(self.test_card)
        self.filepath = os.path.join(scryfall_core.CACHE_DIR, paths[0][0])
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def tearDown(self):
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def test_old_cache_invalidated(self):
        # Old cache has no prices or full_art
        old_data = {
            "query_metadata": {"query_type": "scryfall_card_by_set_and_collector_number"},
            "scryfall_data": {
                "name": "Test Card Name",
                "color_identity": ["W"],
                "type_line": "Creature — Human"
            }
        }
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(old_data, f)
            
        data, path = scryfall_core.load_from_cache(self.test_card)
        self.assertIsNone(data)
        self.assertIsNone(path)

    def test_new_cache_loaded(self):
        new_data = {
            "query_metadata": {"query_type": "scryfall_card_by_set_and_collector_number"},
            "scryfall_data": {
                "name": "Test Card Name",
                "color_identity": ["W"],
                "type_line": "Creature — Human",
                "prices": {"usd": "1.50", "eur": "1.20"},
                "full_art": False
            }
        }
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(new_data, f)
            
        data, path = scryfall_core.load_from_cache(self.test_card)
        self.assertIsNotNone(data)
        self.assertEqual(data["name"], "Test Card Name")
        self.assertEqual(data["prices"]["usd"], "1.50")
        self.assertFalse(data["full_art"])

class TestBinderClassificationLogic(unittest.TestCase):
    def test_parse_price(self):
        self.assertEqual(parse_price("1.50"), 1.50)
        self.assertEqual(parse_price("$2.40"), 2.40)
        self.assertEqual(parse_price("€0.85"), 0.85)
        self.assertEqual(parse_price(None), 0.0)

    def test_is_basic_land(self):
        self.assertTrue(is_basic_land("Basic Land — Forest"))
        self.assertTrue(is_basic_land("Basic Snow-Covered Land — Island"))
        self.assertFalse(is_basic_land("Land — Forest"))

    def test_is_foil(self):
        self.assertTrue(is_foil({"Foil": "foil"}))
        self.assertFalse(is_foil({"Foil": "false"}))

    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_binder_routing_rules(self, mock_resolve, mock_cache):
        # Mock Scryfall cache lookups for test items
        def cache_lookup(query):
            name = query["name"]
            if name == "Expensive Non-Land":
                return {"name": name, "type_line": "Creature", "prices": {"usd": "2.50", "eur": "0.50"}, "full_art": False}, "path"
            elif name == "ExistingALKOOCard":
                return {"name": name, "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False}, "path"
            elif name == "Basic Land Non-Foil":
                return {"name": name, "type_line": "Basic Land — Forest", "prices": {"usd": "0.05", "eur": "0.05"}, "full_art": False}, "path"
            elif name == "Basic Land Fancy":
                return {"name": name, "type_line": "Basic Land — Island", "prices": {"usd": "0.05", "eur": "0.05"}, "full_art": True}, "path"
            elif name == "ExistingPleatherCard":
                return {"name": name, "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False}, "path"
            elif name == "NewPleatherCard":
                return {"name": name, "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False}, "path"
            else:
                return {"name": name, "type_line": "Creature", "prices": {"usd": "0.20", "eur": "0.20"}, "full_art": False}, "path"
        
        mock_cache.side_effect = cache_lookup

        logger = logging.getLogger("Test")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            logger.addHandler(logging.StreamHandler(sys.stdout))

        counts, swaps, binders = assign_cards_to_binders(
            input_csv=TEST_INPUT,
            alkoo_inventory_csv=TEST_ALKOO,
            pleather_inventory_csv=TEST_PLEATHER,
            output_dir=TEST_OUTPUT_DIR,
            logger=logger
        )

        # 1. Check foil upgrades (swaps)
        self.assertIn("ALKOO Case: Swap out non-foil 'ExistingALKOOCard' with incoming foil", swaps)
        self.assertIn("Small Pleather: Swap out non-foil 'ExistingPleatherCard' with incoming foil", swaps)

        # 2. Check internal duplicate routing (NewPleatherCard twice in input, row 8 & 9)
        # One copy should go to Small Pleather, the duplicate one to Duplicates/Unwanted
        pleather_names = [r["Name"] for r in binders["ABinder - Small Pleather"]]
        duplicate_names = [r["Name"] for r in binders["Binder - Duplicates and Unwanted"]]
        self.assertEqual(pleather_names.count("NewPleatherCard"), 1)
        self.assertEqual(duplicate_names.count("NewPleatherCard"), 1)

        # 3. Check outputs were physically created and retained under test_data/outputs/
        self.assertTrue(TEST_OUTPUT_DIR.exists())
        files = list(TEST_OUTPUT_DIR.glob("*"))
        self.assertGreater(len(files), 0)

if __name__ == "__main__":
    unittest.main()
