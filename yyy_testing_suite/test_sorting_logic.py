import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from _core_tools.sorting_logic import (
    get_non_land_wubrg_key,
    get_land_sort_key,
    get_card_wubrg_sort_key
)

class TestSortingLogic(unittest.TestCase):
    
    def test_non_land_wubrg_key_monocolor(self):
        self.assertEqual(get_non_land_wubrg_key(['W']), (0,))
        self.assertEqual(get_non_land_wubrg_key(['U']), (1,))
        self.assertEqual(get_non_land_wubrg_key(['B']), (2,))
        self.assertEqual(get_non_land_wubrg_key(['R']), (3,))
        self.assertEqual(get_non_land_wubrg_key(['G']), (4,))

    def test_non_land_wubrg_key_colorless(self):
        self.assertEqual(get_non_land_wubrg_key([]), (5,))
        self.assertEqual(get_non_land_wubrg_key(['C']), (5,))

    def test_non_land_wubrg_key_multicolor(self):
        self.assertEqual(get_non_land_wubrg_key(['W', 'U']), (6,))
        self.assertEqual(get_non_land_wubrg_key(['R', 'G', 'B']), (6,))

    def test_land_sort_key_colorless(self):
        self.assertEqual(get_land_sort_key([], "Wasteland"), (0, '', 'wasteland'))

    def test_land_sort_key_monocolor(self):
        self.assertEqual(get_land_sort_key(['W'], "Plains"), (1, '0', 'plains'))
        self.assertEqual(get_land_sort_key(['G'], "Forest"), (1, '4', 'forest'))

    def test_land_sort_key_guilds(self):
        self.assertEqual(get_land_sort_key(['U', 'W'], "Hallowed Fountain"), (2, 'azorius', 'hallowed fountain'))
        self.assertEqual(get_land_sort_key(['G', 'B'], "Overgrown Tomb"), (2, 'golgari', 'overgrown tomb'))
        self.assertEqual(get_land_sort_key(['U', 'X'], "weird land"), (1, '1', 'weird land'))

    def test_land_sort_key_multicolor(self):
        self.assertEqual(get_land_sort_key(['W', 'U', 'B'], "Arcane Sanctum"), (3, '', 'arcane sanctum'))
        self.assertEqual(get_land_sort_key(['W', 'U', 'B', 'R'], "Omnath's Land"), (4, '', "omnath's land"))

    def test_card_wubrg_sort_key_groups(self):
        spell_key = get_card_wubrg_sort_key("Lightning Bolt", "Instant", ['R'])
        self.assertEqual(spell_key[0], 0)
        
        nonbasic_key = get_card_wubrg_sort_key("Hallowed Fountain", "Land — Plains Island", ['W', 'U'])
        self.assertEqual(nonbasic_key[0], 1)
        
        basic_key = get_card_wubrg_sort_key("Forest", "Basic Land — Forest", ['G'])
        self.assertEqual(basic_key[0], 2)

    def test_overall_sorting_hierarchy(self):
        cards = [
            {"name": "Forest", "type": "Basic Land", "colors": ['G']},
            {"name": "Tundra", "type": "Land", "colors": ['W', 'U']},
            {"name": "Sol Ring", "type": "Artifact", "colors": []},
            {"name": "Counterspell", "type": "Instant", "colors": ['U']},
            {"name": "Plains", "type": "Basic Land", "colors": ['W']}
        ]
        
        sorted_cards = sorted(cards, key=lambda c: get_card_wubrg_sort_key(c["name"], c["type"], c["colors"]))
        
        expected_order = [
            "Counterspell",
            "Sol Ring",
            "Tundra",
            "Plains",
            "Forest"
        ]
        
        sorted_names = [c["name"] for c in sorted_cards]
        self.assertEqual(sorted_names[0], "Counterspell")
        self.assertEqual(sorted_names[1], "Sol Ring")
        self.assertEqual(sorted_names[2], "Tundra")
        self.assertEqual(sorted_names[3], "Plains")
        self.assertEqual(sorted_names[4], "Forest")

    def test_colored_artifacts_sorting(self):
        # Dreg Recycler is a black artifact creature (colors: ['B'])
        # Sol Ring is a colorless artifact (colors: [])
        # Twin-Silk Spider is a green creature (colors: ['G'])
        cards = [
            {"name": "Twin-Silk Spider", "type": "Creature — Spider", "colors": ['G']},
            {"name": "Dreg Recycler", "type": "Artifact Creature — Zombie", "colors": ['B']},
            {"name": "Sol Ring", "type": "Artifact", "colors": []}
        ]
        
        sorted_cards = sorted(cards, key=lambda c: get_card_wubrg_sort_key(c["name"], c["type"], c["colors"]))
        sorted_names = [c["name"] for c in sorted_cards]
        
        # Expected WUBRG order for non-lands: Black (B) -> Green (G) -> Colorless (C)
        self.assertEqual(sorted_names, ["Dreg Recycler", "Twin-Silk Spider", "Sol Ring"])

    def test_sorting_ignores_hyphens(self):
        # Without ignoring hyphens: Blade-Tribe Berserkers (B-l-a-d-e--...) comes before Bladeback Sliver (B-l-a-d-e-b-...)
        # With ignoring hyphens: Bladeback Sliver (bladeback) comes before Blade-Tribe Berserkers (bladetribe)
        cards = [
            {"name": "Blade-Tribe Berserkers", "type": "Creature — Human Berserker", "colors": ['R']},
            {"name": "Bladeback Sliver", "type": "Creature — Sliver", "colors": ['R']},
            {"name": "Alania's Pathmaker", "type": "Creature — Otter Knight", "colors": ['R']}
        ]
        sorted_cards = sorted(cards, key=lambda c: get_card_wubrg_sort_key(c["name"], c["type"], c["colors"]))
        sorted_names = [c["name"] for c in sorted_cards]
        
        expected = ["Alania's Pathmaker", "Bladeback Sliver", "Blade-Tribe Berserkers"]
        self.assertEqual(sorted_names, expected)

if __name__ == "__main__":
    unittest.main()
