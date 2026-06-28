import os
import re
import csv
import sys
import json
import datetime
import logging
import requests

# --- CONFIGURATION ---
INPUT_FILE = "input.txt"
OUTPUT_DIR = "outputs"
CACHE_DIR = "scryfall_cache"
DUPE_DIR = "duplicate_check"
LOG_DIR = "logs"

# Scryfall blocks default Python requests. We must use a custom User-Agent.
SCRYFALL_HEADERS = {
    'User-Agent': 'MoxfieldImportTool/8.1 (Automated Collection Manager)',
    'Accept': 'application/json;q=0.9,*/*;q=0.8'
}

# --- CRITICAL TLS BUG FIX ---
# By using a custom Session and setting trust_env to False, we force Python
# to ignore the broken global certificate paths set by PostgreSQL.
http_session = requests.Session()
http_session.trust_env = False

CONDITIONS = {
    'm': 'Mint',
    'nm': 'Near Mint',
    'sp': 'Good (Lightly Played)',
    'mp': 'Played',
    'hp': 'Heavily Played',
    'dmg': 'Damaged'
}

# --- LOGGING SETUP ---
def setup_logging():
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"import_log_{timestamp}.log")
    logger = logging.getLogger("MoxfieldTool")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): logger.handlers.clear()
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
    return logger, log_file

logger, log_filename = setup_logging()

# Memory for failed sets to prevent API spamming on typos
failed_sets_memory = set()

# --- SCRYFALL API ---
def get_set_data(set_code):
    if set_code in failed_sets_memory:
        return {}

    if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
    set_code = set_code.lower().lstrip('!')
    cache_file = os.path.join(CACHE_DIR, f"{set_code}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as json_file:
                return json.load(json_file)
        except json.JSONDecodeError: pass

    print(f"--> Downloading data for set '{set_code}'...", file=sys.stderr)
    logger.info(f"Downloading set: {set_code}")
    
    url = f"https://api.scryfall.com/cards/search?q=set:{set_code}&unique=prints&page=1"
    card_map = {}
    has_more = True
    
    try:
        while has_more:
            # Using our custom session to bypass environment variable errors
            response = http_session.get(url, headers=SCRYFALL_HEADERS)
            if response.status_code == 404:
                logger.error(f"Set code '{set_code}' not found on Scryfall.")
                failed_sets_memory.add(set_code)
                return {}
            response.raise_for_status()
            data = response.json()
            for card in data.get('data', []):
                card_map[card.get('collector_number')] = card.get('name')
            has_more = data.get('has_more', False)
            url = data.get('next_page')

        with open(cache_file, 'w', encoding='utf-8') as json_file:
            json.dump(card_map, json_file, indent=2)
        return card_map
    except Exception as e:
        logger.error(f"Network error on {set_code}: {e}")
        failed_sets_memory.add(set_code)
        return {}

def resolve_name(set_code, collector_number, is_token=True):
    clean_code = set_code.lower().lstrip('!')
    
    if is_token:
        # Prevent double 't' if the user explicitly typed the token set code (e.g., tmh3)
        if clean_code.startswith('t') and len(clean_code) >= 4:
            lookup_code = clean_code
        else:
            lookup_code = f"t{clean_code}"
    else:
        lookup_code = clean_code
        
    set_data = get_set_data(lookup_code)
    return set_data.get(collector_number, None), lookup_code

def get_card_data(parsed_set_code, parsed_collector_number):
    card_name, full_set_code = resolve_name(parsed_set_code, parsed_collector_number, is_token=True)
    if not card_name: 
        print(f"!! Warning: Token name not found for {full_set_code.upper()} #{parsed_collector_number}")
        return None
    return {'set': full_set_code, 'cn': parsed_collector_number, 'name': card_name}

# --- HISTORY & PARSING ---
def load_history():
    if not os.path.exists(DUPE_DIR): os.makedirs(DUPE_DIR)
    history_map = {}
    
    for filename in os.listdir(DUPE_DIR):
        if filename.endswith(".txt"):
            with open(os.path.join(DUPE_DIR, filename), 'r', encoding='utf-8') as history_file:
                for line in history_file:
                    line = line.strip()
                    if not line: continue
                    
                    if line.endswith('|F'):
                        identifier = line[:-2]
                        is_foil = True
                    else:
                        identifier = line
                        is_foil = False
                        
                    if identifier in history_map:
                        history_map[identifier] = history_map[identifier] or is_foil
                    else:
                        history_map[identifier] = is_foil
                        
    return history_map

def save_current_history(new_history_map):
    if not new_history_map: return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(DUPE_DIR, f"session_{timestamp}.txt"), 'w', encoding='utf-8') as history_file:
        for identifier, is_foil in new_history_map.items():
            if is_foil:
                history_file.write(f"{identifier}|F\n")
            else:
                history_file.write(f"{identifier}\n")

