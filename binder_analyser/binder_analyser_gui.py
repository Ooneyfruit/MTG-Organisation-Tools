import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from binder_analyser_logic import BinderAnalyser, logger

class BinderAnalyserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MTG Binder Analyser")
        self.root.geometry("1000x800")
        
        self.analyser = BinderAnalyser()
        self.input_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'input'))
        os.makedirs(self.input_dir, exist_ok=True)
        
        # Load last CSV path and ignore proxies state from config
        config = self.load_config()
        self.default_csv = config.get("last_csv", "")
        self.default_ignore_proxies = config.get("ignore_proxies", True) # Default to True
        
        self.create_widgets()

    def load_config(self) -> dict:
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache", "gui_config.json"))
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self, last_csv: str, ignore_proxies: bool):
        config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache"))
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "gui_config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"last_csv": last_csv, "ignore_proxies": ignore_proxies}, f, indent=2)
        except Exception:
            pass

    def create_widgets(self):
        # Main container frame
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- File Selection Row ---
        file_frame = ttk.LabelFrame(main_frame, text="Moxfield CSV File Selection", padding="5 5 5 5")
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_path_var = tk.StringVar(value=self.default_csv)
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(file_frame, text="Browse...", command=self.browse_file)
        browse_btn.pack(side=tk.RIGHT, padx=5)
        
        # --- Settings Row ---
        settings_frame = ttk.LabelFrame(main_frame, text="Analysis Parameters", padding="5 5 5 5")
        settings_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(settings_frame, text="Target Set Code:").pack(side=tk.LEFT, padx=5)
        self.set_code_var = tk.StringVar()
        set_entry = ttk.Entry(settings_frame, textvariable=self.set_code_var, width=15)
        set_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(settings_frame, text="(e.g. dsc, mh2, optional)").pack(side=tk.LEFT, padx=5)
        
        # Ignore Proxies Parameter
        self.ignore_proxies_var = tk.BooleanVar(value=self.default_ignore_proxies)
        proxy_cb = ttk.Checkbutton(settings_frame, text="Ignore Proxies", variable=self.ignore_proxies_var)
        proxy_cb.pack(side=tk.LEFT, padx=20)
        
        run_btn = ttk.Button(settings_frame, text="Run Analysis", command=self.run_analysis)
        run_btn.pack(side=tk.RIGHT, padx=5)
        
        # --- Output Tabbed Area ---
        self.notebook_frame = ttk.LabelFrame(main_frame, text="Analysis Results", padding="5 5 5 5")
        self.notebook_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.notebook = ttk.Notebook(self.notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add initial welcome / summary tab
        self.welcome_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.welcome_tab, text="Summary")
        self.welcome_text = scrolledtext.ScrolledText(self.welcome_tab, wrap=tk.WORD)
        self.welcome_text.pack(fill=tk.BOTH, expand=True)
        
        if self.default_csv:
            self.welcome_text.insert(tk.END, f"Remembered last analyzed CSV:\n{self.default_csv}\n\nClick 'Run Analysis' to process it.")
        else:
            self.welcome_text.insert(tk.END, "Please select a Moxfield CSV file and click 'Run Analysis' to begin.")
        
        # --- Footer/Actions Row ---
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, pady=5)
        
        open_out_btn = ttk.Button(footer_frame, text="Open Outputs Folder", command=self.open_outputs_folder)
        open_out_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(footer_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT, padx=5)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            initialdir=self.input_dir,
            title="Select Moxfield CSV",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if filename:
            self.file_path_var.set(os.path.normpath(filename))
            self.status_var.set("File selected.")

    def run_analysis(self):
        csv_path = self.file_path_var.get()
        if not csv_path:
            messagebox.showwarning("Warning", "Please select a CSV file first.")
            return
            
        if not os.path.exists(csv_path):
            messagebox.showerror("Error", f"Selected CSV file does not exist:\n{csv_path}")
            return
            
        target_set = self.set_code_var.get().strip()
        if not target_set:
            target_set = None
            
        ignore_proxies = self.ignore_proxies_var.get()
        self.save_config(csv_path, ignore_proxies)
            
        self.status_var.set("Analyzing (may fetch MTGGoldfish)...")
        self.root.update_idletasks()
        
        try:
            summary = self.analyser.run_analysis(
                csv_path, 
                target_set=target_set, 
                ignore_proxies=ignore_proxies
            )
            
            # Clear all current tabs
            for tab in self.notebook.tabs():
                self.notebook.forget(tab)
                
            # Recreate welcome/summary tab
            self.welcome_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.welcome_tab, text="Summary")
            self.welcome_text = scrolledtext.ScrolledText(self.welcome_tab, wrap=tk.WORD)
            self.welcome_text.pack(fill=tk.BOTH, expand=True)
            self.welcome_text.insert(tk.END, summary)
            
            # Add dynamic tabs for each metric
            for name, metric in self.analyser.metrics.items():
                tables_dict = metric.get_table_data()
                if tables_dict:
                    # Create tab
                    tab_frame = ttk.Frame(self.notebook)
                    self.notebook.add(tab_frame, text=name.replace('_', ' ').title())
                    
                    # Variable to toggle view
                    toggle_var = tk.BooleanVar(value=False)
                    
                    # Content frame to hold current view
                    content_frame = ttk.Frame(tab_frame)
                    content_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
                    
                    # 1. Text Summary View
                    text_frame = ttk.Frame(content_frame)
                    text_frame.pack(fill=tk.BOTH, expand=True)
                    
                    m_summary = metric.get_summary()
                    t_box = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
                    t_box.pack(fill=tk.BOTH, expand=True)
                    t_box.insert(tk.END, m_summary)
                    t_box.config(state=tk.DISABLED) # read-only
                    
                    # 2. Table View (hidden by default)
                    table_notebook_frame = ttk.Frame(content_frame)
                    
                    # If metagame metric, split pane to show missing decklists details below
                    if name == 'meta_fulfillment':
                        paned = ttk.PanedWindow(table_notebook_frame, orient=tk.VERTICAL)
                        paned.pack(fill=tk.BOTH, expand=True)
                        
                        table_notebook = ttk.Notebook(paned)
                        paned.add(table_notebook, weight=3)
                        
                        details_frame = ttk.LabelFrame(paned, text="Missing Decklist Details (Select a deck above)", padding="5 5 5 5")
                        details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=10)
                        details_text.pack(fill=tk.BOTH, expand=True)
                        details_text.insert(tk.END, "Select an archetype row from the table to see missing cards.")
                        details_text.config(state=tk.DISABLED)
                        paned.add(details_frame, weight=1)
                    else:
                        table_notebook = ttk.Notebook(table_notebook_frame)
                        table_notebook.pack(fill=tk.BOTH, expand=True)
                        details_text = None
                    
                    # Populate sub-tabs in table notebook
                    for sub_tab_name, (headers, rows) in tables_dict.items():
                        sub_tab_frame = ttk.Frame(table_notebook)
                        table_notebook.add(sub_tab_frame, text=sub_tab_name)
                        
                        tree_container = ttk.Frame(sub_tab_frame)
                        tree_container.pack(fill=tk.BOTH, expand=True)
                        
                        tree = ttk.Treeview(tree_container, columns=headers, show="headings", selectmode="browse")
                        
                        tree.sort_col = ""
                        tree.sort_desc = False
                        tree.rows_data = rows
                        tree.headers_list = headers
                        
                        for col in headers:
                            tree.heading(col, text=col, command=lambda c=col, t=tree: sort_tree_column(t, c))
                            align = "w" if col in ["Name", "Artist", "Archetype"] else "center"
                            width = 200 if col in ["Name", "Artist", "Archetype"] else 80
                            tree.column(col, width=width, anchor=align)
                            
                        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview)
                        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=tree.xview)
                        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
                        
                        tree.grid(row=0, column=0, sticky="nsew")
                        vsb.grid(row=0, column=1, sticky="ns")
                        hsb.grid(row=1, column=0, sticky="ew")
                        
                        tree_container.rowconfigure(0, weight=1)
                        tree_container.columnconfigure(0, weight=1)
                        
                        populate_tree(tree, rows)
                        
                        # Bind select listener for metagame archetypes
                        if name == 'meta_fulfillment' and details_text:
                            fmt = sub_tab_name.split()[0].lower()
                            tree.bind(
                                "<<TreeviewSelect>>", 
                                lambda event, t=tree, f=fmt, dt=details_text, m=metric: on_meta_deck_select(t, f, dt, m)
                            )
                            
                        # Add Load More Decks button for metagame
                        if name == 'meta_fulfillment':
                            btn_frame = ttk.Frame(sub_tab_frame, padding="5 5 5 5")
                            btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
                            
                            fmt = sub_tab_name.split()[0].lower()
                            
                            def make_load_more_cb(f=fmt, t=tree, m=metric, s_tab=sub_tab_name):
                                def cb():
                                    self.status_var.set(f"Loading more decks for {f.capitalize()} (fetching MTGGoldfish)...")
                                    self.root.update_idletasks()
                                    try:
                                        m.load_more_decks(f, 10)
                                        new_tables = m.get_table_data()
                                        new_headers, new_rows = new_tables.get(s_tab, ([], []))
                                        
                                        t.rows_data = new_rows
                                        populate_tree(t, new_rows)
                                        self.status_var.set("Additional decks loaded successfully.")
                                    except Exception as ex:
                                        logger.exception("Failed to load more decks")
                                        messagebox.showerror("Error", f"Failed to load more decks:\n{str(ex)}")
                                        self.status_var.set("Failed to load more decks.")
                                return cb
                                
                            load_more_btn = ttk.Button(btn_frame, text="Load More Decks", command=make_load_more_cb())
                            load_more_btn.pack(side=tk.LEFT, padx=5)
                        
                    # Toggle view logic
                    def make_toggle_cb(t_var=toggle_var, txt_fr=text_frame, tbl_fr=table_notebook_frame):
                        def cb():
                            if t_var.get():
                                txt_fr.pack_forget()
                                tbl_fr.pack(fill=tk.BOTH, expand=True)
                            else:
                                tbl_fr.pack_forget()
                                txt_fr.pack(fill=tk.BOTH, expand=True)
                        return cb

                    toggle_cb = ttk.Checkbutton(
                        tab_frame, 
                        text="Show Data Tables", 
                        variable=toggle_var, 
                        command=make_toggle_cb(),
                        style="Toolbutton"
                    )
                    toggle_cb.pack(side=tk.TOP, anchor="nw", padx=5, pady=5)
                    toggle_cb.pack(before=content_frame)
                    
            self.notebook.select(0)
            self.status_var.set("Analysis complete.")
        except Exception as e:
            logger.exception("GUI run_analysis failed")
            messagebox.showerror("Analysis Error", f"An error occurred:\n{str(e)}")
            self.status_var.set("Analysis failed.")

    def open_outputs_folder(self):
        outputs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'outputs'))
        os.makedirs(outputs_dir, exist_ok=True)
        try:
            os.startfile(outputs_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{str(e)}")

def populate_tree(tree, rows):
    tree.delete(*tree.get_children())
    for row in rows:
        display_row = []
        for col_name, val in zip(tree.headers_list, row):
            if col_name == "GBP Price":
                display_row.append(f"£{val:.2f}")
            elif col_name == "EDHREC Rank":
                display_row.append(f"#{val}" if val != 999999 else "Unranked")
            else:
                display_row.append(val)
        tree.insert("", "end", values=display_row)

def sort_tree_column(tree, col):
    idx = tree.headers_list.index(col)
    
    numeric_cols = ["Qty", "GBP Price", "EDHREC Rank", "Total Cards", "Rank Index", "Rank", "Fulfillment %"]
    if tree.sort_col == col:
        tree.sort_desc = not tree.sort_desc
    else:
        tree.sort_col = col
        tree.sort_desc = col in numeric_cols
        
    def sort_key(row):
        val = row[idx]
        if col in numeric_cols:
            try:
                clean_val = str(val).replace('%', '').strip()
                return float(clean_val)
            except (ValueError, TypeError):
                return 0.0
        return str(val).lower()
        
    tree.rows_data.sort(key=sort_key, reverse=tree.sort_desc)
    
    for c in tree.headers_list:
        header_text = c
        if c == tree.sort_col:
            header_text += " ▼" if tree.sort_desc else " ▲"
        tree.heading(c, text=header_text)
        
    populate_tree(tree, tree.rows_data)

def on_meta_deck_select(tree, fmt, details_widget, metric):
    selected = tree.selection()
    if not selected:
        return
    item = tree.item(selected[0])
    values = item['values']
    if not values:
        return
    archetype_name = values[1]
    
    arches = metric.results.get(fmt, [])
    target_arch = None
    for a in arches:
        if a['name'] == archetype_name:
            target_arch = a
            break
            
    if not target_arch:
        return
        
    details_widget.config(state=tk.NORMAL)
    details_widget.delete(1.0, tk.END)
    
    details_widget.insert(tk.END, f"Missing Cards for: {archetype_name} ({fmt.capitalize()} Archetype)\n")
    details_widget.insert(tk.END, f"Theoretical Fulfillment: {target_arch['matched_score']} / {target_arch['target_total']} ({target_arch['fulfillment_pct']:.1f}%)\n")
    details_widget.insert(tk.END, f"Meta Share: {target_arch['pct']}\n")
    details_widget.insert(tk.END, f"Crawler URL: {target_arch['url']}\n")
    details_widget.insert(tk.END, "=" * 60 + "\n\n")
    
    main_missing = target_arch.get('main_missing', {})
    side_missing = target_arch.get('side_missing', {})
    main_matched_cards = target_arch.get('main_matched_cards', {})
    side_matched_cards = target_arch.get('side_matched_cards', {})
    
    if main_missing:
        details_widget.insert(tk.END, "Mainboard Missing Cards (or counts short of archetype pool limit):\n")
        for c_name, qty in main_missing.items():
            details_widget.insert(tk.END, f"  - {qty}x {c_name}\n")
    else:
        details_widget.insert(tk.END, "Mainboard Cards: None missing (Complete!)\n")
        
    details_widget.insert(tk.END, "\n")
    
    if main_matched_cards:
        details_widget.insert(tk.END, "Mainboard Matched Cards (cards you have):\n")
        for c_name, qty in sorted(main_matched_cards.items()):
            details_widget.insert(tk.END, f"  - {qty}x {c_name}\n")
    else:
        details_widget.insert(tk.END, "Mainboard Matched Cards: None\n")
        
    details_widget.insert(tk.END, "\n" + "-" * 50 + "\n\n")
    
    if side_missing:
        details_widget.insert(tk.END, "Sideboard Missing Cards (stitching options short of archetype pool limit):\n")
        for c_name, qty in side_missing.items():
            details_widget.insert(tk.END, f"  - {qty}x {c_name}\n")
    else:
        details_widget.insert(tk.END, "Sideboard Cards: None missing (Stitched sideboard complete!)\n")
        
    details_widget.insert(tk.END, "\n")
    
    if side_matched_cards:
        details_widget.insert(tk.END, "Sideboard Matched Cards (cards you have):\n")
        for c_name, qty in sorted(side_matched_cards.items()):
            details_widget.insert(tk.END, f"  - {qty}x {c_name}\n")
    else:
        details_widget.insert(tk.END, "Sideboard Matched Cards: None\n")
        
    details_widget.config(state=tk.DISABLED)

def main():
    root = tk.Tk()
    app = BinderAnalyserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
