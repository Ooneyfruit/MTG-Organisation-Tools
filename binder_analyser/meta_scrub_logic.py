import os
import re
import json
import time
import urllib.request
import logging
import html as html_lib
from typing import Dict, List, Any, Optional

logger = logging.getLogger("moxfield_binder_analyser_meta")

# Formats to track
FORMATS = ['standard', 'pioneer', 'modern', 'pauper', 'legacy', 'vintage']

# 4 weeks in seconds (4 weeks * 7 days * 24 hours * 60 minutes * 60 seconds)
CACHE_EXPIRY_SECONDS = 4 * 7 * 24 * 60 * 60

def get_cache_dir() -> str:
    """Returns absolute path to cache/meta directory."""
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache", "meta"))
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def fetch_url(url: str) -> Optional[str]:
    """Fetches HTML/text from a URL with standard user agent header."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    req = urllib.request.Request(url, headers=headers)
    time.sleep(0.35)  # Polite delay
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None

def scrape_metagame_archetypes(html: str) -> List[Dict[str, Any]]:
    """Parses MTGGoldfish metagame page HTML to find top archetypes and meta shares."""
    tiles = html.split("<div class='archetype-tile'")
    results = []
    for tile in tiles[1:]:
        link_m = re.search(r'href="(/archetype/[^"#]*#paper)"[^>]*>([^<]+)</a>', tile)
        if not link_m:
            continue
        url = "https://www.mtggoldfish.com" + link_m.group(1)
        name = link_m.group(2).strip()
        
        pct_m = re.search(r'metagame-percentage[\s\S]*?statistic-value[^>]*>\s*([0-9.]+\s*%)', tile)
        pct = pct_m.group(1).strip() if pct_m else "0.0%"
        
        results.append({
            'name': name,
            'url': url,
            'pct': pct
        })
    return results

def parse_decklist_from_archetype_html(html: str) -> Dict[str, Any]:
    """
    Parses both the breakdown pool (for matching variations) and typical decklist
    from the archetype page.
    """
    parts = html.split('<h3>Sideboard</h3>')
    main_part = parts[0]
    side_part = parts[1] if len(parts) > 1 else ""
    
    card_pattern = re.compile(
        r"class='price-card-invisible-label'>([^<]+)</span>[\s\S]*?class='archetype-breakdown-featured-card-text'>\s*([0-9.]+)"
    )
    
    pool_main = {}
    for match in card_pattern.finditer(main_part):
        name = html_lib.unescape(match.group(1).strip())
        qty = int(round(float(match.group(2))))
        pool_main[name] = max(pool_main.get(name, 0), qty)
        
    pool_side = {}
    for match in card_pattern.finditer(side_part):
        name = html_lib.unescape(match.group(1).strip())
        qty = int(round(float(match.group(2))))
        pool_side[name] = max(pool_side.get(name, 0), qty)
        
    # Parse typical decklist
    typical_main = {}
    typical_side = {}
    m = re.search(r'id=[\'"]deck_input_deck[\'"]\s+value=[\'"]([^\'"]+)[\'"]', html)
    if not m:
        m = re.search(r'name=[\'"]deck_input\[deck\][\'"][\s\S]*?value=[\'"]([^\'"]+)[\'"]', html)
    if m:
        val = html_lib.unescape(m.group(1))
        current_section = typical_main
        lines = re.split(r'\r?\n', val)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower() == 'sideboard':
                current_section = typical_side
                continue
            match = re.match(r'^(\d+)\s+(.+)$', line)
            if match:
                qty = int(match.group(1))
                cname = match.group(2).strip()
                current_section[cname] = current_section.get(cname, 0) + qty
                
    # Fallback mappings
    if not pool_main and not pool_side:
        pool_main = typical_main.copy()
        pool_side = typical_side.copy()
    if not typical_main and not typical_side:
        typical_main = pool_main.copy()
        typical_side = pool_side.copy()
        
    return {
        'pool': {'main': pool_main, 'side': pool_side},
        'typical': {'main': typical_main, 'side': typical_side}
    }

def get_format_meta_data(format_name: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Retrieves metagame data (top archetypes and lists) for a format from the full list page.
    Checks cache first unless force_refresh is True or cache is expired (4 weeks).
    """
    format_clean = format_name.strip().lower()
    if format_clean not in FORMATS:
        raise ValueError(f"Unsupported format: {format_name}")
        
    cache_path = os.path.join(get_cache_dir(), f"{format_clean}_meta.json")
    
    # Check cache validity
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Schema upgrade: require at least 30 archetypes in the cache, otherwise force crawl from /full
            if len(data.get('archetypes', [])) >= 30:
                mtime = os.path.getmtime(cache_path)
                age = time.time() - mtime
                if age < CACHE_EXPIRY_SECONDS:
                    logger.info(f"Loaded cached metagame data for {format_clean} (age: {age/3600:.1f} hours)")
                    return data
        except Exception as e:
            logger.warning(f"Failed to read metagame cache for {format_clean}: {e}")
                
    # Crawl metagame data
    logger.info(f"Fetching metagame archetypes for format: {format_clean}")
    meta_url = f"https://www.mtggoldfish.com/metagame/{format_clean}/full"
    meta_html = fetch_url(meta_url)
    if not meta_html:
        logger.error(f"Failed to fetch metagame page for {format_clean}")
        return {'format': format_clean, 'archetypes': []}
        
    archetypes = scrape_metagame_archetypes(meta_html)
    logger.info(f"Found {len(archetypes)} archetypes for {format_clean}")
    
    # Initialize decks structures
    for arch in archetypes:
        arch['crawled'] = False
        arch['decklist'] = {'pool': {'main': {}, 'side': {}}, 'typical': {'main': {}, 'side': {}}}
        
    # Crawl the top 15 initially
    initial_crawl_count = min(15, len(archetypes))
    for idx in range(initial_crawl_count):
        arch = archetypes[idx]
        logger.info(f"[{idx+1}/{initial_crawl_count}] Crawling decklist for: {arch['name']}")
        arch_html = fetch_url(arch['url'])
        if arch_html:
            arch['decklist'] = parse_decklist_from_archetype_html(arch_html)
            arch['crawled'] = True
        else:
            arch['decklist'] = {'pool': {'main': {}, 'side': {}}, 'typical': {'main': {}, 'side': {}}}
            arch['crawled'] = False
            
    meta_data = {
        'format': format_clean,
        'updated_at': time.time(),
        'archetypes': archetypes
    }
    
    # Write cache
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, indent=2)
        logger.info(f"Saved metagame cache for {format_clean} to {cache_path}")
    except Exception as e:
        logger.error(f"Failed to save metagame cache for {format_clean}: {e}")
        
    return meta_data

