import os
import csv
import sys
import tkinter as tk
import glob
import keyboard # type: ignore
import pyperclip # pyright: ignore[reportMissingModuleSource]
import time
import threading

# --- CONFIGURATION ---
OUTPUT_DIR = "outputs"
TRIGGER_KEY = "F8"  # Changed from 'ctrl+space' to 'F8' to prevent sticky-key bugs

def get_latest_timestamp():
    """Finds the most recent timestamp in the outputs folder."""
    pattern = os.path.join(OUTPUT_DIR, "*-double-sided-fronts.csv")
    files = glob.glob(pattern)
    if not files: return None
    files.sort(key=os.path.getmtime, reverse=True)
    return os.path.basename(files[0]).split('-')[0]

def load_sorted_queue(timestamp):
    """Loads CSVs in strict order and sorts them alphabetically."""
    queue = []
    file_suffixes = [
        ("double-sided-fronts.csv", "Fronts (Main)"),
        ("double-sided-backs.csv", "Backs (Main)"),
        ("double-sided-fronts-dupes.csv", "Fronts (Duplicate)"),
        ("double-sided-backs-dupes.csv", "Backs (Duplicate)"),
    ]
    
    for suffix, display_name in file_suffixes:
        filepath = os.path.join(OUTPUT_DIR, f"{timestamp}-{suffix}")
        if not os.path.exists(filepath): continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                # Sort A-Z by Name
                rows.sort(key=lambda x: x.get("Name", "").lower())
                
                for row in rows:
                    tag = row.get("Tags", "")
                    if tag:
                        queue.append({
                            "name": row.get("Name", "Unknown"),
                            "set": row.get("Edition", ""),
                            "cn": row.get("Collector Number", ""),
                            "csv_name": display_name,
                            "tag": tag,
                            "foil": row.get("Foil", "").strip().lower() == "foil" # Capture foil status
                        })
        except Exception: pass
    return queue

class NotesEntryApp:
    def __init__(self, queue):
        self.queue = queue
        self.index = 0
        self.is_pasting = False  # Lock to prevent double-fires
        
        # --- GUI Setup ---
        self.root = tk.Tk()
        self.root.title("Moxfield Note Helper")
        self.root.geometry("400x280") # Slightly taller to accommodate the foil tag
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#222222")

        # Labels
        self.lbl_progress = tk.Label(self.root, text="", fg="#aaaaaa", bg="#222222", font=("Arial", 10))
        self.lbl_progress.pack(pady=(15, 5))

        self.lbl_csv = tk.Label(self.root, text="", fg="#00ccff", bg="#222222", font=("Arial", 11, "bold"))
        self.lbl_csv.pack(pady=2)

        tk.Frame(self.root, height=1, bg="#444444", width=300).pack(pady=5)

        self.lbl_card = tk.Label(self.root, text="Press Start...", fg="#ffffff", bg="#222222", font=("Arial", 14, "bold"))
        self.lbl_card.pack(pady=5)

        self.lbl_set = tk.Label(self.root, text="", fg="#dddddd", bg="#222222", font=("Arial", 10, "italic"))
        self.lbl_set.pack(pady=0)

        # New Foil Indicator Label
        self.lbl_foil = tk.Label(self.root, text="", fg="#ffd700", bg="#222222", font=("Arial", 11, "bold"))
        self.lbl_foil.pack(pady=2)

        self.lbl_tag = tk.Label(self.root, text="", fg="#00ff00", bg="#222222", font=("Consolas", 11))
        self.lbl_tag.pack(pady=10)

        self.lbl_instruct = tk.Label(self.root, text=f"Click 'Notes' Box -> Press [{TRIGGER_KEY}]", fg="#888888", bg="#222222", font=("Arial", 9))
        self.lbl_instruct.pack(side="bottom", pady=15)

        # Setup Hotkey
        keyboard.add_hotkey(TRIGGER_KEY, self.on_hotkey_press)
        
        self.update_display()
        self.root.mainloop()

    def update_display(self):
        if self.index < len(self.queue):
            item = self.queue[self.index]
            self.lbl_progress.config(text=f"Card {self.index + 1} of {len(self.queue)}")
            self.lbl_csv.config(text=f"[{item['csv_name']}]")
            self.lbl_card.config(text=item['name'])
            self.lbl_set.config(text=f"Set: {item['set'].upper()} | CN: {item['cn']}")
            self.lbl_tag.config(text=f"Note: {item['tag']}")
            
            # Dynamic Foil Styling
            if item['foil']:
                self.lbl_foil.config(text="★ FOIL ★")
                self.lbl_card.config(fg="#ffd700") # Turn the card name gold
            else:
                self.lbl_foil.config(text="")
                self.lbl_card.config(fg="#ffffff") # Standard white
                
        else:
            self.lbl_progress.config(text="Complete")
            self.lbl_csv.config(text="All Files Finished")
            self.lbl_card.config(text="Done!", fg="#ffffff")
            self.lbl_set.config(text="")
            self.lbl_foil.config(text="")
            self.lbl_tag.config(text="")
            self.lbl_instruct.config(text="You can close this window.")

    def on_hotkey_press(self):
        """Thread-safe trigger handler."""
        if self.is_pasting or self.index >= len(self.queue):
            return
        
        self.is_pasting = True
        
        # We perform the action in a slight delay to ensure the key is processed
        self.root.after(10, self.perform_paste)

    def perform_paste(self):
        item = self.queue[self.index]
        
        # 1. Load Clipboard
        pyperclip.copy(item['tag'])
        
        # 2. WAIT for the trigger key to be physically released.
        # This prevents F8 from interfering with the Ctrl+V we are about to send.
        while keyboard.is_pressed(TRIGGER_KEY):
            time.sleep(0.05)

        # 3. Send Paste Command
        keyboard.send('ctrl+v')

        # 4. Advance
        self.index += 1
        self.update_display()
        
        # 5. Cooldown to prevent accidental double-paste
        time.sleep(0.3) 
        self.is_pasting = False

def main():
    print("="*60)
    print(f"      MOXFIELD NOTES ENTRY ASSISTANT (Trigger: {TRIGGER_KEY})")
    print("="*60)
    
    # 1. Auto-Detect Timestamp
    latest_ts = get_latest_timestamp()
    target_ts = ""

    if latest_ts:
        print(f"Latest output found: {latest_ts}")
        choice = input("Use this timestamp? (Y/n): ").strip().lower()
        if choice != 'n':
            target_ts = latest_ts
    
    # 2. Manual Fallback
    if not target_ts:
        target_ts = input("Enter timestamp manually: ").strip()
    
    if not target_ts: return

    # 3. Load Queue
    queue = load_sorted_queue(target_ts)
    if not queue:
        print("No cards found.")
        return

    print(f"\nLoaded {len(queue)} cards.")
    print(f"Launching GUI... Focus the browser and press {TRIGGER_KEY} to paste.")
    
    NotesEntryApp(queue)

if __name__ == "__main__":
    main()