import csv
import sys
import os
import datetime

def get_file_path(prompt_text):
    """
    Helper to get a valid file path from the user.
    Allows drag-and-drop of files into the terminal.
    """
    while True:
        path = input(prompt_text).strip()
        # Remove quotes if the user drag-and-dropped the file path
        path = path.strip('"').strip("'")
        if os.path.isfile(path):
            return path
        print(f"Error: File not found at '{path}'. Please try again.")

def write_csv(filename, rows, fieldnames):
    """
    Helper to write a list of dictionaries to a CSV file
    using Moxfield-compliant formatting.
    """
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"--> Saved: '{filename}' ({len(rows)} cards)")
    except IOError as e:
        print(f"Error writing to {filename}: {e}")

def main():
    print("--- Moxfield CSV Deduplicator (Splitter) ---")
    print("This script splits your 'New' list into two files:")
    print("1. A list of cards you DON'T have (Clean Import).")
    print("2. A list of cards you DO have (Removed Duplicates).\n")

    # 1. Get File Paths
    target_csv_path = get_file_path("Enter path to 'Merge Into' CSV (Main List): ")
    source_csv_path = get_file_path("Enter path to 'To Merge' CSV (New List): ")

    # 2. Load Target Names
    existing_names = set()
    print(f"\n--> Loading existing collection from: {os.path.basename(target_csv_path)}...")
    
    try:
        with open(target_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "Name" in row:
                    existing_names.add(row["Name"].strip().lower())
    except Exception as e:
        print(f"Error reading Main list: {e}")
        sys.exit(1)
        
    print(f"    Loaded {len(existing_names)} unique card names.")

    # 3. Process Source List
    print(f"--> Processing new cards from: {os.path.basename(source_csv_path)}...")
    
    unique_rows = []
    duplicate_rows = []
    headers = []

    try:
        with open(source_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            for row in reader:
                name = row.get("Name", "").strip()
                
                if name.lower() in existing_names:
                    duplicate_rows.append(row)
                else:
                    unique_rows.append(row)
                    
    except Exception as e:
        print(f"Error reading New list: {e}")
        sys.exit(1)

    # 4. Generate Output Filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_filename = f"clean_import_{timestamp}.csv"
    dupe_filename = f"removed_duplicates_{timestamp}.csv"

    print("\n" + "="*40)
    
    # 5. Write Clean List
    if unique_rows:
        write_csv(clean_filename, unique_rows, headers)
    else:
        print("--> No unique cards found (Clean list is empty).")

    # 6. Write Duplicate List
    if duplicate_rows:
        write_csv(dupe_filename, duplicate_rows, headers)
    else:
        print("--> No duplicates found (Duplicate list is empty).")

    print("="*40 + "\nDone.")

if __name__ == "__main__":
    main()