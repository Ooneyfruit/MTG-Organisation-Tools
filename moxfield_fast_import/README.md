# Moxfield Fast Importer (`moxfield_fast_import/`)

This directory houses the import engine and interfaces for processing MTG card lists (including double-sided cards and token designations) into formatted Moxfield CSV files.

## Project Structure
- [`moxfield_importer_logic.py`](file:///c:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_importer_logic.py): Core logic handling card regex parsing, batching, and Scryfall query updates.
- [`moxfield_import_cli.py`](file:///c:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_import_cli.py): Console-based interface for running import processes.
- [`moxfield_import_gui.py`](file:///c:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_import_gui.py): Tkinter GUI interface supporting interactive imports, option toggles, and syntax testing.
- `main.py`: The entry-point script pointing to the GUI wrapper.
- `config_settings.json`: Persisted user options (e.g. foil checks, token classification options).

## How to Run

### GUI Mode (Default)
Run from the root or local directory:
```bash
python main.py
```

### CLI Mode
Run the command-line runner:
```bash
python moxfield_import_cli.py
```
Input is read from `input.txt` (or copy-pasted directly). Results will be exported to a `.csv` file.