def load_more_format_decks(format_name: str, count: int = 10) -> Dict[str, Any]:
    """
    Crawls decklists for the next 'count' archetypes that are not yet crawled.
    Updates the local cache file and returns the updated metadata.
    """
    format_clean = format_name.strip().lower()
    cache_path = os.path.join(get_cache_dir(), f"{format_clean}_meta.json")
    
    if not os.path.exists(cache_path):
        return get_format_meta_data(format_clean)
        
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load metagame cache to load more decks for {format_clean}: {e}")
        return {'format': format_clean, 'archetypes': []}
        
    archetypes = meta_data.get('archetypes', [])
    uncrawled_arches = [a for a in archetypes if not a.get('crawled')]
    
    if not uncrawled_arches:
        logger.info(f"All archetypes are already crawled for {format_clean}")
        return meta_data
        
    to_crawl = uncrawled_arches[:count]
    logger.info(f"Loading {len(to_crawl)} more decks for format: {format_clean}")
    
    for idx, arch in enumerate(to_crawl):
        logger.info(f"[{idx+1}/{len(to_crawl)}] Crawling more decklist for: {arch['name']}")
        arch_html = fetch_url(arch['url'])
        if arch_html:
            arch['decklist'] = parse_decklist_from_archetype_html(arch_html)
            arch['crawled'] = True
        else:
            arch['decklist'] = {'pool': {'main': {}, 'side': {}}, 'typical': {'main': {}, 'side': {}}}
            arch['crawled'] = False
            
    # Save back to cache
    meta_data['updated_at'] = time.time()
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, indent=2)
        logger.info(f"Updated metagame cache for {format_clean} (loaded more decks)")
    except Exception as e:
        logger.error(f"Failed to update metagame cache for {format_clean}: {e}")
        
    return meta_data
