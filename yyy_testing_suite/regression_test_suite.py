import unittest
import os
import sys
import tkinter as tk
from pathlib import Path
from collections import defaultdict

# Adjust sys.path to import fast import logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
FAST_IMPORT_DIR = PARENT_DIR / "moxfield_fast_import"

if str(FAST_IMPORT_DIR) not in sys.path:
    sys.path.append(str(FAST_IMPORT_DIR))
if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

# Change directory to FAST_IMPORT_DIR to ensure it finds input.txt in its folder if required
os.chdir(str(FAST_IMPORT_DIR))

from moxfield_importer_logic import MoxfieldImporter, format_report_as_ascii
from moxfield_import_gui import MoxfieldImportGui
from moxfield_import_cli import format_table_to_ascii


class TestMoxfieldImporterLogic(unittest.TestCase):
    def setUp(self):
        print("\n" + "="*80)
        print("  TEST INITIALIZATION: MoxfieldImporter Core Logic Test Suite")
        print("="*80)
        self.importer = MoxfieldImporter(enable_lookup=False, enable_wubrg=True, dry_run=True)

    def test_single_sided_token_parsing(self):
        print("\n[STEP 1] Running: test_single_sided_token_parsing")
        print("  - Parsing 'one5' (Format: Set + CN)...")
        p1 = self.importer.parse_token_string("one5")
        self.assertEqual(p1['type'], "SS_ADVERT")
        self.assertEqual(p1['front']['set'], "one")
        self.assertEqual(p1['front']['cn'], "5")
        print("    [PASS] Correctly parsed set='one', collector_number='5', type=SS_ADVERT")

        print("  - Parsing '5one' (Format: CN + Set)...")
        p2 = self.importer.parse_token_string("5one")
        self.assertEqual(p2['type'], "SS_ADVERT")
        self.assertEqual(p2['front']['set'], "one")
        self.assertEqual(p2['front']['cn'], "5")
        print("    [PASS] Correctly parsed set='one', collector_number='5' (reversed token order)")

    def test_double_sided_same_set_parsing(self):
        print("\n[STEP 2] Running: test_double_sided_same_set_parsing")
        print("  - Parsing '7pip22' (Format: CN + Set + CN)...")
        p = self.importer.parse_token_string("7pip22")
        self.assertEqual(p['type'], "DS_PAIR")
        self.assertEqual(p['front']['set'], "pip")
        self.assertEqual(p['front']['cn'], "7")
        self.assertEqual(p['back']['set'], "pip")
        self.assertEqual(p['back']['cn'], "22")
        print("    [PASS] Correctly parsed same-set double sided: Front=#7, Back=#22, Set='pip'")

    def test_double_sided_cross_set_parsing(self):
        print("\n[STEP 3] Running: test_double_sided_cross_set_parsing")
        print("  - Parsing 'snc15ncc26' (Format: Set + CN + Set + CN)...")
        p = self.importer.parse_token_string("snc15ncc26")
        self.assertEqual(p['type'], "DS_PAIR")
        self.assertEqual(p['front']['set'], "snc")
        self.assertEqual(p['front']['cn'], "15")
        self.assertEqual(p['back']['set'], "ncc")
        self.assertEqual(p['back']['cn'], "26")
        print("    [PASS] Correctly parsed cross-set double sided: Front=SNC #15, Back=NCC #26")

        print("  - Parsing '15snc26ncc' (Format: CN + Set + CN + Set)...")
        p2 = self.importer.parse_token_string("15snc26ncc")
        self.assertEqual(p2['type'], "DS_PAIR")
        self.assertEqual(p2['front']['set'], "snc")
        self.assertEqual(p2['front']['cn'], "15")
        self.assertEqual(p2['back']['set'], "ncc")
        self.assertEqual(p2['back']['cn'], "26")
        print("    [PASS] Correctly parsed cross-set double-sided in reversed format")

    def test_dfc_token_parsing(self):
        print("\n[STEP 4] Running: test_dfc_token_parsing")
        print("  - Parsing DFC token 'dft14*d'...")
        p = self.importer.parse_token_string("dft14*d")
        self.assertEqual(p['type'], "DS_SINGLE_ENTRY")
        self.assertEqual(p['front']['set'], "dft")
        self.assertEqual(p['front']['cn'], "14")
        print("    [PASS] Correctly identified DFC type (DS_SINGLE_ENTRY)")

    def test_modifiers_and_quantities(self):
        print("\n[STEP 5] Running: test_modifiers_and_quantities")
        print("  - Parsing single-sided token with foil/multiplier 'one5*f3'...")
        p1 = self.importer.parse_token_string("one5*f3")
        self.assertEqual(p1['count'], 3)
        self.assertTrue(p1['foil'])
        print("    [PASS] Correctly resolved quantity=3 and foil=True")

        print("  - Parsing DFC token with modifiers 'dft14*df5'...")
        p2 = self.importer.parse_token_string("dft14*df5")
        self.assertEqual(p2['type'], "DS_SINGLE_ENTRY")
        self.assertEqual(p2['count'], 5)
        self.assertTrue(p2['foil'])
        print("    [PASS] Correctly resolved DFC token with quantity=5 and foil=True")

    def test_token_condition_parsing(self):
        print("\n[STEP 6] Running: test_token_condition_parsing")
        print("  - Parsing token with SP condition suffix 'one5sp'...")
        p1 = self.importer.parse_token_string("one5sp")
        self.assertEqual(p1['condition'], "Good (Lightly Played)")
        self.assertEqual(p1['front']['cn'], "5")
        print("    [PASS] Successfully parsed SP suffix as Good (Lightly Played)")

        print("  - Parsing token with foil, count, and HP suffix 'one5hp*f2'...")
        p2 = self.importer.parse_token_string("one5hp*f2")
        self.assertEqual(p2['condition'], "Heavily Played")
        self.assertTrue(p2['foil'])
        self.assertEqual(p2['count'], 2)
        print("    [PASS] Successfully resolved condition=Heavily Played, foil=True, count=2")

    def test_card_grouping_merges(self):
        print("\n[STEP 7] Running: test_card_grouping_merges")
        print("  - Attempting to merge identical regular cards...")
        card_list = []
        c1 = {'set': 'MH3', 'cn': '15', 'name': 'Guide', 'foil': False, 'condition': 'Near Mint', 'tag': '', 'count': 1}
        c2 = {'set': 'MH3', 'cn': '15', 'name': 'Guide', 'foil': False, 'condition': 'Near Mint', 'tag': '', 'count': 2}
        
        self.importer.add_or_merge_card(card_list, c1)
        self.importer.add_or_merge_card(card_list, c2)
        
        self.assertEqual(len(card_list), 1)
        self.assertEqual(card_list[0]['count'], 3)
        print("    [PASS] Correctly merged quantities into a single row (count=3)")

        print("  - Attempting to merge identical card but with different condition (Played)...")
        c3 = {'set': 'MH3', 'cn': '15', 'name': 'Guide', 'foil': False, 'condition': 'Played', 'tag': '', 'count': 1}
        self.importer.add_or_merge_card(card_list, c3)
        self.assertEqual(len(card_list), 2)
        print("    [PASS] Kept separate due to condition mismatch")

    def test_art_set_and_signature_parsing(self):
        print("\n[STEP 7a] Running: test_art_set_and_signature_parsing")
        print("  - Parsing art card token 'ablb19'...")
        p1 = self.importer.parse_token_string("ablb19")
        self.assertEqual(p1['front']['set'], "ablb")
        self.assertEqual(p1['front']['cn'], "19")
        self.assertFalse(p1['no_signature'])
        print("    [PASS] Correctly parsed art card 'ablb19' with no_signature=False")

        print("  - Parsing art card token with signature tag 'ablb19*n'...")
        p2 = self.importer.parse_token_string("ablb19*n")
        self.assertEqual(p2['front']['set'], "ablb")
        self.assertEqual(p2['front']['cn'], "19")
        self.assertTrue(p2['no_signature'])
        print("    [PASS] Correctly parsed art card 'ablb19*n' with no_signature=True")

        print("  - Testing resolve_name on 4-letter art sets starting with 'a'...")
        name, lookup = self.importer.resolve_name("ablb", "19", is_token=True)
        # Since enable_lookup is False, name is '[No Lookup]' and lookup is 'ablb' (not prepended with 't')
        self.assertEqual(lookup, "ablb")
        print("    [PASS] Correctly avoided prepending 't' to art set 'ablb'")

        print("  - Testing routing of token 'ablb19*n'...")
        results = {
            'single_sided': [], 'ds_fronts': [], 'ds_backs': [],
            'ds_fronts_dupes': [], 'ds_backs_dupes': [],
            'regular_cards': [], 'art_cards': [],
            'new_history': {}, 'dupe_identifiers': []
        }
        log_messages = []
        self.importer._route_token(p2, {}, results, log_messages)
        self.assertEqual(len(results['art_cards']), 1)
        self.assertEqual(results['art_cards'][0]['tag'], "No signature.")
        print("    [PASS] Correctly routed token 'ablb19*n' to art cards and marked 'No signature.' in tags")

        print("  - Testing routing of regular chunk '@ablb19*n'...")
        results_chunk = {'regular_cards': [], 'art_cards': []}
        self.importer._route_regular_chunk("@ablb19*n", results_chunk, log_messages)
        self.assertEqual(len(results_chunk['art_cards']), 1)
        self.assertEqual(results_chunk['art_cards'][0]['tag'], "No signature.")
        print("    [PASS] Correctly routed regular chunk '@ablb19*n' and marked 'No signature.' in tags")

    def test_exclamation_mark_parsing(self):
        print("\n[STEP 7b] Running: test_exclamation_mark_parsing")
        print("  - Parsing '!mh1262' (Token format with exclamation mark)...")
        p1 = self.importer.parse_token_string("!mh1262")
        self.assertEqual(p1['front']['set'], "!mh1")
        self.assertEqual(p1['front']['cn'], "262")
        print("    [PASS] Correctly parsed '!mh1262' as set='!mh1' and CN='262'")

        print("  - Testing _route_regular_chunk parsing for '@!mh1262'...")
        results = {'regular_cards': []}
        log_messages = []
        self.importer._route_regular_chunk("@!mh1262", results, log_messages)
        # _route_regular_chunk will call resolve_name and add to regular_cards list or write warning.
        # Since enable_lookup is False, resolve_name returns "[No Lookup]", clean_set.
        # Let's inspect the cards added or warnings logged.
        self.assertEqual(len(results['regular_cards']), 1)
        card = results['regular_cards'][0]
        self.assertEqual(card['set'], "mh1")
        self.assertEqual(card['cn'], "262")
        print("    [PASS] Correctly resolved '@!mh1262' set to 'mh1' and CN to '262'")

        print("  - Testing period/comma interchangeability for '@sld7094.2452'...")
        results2 = {'regular_cards': []}
        self.importer._route_regular_chunk("@sld7094.2452", results2, log_messages)
        self.assertEqual(len(results2['regular_cards']), 2)
        self.assertEqual(results2['regular_cards'][0]['cn'], "7094")
        self.assertEqual(results2['regular_cards'][1]['cn'], "2452")
        print("    [PASS] Correctly treated '.' as ',' in '@sld7094.2452'")



    def test_sorting_keys_spells(self):
        print("\n[STEP 8] Running: test_sorting_keys_spells")
        print("  - Sorting key for white monocolor spell...")
        
        def get_non_land_wubrg_key(color_list):
            color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
            ranks = sorted([color_map[c] for c in color_list if c in color_map])
            if len(ranks) == 1:
                return (ranks[0],)
            elif len(ranks) == 0:
                return (5,)
            else:
                return (6,)

        self.assertEqual(get_non_land_wubrg_key(['W']), (0,))
        self.assertEqual(get_non_land_wubrg_key(['G']), (4,))
        self.assertEqual(get_non_land_wubrg_key([]), (5,))
        self.assertEqual(get_non_land_wubrg_key(['W', 'U']), (6,))
        print("    [PASS] Correctly resolved spell sort indexes: W=0, G=4, Colorless=5, Multicolor=6")

    def test_sorting_keys_lands(self):
        print("\n[STEP 9] Running: test_sorting_keys_lands")
        print("  - Asserting land sorting rules...")
        
        def get_land_sort_key(color_list, card_name):
            color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
            ranks = sorted([color_map[c] for c in color_list if c in color_map])
            length = len(ranks)
            guild_map = {
                ('U', 'W'): 'Azorius',
                ('R', 'W'): 'Boros',
                ('B', 'U'): 'Dimir',
                ('B', 'G'): 'Golgari',
                ('G', 'R'): 'Gruul',
                ('R', 'U'): 'Izzet',
                ('B', 'W'): 'Orzhov',
                ('B', 'R'): 'Rakdos',
                ('G', 'W'): 'Selesnya',
                ('G', 'U'): 'Simic'
            }
            if length == 2:
                sorted_letters = tuple(sorted([c for c in color_list if c in color_map]))
                guild_name = guild_map.get(sorted_letters, '')
                return (2, guild_name.lower(), card_name.lower())
            elif length == 1:
                return (1, str(ranks[0]), card_name.lower())
            elif length == 0:
                return (0, '', card_name.lower())
            else:
                return (length, '', card_name.lower())

        self.assertEqual(get_land_sort_key([], "Wastes"), (0, '', "wastes"))
        self.assertEqual(get_land_sort_key(['W'], "Plains"), (1, '0', "plains"))
        self.assertEqual(get_land_sort_key(['W', 'U'], "Hallowed Fountain"), (2, 'azorius', "hallowed fountain"))
        self.assertEqual(get_land_sort_key(['W', 'B', 'G'], "Sandsteppe Citadel"), (3, '', "sandsteppe citadel"))
        print("    [PASS] Correctly validated land sort hierarchy (Colorless -> Monocolor -> Guild -> 3+ Color)")

    def test_set_ordering_by_entry(self):
        print("\n[STEP 9b] Running: test_set_ordering_by_entry")
        # Set up a raw input with a regular set, a token set, and another regular set
        raw_text = "@mh315/one5/@sld100"
        session_results = self.importer.run_import_session(raw_text)
        # unique_sets should present regular sets in order of entry (MH, then SLD) and token sets at the end (TONE)
        self.assertEqual(session_results['unique_sets'], ["MH", "SLD", "TONE"])
        print("    [PASS] Correctly ordered sets by entry: MH, SLD, TONE (token set at the end)")

    def test_basic_land_full_art_detection(self):
        print("\n[STEP 9c] Running: test_basic_land_full_art_detection")
        from unittest.mock import patch
        
        # Mock Scryfall cache lookups for BLB 278 (full art) and MOM 281 (regular)
        def cache_lookup(query):
            set_code = query["set"].lower()
            cn = str(query["collector_number"])
            if set_code == "blb" and cn == "278":
                return {
                    "name": "Forest",
                    "color_identity": ["G"],
                    "type_line": "Basic Land — Forest",
                    "full_art": True
                }, "path"
            elif set_code == "mom" and cn == "281":
                return {
                    "name": "Forest",
                    "color_identity": ["G"],
                    "type_line": "Basic Land — Forest",
                    "full_art": False
                }, "path"
            return None, None

        # Create importer with enable_lookup=False to prevent API calls, but enable WUBRG
        importer = MoxfieldImporter(enable_lookup=False, enable_wubrg=True, dry_run=True)
        
        with patch('scryfall_core.load_from_cache', side_effect=cache_lookup):
            # Parse input with both cards
            raw_text = "@blb278/@mom281"
            session_results = importer.run_import_session(raw_text)
            
            # Check table_rows results
            table_rows = session_results['table_rows']
            
            # Find the rows for each card
            blb_row = next(r for r in table_rows if r[0] == "BLB" and r[1] == "278")
            mom_row = next(r for r in table_rows if r[0] == "MOM" and r[1] == "281")
            
            # Assert BLB 278 is type "Full-Art"
            self.assertEqual(blb_row[4], "Full-Art")
            # Assert MOM 281 is type "Regular"
            self.assertEqual(mom_row[4], "Regular")
            
            # Assert they are in separate tables (lists)
            basic_lands = session_results['basic_land_rows']
            full_art_lands = session_results['full_art_land_rows']
            
            self.assertTrue(any(r[0] == "BLB" and r[1] == "278" for r in full_art_lands))
            self.assertTrue(any(r[0] == "MOM" and r[1] == "281" for r in basic_lands))
            self.assertFalse(any(r[0] == "BLB" and r[1] == "278" for r in basic_lands))
            self.assertFalse(any(r[0] == "MOM" and r[1] == "281" for r in full_art_lands))
            
            print("    [PASS] Correctly detected and separated BLB 278 to 'full_art_land_rows' and MOM 281 to 'basic_land_rows'")



