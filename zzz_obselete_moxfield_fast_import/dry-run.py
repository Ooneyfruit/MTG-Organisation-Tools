import os
import re
import csv
import sys
import json
import io
import contextlib
import datetime
import logging
import requests
import tkinter as tk
from tkinter import messagebox, scrolledtext
from collections import defaultdict

# --- CONFIGURATION & GLOBAL SETTINGS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "input.txt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
CACHE_DIR = os.path.join(SCRIPT_DIR, "scryfall_cache")
DUPE_DIR = os.path.join(SCRIPT_DIR, "duplicate_check")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

SCRYFALL_HEADERS = {
    'User-Agent': 'MoxfieldImportTool/8.1 (Automated Collection Manager)',
    'Accept': 'application/json;q=0.9,*/*;q=0.8'
}

# TLS environment fix
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

# --- GLOBAL LOGGER SETUP ---
def setup_logging():
    if not os.path.exists(LOG_DIR): 
        os.makedirs(LOG_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"import_log_{timestamp}.log")
    
    logger = logging.getLogger("MoxfieldTool")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): 
        logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
    
    # Console stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)
    
    return logger, log_file

class DryRunApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Moxfield Import - Dry Run & Import Companion")
        self.root.geometry("850x650")
        
        # Initialize logging
        self.logger, self.log_filename = setup_logging()
        self.failed_sets_memory = set()
        
        # --- MENU BAR ---
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Syntax Guide & Tester", command=self.show_help_window)
        
        # --- UI ELEMENTS ---
        # 1. Header Frame
        header_frame = tk.Frame(self.root)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        lbl_title = tk.Label(
            header_frame, 
            text="Moxfield Fast Import - Dry Run & Import Companion", 
            font=("Arial", 12, "bold")
        )
        lbl_title.pack(side="left")
        
        self.lbl_status = tk.Label(
            header_frame,
            text="",
            font=("Arial", 10, "italic")
        )
        self.lbl_status.pack(side="right", padx=10)
        
        # Separator/Divider
        separator = tk.Frame(self.root, height=2, bd=1, relief="sunken")
        separator.pack(fill="x", padx=15, pady=5)
        
        # 2. Control Options Frame (Row 1)
        options_frame = tk.Frame(self.root)
        options_frame.pack(fill="x", padx=15, pady=(5, 2))
        
        lbl_options_desc = tk.Label(
            options_frame, 
            text="Options:     ", 
            font=("Arial", 10, "bold")
        )
        lbl_options_desc.pack(side="left")
        
        # Scryfall Toggle Checkbutton (Checked by default)
        self.var_enable_lookup = tk.BooleanVar(value=True)
        chk_lookup = tk.Checkbutton(
            options_frame, 
            text="Enable Scryfall Lookup (Cache/API)", 
            variable=self.var_enable_lookup,
            command=self.on_lookup_toggle,
            font=("Arial", 9)
        )
        chk_lookup.pack(side="left", padx=10)
        
        # WUBRG Sorting Toggle Checkbutton (Checked by default)
        self.var_enable_wubrg = tk.BooleanVar(value=True)
        self.chk_wubrg = tk.Checkbutton(
            options_frame, 
            text="Sort by WUBRG & Name", 
            variable=self.var_enable_wubrg,
            font=("Arial", 9)
        )
        self.chk_wubrg.pack(side="left", padx=10)
        
        # Dry Run Toggle Checkbutton (Checked by default)
        self.var_dry_run = tk.BooleanVar(value=True)
        self.chk_dry_run = tk.Checkbutton(
            options_frame,
            text="Dry Run Mode (No File Writes)",
            variable=self.var_dry_run,
            command=self.on_dry_run_toggle,
            font=("Arial", 9)
        )
        self.chk_dry_run.pack(side="left", padx=10)
        
        # 3. Actions Frame (Row 2)
        actions_frame = tk.Frame(self.root)
        actions_frame.pack(fill="x", padx=15, pady=(2, 5))
        
        lbl_input_desc = tk.Label(
            actions_frame, 
            text="Input String:", 
            font=("Arial", 10, "bold")
        )
        lbl_input_desc.pack(side="left")
        
        btn_clear = tk.Button(
            actions_frame, 
            text="Clear Input", 
            command=self.clear_input
        )
        btn_clear.pack(side="right", padx=5)
        
        btn_save = tk.Button(
            actions_frame,
            text="Save to input.txt",
            command=self.save_input_file
        )
        btn_save.pack(side="right", padx=5)
        
        btn_load = tk.Button(
            actions_frame, 
            text="Load input.txt", 
            command=self.load_input_file
        )
        btn_load.pack(side="right", padx=5)
        
        # 4. Input Text Box
        self.txt_input = scrolledtext.ScrolledText(
            self.root, 
            height=6,
            font=("Courier", 10)
        )
        self.txt_input.pack(fill="x", padx=15, pady=5)
        
        # 5. Run Analysis / Output Button
        self.btn_run = tk.Button(
            self.root, 
            text="Run Dry Run Analysis", 
            command=self.run_analysis,
            font=("Arial", 10, "bold")
        )
        self.btn_run.pack(fill="x", padx=15, pady=10)
        
        # 6. Results Section
        lbl_results_desc = tk.Label(
            self.root, 
            text="Analysis Report:", 
            font=("Arial", 10, "bold")
        )
        lbl_results_desc.pack(anchor="w", padx=15, pady=(5, 2))
        
        self.txt_results = scrolledtext.ScrolledText(
            self.root, 
            font=("Courier", 10)
        )
        self.txt_results.pack(fill="both", expand=True, padx=15, pady=(2, 15))
        
        # Configure standard text tags for readability (standard colors)
        self.txt_results.tag_config("warning", foreground="red")
        self.txt_results.tag_config("success", foreground="green")
        self.txt_results.tag_config("bold", font=("Courier", 10, "bold"))
        
        # Load input.txt automatically on startup if it exists
        if os.path.exists(INPUT_FILE):
            self.load_input_file()
            self.lbl_status.config(text="Auto-loaded input.txt on startup", fg="green")
            self.logger.info("Auto-loaded input.txt on startup")

    def on_lookup_toggle(self):
        if self.var_enable_lookup.get():
            self.chk_wubrg.config(state="normal")
            self.chk_dry_run.config(state="normal")
        else:
            self.var_enable_wubrg.set(False)
            self.chk_wubrg.config(state="disabled")
            
            self.var_dry_run.set(True)
            self.chk_dry_run.config(state="disabled")
            self.on_dry_run_toggle()

    def on_dry_run_toggle(self):
        if self.var_dry_run.get():
            self.btn_run.config(text="Run Dry Run Analysis")
        else:
            self.btn_run.config(text="Output CSVs")

    def load_input_file(self):
        if os.path.exists(INPUT_FILE):
            try:
                with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                self.txt_input.delete("1.0", tk.END)
                self.txt_input.insert("1.0", content)
                self.lbl_status.config(text=f"Loaded from {os.path.basename(INPUT_FILE)}", fg="green")
                self.logger.info(f"Loaded input.txt content")
            except Exception as e:
                self.logger.error(f"Failed to read file: {e}")
                messagebox.showerror("Error", f"Failed to read file: {e}")
        else:
            self.logger.warning("input.txt file not found")
            messagebox.showwarning("Warning", f"File '{os.path.basename(INPUT_FILE)}' not found.")

    def save_input_file(self):
        try:
            content = self.txt_input.get("1.0", tk.END).strip()
            with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(content)
            self.lbl_status.config(text=f"Saved to {os.path.basename(INPUT_FILE)}", fg="green")
            self.logger.info(f"Saved textbox content to input.txt")
            messagebox.showinfo("Success", f"Successfully saved input box to {os.path.basename(INPUT_FILE)}")
        except Exception as e:
            self.logger.error(f"Failed to save file: {e}")
            messagebox.showerror("Error", f"Failed to save file: {e}")

    def clear_input(self):
        self.txt_input.delete("1.0", tk.END)
        self.lbl_status.config(text="Input cleared", fg="black")
        self.logger.info("Cleared input box")

    def append_result(self, text, tag=None):
        self.txt_results.insert(tk.END, text, tag)

    def append_table_to_widget(self, headers, rows):
        if not rows:
            self.append_result("  No data resolved.\n")
            return
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i in range(len(headers)):
                col_widths[i] = max(col_widths[i], len(str(row[i])))
                
        # Format line separator
        separator = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+\n"
        
        # Print header
        self.append_result(separator)
        header_str = "| " + " | ".join(f"{str(h).ljust(col_widths[i])}" for i, h in enumerate(headers)) + " |\n"
        self.append_result(header_str, "bold")
        self.append_result(separator)
        
        # Print rows
        for row in rows:
            row_str = "| " + " | ".join(f"{str(row[i]).ljust(col_widths[i])}" for i in range(len(headers))) + " |\n"
            self.append_result(row_str)
        self.append_result(separator)

    # --- POP-OUT HELP MENU ---
    def show_help_window(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("Moxfield Fast Import - Syntax Guide & Interactive Tester")
        help_win.geometry("700x720")
        help_win.grab_set() # Focus lock on help window
        
        # Scrollable Guideline Text
        lbl_guide = tk.Label(help_win, text="Import Syntax Guidelines", font=("Arial", 11, "bold"))
        lbl_guide.pack(anchor="w", padx=15, pady=(10, 2))
        
        txt_guide = scrolledtext.ScrolledText(help_win, height=22, font=("Courier", 9))
        txt_guide.pack(fill="both", expand=True, padx=15, pady=5)
        
        guide_content = """==========================================================================================
                     MOXFIELD FAST IMPORT - SYNTAX GUIDE
==========================================================================================

GENERAL OVERVIEW:
-----------------
1. Enter list strings separated by slashes '/' or newlines.
2. Unmarked strings are processed as Tokens (with automatic duplicate checking).
3. Prepend '@' to treat a block as Regular Cards (comma-separated).
4. Foils are automatically prioritized over Non-Foils during token duplicate checking.
5. Distinct CSVs are generated in the /outputs folder when Dry Run Mode is unchecked.

------------------------------------------------------------------------------------------
1. TOKEN SYNTAX (Default Mode)
------------------------------------------------------------------------------------------
Format rules:
  [CN][Set][CN]      - Double-Sided, Same Set (e.g., 7pip22 -> TPIP #7 & TPIP #22)
  [Set][CN][Set][CN] - Double-Sided, Different Sets (e.g., snc15ncc26)
  [Set][CN]          - Single-Sided Token (e.g., one5)
  [CN][Set]          - Single-Sided Token (e.g., 5one)
  !mh3               - Use '!' to force set code MH3 if it contains digits (e.g., 21!mh327)

Token Modifiers (Suffixes after '*'):
  *f   - Foil (e.g., one5*f)
  *d   - Double-Sided DFC (e.g., dft14*d)
  *2   - Quantity multiplier (e.g., one5*2)
  *df3 - Combination (e.g., 3x Foil DFC Token -> dft14*df3)

Token Conditions:
  Tokens can have condition codes (m, nm, sp, mp, hp, dmg) appended to the collector number.
  Examples:
    one5sp    - TONE #5 (Lightly Played)
    one5hp*f  - TONE #5 (Heavily Played, Foil)

------------------------------------------------------------------------------------------
2. REGULAR CARD SYNTAX (Prepend '@')
------------------------------------------------------------------------------------------
Regular card blocks are comma-separated and follow a single '@[Set]' code header.
Format:
  @[Set][CN][foil][condition]*[qty]

Examples:
  @sld7094,2452     -> SLD #7094 and SLD #2452 (Both Near Mint)
  @nem115sp,42f     -> NEM #115 (Lightly Played) and NEM #42 (Foil, Near Mint)
  @!mh315*4         -> MH3 #15 (Quantity of 4, Near Mint)
  @snc5fhp*2        -> SNC #5 (Quantity of 2, Foil, Heavily Played)

Condition Codes:
  m   - Mint
  nm  - Near Mint (Default)
  sp  - Good (Lightly Played)
  mp  - Played
  hp  - Heavily Played
  dmg - Damaged
"""
        txt_guide.insert(tk.END, guide_content)
        txt_guide.config(state="disabled")
        
        # Interactive Parser Tester Frame
        tester_frame = tk.LabelFrame(help_win, text="Interactive Parser Tester", padx=10, pady=10)
        tester_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        desc_lbl = tk.Label(tester_frame, text="Type a single string below and click 'Test Parse' to see how the parser decodes it:", font=("Arial", 9, "italic"))
        desc_lbl.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        ent_test = tk.Entry(tester_frame, width=40, font=("Courier", 10))
        ent_test.grid(row=1, column=0, padx=5, pady=5, sticky="we")
        ent_test.insert(0, "dft14*df3") # Default sample
        
        lbl_parse_result = tk.Label(tester_frame, text="Result: Click Test Parse", font=("Courier", 9, "bold"), fg="blue", anchor="w", justify="left")
        
        def run_test_parse():
            raw_str = ent_test.get().strip()
            if not raw_str:
                lbl_parse_result.config(text="Result: Please enter a string", fg="red")
                return
            
            try:
                if raw_str.startswith('@'):
                    # Parse regular block
                    chunk = raw_str[1:]
                    items = chunk.split(',')
                    parsed_list = []
                    current_set = None
                    
                    for i, item in enumerate(items):
                        item = item.strip().lower()
                        if not item: continue
                        if i == 0:
                            m = re.match(r"^(![a-z0-9]{3,4}|[a-z]+)(.*)$", item)
                            if m:
                                current_set = m.group(1).upper()
                                cn_raw = m.group(2)
                            else:
                                lbl_parse_result.config(text="Result: Failed to parse set code", fg="red")
                                return
                        else:
                            cn_raw = item
                            
                        card_count = 1
                        mult_match = re.search(r'\*(\d+)$', cn_raw)
                        if mult_match:
                            card_count = int(mult_match.group(1))
                            cn_raw = cn_raw[:mult_match.start()]
                            
                        condition_str = "Near Mint"
                        cond_match = re.search(r'(dmg|hp|mp|sp|nm|m)$', cn_raw)
                        if cond_match:
                            condition_str = CONDITIONS[cond_match.group(1)]
                            cn_raw = cn_raw[:-len(cond_match.group(1))]
                            
                        is_foil = False
                        if cn_raw.endswith('f'):
                            is_foil = True
                            cn_raw = cn_raw[:-1]
                            
                        parsed_list.append(f"Set: {current_set}, CN: {cn_raw}, Foil: {is_foil}, Cond: {condition_str}, Qty: {card_count}")
                    
                    out_text = "Type: REGULAR CARD BLOCK\n" + "\n".join(parsed_list)
                    lbl_parse_result.config(text=out_text, fg="green")
                else:
                    # Parse token
                    parsed = self.parse_token_string(raw_str)
                    if parsed['type'] == 'UNKNOWN':
                        lbl_parse_result.config(text="Result: Unknown Format", fg="red")
                    else:
                        out_text = f"Type: {parsed['type']}\n"
                        out_text += f"Front: Set {parsed['front']['set'].upper()}, CN #{parsed['front']['cn']}\n"
                        if 'back' in parsed:
                            out_text += f"Back:  Set {parsed['back']['set'].upper()}, CN #{parsed['back']['cn']}\n"
                        out_text += f"Foil:  {parsed['foil']} | DFC: {'d' in raw_str.lower()}\n"
                        out_text += f"Cond:  {parsed.get('condition', 'Near Mint')} | Qty: {parsed['count']}"
                        lbl_parse_result.config(text=out_text, fg="green")
            except Exception as ex:
                lbl_parse_result.config(text=f"Result Error: {ex}", fg="red")
                
        btn_test = tk.Button(tester_frame, text="Test Parse", command=run_test_parse)
        btn_test.grid(row=1, column=1, padx=5, pady=5)
        
        lbl_parse_result.grid(row=2, column=0, columnspan=2, sticky="we", padx=5, pady=5)
        tester_frame.columnconfigure(0, weight=1)

    # --- MERGE / GROUPING DUPLICATE FUNCTION ---
    def add_or_merge_card(self, card_list, new_card):
        for existing in card_list:
            if (existing.get('set') == new_card.get('set') and
                existing.get('cn') == new_card.get('cn') and
                existing.get('name') == new_card.get('name') and
                existing.get('foil') == new_card.get('foil') and
                existing.get('condition') == new_card.get('condition') and
                existing.get('tag') == new_card.get('tag')):
                
                existing['count'] = existing.get('count', 1) + new_card.get('count', 1)
                return
        card_list.append(new_card)

    # --- CORE LOGIC PORTED FROM MAIN ---
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

        self.logger.info(f"Downloading data for set: '{set_code}'")
        url = f"https://api.scryfall.com/cards/search?q=set:{set_code}&unique=prints&page=1"
        card_map = {}
        has_more = True
        
        try:
            while has_more:
                response = http_session.get(url, headers=SCRYFALL_HEADERS)
                if response.status_code == 404:
                    self.logger.error(f"Set code '{set_code}' not found on Scryfall.")
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
            return card_map
        except Exception as e:
            self.logger.error(f"Network error on {set_code}: {e}")
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
            
        if not self.var_enable_lookup.get():
            return "[No Lookup]", lookup_code
            
        set_data = self.get_set_data(lookup_code)
        return set_data.get(collector_number, None), lookup_code

    def get_card_data(self, parsed_set_code, parsed_collector_number):
        card_name, full_set_code = self.resolve_name(parsed_set_code, parsed_collector_number, is_token=True)
        if not card_name: 
            self.logger.warning(f"Token name not found for {full_set_code.upper()} #{parsed_collector_number}")
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
                            
        return history_map

    def save_current_history(self, new_history_map):
        if not new_history_map: 
            return
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(DUPE_DIR, f"session_{timestamp}.txt"), 'w', encoding='utf-8') as history_file:
            for identifier, is_foil in new_history_map.items():
                if is_foil:
                    history_file.write(f"{identifier}|F\n")
                else:
                    history_file.write(f"{identifier}\n")

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
            self.logger.info(f"Generated output CSV file: {filename}")
        except Exception as e:
            self.logger.error(f"CSV Write Error: {e}")

    def _route_regular_chunk(self, chunk, results):
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
                    self.logger.warning(f"Could not parse set code from: {item}")
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
                self.logger.warning(f"Regular card name not found for {full_set_code.upper()} #{cn_raw}")
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

    def _route_token(self, parsed_token, history_map, results):
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
                back_card['front_name'] = front_card['name'] # back card references front card name for sorting!
                
                front_card['tag'] = f"Back is {back_card['set'].upper()} {back_card['cn']} ({back_card['name']})"
                back_card['tag'] = f"Front is {front_card['set'].upper()} {front_card['cn']} ({front_card['name']})"
                
                card_identifier = f"{front_card['set']}:{front_card['cn']}|{back_card['set']}:{back_card['cn']}"
                
                is_dupe = False
                if card_identifier in history_map:
                    existing_foil_status = history_map[card_identifier]
                    
                    if is_foil and not existing_foil_status:
                        history_map[card_identifier] = True
                        results['new_history'][card_identifier] = True
                        self.logger.info(f"Upgrade: {card_identifier} (Foil replaces Non-Foil)")
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
                    self.logger.info(f"Duplicate: {card_identifier} ({'Foil' if is_foil else 'Non-Foil'})")
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
        
        parsed_tokens = []
        for raw_input_string in raw_input_strings:
            raw_input_string = raw_input_string.strip()
            if not raw_input_string: 
                continue
            
            if raw_input_string.startswith('@'):
                self._route_regular_chunk(raw_input_string, results)
                continue
                
            parsed = self.parse_token_string(raw_input_string)
            if parsed['type'] == 'UNKNOWN':
                self.logger.warning(f"Could not parse token string format: '{raw_input_string}'")
            else:
                parsed_tokens.append(parsed)

        parsed_tokens.sort(key=lambda x: not x.get('foil', False))

        self.logger.info("Processing parsed tokens...")
        for parsed_token in parsed_tokens:
            self._route_token(parsed_token, history_map, results)
            
        return results

    # --- MAIN RUN ANALYSIS METHOD ---
    def run_analysis(self):
        self.btn_run.config(state="disabled", text="Processing...")
        self.root.update_idletasks()
        
        try:
            raw_text = self.txt_input.get("1.0", tk.END).strip()
            if not raw_text:
                messagebox.showwarning("Warning", "Please enter some input to analyze.")
                return
                
            # Parse inputs
            raw_input_strings = raw_text.replace('\n', '/').split('/')
            raw_input_strings = [s.strip() for s in raw_input_strings if s.strip()]
            
            if not raw_input_strings:
                messagebox.showwarning("Warning", "No valid input strings found.")
                return
                
            # Clear results
            self.txt_results.config(state="normal")
            self.txt_results.delete("1.0", tk.END)
            
            self.logger.info(f"Starting analysis session...")

            # Load history
            history_map = self.load_history()
            original_history_keys = set(history_map.keys())
            history_map_copy = history_map.copy()
            
            # Process batch
            results = self.process_batch(raw_input_strings, history_map_copy)
            warnings = []
            
            # Gather card metadata (color identity & type line) using scryfall_core
            scryfall_resolved_data = {}
            
            # Collect all parsed cards
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
                sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, "..", "core_tools")))
                import scryfall_core
                scryfall_core_loaded = True
            except Exception as e:
                warnings.append(f"!! Warning: Failed to load core_tools/scryfall_core.py: {e}")
                self.logger.error(f"Failed to load scryfall_core module: {e}")

            if scryfall_core_loaded:
                # 1. Attempt loading metadata from local cache first (even if lookup is disabled)
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
                    elif self.var_enable_lookup.get():
                        if qkey not in seen_queries:
                            seen_queries.add(qkey)
                            cards_to_resolve.append(card_query)
                            
                # 2. Fetch uncached entries from Scryfall if enabled
                if self.var_enable_lookup.get() and cards_to_resolve:
                    try:
                        self.logger.info(f"Querying Scryfall API for {len(cards_to_resolve)} uncached card metadata...")
                        scryfall_core.resolve_cards(cards_to_resolve)
                        # Load newly fetched records
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
                        self.logger.error(f"Failed to query Scryfall API: {e}")

            # Build list of cards for table
            # Row layout: [set, cn, name, type, foil, condition, qty, note, color_identity, type_line, front_name]
            headers = ["Set", "CN", "Name", "Type", "Foil", "Condition", "Qty", "Note"]
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
                
            # Perform sorting and land extraction
            basic_land_rows = []
            non_basic_land_rows = []
            spell_rows = []
            
            if self.var_enable_wubrg.get():
                # Extract lands, separating basic lands from non-basic lands
                for row in table_rows:
                    is_land = False
                    is_basic = False
                    if row[3] == "Regular":
                        type_line = row[9] # index 9 is type_line
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
                
                # Sorting functions
                def get_non_land_wubrg_key(color_list):
                    color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
                    ranks = sorted([color_map[c] for c in color_list if c in color_map])
                    if len(ranks) == 1:
                        # WUBRG (0 to 4)
                        return (ranks[0],)
                    elif len(ranks) == 0:
                        # Colourless
                        return (5,)
                    else:
                        # id > 1
                        return (6,)
                
                def get_land_sort_key(color_list, card_name):
                    color_map = {'W': 0, 'U': 1, 'B': 2, 'R': 3, 'G': 4}
                    ranks = sorted([color_map[c] for c in color_list if c in color_map])
                    length = len(ranks)
                    
                    if length == 2:
                        sorted_letters = tuple(sorted([c for c in color_list if c in color_map]))
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
                        guild_name = guild_map.get(sorted_letters, '')
                        return (2, guild_name.lower(), card_name.lower())
                    elif length == 1:
                        return (1, str(ranks[0]), card_name.lower())
                    elif length == 0:
                        return (0, '', card_name.lower())
                    else:
                        return (length, '', card_name.lower())
                
                # Sort non-basic lands: Custom Land Key
                non_basic_land_rows.sort(key=lambda x: get_land_sort_key(x[8], x[2]))
                # Sort basic lands: Custom Land Key
                basic_land_rows.sort(key=lambda x: get_land_sort_key(x[8], x[2]))
            else:
                table_rows.sort(key=lambda x: (x[3], x[0], x[1]))
                spell_rows = table_rows
            
            # Calculate counts
            regular_qty = sum(card['count'] for card in results['regular_cards'])
            ss_token_qty = sum(card['count'] for card in results['single_sided'])
            ds_front_qty = sum(card['count'] for card in results['ds_fronts'])
            ds_back_qty = sum(card['count'] for card in results['ds_backs'])
            ds_front_dupe_qty = sum(card['count'] for card in results['ds_fronts_dupes'])
            ds_back_dupe_qty = sum(card['count'] for card in results['ds_backs_dupes'])
            
            total_cards = sum(r[6] for r in table_rows)
            foil_cards = sum(r[6] for r in table_rows if r[4] == "Yes")
            non_foil_cards = total_cards - foil_cards
            
            upgrades_count = sum(1 for key in results['new_history'] if key in original_history_keys)
            new_unique_ds_count = sum(1 for key in results['new_history'] if key not in original_history_keys)
            dupes_count = len(results['dupe_identifiers'])
            
            # Set Distribution
            set_counts = {}
            for r in table_rows:
                if r[3] in ["DS Back", "DS Back (Dupe)"]:
                    continue
                set_code = r[0]
                set_counts[set_code] = set_counts.get(set_code, 0) + r[6]
            sorted_sets = sorted(set_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Write Report to Text Widget
            self.append_result("="*90 + "\n")
            self.append_result(" " * 28 + "MOXFIELD IMPORT DRY RUN REPORT\n")
            self.append_result("="*90 + "\n\n")
            
            # 1. Summary Block
            self.append_result("[1] GENERAL STATISTICS\n", "bold")
            self.append_result("-" * 35 + "\n")
            self.append_result(f"  Total Cards (for Moxfield import):  ")
            self.append_result(f"{total_cards}\n", "bold")
            self.append_result(f"  ├── Regular Cards (Non-token):      {regular_qty}\n")
            self.append_result(f"  └── Tokens (Total physical count):  {ss_token_qty + ds_front_qty + ds_front_dupe_qty}\n")
            self.append_result(f"      ├── Single-Sided:               {ss_token_qty}\n")
            self.append_result(f"      └── Double-Sided (Unique):      {ds_front_qty}\n")
            self.append_result(f"      └── Double-Sided (Duplicate):   {ds_front_dupe_qty}\n\n")
            
            self.append_result("  Foil / Non-Foil Breakdown:\n")
            self.append_result(f"  ├── Foils:                          ")
            self.append_result(f"{foil_cards}\n", "bold")
            self.append_result(f"  └── Non-Foils:                      {non_foil_cards}\n\n")
            
            self.append_result("  Double-Sided Token Duplicate Checking:\n")
            self.append_result(f"  ├── New Unique DS Tokens:               ")
            self.append_result(f"{new_unique_ds_count}\n", "bold")
            self.append_result(f"  ├── Foil Upgrades (Replaces Non-Foil):  ")
            self.append_result(f"{upgrades_count}\n", "bold")
            self.append_result(f"  └── Skipped Duplicates (Already Saved): ")
            self.append_result(f"{dupes_count}\n\n", "bold")
            
            # 2. Warnings
            if warnings:
                self.append_result("[2] WARNINGS / RESOLUTION ISSUES\n", "warning")
                self.append_result("-" * 35 + "\n")
                for w in warnings:
                    self.append_result(f"  {w}\n", "warning")
                self.append_result("\n")
                
            # 3. History Actions Log
            if results['new_history'] or results['dupe_identifiers']:
                self.append_result("[3] HISTORY / DEDUPLICATION LOG\n", "bold")
                self.append_result("-" * 35 + "\n")
                for identifier, is_foil in results['new_history'].items():
                    if identifier in original_history_keys:
                        self.append_result(f"  -> Upgrade: {identifier} (Foil replaces Non-Foil)\n")
                    else:
                        self.append_result(f"  -> New Unique DS Token Saved: {identifier}\n")
                for identifier in results['dupe_identifiers']:
                    self.append_result(f"  -> Duplicate Token Skipped: {identifier}\n")
                self.append_result("\n")
                
            # 4. Set Distribution
            self.append_result("[4] SET DISTRIBUTION (Excludes DS Back-sides for totals)\n", "bold")
            self.append_result("-" * 35 + "\n")
            if sorted_sets:
                for set_code, count in sorted_sets:
                    self.append_result(f"  {set_code:<8} : {count} cards\n")
            else:
                self.append_result("  No sets parsed.\n")
            self.append_result("\n")
            
            # 5. Detailed Tables (Separated by Set if WUBRG sorting is enabled)
            self.append_result("[5] RESOLVED CARD DETAILS\n", "bold")
            self.append_result("-" * 35 + "\n")
            
            if self.var_enable_wubrg.get():
                # Group spells by set code
                set_groups = defaultdict(list)
                for row in spell_rows:
                    set_code = row[0]
                    set_groups[set_code].append(row)
                
                unique_sets = sorted(set_groups.keys())
                
                # Check for token sets (using scryfall_core query or fallback)
                token_sets_detected = set()
                if scryfall_core_loaded:
                    try:
                        for set_code in unique_sets:
                            if scryfall_core.is_token_set(set_code):
                                token_sets_detected.add(set_code.upper())
                    except Exception as e:
                        self.logger.error(f"Error checking token set: {e}")
                for set_code in unique_sets:
                    if set_code.upper() not in token_sets_detected:
                        if set_code.upper().startswith('T') and len(set_code) >= 4:
                            token_sets_detected.add(set_code.upper())
                
                sub_idx = 1
                for set_code in unique_sets:
                    group_rows = set_groups[set_code]
                    
                    if set_code.upper() in token_sets_detected:
                        # Token Set Sorting: Sort alphabetically by front side name, and back side follows front immediately
                        def get_token_sort_key(row):
                            front_name = row[10] # index 10 is front_name
                            side_key = 1 if "Back" in row[3] else 0
                            return (front_name.lower(), side_key, row[2].lower())
                        group_rows.sort(key=get_token_sort_key)
                    else:
                        # Normal Set Sorting: Sort by spells WUBRG key then name
                        group_rows.sort(key=lambda x: (get_non_land_wubrg_key(x[8]), x[2].lower()))
                    
                    self.append_result(f"\n[5.{sub_idx}] SET: {set_code} DETAILS\n", "bold")
                    self.append_result("-" * 35 + "\n")
                    self.append_table_to_widget(headers, group_rows)
                    sub_idx += 1
                
                # Append pooled non-basic lands table
                if non_basic_land_rows:
                    self.append_result(f"\n[5.{sub_idx}] SET: LAND DETAILS\n", "bold")
                    self.append_result("-" * 35 + "\n")
                    self.append_table_to_widget(headers, non_basic_land_rows)
                    sub_idx += 1
                
                # Append pooled basic lands table
                if basic_land_rows:
                    self.append_result(f"\n[5.{sub_idx}] SET: BASIC LAND DETAILS\n", "bold")
                    self.append_result("-" * 35 + "\n")
                    self.append_table_to_widget(headers, basic_land_rows)
                    sub_idx += 1
            else:
                self.append_table_to_widget(headers, table_rows)
            
            # 6. File Generation / History Saving if NOT in dry-run mode
            if not self.var_dry_run.get():
                if not os.path.exists(OUTPUT_DIR):
                    os.makedirs(OUTPUT_DIR)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Write CSV files
                self.write_moxfield_csv(f"{timestamp}-single-sided.csv", results['single_sided'])
                self.write_moxfield_csv(f"{timestamp}-double-sided-fronts.csv", results['ds_fronts'])
                self.write_moxfield_csv(f"{timestamp}-double-sided-backs.csv", results['ds_backs'])
                self.write_moxfield_csv(f"{timestamp}-double-sided-fronts-dupes.csv", results['ds_fronts_dupes'])
                self.write_moxfield_csv(f"{timestamp}-double-sided-backs-dupes.csv", results['ds_backs_dupes'])
                self.write_moxfield_csv(f"{timestamp}-regular-cards.csv", results['regular_cards'])
                
                self.append_result(f"\n[+] Generated CSV files in outputs folder with timestamp: {timestamp}\n", "success")
                
                # Write duplicates file if any
                if results['dupe_identifiers']:
                    dupe_list_path = os.path.join(OUTPUT_DIR, f"{timestamp}-session-dupes.txt")
                    try:
                        with open(dupe_list_path, 'w', encoding='utf-8') as f:
                            for identifier in results['dupe_identifiers']:
                                f.write(f"{identifier}\n")
                        self.append_result(f"[+] Created Dupe List: {timestamp}-session-dupes.txt\n", "success")
                    except Exception as e:
                        self.append_result(f"[!] Warning: Dupe List Write Error: {e}\n", "warning")
                        self.logger.error(f"Failed to write duplicates list: {e}")
                        
                # Update history on disk
                if results['new_history']:
                    self.save_current_history(results['new_history'])
                    self.append_result("[+] Token duplicate check history updated on disk.\n", "success")
                
                self.lbl_status.config(text="Analysis & Import completed successfully", fg="green")
                self.logger.info("Import session complete (CSVs generated and history written).")
            else:
                self.append_result("\n[+] Dry run complete. No files written. History not modified.\n", "success")
                self.lbl_status.config(text="Dry Run completed successfully", fg="green")
                self.logger.info("Dry run analysis complete. No files written.")
                
            self.txt_results.config(state="disabled")
            
        except Exception as e:
            self.logger.error(f"Error during analysis execution: {e}", exc_info=True)
            self.txt_results.config(state="normal")
            self.txt_results.insert(tk.END, f"\nAn error occurred during analysis:\n{e}\n", "warning")
            self.txt_results.config(state="disabled")
            self.lbl_status.config(text="Error occurred", fg="red")
            messagebox.showerror("Error", f"An error occurred: {e}")
            
        finally:
            self.btn_run.config(state="normal", text="Run Dry Run Analysis" if self.var_dry_run.get() else "Output CSVs")

if __name__ == "__main__":
    root = tk.Tk()
    app = DryRunApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
