import logging
import sys
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional

# Import logic
from moxfield_binder_logic import assign_cards_to_binders, is_foil

# --- Configurations ---
SCRIPT_DIR = Path(__file__).parent
INPUTS_DIR = SCRIPT_DIR / "inputs"
LOGS_DIR = SCRIPT_DIR / "logs"

def get_default_path(filename: str) -> Optional[Path]:
    p = INPUTS_DIR / filename
    return p if p.is_file() else None

DEFAULT_INPUT = get_default_path("20260628_184333-regular-cards.csv")
DEFAULT_ALKOO = get_default_path("ALKOO_moxfield_haves_2026-06-28-1818Z.csv")
DEFAULT_PLEATHER = get_default_path("SmallPleather_moxfield_haves_2026-06-28-1818Z.csv")
OUTPUT_DIR = SCRIPT_DIR / "outputs"

class TextHandler(logging.Handler):
    """Logging handler to direct logs to a Tkinter ScrolledText widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
        self.text_widget.after(0, append)

class MoxfieldBinderGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Moxfield Binder Assigner")
        self.root.geometry("780x680")
        
        self.logger = self.setup_logging()

        # --- Header & Graphical Flowchart ---
        header_frame = tk.Frame(root)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        lbl_title = tk.Label(
            header_frame, 
            text="Moxfield Binder Assigner", 
            font=("Arial", 14, "bold")
        )
        lbl_title.pack(anchor="w")

        diagram_frame = tk.LabelFrame(root, text="Binder Assignment Workflow Flowchart", font=("Arial", 9, "bold"), padx=10, pady=5)
        diagram_frame.pack(fill="x", padx=15, pady=5)

        canvas = tk.Canvas(diagram_frame, height=90, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
        canvas.pack(fill="x", expand=True, pady=5)

        # Draw flowchart elements
        canvas.create_rectangle(15, 25, 125, 65, fill="#e8f4fd", outline="#b3d7ff", width=1.5)
        canvas.create_text(70, 45, text="Incoming CSV\n(Regular Cards)", font=("Arial", 8, "bold"), justify="center", fill="#004085")

        canvas.create_line(130, 45, 175, 45, arrow=tk.LAST, width=2, fill="#6c757d")
        
        canvas.create_line(175, 45, 230, 15, arrow=tk.LAST, width=1.5, fill="#ffc107")
        canvas.create_rectangle(235, 3, 355, 27, fill="#fff3cd", outline="#ffeeba", width=1)
        canvas.create_text(295, 15, text="Price > $1 / €1 ➔ Yellow", font=("Arial", 8), fill="#856404")

        canvas.create_line(175, 45, 230, 35, arrow=tk.LAST, width=1.5, fill="#dc3545")
        canvas.create_rectangle(235, 29, 355, 53, fill="#f8d7da", outline="#f5c6cb", width=1)
        canvas.create_text(295, 41, text="ALKOO Sets ➔ ALKOO Case", font=("Arial", 8), fill="#721c24")

        canvas.create_line(175, 45, 230, 55, arrow=tk.LAST, width=1.5, fill="#28a745")
        canvas.create_rectangle(235, 55, 355, 79, fill="#d4edda", outline="#c3e6cb", width=1)
        canvas.create_text(295, 67, text="Basics ➔ Basics/Fancy", font=("Arial", 8), fill="#155724")

        canvas.create_line(175, 45, 230, 75, arrow=tk.LAST, width=1.5, fill="#17a2b8")
        canvas.create_rectangle(235, 78, 355, 88, fill="#e2e3e5", outline="#d6d8db", width=1)
        canvas.create_text(295, 83, text="Rest ➔ Small Pleather", font=("Arial", 8), fill="#383d41")

        canvas.create_line(360, 41, 420, 41, arrow=tk.LAST, width=1.5, fill="#6c757d")
        canvas.create_line(360, 83, 420, 83, arrow=tk.LAST, width=1.5, fill="#6c757d")
        
        canvas.create_rectangle(425, 35, 545, 75, fill="#fdfdfe", outline="#dfdfdf", width=1)
        canvas.create_text(485, 55, text="Duplicate Checks\n(Foil upgrades generate swaps)", font=("Arial", 7), justify="center", fill="#333333")

        canvas.create_line(550, 55, 595, 55, arrow=tk.LAST, width=1.5, fill="#6c757d")
        canvas.create_rectangle(600, 35, 740, 75, fill="#e2e3e5", outline="#d6d8db", width=1)
        canvas.create_text(670, 55, text="Duplicates & Unwanted CSV\n& swap_recommendations.txt", font=("Arial", 7, "bold"), justify="center", fill="#383d41")

        # --- File Fields ---
        files_frame = tk.LabelFrame(root, text="File Configuration", font=("Arial", 9, "bold"), padx=10, pady=10)
        files_frame.pack(fill="x", padx=15, pady=5)

        lbl_input = tk.Label(files_frame, text="Incoming Card List CSV:")
        lbl_input.grid(row=0, column=0, sticky="w", pady=5)
        self.ent_input = tk.Entry(files_frame, width=65)
        self.ent_input.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        btn_browse_input = tk.Button(files_frame, text="Browse...", command=self.browse_input)
        btn_browse_input.grid(row=0, column=2, padx=5, pady=5)

        lbl_alkoo = tk.Label(files_frame, text="Existing ALKOO Case CSV:")
        lbl_alkoo.grid(row=1, column=0, sticky="w", pady=5)
        self.ent_alkoo = tk.Entry(files_frame, width=65)
        self.ent_alkoo.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        btn_browse_alkoo = tk.Button(files_frame, text="Browse...", command=self.browse_alkoo)
        btn_browse_alkoo.grid(row=1, column=2, padx=5, pady=5)

        lbl_pleather = tk.Label(files_frame, text="Existing Small Pleather CSV:")
        lbl_pleather.grid(row=2, column=0, sticky="w", pady=5)
        self.ent_pleather = tk.Entry(files_frame, width=65)
        self.ent_pleather.grid(row=2, column=1, padx=5, pady=5, sticky="we")
        btn_browse_pleather = tk.Button(files_frame, text="Browse...", command=self.browse_pleather)
        btn_browse_pleather.grid(row=2, column=2, padx=5, pady=5)

        files_frame.columnconfigure(1, weight=1)

        act_frame = tk.Frame(root)
        act_frame.pack(fill="x", padx=15, pady=10)

        self.btn_run = tk.Button(
            act_frame,
            text="Categorize & Assign Cards ➔",
            command=self.run_assignment,
            font=("Arial", 10, "bold"),
            bg="#d4edda"
        )
        self.btn_run.pack(side="right", padx=5)

        # --- Console Output Panel ---
        results_frame = tk.LabelFrame(root, text="Execution Terminal & Swap Recommendations", font=("Arial", 9, "bold"), padx=10, pady=10)
        results_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.txt_logs = scrolledtext.ScrolledText(results_frame, font=("Courier", 10), state='disabled', bg="#f8f9fa")
        self.txt_logs.pack(fill="both", expand=True)

        text_handler = TextHandler(self.txt_logs)
        text_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(text_handler)

        self.prefill_fields()

    def setup_logging(self) -> logging.Logger:
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"assigner_gui_{timestamp}.log"
        
        logger = logging.getLogger("BinderAssignerGUI")
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()

        # File Handler under /logs
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)

        # Console Stream
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

        return logger

    def prefill_fields(self):
        if DEFAULT_INPUT:
            self.ent_input.insert(0, str(DEFAULT_INPUT))
        if DEFAULT_ALKOO:
            self.ent_alkoo.insert(0, str(DEFAULT_ALKOO))
        if DEFAULT_PLEATHER:
            self.ent_pleather.insert(0, str(DEFAULT_PLEATHER))
        self.logger.info("Initialized file configuration fields with available test defaults.")

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select Incoming Card List CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_input.delete(0, tk.END)
            self.ent_input.insert(0, filename)

    def browse_alkoo(self):
        filename = filedialog.askopenfilename(
            title="Select Existing ALKOO Case CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_alkoo.delete(0, tk.END)
            self.ent_alkoo.insert(0, filename)

    def browse_pleather(self):
        filename = filedialog.askopenfilename(
            title="Select Existing Small Pleather CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_pleather.delete(0, tk.END)
            self.ent_pleather.insert(0, filename)

    def run_assignment(self):
        input_csv = Path(self.ent_input.get().strip())
        alkoo_csv = Path(self.ent_alkoo.get().strip())
        pleather_csv = Path(self.ent_pleather.get().strip())

        if not input_csv.is_file():
            messagebox.showerror("Error", f"Incoming card list CSV not found:\n{input_csv}")
            return
        if not alkoo_csv.is_file():
            messagebox.showerror("Error", f"Existing ALKOO Case CSV not found:\n{alkoo_csv}")
            return
        if not pleather_csv.is_file():
            messagebox.showerror("Error", f"Existing Small Pleather CSV not found:\n{pleather_csv}")
            return

        self.txt_logs.configure(state='normal')
        self.txt_logs.delete("1.0", tk.END)
        self.txt_logs.configure(state='disabled')

        self.logger.info("Starting Moxfield card categorization assignment...")
        
        try:
            counts, swaps, binders = assign_cards_to_binders(
                input_csv=input_csv,
                alkoo_inventory_csv=alkoo_csv,
                pleather_inventory_csv=pleather_csv,
                output_dir=OUTPUT_DIR,
                logger=self.logger
            )
            
            self.logger.info("\n" + "="*70)
            self.logger.info("      DETAILED BINDER CLASSIFICATION REPORT")
            self.logger.info("="*70)
            for binder, rows in binders.items():
                self.logger.info(f"\n📁 {binder} ({len(rows)} entry/entries):")
                if rows:
                    ordered_keys = []
                    tallied = {}
                    for r in rows:
                        name = r.get("Name", "").strip()
                        edition = r.get("Edition", "").strip().upper()
                        cn = r.get("Collector Number", "").strip()
                        foil_str = "Foil" if is_foil(r) else "Non-Foil"
                        cond = r.get("Condition", "").strip()
                        qty = int(r.get("Count", "1") or 1)
                        
                        key = (name, edition, cn, foil_str, cond)
                        if key not in tallied:
                            ordered_keys.append(key)
                        tallied[key] = tallied.get(key, 0) + qty
                    for key in ordered_keys:
                        name, edition, cn, foil, cond = key
                        count = tallied[key]
                        details = f"{name} (Edition: {edition}, CN: {cn}, Foil: {foil}, Condition: {cond})"
                        qty_str = f" [{count}x]"
                        self.logger.info(f"   - {details}{qty_str}")
                else:
                    self.logger.info("   (Empty)")

            self.logger.info("\n" + "="*70)
            self.logger.info("      CLASSIFICATION SUMMARY")
            self.logger.info("="*70)
            for binder, count in counts.items():
                self.logger.info(f"  {binder.ljust(35)}: {count} card(s)")
            self.logger.info("="*70)
            
            if swaps:
                self.logger.info("\nPhysical Swap Recommendations:")
                for swap in swaps:
                    self.logger.info(f"  - {swap}")
            else:
                self.logger.info("\nNo card swaps recommended.")

            messagebox.showinfo(
                "Execution Complete",
                f"Successfully categorized cards!\n\n"
                f"Results output folder:\n{OUTPUT_DIR.resolve()}"
            )
        except Exception as e:
            self.logger.error(f"Error executing card assignment: {e}", exc_info=True)
            messagebox.showerror("Execution Error", f"An error occurred: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MoxfieldBinderGui(root)
    root.mainloop()