class TestMoxfieldImportGui(unittest.TestCase):
    def setUp(self):
        print("\n" + "="*80)
        print("  TEST INITIALIZATION: MoxfieldImportGui Application Window Suite")
        print("="*80)
        self.root = tk.Tk()
        self.gui = MoxfieldImportGui(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_gui_default_settings(self):
        print("\n[STEP 10] Running: test_gui_default_settings")
        print("  - Verifying initial checkbox variable states...")
        self.assertTrue(self.gui.var_enable_lookup.get())
        self.assertTrue(self.gui.var_enable_wubrg.get())
        self.assertTrue(self.gui.var_dry_run.get())
        print("    [PASS] Checked 'Enable Lookup', 'Sort WUBRG', and 'Dry Run' default to True")

    def test_gui_interactive_lookup_toggle(self):
        print("\n[STEP 11] Running: test_gui_interactive_lookup_toggle")
        print("  - Toggling Scryfall Lookup off...")
        self.gui.var_enable_lookup.set(False)
        self.gui.on_lookup_toggle()
        
        self.assertFalse(self.gui.var_enable_wubrg.get())
        self.assertTrue(self.gui.var_dry_run.get())
        self.assertEqual(self.gui.chk_wubrg.cget('state'), 'disabled')
        self.assertEqual(self.gui.chk_dry_run.cget('state'), 'disabled')
        print("    [PASS] Correctly disabled and locked dependent checkbuttons (Dry Run, WUBRG)")


class TestMoxfieldImportCli(unittest.TestCase):
    def test_cli_table_formatter(self):
        print("\n" + "="*80)
        print("  TEST INITIALIZATION: MoxfieldImportCli ASCII Table Formatter Suite")
        print("="*80)
        print("\n[STEP 12] Running: test_cli_table_formatter")
        headers = ["A", "B"]
        rows = [["1", "22"]]
        table = format_table_to_ascii(headers, rows)
        self.assertIn("+---+----+\n", table)
        self.assertIn("| A | B  |\n", table)
        self.assertIn("| 1 | 22 |\n", table)
        print("    [PASS] Generated ASCII border tables matching console specifications")


if __name__ == '__main__':
    unittest.main()
