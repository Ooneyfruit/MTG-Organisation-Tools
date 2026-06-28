import os
import sys
import json
import shutil
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from _core_tools.scryfall_core import (
    CACHE_DIR,
    sanitize_filename,
    get_cache_paths,
    load_from_cache,
    save_to_cache,
    load_set_metadata_from_cache,
    save_set_metadata_to_cache
)

class TestScryfallCore(unittest.TestCase):

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("Aberrant"), "aberrant")
        self.assertEqual(sanitize_filename("An Offer You Can't Refuse"), "an_offer_you_can_t_refuse")
        self.assertEqual(sanitize_filename("  Thalia, Guardian of Thraben  "), "thalia_guardian_of_thraben")
        self.assertEqual(sanitize_filename("Black // White"), "black_white")

    def test_get_cache_paths_set_and_cn(self):
        card = {
            "name": "Aberrant",
            "set": "40k",
            "collector_number": "86"
        }
        paths = get_cache_paths(card)
        self.assertGreaterEqual(len(paths), 3)
        self.assertEqual(paths[0][0], os.path.join("40k", "set_40k_86.json"))
        self.assertEqual(paths[0][1], "scryfall_card_by_set_and_collector_number")
        self.assertEqual(paths[1][0], os.path.join("40k", "name_set_aberrant_40k.json"))
        self.assertEqual(paths[1][1], "scryfall_card_by_exact_name_and_set")

    def test_get_cache_paths_name_only(self):
        card = {
            "name": "Aberrant"
        }
        paths = get_cache_paths(card)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0][0], os.path.join("_general", "name_aberrant.json"))
        self.assertEqual(paths[0][1], "scryfall_card_by_exact_name")

    def test_cache_load_and_save_workflow(self):
        card = {
            "name": "Test Cache Card",
            "set": "TCC",
            "collector_number": "1"
        }
        
        cache_paths = get_cache_paths(card)
        for rel_path, _, _ in cache_paths:
            filepath = os.path.join(CACHE_DIR, rel_path)
            if os.path.exists(filepath):
                os.remove(filepath)
                
        data, path = load_from_cache(card)
        self.assertIsNone(data)
        self.assertIsNone(path)
        
        scryfall_data = {
            "name": "Test Cache Card",
            "color_identity": ["W"],
            "type_line": "Creature — Soldier",
            "prices": {"usd": "0.50"},
            "full_art": False,
            "extra_unneeded_field": "discard me"
        }
        
        save_to_cache(
            card_parsed=card,
            scryfall_data=scryfall_data,
            query_type_used="scryfall_card_by_set_and_collector_number",
            query_params_used={"set": "TCC", "collector_number": "1"}
        )
        
        loaded_data, loaded_path = load_from_cache(card)
        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data["name"], "Test Cache Card")
        self.assertEqual(loaded_data["color_identity"], ["W"])
        self.assertEqual(loaded_data["type_line"], "Creature — Soldier")
        self.assertEqual(loaded_data["prices"], {"usd": "0.50"})
        self.assertFalse(loaded_data["full_art"])
        self.assertNotIn("extra_unneeded_field", loaded_data)
        
        if loaded_path and os.path.exists(loaded_path):
            os.remove(loaded_path)
            try:
                os.rmdir(os.path.dirname(loaded_path))
            except Exception:
                pass

    def test_cache_validation_heuristics(self):
        card = {
            "name": "Old Card",
            "set": "OLD",
            "collector_number": "5"
        }
        
        paths = get_cache_paths(card)
        filepath = os.path.join(CACHE_DIR, paths[0][0])
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        old_payload = {
            "query_metadata": {
                "query_type": "scryfall_card_by_set_and_collector_number"
            },
            "scryfall_data": {
                "name": "Old Card",
                "color_identity": ["B"],
                "type_line": "Sorcery"
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_payload, f)
            
        loaded_data, loaded_path = load_from_cache(card)
        self.assertIsNone(loaded_data)
        self.assertIsNone(loaded_path)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            try:
                os.rmdir(os.path.dirname(filepath))
            except Exception:
                pass

    def test_set_metadata_caching(self):
        set_code = "TST"
        set_data = {
            "code": "tst",
            "name": "Test Set Metadata",
            "set_type": "expansion"
        }
        
        save_set_metadata_to_cache(set_code, set_data)
        
        loaded_meta = load_set_metadata_from_cache(set_code)
        self.assertIsNotNone(loaded_meta)
        self.assertEqual(loaded_meta["code"], "tst")
        self.assertEqual(loaded_meta["name"], "Test Set Metadata")
        self.assertEqual(loaded_meta["set_type"], "expansion")
        
        filepath = os.path.join(CACHE_DIR, set_code.lower(), f"set_metadata_{set_code.lower()}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            try:
                os.rmdir(os.path.dirname(filepath))
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