def parse_token_string(raw_token_string):
    normalized_string = raw_token_string.strip().lower()
    
    base_token, sep, mods = normalized_string.partition('*')
    is_foil = 'f' in mods
    is_dfc = 'd' in mods
    count_match = re.search(r'\d+', mods)
    count = int(count_match.group()) if count_match else 1
    
    SET_CODE_REGEX = r"(?:![\w]{3,4}|[a-z]+)"

    def result(type_str, front_data, back_data=None):
        out = {'type': type_str, 'front': front_data, 'count': count, 'foil': is_foil, 'raw': raw_token_string}
        if back_data: out['back'] = back_data
        return out

    match = re.match(rf"^({SET_CODE_REGEX})(\d+)({SET_CODE_REGEX})(\d+)$", base_token)
    if match:
        set_a, cn_a, set_b, cn_b = match.groups()
        if set_a.lstrip('!') == set_b.lstrip('!') and cn_a == cn_b:
            return result('SS_DUPLICATE_SIDES', {'set': set_a, 'cn': cn_a})
        return result('DS_PAIR', {'set': set_a, 'cn': cn_a}, {'set': set_b, 'cn': cn_b})

    match = re.match(rf"^(\d+)({SET_CODE_REGEX})(\d+)({SET_CODE_REGEX})$", base_token)
    if match:
        cn_a, set_a, cn_b, set_b = match.groups()
        if set_a.lstrip('!') == set_b.lstrip('!') and cn_a == cn_b:
            return result('SS_DUPLICATE_SIDES', {'set': set_a, 'cn': cn_a})
        return result('DS_PAIR', {'set': set_a, 'cn': cn_a}, {'set': set_b, 'cn': cn_b})

    match = re.match(rf"^(\d+)({SET_CODE_REGEX})(\d+)$", base_token)
    if match:
        cn_a, set_code, cn_b = match.groups()
        return result('DS_PAIR', {'set': set_code, 'cn': cn_a}, {'set': set_code, 'cn': cn_b})

    match = re.match(rf"^({SET_CODE_REGEX})(\d+)$", base_token)
    if match: 
        route_type = 'DS_SINGLE_ENTRY' if is_dfc else 'SS_ADVERT'
        return result(route_type, {'set': match.group(1), 'cn': match.group(2)})

    match = re.match(rf"^(\d+)({SET_CODE_REGEX})$", base_token)
    if match: 
        route_type = 'DS_SINGLE_ENTRY' if is_dfc else 'SS_ADVERT'
        return result(route_type, {'set': match.group(2), 'cn': match.group(1)})

    return {'type': 'UNKNOWN', 'raw': raw_token_string}

# --- CSV WRITER ---
def write_moxfield_csv(filename, cards):
    if not cards: return
    filepath = os.path.join(OUTPUT_DIR, filename)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
            writer.writerow(["Count","Tradelist Count","Name","Edition","Condition","Language","Foil","Tags","Last Modified","Collector Number","Alter","Proxy","Purchase Price"])
            
            for card in cards:
                count_str = str(card.get('count', 1))
                foil_str = "foil" if card.get('foil') else ""
                tag_content = card.get('tag', "")
                condition_str = card.get('condition', "Near Mint")
                
                writer.writerow([count_str, count_str, card['name'], card['set'], condition_str, "English", foil_str, 
                                 tag_content, timestamp, card['cn'], "False", "False", ""])
        print(f"Created CSV: {filename} ({len(cards)} entries)")
        logger.info(f"Generated {filename}")
    except Exception as e:
        logger.error(f"CSV Write Error: {e}")

# --- PROCESSING HELPERS ---
def get_user_inputs():
    raw_input_strings = []
    if os.path.exists(INPUT_FILE):
        if input(f"Found '{INPUT_FILE}'. Use it? (Y/n): ").lower() != 'n':
            try:
                with open(INPUT_FILE) as input_file: 
                    raw_input_strings = input_file.read().strip().replace('\n','/').split('/')
            except Exception: pass
    
    if not raw_input_strings:
        raw_input_strings = input("\nInput string: ").strip().split('/')
    return raw_input_strings

