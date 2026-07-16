import os
import sys
import queue
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Adjust sys.path to import logic
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.append(str(PARENT_DIR))

import moxfield_yellow_binder_logic as logic

CONFIG_FILE = SCRIPT_DIR / "config.json"

class YellowBinderGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Moxfield Yellow Binder Checker")
        self.root.geometry("650x550")

        # Variables
        self.yellow_path = tk.StringVar()
        self.other_paths = []
        self.output_dir = tk.StringVar(value=str(SCRIPT_DIR / "outputs"))
        self.status_msg = tk.StringVar(value="Select files and click 'Run Analysis'.")

        self.task_queue = queue.Queue()

        self.create_widgets()
        self.load_config()

        # Start queue processing
        self.root.after(100, self.process_queue)

    def create_widgets(self):
        # 1. Yellow Binder selection
        yellow_frame = tk.LabelFrame(self.root, text="Yellow Binder", padx=10, pady=10)
        yellow_frame.pack(fill="x", padx=10, pady=5)

        lbl_yellow = tk.Label(yellow_frame, text="Yellow CSV:")
        lbl_yellow.pack(side="left", padx=(0, 5))

        ent_yellow = tk.Entry(yellow_frame, textvariable=self.yellow_path)
        ent_yellow.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_browse_yellow = tk.Button(yellow_frame, text="Browse...", command=self.browse_yellow)
        btn_browse_yellow.pack(side="right")

        # 2. Others Binders selection
        others_frame = tk.LabelFrame(self.root, text="Other Binders", padx=10, pady=10)
        others_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Buttons row
        btn_panel = tk.Frame(others_frame)
        btn_panel.pack(fill="x", anchor="w", pady=(0, 5))

        btn_add_others = tk.Button(btn_panel, text="Add CSVs...", command=self.browse_others)
        btn_add_others.pack(side="left", padx=(0, 5))

        btn_remove_selected = tk.Button(btn_panel, text="Remove Selected", command=self.remove_selected_others)
        btn_remove_selected.pack(side="left", padx=(0, 5))

        btn_clear_all = tk.Button(btn_panel, text="Clear All", command=self.clear_all_others)
        btn_clear_all.pack(side="left")

        # Listbox with Scrollbar
        list_container = tk.Frame(others_frame)
        list_container.pack(fill="both", expand=True)

        self.listbox_others = tk.Listbox(list_container, selectmode=tk.MULTIPLE)
        self.listbox_others.pack(fill="both", expand=True, side="left", padx=(0, 5))

        scroll_others = tk.Scrollbar(list_container, orient="vertical", command=self.listbox_others.yview)
        scroll_others.pack(fill="y", side="right")
        self.listbox_others.config(yscrollcommand=scroll_others.set)

        # 3. Output dir selection
        output_frame = tk.LabelFrame(self.root, text="Output Directory", padx=10, pady=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        lbl_output = tk.Label(output_frame, text="Output Folder:")
        lbl_output.pack(side="left", padx=(0, 5))

        ent_output = tk.Entry(output_frame, textvariable=self.output_dir)
        ent_output.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_browse_output = tk.Button(output_frame, text="Browse...", command=self.browse_output)
        btn_browse_output.pack(side="right")

        # 4. Status and Actions
        action_frame = tk.Frame(self.root, pady=10)
        action_frame.pack(fill="x", padx=10)

        self.lbl_status = tk.Label(action_frame, textvariable=self.status_msg, anchor="w", fg="blue")
        self.lbl_status.pack(fill="x", side="left", expand=True)

        self.btn_run = tk.Button(action_frame, text="Run Analysis", command=self.start_analysis, width=15)
        self.btn_run.pack(side="right")

        # 5. Market manipulation disclaimer note
        lbl_note = tk.Label(
            self.root,
            text="Note: Threshold is strictly >= 1.00 GBP when converted from USD (x0.77) or EUR (x0.85). Cards with large USD/EUR discrepancies (diff >= 1.30, low < 0.70 for USD-high or < 0.55 for EUR-high) are checked against other cached printings; if unsupported, they are flagged as manipulated & ignored.",
            fg="gray",
            font=("Arial", 8, "italic"),
            wraplength=600
        )
        lbl_note.pack(side="bottom", fill="x", pady=(0, 10))

    def load_config(self):
        """Loads inputs used in the last run from a config file."""
        if not CONFIG_FILE.is_file():
            return
        try:
            with CONFIG_FILE.open('r', encoding='utf-8') as f:
                config = json.load(f)
            
            y_path = config.get("yellow_path", "")
            if y_path and os.path.exists(y_path):
                self.yellow_path.set(y_path)
            
            o_paths = config.get("other_paths", [])
            self.other_paths = []
            for p in o_paths:
                if os.path.exists(p):
                    self.other_paths.append(Path(p))
            
            # Repopulate listbox
            self.listbox_others.delete(0, tk.END)
            for path in self.other_paths:
                self.listbox_others.insert(tk.END, path.name)

            out_dir = config.get("output_dir", "")
            if out_dir:
                self.output_dir.set(out_dir)

        except Exception as e:
            print(f"Warning: Failed to load config: {e}", file=sys.stderr)

    def save_config(self):
        """Saves current inputs to a config file."""
        try:
            config = {
                "yellow_path": self.yellow_path.get().strip(),
                "other_paths": [str(p) for p in self.other_paths],
                "output_dir": self.output_dir.get().strip()
            }
            with CONFIG_FILE.open('w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}", file=sys.stderr)

    def browse_yellow(self):
        filename = filedialog.askopenfilename(
            title="Select Yellow Binder CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.yellow_path.set(filename)

    def browse_others(self):
        filenames = filedialog.askopenfilenames(
            title="Select Other Binder CSVs",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filenames:
            for f in filenames:
                path = Path(f)
                if path not in self.other_paths:
                    self.other_paths.append(path)
                    self.listbox_others.insert(tk.END, path.name)

    def remove_selected_others(self):
        selected_indices = list(self.listbox_others.curselection())
        # Delete from listbox and list in reverse order to keep indices correct
        for idx in sorted(selected_indices, reverse=True):
            self.listbox_others.delete(idx)
            self.other_paths.pop(idx)

    def clear_all_others(self):
        self.listbox_others.delete(0, tk.END)
        self.other_paths = []

    def browse_output(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir.set(directory)

    def start_analysis(self):
        y_path = self.yellow_path.get().strip()
        if not y_path or not Path(y_path).is_file():
            messagebox.showerror("Error", "Please select a valid Yellow Binder CSV file.")
            return

        if not self.other_paths:
            messagebox.showerror("Error", "Please select at least one other binder CSV file.")
            return

        self.btn_run.config(state="disabled")
        self.status_msg.set("Starting analysis...")

        # Start analysis thread
        threading.Thread(target=self.run_analysis_thread, daemon=True).start()

    def run_analysis_thread(self):
        try:
            y_path = Path(self.yellow_path.get().strip())
            out_dir = Path(self.output_dir.get().strip())

            def progress_cb(msg):
                self.task_queue.put(("progress", msg))

            move_to_yellow, remove_from_yellow = logic.check_binders(
                y_path,
                self.other_paths,
                progress_callback=progress_cb
            )

            # Write outputs
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir.mkdir(parents=True, exist_ok=True)
            move_csv_path = out_dir / f"{timestamp}_move_to_yellow.csv"
            remove_csv_path = out_dir / f"{timestamp}_remove_from_yellow.csv"

            logic.write_output_csv(move_csv_path, move_to_yellow)
            logic.write_output_csv(remove_csv_path, remove_from_yellow)

            # Save configuration upon successful run
            self.save_config()

            self.task_queue.put(("success", (len(move_to_yellow), len(remove_from_yellow), out_dir)))

        except Exception as e:
            self.task_queue.put(("error", str(e)))

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.task_queue.get_nowait()
                if msg_type == "progress":
                    self.status_msg.set(data)
                elif msg_type == "success":
                    moves, removes, out_dir = data
                    self.status_msg.set("Analysis complete.")
                    self.btn_run.config(state="normal")
                    messagebox.showinfo(
                        "Success",
                        f"Analysis finished successfully!\n\n"
                        f"- Move to Yellow: {moves} card(s)\n"
                        f"- Remove from Yellow: {removes} card(s)\n\n"
                        f"CSVs saved to:\n{out_dir}"
                    )
                elif msg_type == "error":
                    self.status_msg.set("Error during analysis.")
                    self.btn_run.config(state="normal")
                    messagebox.showerror("Error", f"An error occurred:\n{data}")
        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

def main():
    root = tk.Tk()
    app = YellowBinderGUI(root)
    root.mainloop()

    # Save config on window closure as well
    app.save_config()

if __name__ == "__main__":
    main()
