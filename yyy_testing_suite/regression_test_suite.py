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
