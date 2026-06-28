import os
import sys
import logging
import datetime
import tkinter as tk
from tkinter import messagebox, scrolledtext

# Add SCRIPT_DIR to path to allow importing local modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from moxfield_importer_logic import MoxfieldImporter, format_report_as_ascii, CONDITIONS

# --- FILE PATHS ---
INPUT_FILE = os.path.join(SCRIPT_DIR, "input.txt")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# --- GLOBAL LOGGER SETUP ---
def setup_logging():
    if not os.path.exists(LOG_DIR): 
        os.makedirs(LOG_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"import_gui_log_{timestamp}.log")
    
    logger = logging.getLogger("MoxfieldToolGui")
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

class MoxfieldImportGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Moxfield Import - Dry Run & Import Companion")
        self.root.geometry("850x650")
        
        # Initialize logging
        self.logger, self.log_filename = setup_logging()
        
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

    def format_table_to_ascii(self, headers, rows):
        if not rows:
            return "  No data resolved.\n"
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i in range(len(headers)):
                col_widths[i] = max(col_widths[i], len(str(row[i])))
                
        separator = "+" + "+".join("-" * (width + 2) for width in col_widths) + "+\n"
        
        out = separator
        out += "| " + " | ".join(f"{str(h).ljust(col_widths[i])}" for i, h in enumerate(headers)) + " |\n"
        out += separator
        for row in rows:
            out += "| " + " | ".join(f"{str(row[i]).ljust(col_widths[i])}" for i in range(len(headers))) + " |\n"
        out += separator
        return out

    def show_help_window(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("Moxfield Fast Import - Syntax Guide & Interactive Tester")
        help_win.geometry("760x820")
        help_win.grab_set()
        
        # Scrollable Guideline Text
        lbl_guide = tk.Label(help_win, text="Import Syntax Guidelines & Documentation", font=("Arial", 11, "bold"))
        lbl_guide.pack(anchor="w", padx=15, pady=(10, 2))
        
        txt_guide = scrolledtext.ScrolledText(help_win, height=26, font=("Courier", 9))
        txt_guide.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Configure tags for beautiful formatting
        txt_guide.tag_config("banner", font=("Courier", 9, "bold"), foreground="#1A365D")
        txt_guide.tag_config("h1", font=("Courier", 10, "bold"), foreground="#2B6CB0")
        txt_guide.tag_config("h2", font=("Courier", 9, "bold"), foreground="#2B6CB0")
        txt_guide.tag_config("bold", font=("Courier", 9, "bold"))
        txt_guide.tag_config("accent", font=("Courier", 9, "bold"), foreground="#C53030")
        
        # Insert styled guide content
        txt_guide.insert(tk.END, "="*90 + "\n", "banner")
        txt_guide.insert(tk.END, " " * 28 + "MOXFIELD FAST IMPORT - SYNTAX GUIDE\n", "banner")
        txt_guide.insert(tk.END, "="*90 + "\n\n", "banner")
        
        txt_guide.insert(tk.END, "GENERAL OVERVIEW:\n", "h1")
        txt_guide.insert(tk.END, "-----------------\n", "h1")
        txt_guide.insert(tk.END, "1. Separate card input entries using slashes ('/') or newlines.\n")
        txt_guide.insert(tk.END, "2. ")
        txt_guide.insert(tk.END, "Default Mode", "bold")
        txt_guide.insert(tk.END, ": Input strings are evaluated under ")
        txt_guide.insert(tk.END, "Token Syntax", "accent")
        txt_guide.insert(tk.END, " (supporting DFCs, single-sided tokens, and same/cross-set combinations).\n")
        txt_guide.insert(tk.END, "3. ")
        txt_guide.insert(tk.END, "Regular Card Mode", "bold")
        txt_guide.insert(tk.END, ": Prepend ")
        txt_guide.insert(tk.END, "@", "accent")
        txt_guide.insert(tk.END, " to treat a block as ")
        txt_guide.insert(tk.END, "Regular Cards", "accent")
        txt_guide.insert(tk.END, " (standard spells, lands, etc.).\n")
        txt_guide.insert(tk.END, "4. Automatically prioritises Foils over Non-Foils during token deduplication checks.\n")
        txt_guide.insert(tk.END, "5. Generates Moxfield-ready CSV lists in the `/outputs` directory (when Dry Run is disabled).\n\n")
        
        txt_guide.insert(tk.END, "1. TOKEN SYNTAX MODE (Default / Unmarked)\n", "h1")
        txt_guide.insert(tk.END, "---------------------------------------------------------\n", "h1")
        txt_guide.insert(tk.END, "Not every card entered in default mode is a token, but the parser specifically evaluates these strings using MTG token collector formats:\n\n")
        
        txt_guide.insert(tk.END, "  * Double-Sided Token (Same Set):\n", "bold")
        txt_guide.insert(tk.END, "    7pip22        -> TPIP #7 (Front) and TPIP #22 (Back)\n")
        txt_guide.insert(tk.END, "  * Double-Sided Token (Different Sets):\n", "bold")
        txt_guide.insert(tk.END, "    snc15ncc26    -> TSNC #15 (Front) and TNCC #26 (Back)\n")
        txt_guide.insert(tk.END, "  * Double-Sided Single Entry (DFC Token):\n", "bold")
        txt_guide.insert(tk.END, "    dft14*d       -> TDFT #14 (Front/Back share collector number)\n")
        txt_guide.insert(tk.END, "  * Single-Sided Token:\n", "bold")
        txt_guide.insert(tk.END, "    one5 OR 5one  -> TONE #5 (supports Set+CN or CN+Set)\n")
        txt_guide.insert(tk.END, "  * Set Forcing ('!'):\n", "bold")
        txt_guide.insert(tk.END, "    21!mh327      -> TMH3 #21 (Front) and TMH3 #27 (Back) [used if set contains numbers]\n\n")
        
        txt_guide.insert(tk.END, "2. REGULAR CARD MODE (Starts with '@')\n", "h1")
        txt_guide.insert(tk.END, "---------------------------------------------------------\n", "h1")
        txt_guide.insert(tk.END, "Used for regular non-token cards (creatures, spells, non-token lands). A block represents a set, followed by collector numbers separated by commas.\n\n")
        txt_guide.insert(tk.END, "  Syntax: @[Set][CN][modifiers]\n\n", "bold")
        txt_guide.insert(tk.END, "  * Standard Entry (Near Mint default):\n")
        txt_guide.insert(tk.END, "    @sld7094,2452   -> SLD #7094 (Near Mint) and SLD #2452 (Near Mint)\n\n")

        txt_guide.insert(tk.END, "3. SUFFIX MODIFIERS & CONDITIONS (Universal)\n", "h1")
        txt_guide.insert(tk.END, "---------------------------------------------------------\n", "h1")
        txt_guide.insert(tk.END, "Suffix modifiers can be applied to BOTH tokens (Default Mode) and regular cards (Starts with '@'):\n\n")
        
        txt_guide.insert(tk.END, "  * Foiling ('f'):\n", "bold")
        txt_guide.insert(tk.END, "    one5*f          -> Token: Foil TONE #5\n")
        txt_guide.insert(tk.END, "    @nem42f         -> Regular Card: Foil NEM #42\n")
        txt_guide.insert(tk.END, "  * Quantity Multiplier ('*<qty>'):\n", "bold")
        txt_guide.insert(tk.END, "    one5*3          -> Token: 3x TONE #5\n")
        txt_guide.insert(tk.END, "    @!mh315*4       -> Regular Card: 4x MH3 #15\n")
        txt_guide.insert(tk.END, "  * Condition Suffixes:\n", "bold")
        txt_guide.insert(tk.END, "    one5sp          -> Token: Lightly Played TONE #5\n")
        txt_guide.insert(tk.END, "    @nem115hp       -> Regular Card: Heavily Played NEM #115\n")
        txt_guide.insert(tk.END, "  * Combined Modifiers:\n", "bold")
        txt_guide.insert(tk.END, "    one5fsp*2       -> Token: 2x Foil, Lightly Played TONE #5\n")
        txt_guide.insert(tk.END, "    @nem115fsp*4    -> Regular Card: 4x Foil, Lightly Played NEM #115\n\n")

        txt_guide.insert(tk.END, "  Condition Codes:\n", "h2")
        txt_guide.insert(tk.END, "    m   -> Mint\n")
        txt_guide.insert(tk.END, "    nm  -> Near Mint (Default)\n")
        txt_guide.insert(tk.END, "    sp  -> Good (Lightly Played)\n")
        txt_guide.insert(tk.END, "    mp  -> Played\n")
        txt_guide.insert(tk.END, "    hp  -> Heavily Played\n")
        txt_guide.insert(tk.END, "    dmg -> Damaged\n\n")

        txt_guide.insert(tk.END, "4. ADVANCED DEDUPLICATION & SORTING\n", "h1")
        txt_guide.insert(tk.END, "---------------------------------------------------------\n", "h1")
        txt_guide.insert(tk.END, "  * Token Duplicate Checking: ", "bold")
        txt_guide.insert(tk.END, "Identifies double-sided tokens that have already been saved to files in previous runs using duplicate_check/*.txt. Allows automatic foil upgrades, while skipping duplicate non-foils.\n")
        txt_guide.insert(tk.END, "  * Token Set Layout: ", "bold")
        txt_guide.insert(tk.END, "Under WUBRG sorting, sets verified as token-only sets sort cards by the name of the front-side token, placing the back-side immediately below it.\n")
        txt_guide.insert(tk.END, "  * Land Extraction: ", "bold")
        txt_guide.insert(tk.END, "Under WUBRG sorting, regular lands are pooled together into LAND DETAILS (sorting: Colorless -> WUBRG -> 2-Color Guilds alphabetically -> 3+ Colors by name). Basic lands are separated into BASIC LAND DETAILS.\n")
        txt_guide.insert(tk.END, "  * Multicolor spells: ", "bold")
        txt_guide.insert(tk.END, "Multicolor spells (id > 1) in regular sets are grouped and sorted purely alphabetically by card name.\n")
        
        txt_guide.config(state="disabled")
        
        # Interactive Parser Tester Frame
        tester_frame = tk.LabelFrame(help_win, text="Interactive Parser Tester", padx=10, pady=10)
        tester_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        desc_lbl = tk.Label(tester_frame, text="Type a single string below and click 'Test Parse' to see how the parser decodes it:", font=("Arial", 9, "italic"))
        desc_lbl.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        ent_test = tk.Entry(tester_frame, width=40, font=("Courier", 10))
        ent_test.grid(row=1, column=0, padx=5, pady=5, sticky="we")
        ent_test.insert(0, "dft14*df3")
        
        lbl_parse_result = tk.Label(tester_frame, text="Result: Click Test Parse", font=("Courier", 9, "bold"), fg="blue", anchor="w", justify="left")
        
        # Instantiate a parser logic mock for tester
        parser_instance = MoxfieldImporter()

        def run_test_parse():
            raw_str = ent_test.get().strip()
            if not raw_str:
                lbl_parse_result.config(text="Result: Please enter a string", fg="red")
                return
            
            try:
                if raw_str.startswith('@'):
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
                    parsed = parser_instance.parse_token_string(raw_str)
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

    def run_analysis(self):
        self.btn_run.config(state="disabled", text="Processing...")
        self.root.update_idletasks()
        
        try:
            raw_text = self.txt_input.get("1.0", tk.END).strip()
            if not raw_text:
                messagebox.showwarning("Warning", "Please enter some input to analyze.")
                return
                
            self.txt_results.config(state="normal")
            self.txt_results.delete("1.0", tk.END)
            
            # Setup Importer instance
            importer = MoxfieldImporter(
                enable_lookup=self.var_enable_lookup.get(),
                enable_wubrg=self.var_enable_wubrg.get(),
                dry_run=self.var_dry_run.get(),
                logger=self.logger
            )
            
            # Perform import execution
            results = importer.run_import_session(raw_text)
            
            if results is None:
                messagebox.showwarning("Warning", "No valid input strings found.")
                return
                
            # Format results
            headers = ["Set", "CN", "Name", "Type", "Foil", "Condition", "Qty", "Note"]
            report = format_report_as_ascii(
                results_dict=results, 
                headers=headers, 
                append_table_callback=self.format_table_to_ascii,
                enable_wubrg=self.var_enable_wubrg.get()
            )
            
            # Print to text box
            self.append_result(report)
            
            # Update status
            if self.var_dry_run.get():
                self.lbl_status.config(text="Dry Run completed successfully", fg="green")
            else:
                self.lbl_status.config(text="Import completed (files generated)", fg="green")
                
            self.txt_results.config(state="disabled")
            
        except Exception as e:
            self.logger.error(f"Error executing GUI analysis: {e}", exc_info=True)
            self.txt_results.config(state="normal")
            self.txt_results.insert(tk.END, f"\nAn error occurred during analysis:\n{e}\n", "warning")
            self.txt_results.config(state="disabled")
            self.lbl_status.config(text="Error occurred", fg="red")
            messagebox.showerror("Error", f"An error occurred: {e}")
            
        finally:
            self.btn_run.config(state="normal", text="Run Dry Run Analysis" if self.var_dry_run.get() else "Output CSVs")

if __name__ == "__main__":
    root = tk.Tk()
    app = MoxfieldImportGui(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
