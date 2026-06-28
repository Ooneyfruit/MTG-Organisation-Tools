# Moxfield CSV Comparator (`moxfield_csv_comparator/`)

A utility to compare a pending or new Moxfield export list against an existing base collection to see which cards are new, upgraded (e.g. to foil), or already owned.

## Setup & Folders
- `/input/`: Place your comparison source files here:
  1. Base collection CSV (e.g. `collection.csv`).
  2. New incoming list CSV.
- `/outputs/`: Generated output difference sheets will be placed here.
- `/logs/`: Contains run log records.

## Usage
1. Position files in `/input/`.
2. Execute the comparator:
   ```bash
   python main.py
   ```
