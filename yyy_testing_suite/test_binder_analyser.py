import os
import sys
import unittest
from pathlib import Path

# Adjust sys.path to import binder_analyser logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent

if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

BINDER_ANALYSER_DIR = PARENT_DIR / "binder_analyser"
if str(BINDER_ANALYSER_DIR) not in sys.path:
    sys.path.append(str(BINDER_ANALYSER_DIR))

import binder_analyser_logic as logic

class TestBinderAnalyser(unittest.TestCase):
    def setUp(self):
        self.test_csv = SCRIPT_DIR / "binder_analyser" / "test_data" / "test_collection.csv"
        self.analyser = logic.BinderAnalyser()

    def test_set_counter_metric(self):
        metric = logic.SetCounterMetric()
        
        # Test basic processing
        metric.process_card({'name': 'Card A', 'edition': 'mh2', 'count': '3'})
        metric.process_card({'name': 'Card B', 'edition': 'MH2', 'count': 1})
        metric.process_card({'name': 'Card C', 'edition': 'dsc', 'count': 'invalid'})
        metric.process_card({'name': 'Card D', 'edition': '', 'count': 2})
        
        data = metric.get_data()
        self.assertEqual(data.get('mh2'), 4)
        self.assertEqual(data.get('dsc'), 1)
        self.assertEqual(data.get('unknown'), 2)
        
        summary = metric.get_summary()
        self.assertIn("MH2", summary)
        self.assertIn("DSC", summary)
        
        table_data = metric.get_table_data()
        self.assertIn("Set Counts", table_data)
        headers, rows = table_data["Set Counts"]
        self.assertEqual(headers, ["Set Code", "Total Cards"])
        self.assertIn(["MH2", 4], rows)

    def test_artist_spotlight_metric(self):
        metric = logic.ArtistSpotlightMetric()
        
        orig_load = logic.scryfall_core.load_from_cache
        try:
            logic.scryfall_core.load_from_cache = lambda card: ({
                'name': card['name'],
                'artist': 'John Avon' if card['name'] == 'Card A' else 'Rebecca Guay',
                'color_identity': [],
                'type_line': 'Land',
                'prices': {},
                'full_art': False,
                'frame_effects': [],
                'promo_types': [],
                'promo': False,
                'border_color': 'black',
                'rarity': 'rare',
                'edhrec_rank': None
            }, 'dummy_path')
            
            metric.process_card({'name': 'Card A', 'edition': 'mh2', 'count': 2})
            metric.process_card({'name': 'Card B', 'edition': 'mh2', 'count': 1})
            
            data = metric.get_data()
            self.assertEqual(data.get('John Avon'), 2)
            self.assertEqual(data.get('Rebecca Guay'), 1)
            
            table_data = metric.get_table_data()
            self.assertIn("Artist Counts", table_data)
            headers, rows = table_data["Artist Counts"]
            self.assertEqual(headers, ["Artist", "Total Cards"])
            self.assertIn(["John Avon", 2], rows)
            
        finally:
            logic.scryfall_core.load_from_cache = orig_load

    def test_rich_staple_audit_metric(self):
        metric = logic.RichStapleAuditMetric()
        
        orig_load = logic.scryfall_core.load_from_cache
        orig_prices = logic.yellow_binder_logic.get_card_prices
        
        try:
            logic.scryfall_core.load_from_cache = lambda card: ({
                'name': card['name'],
                'artist': 'John Avon',
                'color_identity': [],
                'type_line': 'Sorcery',
                'edhrec_rank': card.get('edhrec_rank'),
                'rarity': card.get('rarity', 'common'),
                'prices': {},
                'full_art': False,
                'frame_effects': [],
                'promo_types': [],
                'promo': False,
                'border_color': 'black'
            }, 'dummy_path')
            
            def mock_get_card_prices(scry_data, foil):
                name = scry_data['name']
                if name == 'HighValue':
                    return (5.0, 5.0, 5.0) if foil else (3.0, 3.0, 3.0)
                elif name == 'Budget':
                    return 0.5, 0.5, 0.5
                elif name == 'BulkRare':
                    return 0.5, 0.5, 0.5
                elif name == 'HiddenGem':
                    return 1.5, 1.5, 1.5
                return 0.1, 0.1, 0.1
                
            logic.yellow_binder_logic.get_card_prices = mock_get_card_prices
            
            # Process mock cards
            # 1. High-Value Staples: rank <= 1500, GBP >= 4.00
            # Test duplicate merging:
            # - 1x Foil HighValue at MH2 (price 5.0)
            # - 2x Non-Foil HighValue at LTR (price 3.0)
            # Merged count should be 3, average price 4.0, foil 'Mixed', set 'LTR, MH2'
            metric.process_card({'name': 'HighValue', 'edition': 'mh2', 'count': 1, 'edhrec_rank': 100, 'rarity': 'mythic', 'Foil': 'foil'})
            metric.process_card({'name': 'HighValue', 'edition': 'ltr', 'count': 2, 'edhrec_rank': 100, 'rarity': 'mythic', 'Foil': ''})
            
            # 2. Budget Staples: rank <= 1500, GBP < 0.80
            metric.process_card({'name': 'Budget', 'edition': 'mh2', 'count': 2, 'edhrec_rank': 200, 'rarity': 'common'})
            # 3. Bulk Rares: rarity is rare/mythic, rank > 5000, GBP < 0.80
            metric.process_card({'name': 'BulkRare', 'edition': 'mh2', 'count': 1, 'edhrec_rank': 6000, 'rarity': 'rare'})
            # 4. Hidden Gems: common/uncommon, rank <= 3000, GBP >= 0.80
            metric.process_card({'name': 'HiddenGem', 'edition': 'mh2', 'count': 1, 'edhrec_rank': 2500, 'rarity': 'uncommon'})
            
            data = metric.get_data()
            categories = data['categories']
            self.assertEqual(categories.get('High-Value Staples'), 3)
            self.assertEqual(categories.get('Budget Staples'), 2)
            self.assertEqual(categories.get('Bulk Rares'), 1)
            self.assertEqual(categories.get('Hidden Gems'), 1)
            
            summary = metric.get_summary()
            self.assertIn("Binder Utility Rate: 85.7%", summary)
            self.assertIn("High-Value Staples (Top 15):", summary)
            
            table_data = metric.get_table_data()
            self.assertIn("All Cards", table_data)
            self.assertIn("High-Value Staples", table_data)
            headers, rows = table_data["All Cards"]
            self.assertIn("Rank Index", headers)
            # Find the merged row for HighValue
            hv_row = [r for r in rows if r[1] == 'HighValue'][0]
            self.assertEqual(hv_row[0], 1) # Rank Index
            self.assertEqual(hv_row[2], 'LTR, MH2') # Set
            self.assertEqual(hv_row[4], 'Mixed') # Foil
            self.assertEqual(hv_row[5], 3) # Qty
            self.assertEqual(hv_row[6], 4.0) # Avg GBP price
            self.assertEqual(hv_row[-1], 'High-Value Staples')
            
        finally:
            logic.scryfall_core.load_from_cache = orig_load
            logic.yellow_binder_logic.get_card_prices = orig_prices

    def test_run_analysis_success(self):
        if not self.test_csv.exists():
            self.skipTest(f"Test CSV not found at {self.test_csv}")
            
        summary = self.analyser.run_analysis(str(self.test_csv), target_set="dsc")
        self.assertIn("Total Rows: 6", summary)
        self.assertIn("Total Cards: 13", summary)
        self.assertIn("TARGET SET: DSC", summary)
        self.assertIn("Total Cards for 'DSC': 6", summary)

    def test_ignore_proxies(self):
        temp_csv = SCRIPT_DIR / "binder_analyser" / "test_data" / "temp_proxy_test.csv"
        try:
            with open(temp_csv, 'w', encoding='utf-8') as f:
                f.write('"Count","Name","Edition","Proxy"\n')
                f.write('"1","Card Real","mh2","False"\n')
                f.write('"3","Card Proxy","mh2","True"\n')
            
            # Run without ignoring
            summary_all = self.analyser.run_analysis(str(temp_csv), ignore_proxies=False)
            self.assertIn("Total Cards: 4", summary_all)
            
            # Run with ignoring
            summary_ignored = self.analyser.run_analysis(str(temp_csv), ignore_proxies=True)
            self.assertIn("Total Cards: 1", summary_ignored)
            
        finally:
            if temp_csv.exists():
                os.remove(temp_csv)

    def test_meta_fulfillment_metric(self):
        metric = logic.MetaFulfillmentMetric()
        
        orig_get_meta = logic.meta_scrub_logic.get_format_meta_data
        try:
            logic.meta_scrub_logic.get_format_meta_data = lambda fmt: {
                'format': fmt,
                'archetypes': [
                    {
                        'name': 'Mock Archetype A',
                        'pct': '10.0%',
                        'url': 'http://mock/a',
                        'crawled': True,
                        'decklist': {
                            'main': {'Llanowar Elves': 4, 'Lightning Bolt': 4, 'Forest': 10},
                            'side': {'Rest in Peace': 2, 'Pyroblast': 2, 'Plains': 3}
                        }
                    }
                ]
            }
            
            # User binder has 4 Forest and 2 Plains, but they should be ignored
            metric.process_card({'name': 'Llanowar Elves', 'count': 4})
            metric.process_card({'name': 'Lightning Bolt', 'count': 2})
            metric.process_card({'name': 'Rest in Peace', 'count': 2})
            metric.process_card({'name': 'Forest', 'count': 4})
            metric.process_card({'name': 'Plains', 'count': 2})
            
            data = metric.get_data()
            self.assertIn('results', data)
            self.assertIn('standard', data['results'])
            
            standard_results = data['results']['standard']
            self.assertEqual(len(standard_results), 1)
            
            arch = standard_results[0]
            self.assertEqual(arch['name'], 'Mock Archetype A')
            self.assertEqual(arch['matched_score'], 8)
            self.assertEqual(arch['target_total'], 12)  # 8 main + 4 side (basics excluded)
            self.assertAlmostEqual(arch['fulfillment_pct'], 66.6666, places=2)
            
            self.assertEqual(arch['main_missing'].get('Lightning Bolt'), 2)
            self.assertNotIn('Llanowar Elves', arch['main_missing'])
            self.assertNotIn('Forest', arch['main_missing'])
            self.assertEqual(arch['side_missing'].get('Pyroblast'), 2)
            self.assertNotIn('Rest in Peace', arch['side_missing'])
            self.assertNotIn('Plains', arch['side_missing'])
            
            # Assert matched cards
            self.assertEqual(arch['main_matched_cards'].get('Llanowar Elves'), 4)
            self.assertEqual(arch['main_matched_cards'].get('Lightning Bolt'), 2)
            self.assertNotIn('Forest', arch['main_matched_cards'])
            self.assertEqual(arch['side_matched_cards'].get('Rest in Peace'), 2)
            self.assertNotIn('Plains', arch['side_matched_cards'])
            
            summary = metric.get_summary()
            self.assertIn("Mock Archetype A", summary)
            
            table_data = metric.get_table_data()
            self.assertIn("Standard Meta", table_data)
            headers, rows = table_data["Standard Meta"]
            self.assertIn("Fulfillment", headers)
            self.assertEqual(rows[0][1], "Mock Archetype A")
            self.assertEqual(rows[0][3], "8 / 12")
            
            # Assert load_more_decks works and resets post_processed flag
            metric.load_more_decks('standard', 1)
            self.assertFalse(metric.post_processed)
            
        finally:
            logic.meta_scrub_logic.get_format_meta_data = orig_get_meta

if __name__ == "__main__":
    sys.exit(unittest.main())
