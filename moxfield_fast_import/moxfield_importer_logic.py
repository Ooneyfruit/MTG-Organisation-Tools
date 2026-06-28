import os
import re
import csv
import sys
import json
import io
import datetime
import requests
from collections import defaultdict

# --- CONFIGURATION & PATHS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "scryfall_cache")
DUPE_DIR = os.path.join(SCRIPT_DIR, "duplicate_check")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")

# Add _core_tools to path for sorting_logic import
CORE_TOOLS_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "_core_tools"))
if CORE_TOOLS_PATH not in sys.path:
    sys.path.append(CORE_TOOLS_PATH)

from sorting_logic import GUILD_MAP, get_non_land_wubrg_key, get_land_sort_key

SCRYFALL_HEADERS = {
    'User-Agent': 'MoxfieldImportTool/8.1 (Automated Collection Manager)',
    'Accept': 'application/json;q=0.9,*/*;q=0.8'
}

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

class MoxfieldImporter:
    def __init__(self, enable_lookup=True, enable_wubrg=True, dry_run=True, logger=None):
        self.enable_lookup = enable_lookup
        self.enable_wubrg = enable_wubrg
        self.dry_run = dry_run
        self.logger = logger
        self.failed_sets_memory = set()

    def get_set_data(self, set_code):
        if set_code in self.failed_sets_memory:
            return {}

        if not os.path.exists(CACHE_DIR): 
            os.makedirs(CACHE_DIR)
        set_code = set_code.lower().lstrip('!')
        cache_file = os.path.join(CACHE_DIR, f"{set_code}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as json_file:
                    return json.load(json_file)
            except json.JSONDecodeError: 
                pass

        if self.logger:
            self.logger.info(f"Downloading Scryfall set database for set code: '{set_code.upper()}'")
        
        url = f"https://api.scryfall.com/cards/search?q=set:{set_code}&unique=prints&page=1"
        card_map = {}
        has_more = True
        
        try:
            while has_more:
                response = http_session.get(url, headers=SCRYFALL_HEADERS)
                if response.status_code == 404:
                    if self.logger:
                        self.logger.error(f"Set code '{set_code.upper()}' not found on Scryfall API.")
                    self.failed_sets_memory.add(set_code)
                    return {}
                response.raise_for_status()
                data = response.json()
                for card in data.get('data', []):
                    card_map[card.get('collector_number')] = card.get('name')
                has_more = data.get('has_more', False)
                url = data.get('next_page')

            with open(cache_file, 'w', encoding='utf-8') as json_file:
                json.dump(card_map, json_file, indent=2)
            if self.logger:
                self.logger.info(f"Successfully cached set data locally for set: '{set_code.upper()}' ({len(card_map)} prints)")
            return card_map
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to query set '{set_code.upper()}': {e}")
            self.failed_sets_memory.add(set_code)
            return {}

    def resolve_name(self, set_code, collector_number, is_token=True):
        clean_code = set_code.lower().lstrip('!')
        if is_token:
            if clean_code.startswith('t') and len(clean_code) >= 4:
                lookup_code = clean_code
            else:
                lookup_code = f"t{clean_code}"
        else:
            lookup_code = clean_code
            
        if not self.enable_lookup:
            return "[No Lookup]", lookup_code
            
        set_data = self.get_set_data(lookup_code)
        card_name = set_data.get(collector_number, None)
        
        if card_name and self.logger:
            self.logger.info(f"Resolved name '{card_name}' for print: set={lookup_code.upper()} cn=#{collector_number}")
            
        return card_name, lookup_code

    def get_card_data(self, parsed_set_code, parsed_collector_number):
        card_name, full_set_code = self.resolve_name(parsed_set_code, parsed_collector_number, is_token=True)
        if not card_name: 
            if self.logger:
                self.logger.warning(f"Failed token name lookup: set={full_set_code.upper()} cn=#{parsed_collector_number}")
            return None
        return {'set': full_set_code, 'cn': parsed_collector_number, 'name': card_name}

    def load_history(self):
        if not os.path.exists(DUPE_DIR): 
            os.makedirs(DUPE_DIR)
        history_map = {}
        
        for filename in os.listdir(DUPE_DIR):
            if filename.endswith(".txt"):
                with open(os.path.join(DUPE_DIR, filename), 'r', encoding='utf-8') as history_file:
                    for line in history_file:
                        line = line.strip()
                        if not line: 
                            continue
                        
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
                            
        if self.logger:
            self.logger.info(f"Loaded {len(history_map)} token duplicate histories from disk.")
        return history_map

    def save_current_history(self, new_history_map):
        if not new_history_map: 
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(DUPE_DIR, f"session_{timestamp}.txt")
        with open(filepath, 'w', encoding='utf-8') as history_file:
            for identifier, is_foil in new_history_map.items():
                if is_foil:
                    history_file.write(f"{identifier}|F\n")
                else:
                    history_file.write(f"{identifier}\n")
        if self.logger:
            self.logger.info(f"Saved {len(new_history_map)} new history checks to history log: {filepath}")

    def parse_token_string(self, raw_token_string):
        normalized_string = raw_token_string.strip().lower()
        
        base_token, sep, mods = normalized_string.partition('*')
        is_foil = 'f' in mods
        is_dfc = 'd' in mods
        count_match = re.search(r'\d+', mods)
        count = int(count_match.group()) if count_match else 1
        
        SET_CODE_REGEX = r"(?:![\w]{3,4}|[a-z]+)"

        # Check for condition in token (like one5sp or one5*fsp)
        condition_str = "Near Mint"
        cond_match = re.search(r'(\d+)(dmg|hp|mp|sp|nm|m)$', base_token)
        if cond_match:
            cond_key = cond_match.group(2)
            condition_str = CONDITIONS[cond_key]
            base_token = base_token[:-len(cond_key)]

        def result(type_str, front_data, back_data=None):
            out = {
                'type': type_str, 
                'front': front_data, 
                'count': count, 
                'foil': is_foil, 
                'condition': condition_str, 
                'raw': raw_token_string
            }
            if back_data: 
                out['back'] = back_data
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

    def write_moxfield_csv(self, filename, cards):
        if not cards: 
            return
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
            if self.logger:
                self.logger.info(f"Successfully generated import CSV file: '{filepath}' ({len(cards)} entries)")
        except Exception as e:
            if self.logger:
                self.logger.error(f"CSV Write Error on file {filename}: {e}")

    def add_or_merge_card(self, card_list, new_card):
        for existing in card_list:
            if (existing.get('set') == new_card.get('set') and
                existing.get('cn') == new_card.get('cn') and
                existing.get('name') == new_card.get('name') and
                existing.get('foil') == new_card.get('foil') and
                existing.get('condition') == new_card.get('condition') and
                existing.get('tag') == new_card.get('tag')):
                
                old_qty = existing.get('count', 1)
                existing['count'] = old_qty + new_card.get('count', 1)
                if self.logger:
                    self.logger.info(f"Merged duplicate card entry: '{new_card['name']}' ({new_card['set'].upper()} #{new_card['cn']}) - Quantity increased from {old_qty} to {existing['count']}")
                return
        card_list.append(new_card)

    def _route_regular_chunk(self, chunk, results, log_messages):
        chunk = chunk[1:] # Strip the '@' trigger
        items = chunk.split(',')
        current_set = None
        
        for i, item in enumerate(items):
            item = item.strip().lower()
            if not item: 
                continue
            
            if i == 0:
                m = re.match(r"^(![a-z0-9]{3,4}|[a-z]+)(.*)$", item)
                if m:
                    current_set = m.group(1)
                    cn_raw = m.group(2)
                else:
                    if self.logger:
                        self.logger.warning(f"Could not parse set code from regular block: {item}")
                    continue
            else:
                cn_raw = item
            
            if not current_set: 
                continue
            
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
                
            card_name, full_set_code = self.resolve_name(current_set, cn_raw, is_token=False)
            if not card_name: 
                warn_msg = f"!! Warning: Regular card name not found for {full_set_code.upper()} #{cn_raw}"
                log_messages.append(warn_msg)
                if self.logger:
                    self.logger.warning(warn_msg)
                continue
                
            self.add_or_merge_card(results['regular_cards'], {
                'set': full_set_code,
                'cn': cn_raw,
                'name': card_name,
                'foil': is_foil,
                'condition': condition_str,
                'count': card_count,
                'tag': "",
                'front_name': card_name
            })

    def _route_token(self, parsed_token, history_map, results, log_messages):
        count = parsed_token.get('count', 1)
        is_foil = parsed_token.get('foil', False)
        condition_str = parsed_token.get('condition', "Near Mint")

        if parsed_token['type'] in ['SS_ADVERT', 'SS_DUPLICATE_SIDES', 'DS_SINGLE_ENTRY']:
            card_data = self.get_card_data(parsed_token['front']['set'], parsed_token['front']['cn'])
            if card_data:
                card_data['count'] = count
                card_data['foil'] = is_foil
                card_data['condition'] = condition_str
                card_data['tag'] = ""
                card_data['front_name'] = card_data['name']
                if parsed_token['type'] == 'DS_SINGLE_ENTRY': 
                    self.add_or_merge_card(results['ds_fronts'], card_data)
                else: 
                    self.add_or_merge_card(results['single_sided'], card_data)

        elif parsed_token['type'] == 'DS_PAIR':
            front_card = self.get_card_data(parsed_token['front']['set'], parsed_token['front']['cn'])
            back_card = self.get_card_data(parsed_token['back']['set'], parsed_token['back']['cn'])
            
            if front_card and back_card:
                front_card['count'] = count
                front_card['foil'] = is_foil
                front_card['condition'] = condition_str
                front_card['front_name'] = front_card['name']
                
                back_card['count'] = count
                back_card['foil'] = is_foil
                back_card['condition'] = condition_str
                back_card['front_name'] = front_card['name']
                
                front_card['tag'] = f"Back is {back_card['set'].upper()} {back_card['cn']} ({back_card['name']})"
                back_card['tag'] = f"Front is {front_card['set'].upper()} {front_card['cn']} ({front_card['name']})"
                
                card_identifier = f"{front_card['set']}:{front_card['cn']}|{back_card['set']}:{back_card['cn']}"
                
                is_dupe = False
                if card_identifier in history_map:
                    existing_foil_status = history_map[card_identifier]
                    
                    if is_foil and not existing_foil_status:
                        history_map[card_identifier] = True
                        results['new_history'][card_identifier] = True
                        upgrade_msg = f"  -> Upgrade: {card_identifier} (Foil replaces Non-Foil)"
                        log_messages.append(upgrade_msg)
                        if self.logger:
                            self.logger.info(upgrade_msg)
                    else:
                        is_dupe = True 
                else:
                    history_map[card_identifier] = is_foil
                    results['new_history'][card_identifier] = is_foil

                if is_dupe:
                    self.add_or_merge_card(results['ds_fronts_dupes'], front_card)
                    self.add_or_merge_card(results['ds_backs_dupes'], back_card)
                    dupe_line = f"{card_identifier}|F" if is_foil else card_identifier
                    results['dupe_identifiers'].append(dupe_line)
                    dupe_msg = f"  -> Duplicate: {card_identifier} ({'Foil' if is_foil else 'Non-Foil'})"
                    log_messages.append(dupe_msg)
                    if self.logger:
                        self.logger.info(dupe_msg)
                else:
                    self.add_or_merge_card(results['ds_fronts'], front_card)
                    self.add_or_merge_card(results['ds_backs'], back_card)

    def process_batch(self, raw_input_strings, history_map):
        results = {
            'single_sided': [], 'ds_fronts': [], 'ds_backs': [],
            'ds_fronts_dupes': [], 'ds_backs_dupes': [],
            'regular_cards': [], 
            'new_history': {}, 
            'dupe_identifiers': []
        }
        log_messages = []
        parsed_tokens = []
        
        for raw_input_string in raw_input_strings:
            raw_input_string = raw_input_string.strip()
            if not raw_input_string: 
                continue
            
            if raw_input_string.startswith('@'):
                self._route_regular_chunk(raw_input_string, results, log_messages)
                continue
                
            parsed = self.parse_token_string(raw_input_string)
            if parsed['type'] == 'UNKNOWN':
                warn_msg = f"!! Warning: Could not parse '{raw_input_string}'"
                log_messages.append(warn_msg)
                if self.logger:
                    self.logger.warning(warn_msg)
            else:
                parsed_tokens.append(parsed)

        parsed_tokens.sort(key=lambda x: not x.get('foil', False))
        
        if self.logger:
            self.logger.info(f"Processing batch of {len(parsed_tokens)} parsed token strings...")
        for parsed_token in parsed_tokens:
            self._route_token(parsed_token, history_map, results, log_messages)
            
        return results, log_messages

    def run_import_session(self, raw_input_text):
        raw_input_strings = raw_input_text.replace('\n', '/').split('/')
        raw_input_strings = [s.strip() for s in raw_input_strings if s.strip()]
        
        if not raw_input_strings:
            if self.logger:
                self.logger.warning("Empty input string provided to session.")
            return None

        if self.logger:
            self.logger.info(f"Starting Moxfield Importer session with {len(raw_input_strings)} raw inputs.")

        # Load history
        history_map = self.load_history()
        original_history_keys = set(history_map.keys())
        history_map_copy = history_map.copy()
        
        # Process batch
        results, log_messages = self.process_batch(raw_input_strings, history_map_copy)
        warnings = [msg for msg in log_messages if msg.startswith("!! Warning:")]
        dedupe_logs = [msg for msg in log_messages if msg.startswith("  ->")]
        
        # Gather card metadata using scryfall_core if loaded
        scryfall_resolved_data = {}
        all_parsed_cards = (
            results['regular_cards'] + 
            results['single_sided'] + 
            results['ds_fronts'] + 
            results['ds_backs'] + 
            results['ds_fronts_dupes'] + 
            results['ds_backs_dupes']
        )
        
        scryfall_core_loaded = False
        try:
            sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "..", "_core_tools")))
            import scryfall_core
            scryfall_core_loaded = True
        except Exception as e:
            warnings.append(f"!! Warning: Failed to load scryfall_core: {e}")
            if self.logger:
                self.logger.error(f"Failed to import scryfall_core library: {e}")

        if scryfall_core_loaded:
            cards_to_resolve = []
            seen_queries = set()
            for card in all_parsed_cards:
                qkey = (card['set'].lower(), str(card['cn']).lower())
                card_query = {
                    'set': card['set'],
                    'collector_number': str(card['cn']),
                    'name': card['name']
                }
                data, _ = scryfall_core.load_from_cache(card_query)
                if data:
                    scryfall_resolved_data[qkey] = {
                        'color_identity': data.get('color_identity', []),
                        'type_line': data.get('type_line', "")
                    }
                elif self.enable_lookup:
                    if qkey not in seen_queries:
                        seen_queries.add(qkey)
                        cards_to_resolve.append(card_query)
                        
            if self.enable_lookup and cards_to_resolve:
                try:
                    if self.logger:
                        self.logger.info(f"Querying Scryfall API metadata endpoints for {len(cards_to_resolve)} cards...")
                    scryfall_core.resolve_cards(cards_to_resolve)
                    for query in cards_to_resolve:
                        qkey = (query['set'].lower(), str(query['collector_number']).lower())
                        data, _ = scryfall_core.load_from_cache(query)
                        if data:
                            scryfall_resolved_data[qkey] = {
                                'color_identity': data.get('color_identity', []),
                                'type_line': data.get('type_line', "")
                            }
                except Exception as e:
                    warnings.append(f"!! Warning: Failed to query Scryfall API: {e}")
                    if self.logger:
                        self.logger.error(f"Failed to query Scryfall API metadata: {e}")

        # Build list of cards for table
        # Row layout: [set, cn, name, type, foil, condition, qty, note, color_identity, type_line, front_name]
        table_rows = []
        def get_card_metadata(card):
            qkey = (card['set'].lower(), str(card['cn']).lower())
            meta = scryfall_resolved_data.get(qkey, {'color_identity': [], 'type_line': ""})
            return meta.get('color_identity', []), meta.get('type_line', "")

        for card in results['regular_cards']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "Regular", "Yes" if card['foil'] else "No", card['condition'], card['count'], "", ci, tl, card.get('front_name', card['name'])])
            
        for card in results['single_sided']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "SS Token", "Yes" if card['foil'] else "No", "N/A", card['count'], "", ci, tl, card.get('front_name', card['name'])])
            
        for card in results['ds_fronts']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "DS Front", "Yes" if card['foil'] else "No", "N/A", card['count'], card.get('tag', ""), ci, tl, card.get('front_name', card['name'])])
            
        for card in results['ds_backs']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "DS Back", "Yes" if card['foil'] else "No", "N/A", card['count'], card.get('tag', ""), ci, tl, card.get('front_name', card['name'])])
            
        for card in results['ds_fronts_dupes']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "DS Front (Dupe)", "Yes" if card['foil'] else "No", "N/A", card['count'], card.get('tag', ""), ci, tl, card.get('front_name', card['name'])])
            
        for card in results['ds_backs_dupes']:
            ci, tl = get_card_metadata(card)
            table_rows.append([card['set'].upper(), card['cn'], card['name'], "DS Back (Dupe)", "Yes" if card['foil'] else "No", "N/A", card['count'], card.get('tag', ""), ci, tl, card.get('front_name', card['name'])])
            
        # Group and Sort Spells/Lands
        basic_land_rows = []
        non_basic_land_rows = []
        spell_rows = []
        
        if self.enable_wubrg:
            for row in table_rows:
                is_land = False
                is_basic = False
                if row[3] == "Regular":
                    type_line = row[9]
                    if "land" in type_line.lower():
                        is_land = True
                        if "basic" in type_line.lower():
                            is_basic = True
                
                if is_basic:
                    basic_land_rows.append(row)
                elif is_land:
                    non_basic_land_rows.append(row)
                else:
                    spell_rows.append(row)
            
            # Sort non-basic and basic lands
            non_basic_land_rows.sort(key=lambda x: get_land_sort_key(x[8], x[2]))
            basic_land_rows.sort(key=lambda x: get_land_sort_key(x[8], x[2]))
        else:
            table_rows.sort(key=lambda x: (x[3], x[0], x[1]))
            spell_rows = table_rows

        # Group spells by set code
        set_groups = defaultdict(list)
        for row in spell_rows:
            set_code = row[0]
            set_groups[set_code].append(row)
            
        unique_sets = sorted(set_groups.keys())
        token_sets_detected = set()
        
        if scryfall_core_loaded:
            try:
                for set_code in unique_sets:
                    if scryfall_core.is_token_set(set_code):
                        token_sets_detected.add(set_code.upper())
            except Exception:
                pass
        for set_code in unique_sets:
            if set_code.upper() not in token_sets_detected:
                if set_code.upper().startswith('T') and len(set_code) >= 4:
                    token_sets_detected.add(set_code.upper())

        # Sort spells in each group individually
        if self.enable_wubrg:
            for set_code in unique_sets:
                group_rows = set_groups[set_code]
                if set_code.upper() in token_sets_detected:
                    def get_token_sort_key(row):
                        front_name = row[10]
                        side_key = 1 if "Back" in row[3] else 0
                        return (front_name.lower(), side_key, row[2].lower())
                    group_rows.sort(key=get_token_sort_key)
                else:
                    group_rows.sort(key=lambda x: (get_non_land_wubrg_key(x[8]), x[2].lower()))

        if self.logger:
            self.logger.info(f"Categorized output card sets: {len(spell_rows)} spells inside {len(unique_sets)} sets ({len(token_sets_detected)} token sets), {len(non_basic_land_rows)} utility lands, {len(basic_land_rows)} basic lands.")

        # Save files if NOT in dry-run mode
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        files_written = []
        if not self.dry_run:
            if self.logger:
                self.logger.info(f"Writing CSV import spreadsheets to outputs/ (timestamp: {timestamp})")
            if not os.path.exists(OUTPUT_DIR):
                os.makedirs(OUTPUT_DIR)
                
            self.write_moxfield_csv(f"{timestamp}-single-sided.csv", results['single_sided'])
            self.write_moxfield_csv(f"{timestamp}-double-sided-fronts.csv", results['ds_fronts'])
            self.write_moxfield_csv(f"{timestamp}-double-sided-backs.csv", results['ds_backs'])
            self.write_moxfield_csv(f"{timestamp}-double-sided-fronts-dupes.csv", results['ds_fronts_dupes'])
            self.write_moxfield_csv(f"{timestamp}-double-sided-backs-dupes.csv", results['ds_backs_dupes'])
            self.write_moxfield_csv(f"{timestamp}-regular-cards.csv", results['regular_cards'])
            
            files_written.append(f"CSV files generated in outputs/ (timestamp: {timestamp})")
            
            if results['dupe_identifiers']:
                dupe_list_path = os.path.join(OUTPUT_DIR, f"{timestamp}-session-dupes.txt")
                try:
                    with open(dupe_list_path, 'w', encoding='utf-8') as f:
                        for identifier in results['dupe_identifiers']:
                            f.write(f"{identifier}\n")
                    files_written.append(f"Created duplicates list: {timestamp}-session-dupes.txt")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Dupe List Write Error: {e}")
                        
            if results['new_history']:
                self.save_current_history(results['new_history'])
                files_written.append("History file saved for token duplicate checks.")

        # Aggregate set totals
        set_counts = {}
        for r in table_rows:
            if r[3] in ["DS Back", "DS Back (Dupe)"]:
                continue
            set_code = r[0]
            set_counts[set_code] = set_counts.get(set_code, 0) + r[6]
        sorted_sets = sorted(set_counts.items(), key=lambda x: x[1], reverse=True)

        regular_qty = sum(card['count'] for card in results['regular_cards'])
        ss_token_qty = sum(card['count'] for card in results['single_sided'])
        ds_front_qty = sum(card['count'] for card in results['ds_fronts'])
        ds_front_dupe_qty = sum(card['count'] for card in results['ds_fronts_dupes'])
        total_cards = sum(r[6] for r in table_rows)
        foil_cards = sum(r[6] for r in table_rows if r[4] == "Yes")
        non_foil_cards = total_cards - foil_cards
        
        upgrades_count = sum(1 for key in results['new_history'] if key in original_history_keys)
        new_unique_ds_count = sum(1 for key in results['new_history'] if key not in original_history_keys)
        dupes_count = len(results['dupe_identifiers'])

        return {
            'total_cards': total_cards,
            'regular_qty': regular_qty,
            'ss_token_qty': ss_token_qty,
            'ds_front_qty': ds_front_qty,
            'ds_front_dupe_qty': ds_front_dupe_qty,
            'foil_cards': foil_cards,
            'non_foil_cards': non_foil_cards,
            'new_unique_ds_count': new_unique_ds_count,
            'upgrades_count': upgrades_count,
            'dupes_count': dupes_count,
            'warnings': warnings,
            'dedupe_logs': dedupe_logs,
            'sorted_sets': sorted_sets,
            'set_groups': set_groups,
            'non_basic_land_rows': non_basic_land_rows,
            'basic_land_rows': basic_land_rows,
            'table_rows': table_rows,
            'files_written': files_written,
            'unique_sets': unique_sets
        }

