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
    is_foil,
    load_alkoo_sets,
    write_alkoo_sets,
    load_largepleather_sets,
    write_largepleather_sets
)

# Test Data Paths (pointing to directory under yyy_testing_suite)
TEST_DATA_DIR = SCRIPT_DIR / "moxfield_binder_assigner" / "test_data"
TEST_INPUT = TEST_DATA_DIR / "test_input_cards.csv"
TEST_ALKOO = TEST_DATA_DIR / "test_alkoo_inventory.csv"
TEST_PLEATHER = TEST_DATA_DIR / "test_pleather_inventory.csv"
TEST_LARGEPLEATHER = TEST_DATA_DIR / "test_largepleather_inventory.csv"
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
                "full_art": False,
                "frame_effects": [],
                "promo_types": [],
                "promo": False,
                "border_color": "black",
                "artist": "Test Artist",
                "rarity": "rare",
                "edhrec_rank": 100
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
            largepleather_inventory_csv=TEST_LARGEPLEATHER,
            output_dir=TEST_OUTPUT_DIR,
            logger=logger
        )

        # 1. Check foil upgrades (swaps)
        self.assertIn("ALKOO Case: Swap out existing non-foil version of 'ExistingALKOOCard' (DFT) (Score: 0.0) with incoming fancier foil version (Score: 100.0)", swaps)
        self.assertIn("Small Pleather: Swap out existing non-foil version of 'ExistingPleatherCard' (Score: 0.0) with incoming fancier foil version (Score: 100.0)", swaps)
        self.assertIn("Large Pleather: Swap out existing non-foil version of 'ExistingLargePleatherCard' (40K) (Score: 0.0) with incoming fancier foil version (Score: 100.0)", swaps)

        # 2. Check internal duplicate routing (NewPleatherCard twice in input, row 8 & 9)
        # One copy should go to Small Pleather, the duplicate one to Duplicates/Unwanted
        pleather_names = [r["Name"] for r in binders["ABinder - Small Pleather"]]
        duplicate_names = [r["Name"] for r in binders["Binder - Duplicates and Unwanted"]]
        self.assertEqual(pleather_names.count("NewPleatherCard"), 1)
        self.assertEqual(duplicate_names.count("NewPleatherCard"), 1)

        # Also check Large Pleather internal duplicates
        lp_names = [r["Name"] for r in binders["Binder - Large Pleather"]]
        self.assertEqual(lp_names.count("NewLargePleatherCard"), 1)
        self.assertEqual(duplicate_names.count("NewLargePleatherCard"), 1)

        # 3. Check outputs were physically created and retained under test_data/outputs/
        self.assertTrue(TEST_OUTPUT_DIR.exists())
        files = list(TEST_OUTPUT_DIR.glob("*"))
        self.assertGreater(len(files), 0)

class TestAlkooSets(unittest.TestCase):
    def setUp(self):
        self.temp_file = Path(__file__).parent / "temp_alkoo.txt"
        if self.temp_file.exists():
            self.temp_file.unlink()

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_load_and_write_alkoo_sets(self):
        test_sets = {"MH3", "DFT", "ONE"}
        write_alkoo_sets(test_sets, self.temp_file)
        
        loaded = load_alkoo_sets(self.temp_file, fallback_to_base=False)
        self.assertEqual(loaded, test_sets)

