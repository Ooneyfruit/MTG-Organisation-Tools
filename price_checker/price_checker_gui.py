import os
import sys
import csv
import logging
import datetime
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Set up sys.path to import _core_tools
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from _core_tools import scryfall_core
except ImportError as e:
    scryfall_core = None

# Configuration
OUTPUT_DIR = ROOT_DIR / "price_checker" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUTPUT_DIR / "price_checker.log"

# Setup Logging to file and console
logger = logging.getLogger("PriceCheckerGUI")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()

fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(ch)

class PriceCheckerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MTG Collection Price Checker")
        self.root.geometry("800x600")

        # Application State
        self.csv_path = tk.StringVar()
        self.processed_cards = []
        self.sort_column = "Total USD"
        self.sort_descending = True
        self.task_queue = queue.Queue()
        
        # Build standard UI widgets
        self.create_widgets()
        
        # Check dependencies
        if not scryfall_core:
            messagebox.showerror("Error", "Could not load scryfall_core.py. Check that _core_tools is in the workspace.")
            logger.error("Could not load scryfall_core.py.")

        # Auto-detect default CSV if it exists
        default_csv = ROOT_DIR / "moxfield_binder_assigner" / "inputs" / "20260628_184333-regular-cards.csv"
        if default_csv.exists():
            self.csv_path.set(str(default_csv))
            logger.info(f"Auto-detected default CSV: {default_csv}")

        # Start checking queue for thread messages
        self.root.after(100, self.process_queue)

    def create_widgets(self):
        # 1. File Selection Section
        file_frame = tk.LabelFrame(self.root, text="CSV File Selection", padx=10, pady=10)
        file_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_file = tk.Label(file_frame, text="Moxfield CSV:")
        lbl_file.pack(side="left", padx=(0, 5))
        
        ent_file = tk.Entry(file_frame, textvariable=self.csv_path)
        ent_file.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        btn_browse = tk.Button(file_frame, text="Browse...", command=self.browse_csv)
        btn_browse.pack(side="left", padx=(0, 5))
        
        btn_run = tk.Button(file_frame, text="Check Prices", command=self.start_price_checking)
        btn_run.pack(side="left")

        # 2. Progress / Status Panel (Hidden by default, shown when running)
        self.progress_frame = tk.Frame(self.root, padx=10, pady=5)
        self.progress_label = tk.Label(self.progress_frame, text="Ready")
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate")
        
        # 3. Results Section (Table)
        results_frame = tk.LabelFrame(self.root, text="Resolved Card Prices", padx=10, pady=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.lbl_card_count = tk.Label(results_frame, text="No cards loaded")
        self.lbl_card_count.pack(anchor="w", pady=(0, 5))
        
        table_container = tk.Frame(results_frame)
        table_container.pack(fill="both", expand=True)
        
        # Setup columns
        self.columns = ("Name", "Set", "CN", "Foil", "Qty", "Unit USD", "Total USD", "Unit EUR", "Total EUR")
        self.tree = ttk.Treeview(table_container, columns=self.columns, show="headings", selectmode="browse")
        
        # Column configuration
        col_widths = {"Name": 200, "Set": 60, "CN": 60, "Foil": 60, "Qty": 50, "Unit USD": 80, "Total USD": 90, "Unit EUR": 80, "Total EUR": 90}
        col_aligns = {"Name": "w", "Set": "center", "CN": "center", "Foil": "center", "Qty": "center", "Unit USD": "e", "Total USD": "e", "Unit EUR": "e", "Total EUR": "e"}
        
        for col in self.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=col_widths.get(col, 80), anchor=col_aligns.get(col, "center"))

        # Scrollbars
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

        # 4. Totals Footer Panel
        self.totals_frame = tk.LabelFrame(self.root, text="Summary Totals", padx=10, pady=10)
        self.totals_frame.pack(fill="x", padx=10, pady=10)
        
        self.lbl_tot_qty = tk.Label(self.totals_frame, text="Total Quantity: 0", font=("Arial", 10, "bold"))
        self.lbl_tot_qty.pack(side="left", expand=True)
        
        self.lbl_tot_usd = tk.Label(self.totals_frame, text="Total Value (USD): $0.00", font=("Arial", 10, "bold"))
        self.lbl_tot_usd.pack(side="left", expand=True)
        
        self.lbl_tot_eur = tk.Label(self.totals_frame, text="Total Value (EUR): €0.00", font=("Arial", 10, "bold"))
        self.lbl_tot_eur.pack(side="left", expand=True)

    def browse_csv(self):
        filename = filedialog.askopenfilename(
            title="Open Moxfield Collection CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.csv_path.set(filename)

    def show_progress_panel(self, show=True):
        if show:
            self.progress_frame.pack(fill="x", padx=10, pady=5, before=self.totals_frame)
            self.progress_label.pack(side="left", padx=(5, 10))
            self.progress_bar.pack(side="left", fill="x", expand=True)
        else:
            self.progress_frame.pack_forget()

    def update_progress(self, current, total, text):
        self.progress_label.config(text=text)
        if total > 0:
            percent = (current / total) * 100
            self.progress_bar.config(value=percent)
        self.root.update_idletasks()

    def start_price_checking(self):
        path_str = self.csv_path.get().strip()
        if not path_str:
            messagebox.showwarning("Warning", "Please select a CSV file first.")
            return
            
        csv_file = Path(path_str)
        if not csv_file.exists():
            messagebox.showerror("Error", f"File does not exist: {path_str}")
            return

        self.show_progress_panel(True)
        self.update_progress(0, 100, "Initializing...")
        
        self.tree.delete(*self.tree.get_children())
        self.processed_cards = []
        
        # Run resolution in background thread
        threading.Thread(target=self.bg_resolve_prices, args=(csv_file,), daemon=True).start()

    def bg_resolve_prices(self, csv_path: Path):
        try:
            self.task_queue.put(('status', (10, 100, "Reading CSV file...")))
            cards = []
            
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    name = row.get('Name', '').strip()
                    edition = row.get('Edition', '').strip()
                    collector_num = row.get('Collector Number', '').strip()
                    count_str = row.get('Count', '1').strip()
                    
                    try:
                        count = int(count_str) if count_str else 1
                    except ValueError:
                        count = 1

                    if not name:
                        continue

                    cards.append({
                        'name': name,
                        'set': edition,
                        'collector_number': collector_num,
                        'foil': is_foil(row),
                        'count': count,
                        'original_row': row
                    })

            if not cards:
                self.task_queue.put(('error', "No valid cards found in the CSV."))
                return

            self.task_queue.put(('status', (30, 100, f"Resolving {len(cards)} card(s) from cache/API...")))
            
            scryfall_queries = []
            for card in cards:
                scryfall_queries.append({
                    'name': card['name'],
                    'set': card['set'],
                    'collector_number': card['collector_number']
                })
                
            scryfall_core.resolve_cards(scryfall_queries)
            
            self.task_queue.put(('status', (70, 100, "Extracting prices...")))
            
            processed = []
            total_qty = 0
            total_usd = 0.0
            total_eur = 0.0

            for card in cards:
                query = {
                    'name': card['name'],
                    'set': card['set'],
                    'collector_number': card['collector_number']
                }
                scry_data, _ = scryfall_core.load_from_cache(query)
                
                usd_unit = 0.0
                eur_unit = 0.0
                
                if scry_data:
                    prices = scry_data.get('prices', {})
                    if card['foil']:
                        usd_unit = parse_price(prices.get('usd_foil'))
                        if usd_unit == 0.0:
                            usd_unit = parse_price(prices.get('usd'))
                        
                        eur_unit = parse_price(prices.get('eur_foil'))
                        if eur_unit == 0.0:
                            eur_unit = parse_price(prices.get('eur'))
                    else:
                        usd_unit = parse_price(prices.get('usd'))
                        if usd_unit == 0.0:
                            usd_unit = parse_price(prices.get('usd_foil'))
                        
                        eur_unit = parse_price(prices.get('eur'))
                        if eur_unit == 0.0:
                            eur_unit = parse_price(prices.get('eur_foil'))

                card_usd_total = usd_unit * card['count']
                card_eur_total = eur_unit * card['count']

                processed.append({
                    'Name': card['name'],
                    'Set': card['set'],
                    'CN': card['collector_number'],
                    'Foil': "Yes" if card['foil'] else "No",
                    'Qty': card['count'],
                    'Unit USD': usd_unit,
                    'Total USD': card_usd_total,
                    'Unit EUR': eur_unit,
                    'Total EUR': card_eur_total,
                    'original_row': card['original_row']
                })

                total_qty += card['count']
                total_usd += card_usd_total
                total_eur += card_eur_total

            # Generate output CSV file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_csv_path = OUTPUT_DIR / f"price_check_result_{timestamp}.csv"
            
            with open(output_csv_path, mode='w', encoding='utf-8', newline='') as out_f:
                if processed:
                    fieldnames = list(processed[0]['original_row'].keys()) + [
                        'Unit USD', 'Total USD', 'Unit EUR', 'Total EUR'
                    ]
                    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                    writer.writeheader()
                    for c in processed:
                        row_data = c['original_row'].copy()
                        row_data['Unit USD'] = f"{c['Unit USD']:.2f}"
                        row_data['Total USD'] = f"{c['Total USD']:.2f}"
                        row_data['Unit EUR'] = f"{c['Unit EUR']:.2f}"
                        row_data['Total EUR'] = f"{c['Total EUR']:.2f}"
                        writer.writerow(row_data)

            self.task_queue.put(('success', (processed, total_qty, total_usd, total_eur, output_csv_path)))
            
        except Exception as e:
            self.task_queue.put(('error', str(e)))

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.task_queue.get_nowait()
                if msg_type == 'status':
                    current, total, text = data
                    self.update_progress(current, total, text)
                elif msg_type == 'error':
                    self.show_progress_panel(False)
                    messagebox.showerror("Error", f"Failed to check prices: {data}")
                    logger.error(f"Error checking prices: {data}")
                elif msg_type == 'success':
                    processed, total_qty, total_usd, total_eur, output_csv_path = data
                    self.processed_cards = processed
                    self.show_progress_panel(False)
                    
                    # Update totals
                    self.lbl_tot_qty.config(text=f"Total Quantity: {total_qty}")
                    self.lbl_tot_usd.config(text=f"Total Value (USD): ${total_usd:,.2f}")
                    self.lbl_tot_eur.config(text=f"Total Value (EUR): €{total_eur:,.2f}")
                    self.lbl_card_count.config(text=f"{len(processed)} unique entries loaded")
                    
                    # Refresh table display
                    self.refresh_table()
                    
                    messagebox.showinfo("Success", f"Prices resolved successfully!\n\nOutput saved to:\n{output_csv_path}")
                    logger.info(f"Price resolution successful. Output CSV: {output_csv_path}")
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        
        # Sort data
        multiplier = -1 if self.sort_descending else 1
        
        def sort_key(x):
            val = x.get(self.sort_column)
            if isinstance(val, str):
                return val.lower()
            return val

        self.processed_cards.sort(key=sort_key, reverse=self.sort_descending)
        
        for item in self.processed_cards:
            self.tree.insert("", "end", values=(
                item['Name'],
                item['Set'].upper(),
                item['CN'],
                item['Foil'],
                item['Qty'],
                f"${item['Unit USD']:.2f}",
                f"${item['Total USD']:.2f}",
                f"€{item['Unit EUR']:.2f}",
                f"€{item['Total EUR']:.2f}"
            ))

    def sort_by_column(self, col):
        if self.sort_column == col:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = col
            if col in ["Qty", "Unit USD", "Total USD", "Unit EUR", "Total EUR"]:
                self.sort_descending = True
            else:
                self.sort_descending = False
        
        for c in self.columns:
            header_text = c
            if c == self.sort_column:
                header_text += " ▼" if self.sort_descending else " ▲"
            self.tree.heading(c, text=header_text)
            
        self.refresh_table()

def parse_price(val) -> float:
    """Safely converts price strings or None to floats."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace('$', '').replace('€', '').strip())
    except ValueError:
        return 0.0

def is_foil(row: dict) -> bool:
    """Returns True if the card row is a foil or etched version."""
    raw = row.get('Foil', '').strip().lower()
    return bool(raw and raw != 'false')

def main():
    root = tk.Tk()
    app = PriceCheckerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
