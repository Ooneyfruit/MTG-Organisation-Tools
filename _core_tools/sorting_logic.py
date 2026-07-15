from typing import List, Tuple

# --- GUILD MAPS FOR LAND SORTING ---
GUILD_MAP = {
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

def get_non_land_wubrg_key(color_list: List[str]) -> Tuple[int, ...]:
    """Returns a sorting key for non-land cards based on WUBRG color identity."""
    color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
    ranks = sorted([color_map[c] for c in color_list if c in color_map])
    if len(ranks) == 1:
        return (ranks[0],)
    elif len(ranks) == 0:
        return (5,) # Colorless
    else:
        return (6,) # Multicolor

def get_land_sort_key(color_list: List[str], card_name: str) -> Tuple[int, str, str]:
    """Returns a sorting key for land cards (grouped by colorless, mono, guild, shard/wedge)."""
    color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
    ranks = sorted([color_map[c] for c in color_list if c in color_map])
    length = len(ranks)
    
    clean_name = card_name.lower().replace("-", "")
    
    if length == 2:
        sorted_letters = tuple(sorted([c for c in color_list if c in color_map]))
        guild_name = GUILD_MAP.get(sorted_letters, '')
        return (2, guild_name.lower(), clean_name)
    elif length == 1:
        return (1, str(ranks[0]), clean_name)
    elif length == 0:
        return (0, '', clean_name)
    else:
        return (length, '', clean_name)

def get_card_wubrg_sort_key(name: str, type_line: str, color_identity: List[str]) -> Tuple[int, tuple, str]:
    """
    Unified sorting key generator for WUBRG ordering.
    Groups:
      0: Spells (sorted by WUBRG, then Name)
      1: Non-basic lands (sorted by WUBRG/Guild, then Name)
      2: Basic lands (sorted by WUBRG, then Name)
    """
    is_land = "land" in type_line.lower()
    is_basic = "basic" in type_line.lower() and is_land
    
    clean_name = name.lower().replace("-", "")
    
    if is_basic:
        return (2, get_land_sort_key(color_identity, name), clean_name)
    elif is_land:
        return (1, get_land_sort_key(color_identity, name), clean_name)
    else:
        # We wrap get_non_land_wubrg_key to match tuple comparison depth
        return (0, get_non_land_wubrg_key(color_identity), clean_name)