def format_report_as_ascii(results_dict, headers, append_table_callback, enable_wubrg=True):
    out = io.StringIO()
    
    out.write("="*90 + "\n")
    out.write(" " * 28 + "MOXFIELD IMPORT DRY RUN REPORT\n")
    out.write("="*90 + "\n\n")
    
    # 1. Summary Block
    out.write("[1] GENERAL STATISTICS\n")
    out.write("-" * 35 + "\n")
    out.write(f"  Total Cards (for Moxfield import):  {results_dict['total_cards']}\n")
    out.write(f"  ├── Regular Cards (Non-token):      {results_dict['regular_qty']}\n")
    out.write(f"  └── Tokens (Total physical count):  {results_dict['ss_token_qty'] + results_dict['ds_front_qty'] + results_dict['ds_front_dupe_qty']}\n")
    out.write(f"      ├── Single-Sided:               {results_dict['ss_token_qty']}\n")
    out.write(f"      └── Double-Sided (Unique):      {results_dict['ds_front_qty']}\n")
    out.write(f"      └── Double-Sided (Duplicate):   {results_dict['ds_front_dupe_qty']}\n\n")
    
    out.write("  Foil / Non-Foil Breakdown:\n")
    out.write(f"  ├── Foils:                          {results_dict['foil_cards']}\n")
    out.write(f"  └── Non-Foils:                      {results_dict['non_foil_cards']}\n\n")
    
    out.write("  Double-Sided Token Duplicate Checking:\n")
    out.write(f"  ├── New Unique DS Tokens:               {results_dict['new_unique_ds_count']}\n")
    out.write(f"  ├── Foil Upgrades (Replaces Non-Foil):  {results_dict['upgrades_count']}\n")
    out.write(f"  └── Skipped Duplicates (Already Saved): {results_dict['dupes_count']}\n\n")
    
    # 2. Warnings
    if results_dict['warnings']:
        out.write("[2] WARNINGS / RESOLUTION ISSUES\n")
        out.write("-" * 35 + "\n")
        for w in results_dict['warnings']:
            out.write(f"  {w}\n")
        out.write("\n")
        
    # 3. Deduplication Log
    if results_dict['dedupe_logs']:
        out.write("[3] HISTORY / DEDUPLICATION LOG\n")
        out.write("-" * 35 + "\n")
        for log in results_dict['dedupe_logs']:
            out.write(f"  {log}\n")
        out.write("\n")
        
    # 4. Set Distribution
    out.write("[4] SET DISTRIBUTION (Excludes DS Back-sides for totals)\n")
    out.write("-" * 35 + "\n")
    if results_dict['sorted_sets']:
        for set_code, count in results_dict['sorted_sets']:
            out.write(f"  {set_code:<8} : {count} cards\n")
    else:
        out.write("  No sets parsed.\n")
    out.write("\n")
    
    # 5. Resolved Details
    out.write("[5] RESOLVED CARD DETAILS\n")
    out.write("-" * 35 + "\n")
    
    report_string = out.getvalue()
    out.close()
    
    # Let calling script print tables to widget or console
    if enable_wubrg:
        sub_idx = 1
        for set_code in results_dict['unique_sets']:
            group_rows = results_dict['set_groups'][set_code]
            report_string += f"\n[5.{sub_idx}] SET: {set_code} DETAILS\n" + "-" * 35 + "\n"
            report_string += append_table_callback(headers, group_rows)
            sub_idx += 1
            
        if results_dict['non_basic_land_rows']:
            report_string += f"\n[5.{sub_idx}] SET: LAND DETAILS\n" + "-" * 35 + "\n"
            report_string += append_table_callback(headers, results_dict['non_basic_land_rows'])
            sub_idx += 1
            
        if results_dict['basic_land_rows']:
            report_string += f"\n[5.{sub_idx}] SET: BASIC LAND DETAILS\n" + "-" * 35 + "\n"
            report_string += append_table_callback(headers, results_dict['basic_land_rows'])
            sub_idx += 1
    else:
        report_string += append_table_callback(headers, results_dict['table_rows'])
        
    # 6. Files written
    if results_dict['files_written']:
        report_string += "\n" + "="*80 + "\n"
        report_string += "[+] OUTPUT GENERATION LOG:\n"
        report_string += "="*80 + "\n"
        for log in results_dict['files_written']:
            report_string += f"  {log}\n"
            
    return report_string