def _route_regular_chunk(chunk, results):
    """Processes chunks marked with '@' as regular, non-token cards."""
    chunk = chunk[1:] # Strip the '@' trigger
    items = chunk.split(',')
    current_set = None
    
    for i, item in enumerate(items):
        item = item.strip().lower()
        if not item: continue
        
        if i == 0:
            m = re.match(r"^(![a-z0-9]{3,4}|[a-z]+)(.*)$", item)
            if m:
                current_set = m.group(1)
                cn_raw = m.group(2)
            else:
                logger.warning(f"Could not parse set code from: {item}")
                print(f"!! Warning: Could not parse '{item}'")
                continue
        else:
            cn_raw = item
        
        if not current_set: continue
        
        card_count = 1
        mult_match = re.search(r'\*(\d+)$', cn_raw)
        if mult_match:
            card_count = int(mult_match.group(1))
            cn_raw = cn_raw[:mult_match.start()]
            
        condition_str = "Near Mint"
        cond_match = re.search(r'(dmg|hp|mp|sp|nm|m)$', cn_raw)
        if cond_match:
            cond_key = cond_match.group(1)
            condition_str = CONDITIONS[cond_key]
            cn_raw = cn_raw[:-len(cond_key)]
            
        is_foil = False
        if cn_raw.endswith('f'):
            is_foil = True
            cn_raw = cn_raw[:-1]
            
        card_name, full_set_code = resolve_name(current_set, cn_raw, is_token=False)
        if not card_name: 
            print(f"!! Warning: Regular card name not found for {full_set_code.upper()} #{cn_raw}")
            continue
            
        results['regular_cards'].append({
            'set': full_set_code,
            'cn': cn_raw,
            'name': card_name,
            'foil': is_foil,
            'condition': condition_str,
            'count': card_count
        })

def _route_token(parsed_token, history_map, results):
    count = parsed_token.get('count', 1)
    is_foil = parsed_token.get('foil', False)

    if parsed_token['type'] in ['SS_ADVERT', 'SS_DUPLICATE_SIDES', 'DS_SINGLE_ENTRY']:
        card_data = get_card_data(parsed_token['front']['set'], parsed_token['front']['cn'])
        if card_data:
            card_data['count'] = count
            card_data['foil'] = is_foil
            if parsed_token['type'] == 'DS_SINGLE_ENTRY': 
                results['ds_fronts'].append(card_data)
            else: 
                results['single_sided'].append(card_data)

    elif parsed_token['type'] == 'DS_PAIR':
        front_card = get_card_data(parsed_token['front']['set'], parsed_token['front']['cn'])
        back_card = get_card_data(parsed_token['back']['set'], parsed_token['back']['cn'])
        
        if front_card and back_card:
            front_card['count'] = count
            front_card['foil'] = is_foil
            back_card['count'] = count
            back_card['foil'] = is_foil
            
            front_card['tag'] = f"Back is {back_card['set'].upper()} {back_card['cn']} ({back_card['name']})"
            back_card['tag'] = f"Front is {front_card['set'].upper()} {front_card['cn']} ({front_card['name']})"
            
            card_identifier = f"{front_card['set']}:{front_card['cn']}|{back_card['set']}:{back_card['cn']}"
            
            is_dupe = False
            if card_identifier in history_map:
                existing_foil_status = history_map[card_identifier]
                
                if is_foil and not existing_foil_status:
                    history_map[card_identifier] = True
                    results['new_history'][card_identifier] = True
                    print(f"  -> Upgrade: {card_identifier} (Foil replaces Non-Foil)")
                else:
                    is_dupe = True 
            else:
                history_map[card_identifier] = is_foil
                results['new_history'][card_identifier] = is_foil

            if is_dupe:
                results['ds_fronts_dupes'].append(front_card)
                results['ds_backs_dupes'].append(back_card)
                dupe_line = f"{card_identifier}|F" if is_foil else card_identifier
                results['dupe_identifiers'].append(dupe_line)
                print(f"  -> Duplicate: {card_identifier} ({'Foil' if is_foil else 'Non-Foil'})")
            else:
                results['ds_fronts'].append(front_card)
                results['ds_backs'].append(back_card)

