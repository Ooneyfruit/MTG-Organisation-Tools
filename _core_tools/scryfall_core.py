import os
import re
import sys
import json
import time
import datetime
import requests

# --- CONFIGURATION ---
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache"))
DELAY_SECONDS = 0.3  # Polite delay between API requests

SCRYFALL_HEADERS = {
    'User-Agent': 'MTGColorCounter/2.0 (Automated Collection Manager; dougl@example.com)',
    'Accept': 'application/json;q=0.9,*/*;q=0.8'
}

# --- TLS FIX ---
# Avoid certificate resolution issues on environments with postgresql environment variables
http_session = requests.Session()
http_session.trust_env = False

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def sanitize_filename(name):
    # Keep only alphanumeric characters and underscores to make safe filenames
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')

def get_cache_paths(card_parsed):
    paths = []
    # Determine set folder
    s_set = None
    if card_parsed.get('set'):
        s_set = sanitize_filename(card_parsed['set'])

    # 1. By set and collector number
    if s_set and card_parsed.get('collector_number'):
        s_cn = sanitize_filename(card_parsed['collector_number'])
        paths.append((os.path.join(s_set, f"set_{s_set}_{s_cn}.json"), "scryfall_card_by_set_and_collector_number", {
            "set": card_parsed['set'],
            "collector_number": card_parsed['collector_number']
        }))
    # 2. By exact name and set
    if card_parsed.get('name') and s_set:
        s_name = sanitize_filename(card_parsed['name'])
        paths.append((os.path.join(s_set, f"name_set_{s_name}_{s_set}.json"), "scryfall_card_by_exact_name_and_set", {
            "name": card_parsed['name'],
            "set": card_parsed['set']
        }))
    # 3. By exact name
    if card_parsed.get('name'):
        s_name = sanitize_filename(card_parsed['name'])
        if s_set:
            paths.append((os.path.join(s_set, f"name_{s_name}.json"), "scryfall_card_by_exact_name", {
                "name": card_parsed['name']
            }))
        paths.append((os.path.join("_general", f"name_{s_name}.json"), "scryfall_card_by_exact_name", {
            "name": card_parsed['name']
        }))
    return paths

def load_from_cache(card_parsed):
    ensure_cache_dir()
    cache_variants = get_cache_paths(card_parsed)
    for rel_path, query_type, params in cache_variants:
        filepath = os.path.join(CACHE_DIR, rel_path)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "scryfall_data" in data and "type_line" in data["scryfall_data"]:
                        scry_data = data["scryfall_data"]
                        if "prices" not in scry_data or "full_art" not in scry_data:
                            # Out of date cache schema; return None to trigger fresh fetch
                            continue
                        return scry_data, filepath
            except Exception:
                pass
    return None, None