class TestLargePleatherSets(unittest.TestCase):
    def setUp(self):
        self.temp_file = Path(__file__).parent / "temp_largepleather.txt"
        if self.temp_file.exists():
            self.temp_file.unlink()

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_load_and_write_largepleather_sets(self):
        test_sets = {"40K", "BRC", "PIP"}
        write_largepleather_sets(test_sets, self.temp_file)
        
        loaded = load_largepleather_sets(self.temp_file, fallback_to_base=False)
        self.assertEqual(loaded, test_sets)

    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_custom_alkoo_sets_routing(self, mock_resolve, mock_cache):
        # We specify a custom set set code (e.g. "CUST") and check if it gets routed to ALKOO Case
        def cache_lookup(query):
            return {"name": query["name"], "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False}, "path"
        mock_cache.side_effect = cache_lookup

        # Make input rows contain a card with Edition="CUST"
        # We will pass {"CUST"} as the custom alkoo_sets
        logger = logging.getLogger("Test")
        logger.setLevel(logging.ERROR)
        
        counts, swaps, binders = assign_cards_to_binders(
            input_csv=TEST_INPUT,
            alkoo_inventory_csv=TEST_ALKOO,
            pleather_inventory_csv=TEST_PLEATHER,
            largepleather_inventory_csv=TEST_LARGEPLEATHER,
            output_dir=TEST_OUTPUT_DIR,
            logger=logger,
            alkoo_sets={"CUST"}
        )
        
        # Verify that any card with edition "CUST" is routed to ALKOO Case
        # In test_input_cards.csv, there is a card like 'Expensive Non-Land' which has edition 'DFT'.
        # Let's verify that with alkoo_sets={"CUST"}, 'DFT' card is NOT in ALKOO Case (instead it goes to Pleather because it's cheap and not in alkoo_sets)
        alkoo_binder_names = [r["Name"] for r in binders["Binder - ALKOO Case"]]
        # In the original test, ExistingALKOOCard (Edition: DFT) would have gone to ALKOO case or duplicates.
        # Now DFT is not in alkoo_sets, so it shouldn't go to ALKOO Case.
        self.assertNotIn("ExistingALKOOCard", alkoo_binder_names)


class TestBasicLandsDeduplication(unittest.TestCase):
    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_basic_lands_not_deduplicated(self, mock_resolve, mock_cache):
        # We simulate incoming rows with multiple Forest entries
        temp_input = Path(__file__).parent / "temp_basics_test.csv"
        csv_content = (
            '"Count","Name","Edition","Condition","Language","Foil","Collector Number","Alter","Proxy","Purchase Price"\n'
            '"1","Forest","BLB","Near Mint","English","","278","","",""\n'
            '"1","Forest","BLB","Near Mint","English","foil","278","","",""\n'
            '"1","Island","BLB","Near Mint","English","","279","","",""\n'
        )
        with open(temp_input, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        def cache_lookup(query):
            name = query["name"]
            if name == "Forest":
                return {"name": "Forest", "type_line": "Basic Land — Forest", "prices": {"usd": "0.05", "eur": "0.05"}, "full_art": False}, "path"
            elif name == "Island":
                return {"name": "Island", "type_line": "Basic Land — Island", "prices": {"usd": "0.05", "eur": "0.05"}, "full_art": False}, "path"
            return None, None

        mock_cache.side_effect = cache_lookup

        logger = logging.getLogger("Test")
        logger.setLevel(logging.ERROR)

        try:
            counts, swaps, binders = assign_cards_to_binders(
                input_csv=temp_input,
                alkoo_inventory_csv=TEST_ALKOO,
                pleather_inventory_csv=TEST_PLEATHER,
                largepleather_inventory_csv=TEST_LARGEPLEATHER,
                output_dir=TEST_OUTPUT_DIR,
                logger=logger
            )
            
            # Since Forest is a basic land, both copies should be retained!
            # The non-foil Forest goes to "Binder - Basics"
            # The foil Forest goes to "Binder - Fancy Basics"
            # The Island goes to "Binder - Basics"
            # None should be in "Binder - Duplicates and Unwanted"
            basics_names = [r["Name"] for r in binders["Binder - Basics"]]
            fancy_basics_names = [r["Name"] for r in binders["Binder - Fancy Basics"]]
            duplicate_names = [r["Name"] for r in binders["Binder - Duplicates and Unwanted"]]

            self.assertEqual(basics_names.count("Forest"), 1)
            self.assertEqual(fancy_basics_names.count("Forest"), 1)
            self.assertEqual(basics_names.count("Island"), 1)
            self.assertEqual(len(duplicate_names), 0)

        finally:
            if temp_input.exists():
                temp_input.unlink()


class TestSeparatePoolDeduplication(unittest.TestCase):
    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_separate_pool_deduplication(self, mock_resolve, mock_cache):
        temp_input = Path(__file__).parent / "temp_pool_test.csv"
        csv_content = (
            '"Count","Name","Edition","Condition","Language","Foil","Collector Number","Alter","Proxy","Purchase Price"\n'
            '"1","Kitesail","MOM","Near Mint","English","foil","100","","",""\n'
            '"1","Kitesail","MOM","Near Mint","English","","100","","",""\n'
            '"1","Kitesail","WWK","Near Mint","English","","200","","",""\n'
        )
        with open(temp_input, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        def cache_lookup(query):
            name = query["name"]
            # Both MOM and WWK versions are cheap creatures (non-land, non-basic)
            return {
                "name": name,
                "type_line": "Artifact — Equipment",
                "prices": {"usd": "0.10", "eur": "0.10"},
                "full_art": False
            }, "path"

        mock_cache.side_effect = cache_lookup

        logger = logging.getLogger("Test")
        logger.setLevel(logging.ERROR)

        try:
            counts, swaps, binders = assign_cards_to_binders(
                input_csv=temp_input,
                alkoo_inventory_csv=TEST_ALKOO,
                pleather_inventory_csv=TEST_PLEATHER,
                largepleather_inventory_csv=TEST_LARGEPLEATHER,
                output_dir=TEST_OUTPUT_DIR,
                logger=logger,
                alkoo_sets={"MOM"}
            )
            
            # Foil MOM Kitesail should go to ALKOO Case
            # Non-foil MOM Kitesail should go to Duplicates/Unwanted
            # WWK Kitesail should go to Small Pleather
            alkoo_names = [r["Name"] for r in binders["Binder - ALKOO Case"]]
            pleather_names = [r["Name"] for r in binders["ABinder - Small Pleather"]]
            duplicate_names = [r["Name"] for r in binders["Binder - Duplicates and Unwanted"]]

            self.assertEqual(alkoo_names.count("Kitesail"), 1)
            self.assertEqual(pleather_names.count("Kitesail"), 1)
            self.assertEqual(duplicate_names.count("Kitesail"), 1)

            # Check that the foil version went to ALKOO Case
            foil_statuses = [is_foil(r) for r in binders["Binder - ALKOO Case"] if r["Name"] == "Kitesail"]
            self.assertTrue(foil_statuses[0])

        finally:
            if temp_input.exists():
                temp_input.unlink()


class TestAlkooSorting(unittest.TestCase):
    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_alkoo_sorting_by_set_then_wubrg(self, mock_resolve, mock_cache):
        temp_input = Path(__file__).parent / "temp_alkoo_sort_test.csv"
        csv_content = (
            '"Count","Name","Edition","Condition","Language","Foil","Collector Number","Alter","Proxy","Purchase Price"\n'
            '"1","Wary Thespian","MOM","Near Mint","English","","215","","",""\n'
            '"1","Dreg Recycler","MOM","Near Mint","English","","100","","",""\n'
            '"1","Blue Spell","BLB","Near Mint","English","","10","","",""\n'
            '"1","White Spell","BLB","Near Mint","English","","20","","",""\n'
        )
        with open(temp_input, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        def cache_lookup(query):
            name = query["name"]
            if name == "Wary Thespian":
                return {"name": "Wary Thespian", "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False, "color_identity": ["G"]}, "path"
            elif name == "Dreg Recycler":
                return {"name": "Dreg Recycler", "type_line": "Creature", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False, "color_identity": ["B"]}, "path"
            elif name == "Blue Spell":
                return {"name": "Blue Spell", "type_line": "Instant", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False, "color_identity": ["U"]}, "path"
            elif name == "White Spell":
                return {"name": "White Spell", "type_line": "Sorcery", "prices": {"usd": "0.10", "eur": "0.10"}, "full_art": False, "color_identity": ["W"]}, "path"
            return None, None

        mock_cache.side_effect = cache_lookup

        logger = logging.getLogger("Test")
        logger.setLevel(logging.ERROR)

        try:
            counts, swaps, binders = assign_cards_to_binders(
                input_csv=temp_input,
                alkoo_inventory_csv=TEST_ALKOO,
                pleather_inventory_csv=TEST_PLEATHER,
                largepleather_inventory_csv=TEST_LARGEPLEATHER,
                output_dir=TEST_OUTPUT_DIR,
                logger=logger,
                alkoo_sets={"BLB", "MOM"}
            )
            
            alkoo_cards = binders["Binder - ALKOO Case"]
            names = [r["Name"] for r in alkoo_cards]
            
            # Expected order:
            # BLB (White -> Blue) -> MOM (Black -> Green)
            expected = ["White Spell", "Blue Spell", "Dreg Recycler", "Wary Thespian"]
            self.assertEqual(names, expected)

        finally:
            if temp_input.exists():
                temp_input.unlink()


class TestPleatherNameOnlyDeduplication(unittest.TestCase):
    @patch('_core_tools.scryfall_core.load_from_cache')
    @patch('_core_tools.scryfall_core.resolve_cards')
    def test_pleather_name_only_deduplication(self, mock_resolve, mock_cache):
        temp_input = Path(__file__).parent / "temp_pleather_name_test.csv"
        csv_content = (
            '"Count","Name","Edition","Condition","Language","Foil","Collector Number","Alter","Proxy","Purchase Price"\n'
            '"1","Quench","RNA","Near Mint","English","","100","","",""\n'
            '"1","Quench","RVR","Near Mint","English","","200","","",""\n'
        )
        with open(temp_input, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        # RVR Quench is foil, so RVR is fancier (score 100) than RNA (score 0)
        # Note: both are in Pleather since RVR/RNA are not in alkoo_sets.
        def cache_lookup(query):
            name = query["name"]
            return {
                "name": name,
                "type_line": "Instant",
                "prices": {"usd": "0.10", "eur": "0.10"},
                "full_art": False
            }, "path"

        mock_cache.side_effect = cache_lookup

        logger = logging.getLogger("Test")
        logger.setLevel(logging.ERROR)

        try:
            # RVR is foil in our test inputs (simulate foil upgrade check)
            # In test_input_cards.csv or manually we can make one of them foil or higher score.
            # RVR has foil, RNA doesn't. We simulate that by reading the CSV rows.
            # RVR is row 2, let's make it foil in csv_content:
            pass
        except Exception:
            pass

        # Let's adjust csv_content so RVR has foil
        csv_content = (
            '"Count","Name","Edition","Condition","Language","Foil","Collector Number","Alter","Proxy","Purchase Price"\n'
            '"1","Quench","RNA","Near Mint","English","","100","","",""\n'
            '"1","Quench","RVR","Near Mint","English","foil","200","","",""\n'
        )
        with open(temp_input, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        try:
            counts, swaps, binders = assign_cards_to_binders(
                input_csv=temp_input,
                alkoo_inventory_csv=TEST_ALKOO,
                pleather_inventory_csv=TEST_PLEATHER,
                largepleather_inventory_csv=TEST_LARGEPLEATHER,
                output_dir=TEST_OUTPUT_DIR,
                logger=logger,
                alkoo_sets=set()  # No ALKOO sets, so both are Pleather candidates
            )
            
            pleather_names = [r["Name"] for r in binders["ABinder - Small Pleather"]]
            duplicate_names = [r["Name"] for r in binders["Binder - Duplicates and Unwanted"]]

            # Since duplicate checking for Pleather is name-only, the two copies of Quench
            # should be deduplicated down to 1.
            # Specifically, the fancier RVR (foil) should be kept, and the RNA one should be sent to duplicates.
            self.assertEqual(pleather_names.count("Quench"), 1)
            self.assertEqual(duplicate_names.count("Quench"), 1)

            # The retained one should be the RVR version (foil)
            retained_editions = [r["Edition"] for r in binders["ABinder - Small Pleather"] if r["Name"] == "Quench"]
            self.assertEqual(retained_editions[0], "RVR")

        finally:
            if temp_input.exists():
                temp_input.unlink()


if __name__ == "__main__":
    unittest.main()
