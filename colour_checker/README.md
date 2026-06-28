# Color Checker Tools (`colour_checker/`)

This directory contains scripts for parsing card lists, matching them against local card collections, and identifying commander color distributions.

## Scripts

### 1. [`colour_checker.py`](file:///c:/Users/dougl/Documents/Code/_MTG/colour_checker/colour_checker.py)
Parses a deck or list of cards and prints out color identity tallies resolved via Scryfall.
- **Input**: `input.txt` (List of cards in the format: `Quantity Name (Set) CollectorNumber`)
- **Output**: Prints a report showing:
  1. Individual constituent color counts (how many cards have W, U, B, R, G in their color identity).
  2. Distinct color groupings (exact count of colorless cards, mono-color cards, and multi-color deck combinations).

### 2. [`golgari_deck_helper.py`](file:///c:/Users/dougl/Documents/Code/_MTG/colour_checker/golgari_deck_helper.py)
Filters an exported collection file to find candidate cards that fit the Golgari color identity (inclusive of Colorless, Mono-Green, Mono-Black, and Black-Green multi-color cards) and aren't already excluded.
- **Input**:
  - `collection.csv` (Moxfield CSV collection export).
  - `input.txt` (Excludes any cards matching the names in this file).
  - `ignore/*.csv` (Optional subdirectory containing extra CSV lists of cards to exclude).
- **Output**: `output.txt` (A sorted list of unique eligible cards to purchase or pull).

## Setup & Running

1. Populate `input.txt` or `collection.csv` inside this folder.
2. Run the desired script:
   ```bash
   # Run Color Identity Counter
   python colour_checker.py

   # Run Golgari Deck Helper
   python golgari_deck_helper.py
   ```
