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

    def test_run_analysis_success(self):
        if not self.test_csv.exists():
            self.skipTest(f"Test CSV not found at {self.test_csv}")
            
        summary = self.analyser.run_analysis(str(self.test_csv), target_set="dsc")
        self.assertIn("Total Rows: 6", summary)
        self.assertIn("Total Cards: 13", summary)
        self.assertIn("TARGET SET: DSC", summary)
        self.assertIn("Total Cards for 'DSC': 6", summary)

if __name__ == "__main__":
    unittest.main()
