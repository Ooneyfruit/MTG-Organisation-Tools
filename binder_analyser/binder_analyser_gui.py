import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from binder_analyser_logic import BinderAnalyser, logger

class BinderAnalyserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MTG Binder Analyser")
        self.root.geometry("600x500")
        
        self.analyser = BinderAnalyser()
        self.input_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'input'))
        os.makedirs(self.input_dir, exist_ok=True)
        
        self.create_widgets()

    def create_widgets(self):
        # Main container frame
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- File Selection Row ---
        file_frame = ttk.LabelFrame(main_frame, text="Moxfield CSV File Selection", padding="5 5 5 5")
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_path_var = tk.StringVar()
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
        
        run_btn = ttk.Button(settings_frame, text="Run Analysis", command=self.run_analysis)
        run_btn.pack(side=tk.RIGHT, padx=5)
        
        # --- Output/Log Summary Area ---
        output_frame = ttk.LabelFrame(main_frame, text="Analysis Summary Output", padding="5 5 5 5")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=15)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
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
            
        self.status_var.set("Analyzing...")
        self.root.update_idletasks()
        
        try:
            summary = self.analyser.run_analysis(csv_path, target_set=target_set)
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, summary)
            self.status_var.set("Analysis complete.")
        except Exception as e:
            messagebox.showerror("Analysis Error", f"An error occurred:\n{str(e)}")
            self.status_var.set("Analysis failed.")

    def open_outputs_folder(self):
        outputs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'outputs'))
        os.makedirs(outputs_dir, exist_ok=True)
        try:
            os.startfile(outputs_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{str(e)}")

def main():
    root = tk.Tk()
    app = BinderAnalyserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