def process_batch(raw_input_strings, history_map):
    results = {
        'single_sided': [], 'ds_fronts': [], 'ds_backs': [],
        'ds_fronts_dupes': [], 'ds_backs_dupes': [],
        'regular_cards': [], 
        'new_history': {}, 
        'dupe_identifiers': []
    }
    
    parsed_tokens = []
    for raw_input_string in raw_input_strings:
        raw_input_string = raw_input_string.strip()
        if not raw_input_string: continue
        
        if raw_input_string.startswith('@'):
            _route_regular_chunk(raw_input_string, results)
            continue
            
        parsed = parse_token_string(raw_input_string)
        if parsed['type'] == 'UNKNOWN':
            logger.warning(f"Unknown format: {raw_input_string}")
            print(f"!! Warning: Could not parse '{raw_input_string}'")
        else:
            parsed_tokens.append(parsed)

    parsed_tokens.sort(key=lambda x: not x.get('foil', False))

    print("\nProcessing...")
    
    for parsed_token in parsed_tokens:
        _route_token(parsed_token, history_map, results)
        
    return results

# --- MAIN ---
def main():
    print("="*80)
    print("      MOXFIELD UNIFIED IMPORT TOOL (v8.1 - Anti-Block & Smart Tokens)")
    print("="*80)
    print("OVERVIEW:")
    print("1. Enter strings separated by slashes '/'.")
    print("2. Normal input is treated as Tokens (with automatic deduplication).")
    print("3. Prepend '@' to treat a block as Regular Cards (Comma-separated).")
    print("4. Foils are automatically prioritised over Non-Foils in Tokens.")
    print("5. Distinct CSVs are generated in the /outputs folder.")
    print("-" * 80)
    print("TOKEN SYNTAX (Default Mode):")
    print("  7pip22        -> Double-Sided Same Set (TPIP #7 & #22)")
    print("  snc15ncc26    -> Double-Sided Diff Set")
    print("  dft14*d       -> Double-Sided Single Entry (e.g. DFC Token)")
    print("  one5 OR 5one  -> Single-Sided (Set+CN or CN+Set both work)")
    print("  !mh3          -> Use '!' to force a set code if it contains numbers.")
    print("                   (e.g., 21!mh327 will parse as TMH3 21 and 27).")
    print("-" * 80)
    print("TOKEN MODIFIERS (*count / *f / *d):")
    print("  1dsk*f        -> 1x DSK #1 (Foil)")
    print("  4sos10*f2     -> 2x SOS #4 & #10 (Double-Sided, Foil)")
    print("  dft14*df3     -> 3x Double-Sided Single Entry (Foil)")
    print("-" * 80)
    print("REGULAR CARD SYNTAX (Starts with @):")
    print("  @sld7094,2452 -> SLD #7094 and SLD #2452 (Both Near Mint)")
    print("  @nem115sp,42f -> NEM #115 (Lightly Played) and NEM #42 (Foil)")
    print("  @!mh315*4     -> MH3 #15 (Quantity of 4)")
    print("  Codes: M (Mint) | NM (Near Mint) | SP (Good/Lightly Played)")
    print("         MP (Played) | HP (Heavily Played) | DMG (Damaged)")
    print("="*80)

    raw_input_strings = get_user_inputs()
    history_map = load_history()
    
    results = process_batch(raw_input_strings, history_map)

    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    write_moxfield_csv(f"{timestamp}-single-sided.csv", results['single_sided'])
    write_moxfield_csv(f"{timestamp}-double-sided-fronts.csv", results['ds_fronts'])
    write_moxfield_csv(f"{timestamp}-double-sided-backs.csv", results['ds_backs'])
    write_moxfield_csv(f"{timestamp}-double-sided-fronts-dupes.csv", results['ds_fronts_dupes'])
    write_moxfield_csv(f"{timestamp}-double-sided-backs-dupes.csv", results['ds_backs_dupes'])
    write_moxfield_csv(f"{timestamp}-regular-cards.csv", results['regular_cards'])

    if results['dupe_identifiers']:
        dupe_list_path = os.path.join(OUTPUT_DIR, f"{timestamp}-session-dupes.txt")
        try:
            with open(dupe_list_path, 'w', encoding='utf-8') as f:
                for identifier in results['dupe_identifiers']:
                    f.write(f"{identifier}\n")
            print(f"Created Dupe List: {timestamp}-session-dupes.txt")
        except Exception as e:
            logger.error(f"Dupe List Write Error: {e}")

    if results['new_history']: save_current_history(results['new_history'])
    print("\nDone.")

if __name__ == "__main__":
    main()