def save_to_cache(card_parsed, scryfall_data, query_type_used, query_params_used):
    ensure_cache_dir()
    cache_variants = get_cache_paths(card_parsed)
    if not cache_variants:
        return
    
    rel_path_to_save = None
    for rel_path, query_type, params in cache_variants:
        if query_type == query_type_used:
            rel_path_to_save = rel_path
            break
            
    if not rel_path_to_save:
        rel_path_to_save = cache_variants[0][0]

    filepath = os.path.join(CACHE_DIR, rel_path_to_save)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Keep only the essential fields
    narrow_scryfall_data = {
        "name": scryfall_data.get("name"),
        "color_identity": scryfall_data.get("color_identity", []),
        "type_line": scryfall_data.get("type_line", ""),
        "prices": scryfall_data.get("prices", {}),
        "full_art": scryfall_data.get("full_art", False)
    }
    
    endpoint_templates = {
        "scryfall_card_by_set_and_collector_number": "https://api.scryfall.com/cards/{set}/{collector_number}",
        "scryfall_card_by_exact_name_and_set": "https://api.scryfall.com/cards/named?exact={name}&set={set}",
        "scryfall_card_by_exact_name": "https://api.scryfall.com/cards/named?exact={name}"
    }
    
    cache_payload = {
        "query_metadata": {
            "query_type": query_type_used,
            "endpoint_template": endpoint_templates.get(query_type_used, ""),
            "query_params": query_params_used,
            "queried_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        },
        "scryfall_data": narrow_scryfall_data
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cache_payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to write cache file {rel_path_to_save}: {e}", file=sys.stderr)

def fetch_cards_batch_from_scryfall(batch_cards):
    """
    Sends a batch of parsed card queries to the Scryfall POST /cards/collection endpoint.
    Filters the results and writes them to the cache.
    """
    identifiers = []
    query_infos = []
    
    for card in batch_cards:
        if card.get('set') and card.get('collector_number'):
            identifiers.append({
                "set": card['set'],
                "collector_number": card['collector_number']
            })
            query_infos.append((card, "scryfall_card_by_set_and_collector_number", {
                "set": card['set'],
                "collector_number": card['collector_number']
            }))
        elif card.get('name') and card.get('set'):
            identifiers.append({
                "name": card['name'],
                "set": card['set']
            })
            query_infos.append((card, "scryfall_card_by_exact_name_and_set", {
                "name": card['name'],
                "set": card['set']
            }))
        elif card.get('name'):
            identifiers.append({
                "name": card['name']
            })
            query_infos.append((card, "scryfall_card_by_exact_name", {
                "name": card['name']
            }))
            
    if not identifiers:
        return
        
    print(f"--> Batch querying Scryfall for {len(identifiers)} card(s)...")
    time.sleep(DELAY_SECONDS)
    
    url = "https://api.scryfall.com/cards/collection"
    headers = {
        **SCRYFALL_HEADERS,
        "Content-Type": "application/json"
    }
    
    try:
        response = http_session.post(url, json={"identifiers": identifiers}, headers=headers)
        if response.status_code != 200:
            print(f"Error: Scryfall API returned status code {response.status_code}", file=sys.stderr)
            try:
                err_data = response.json()
                print(f"Details: {err_data.get('details', '')}", file=sys.stderr)
            except Exception:
                pass
            return
            
        response_data = response.json()
        returned_cards = response_data.get('data', [])
        
        # Match returned cards back to query_infos
        for scryfall_card in returned_cards:
            matched_queries = []
            scry_name = scryfall_card.get('name', '').lower()
            scry_set = scryfall_card.get('set', '').lower()
            scry_cn = str(scryfall_card.get('collector_number', '')).lower()
            
            for card_parsed, q_type, q_params in query_infos:
                is_match = False
                if q_type == "scryfall_card_by_set_and_collector_number":
                    if q_params['set'].lower() == scry_set and str(q_params['collector_number']).lower() == scry_cn:
                        is_match = True
                elif q_type == "scryfall_card_by_exact_name_and_set":
                    q_name = q_params['name'].lower()
                    if (q_name == scry_name or scry_name.startswith(q_name + " //")) and q_params['set'].lower() == scry_set:
                        is_match = True
                elif q_type == "scryfall_card_by_exact_name":
                    q_name = q_params['name'].lower()
                    if q_name == scry_name or scry_name.startswith(q_name + " //"):
                        is_match = True
                        
                if is_match:
                    matched_queries.append((card_parsed, q_type, q_params))
            
            if matched_queries:
                for card_parsed, q_type, q_params in matched_queries:
                    save_to_cache(card_parsed, scryfall_card, q_type, q_params)
            else:
                fallback_params = {
                    "set": scryfall_card.get('set', ''),
                    "collector_number": scryfall_card.get('collector_number', '')
                }
                save_to_cache(scryfall_card, scryfall_card, "scryfall_card_by_set_and_collector_number", fallback_params)
                
    except Exception as e:
        print(f"Network error querying Scryfall batch: {e}", file=sys.stderr)

def resolve_cards(cards):
    """
    Resolves details for a list of parsed card dicts.
    First loads from local cache, then fetches uncached cards in batches of 75.
    """
    uncached = []
    cached_count = 0
    
    # 1. Check Cache
    for card in cards:
        data, path = load_from_cache(card)
        if data:
            cached_count += 1
        else:
            uncached.append(card)
            
    print(f"Cache status: {cached_count} card(s) found in cache, {len(uncached)} card(s) need to be fetched.")
    
    # 2. Batch Query Uncached Cards
    if uncached:
        BATCH_SIZE = 75
        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i:i+BATCH_SIZE]
            fetch_cards_batch_from_scryfall(batch)

def load_set_metadata_from_cache(set_code):
    ensure_cache_dir()
    set_code = set_code.lower().lstrip('!')
    filepath = os.path.join(CACHE_DIR, set_code, f"set_metadata_{set_code}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_set_metadata_to_cache(set_code, data):
    ensure_cache_dir()
    set_code = set_code.lower().lstrip('!')
    filepath = os.path.join(CACHE_DIR, set_code, f"set_metadata_{set_code}.json")
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def fetch_set_metadata(set_code):
    clean_code = set_code.lower().lstrip('!')
    data = load_set_metadata_from_cache(clean_code)
    if data:
        return data
    
    url = f"https://api.scryfall.com/sets/{clean_code}"
    time.sleep(DELAY_SECONDS)
    try:
        response = http_session.get(url, headers=SCRYFALL_HEADERS)
        if response.status_code == 200:
            set_data = response.json()
            narrow_data = {
                "code": set_data.get("code"),
                "name": set_data.get("name"),
                "set_type": set_data.get("set_type")
            }
            save_set_metadata_to_cache(clean_code, narrow_data)
            return narrow_data
    except Exception:
        pass
    return None

def is_token_set(set_code):
    clean_code = set_code.lower().lstrip('!')
    meta = fetch_set_metadata(clean_code)
    if meta:
        return meta.get("set_type") in ["token", "memorabilia"]
    return clean_code.startswith('t') and len(clean_code) >= 4
