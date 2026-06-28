import logging
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Tuple, Optional

# Import core comparator logic
from moxfield_comparator_logic import compare_csv_files

# --- Configuration ---
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("outputs")
OUTPUT_CSV = OUTPUT_DIR / "new_cards_to_import.csv"
OUTPUT_LOG = OUTPUT_DIR / "comparison_summary.txt"
RUNTIME_LOG = OUTPUT_DIR / "runtime.log"

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

class MoxfieldComparatorGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Moxfield CSV Comparator")
        self.root.geometry("750x600")
        
        # Setup logging
        self.logger = self.setup_logging()

        # --- Header & Visual Setup ---
        header_frame = tk.Frame(root)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        lbl_title = tk.Label(
            header_frame, 
            text="Moxfield CSV Comparator", 
            font=("Arial", 14, "bold")
        )
        lbl_title.pack(anchor="w")

        # Visual description/diagram showing how the program works using graphical elements
        diagram_frame = tk.LabelFrame(root, text="Process Flow Diagram", font=("Arial", 9, "bold"), padx=10, pady=5)
        diagram_frame.pack(fill="x", padx=15, pady=5)

        # Create Canvas for drawing the boxes and arrows
        canvas = tk.Canvas(diagram_frame, height=65, bg="#ffffff", highlightthickness=1, highlightbackground="#cccccc")
        canvas.pack(fill="x", expand=True, pady=5)

        # Draw box 1: Input CSV
        canvas.create_rectangle(15, 10, 155, 55, fill="#e8f4fd", outline="#b3d7ff", width=1.5)
        canvas.create_text(85, 32, text="Input CSV\n(Awaiting Cards)", font=("Arial", 9, "bold"), justify="center", fill="#004085")

        # Arrow 1: Input -> Dest
        canvas.create_line(160, 32, 240, 32, arrow=tk.LAST, width=2, fill="#6c757d")
        canvas.create_text(200, 20, text="Compared to", font=("Arial", 8, "italic"), fill="#495057")

        # Draw box 2: Destination CSV
        canvas.create_rectangle(245, 10, 385, 55, fill="#f8d7da", outline="#f5c6cb", width=1.5)
        canvas.create_text(315, 32, text="Destination CSV\n(Base Collection)", font=("Arial", 9, "bold"), justify="center", fill="#721c24")

        # Arrow 2: Dest -> Outputs
        canvas.create_line(390, 32, 470, 32, arrow=tk.LAST, width=2, fill="#6c757d")
        canvas.create_text(430, 20, text="Filters out dupes", font=("Arial", 8, "italic"), fill="#495057")

        # Draw box 3: Outputs
        canvas.create_rectangle(475, 10, 645, 55, fill="#d4edda", outline="#c3e6cb", width=1.5)
        canvas.create_text(560, 32, text="Outputs / Results\n(Import CSV & Summary)", font=("Arial", 9, "bold"), justify="center", fill="#155724")

        # --- File Selection Section ---
        files_frame = tk.LabelFrame(root, text="File Selection", font=("Arial", 9, "bold"), padx=10, pady=10)
        files_frame.pack(fill="x", padx=15, pady=5)

        # Input (Awaiting/New Cards)
        lbl_input = tk.Label(files_frame, text="Input (Awaiting/New Cards):")
        lbl_input.grid(row=0, column=0, sticky="w", pady=5)
        self.ent_input = tk.Entry(files_frame, width=60)
        self.ent_input.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        btn_browse_input = tk.Button(files_frame, text="Browse...", command=self.browse_input)
        btn_browse_input.grid(row=0, column=2, padx=5, pady=5)

        # Destination (Base Collection)
        lbl_dest = tk.Label(files_frame, text="Destination (Base Collection):")
        lbl_dest.grid(row=1, column=0, sticky="w", pady=5)
        self.ent_dest = tk.Entry(files_frame, width=60)
        self.ent_dest.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        btn_browse_dest = tk.Button(files_frame, text="Browse...", command=self.browse_dest)
        btn_browse_dest.grid(row=1, column=2, padx=5, pady=5)

        # Make column 1 expand
        files_frame.columnconfigure(1, weight=1)

        # Buttons Frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=15, pady=10)

        self.btn_swap = tk.Button(btn_frame, text="Swap Files ⇄", command=self.swap_files)
        self.btn_swap.pack(side="left", padx=5)

        self.btn_run = tk.Button(
            btn_frame, 
            text="Run Comparison ➔", 
            command=self.run_comparison,
            font=("Arial", 10, "bold"),
            bg="#d1e7dd"
        )
        self.btn_run.pack(side="right", padx=5)

        # --- Console/Results Output Panel ---
        results_frame = tk.LabelFrame(root, text="Logs & Results Summary", font=("Arial", 9, "bold"), padx=10, pady=10)
        results_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.txt_logs = scrolledtext.ScrolledText(results_frame, font=("Courier", 10), state='disabled', bg="#f8f9fa")
        self.txt_logs.pack(fill="both", expand=True)

        # Attach text logging handler
        text_handler = TextHandler(self.txt_logs)
        text_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(text_handler)

        # Attempt to auto-detect files on startup
        self.auto_detect_files()

    def setup_logging(self) -> logging.Logger:
        OUTPUT_DIR.mkdir(exist_ok=True)
        logger = logging.getLogger("MTGComparatorGUI")
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()

        # File Handler for runtime
        fh = logging.FileHandler(RUNTIME_LOG, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)

        # Stream Handler for stdout
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

        return logger

    def auto_detect_files(self):
        """Pre-populates fields with the two newest CSV files in the input/ folder."""
        if not INPUT_DIR.exists():
            INPUT_DIR.mkdir(exist_ok=True)
            return

        csv_files = list(INPUT_DIR.glob("*.csv"))
        if len(csv_files) >= 2:
            # Sort newest first using OS metadata creation time
            sorted_files = sorted(csv_files, key=lambda p: p.stat().st_ctime, reverse=True)
            input_file = sorted_files[0]
            dest_file = sorted_files[1]

            self.ent_dest.insert(0, str(dest_file.resolve()))
            self.ent_input.insert(0, str(input_file.resolve()))
            self.logger.info(f"Auto-detected most recent files on startup:")
            self.logger.info(f"  Destination: {dest_file.name}")
            self.logger.info(f"  Input:       {input_file.name}\n")
        else:
            self.logger.info("Please browse or type file paths manually to start.")

    def browse_dest(self):
        filename = filedialog.askopenfilename(
            title="Select Destination CSV (Base Collection)",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_dest.delete(0, tk.END)
            self.ent_dest.insert(0, filename)

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select Input CSV (New/Awaiting Cards)",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_input.delete(0, tk.END)
            self.ent_input.insert(0, filename)

    def swap_files(self):
        dest_val = self.ent_dest.get()
        input_val = self.ent_input.get()
        self.ent_dest.delete(0, tk.END)
        self.ent_dest.insert(0, input_val)
        self.ent_input.delete(0, tk.END)
        self.ent_input.insert(0, dest_val)
        self.logger.info("Swapped file paths in inputs.")

    def run_comparison(self):
        dest_path_str = self.ent_dest.get().strip()
        input_path_str = self.ent_input.get().strip()

        if not dest_path_str or not input_path_str:
            messagebox.showwarning("Warning", "Please specify both Destination and Input file paths.")
            return

        dest_path = Path(dest_path_str)
        input_path = Path(input_path_str)

        if not dest_path.is_file():
            messagebox.showerror("Error", f"Destination file not found:\n{dest_path}")
            return
        if not input_path.is_file():
            messagebox.showerror("Error", f"Input file not found:\n{input_path}")
            return

        self.logger.info("Starting comparison...")
        try:
            new_count, dest_dupes, internal_dupes, new_cards = compare_csv_files(
                dest_path=dest_path,
                input_path=input_path,
                output_csv_path=OUTPUT_CSV,
                output_log_path=OUTPUT_LOG,
                logger=self.logger
            )
            messagebox.showinfo(
                "Comparison Complete", 
                f"Completed successfully!\n\n"
                f"New Unique Cards: {new_count}\n"
                f"Base Duplicates Ignored: {dest_dupes}\n"
                f"Input Duplicates Ignored: {internal_dupes}\n\n"
                f"Outputs saved to: {OUTPUT_DIR.resolve()}"
            )
        except Exception as e:
            self.logger.error(f"Error during comparison: {e}", exc_info=True)
            messagebox.showerror("Execution Error", f"An error occurred: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MoxfieldComparatorGui(root)
    root.mainloop()
