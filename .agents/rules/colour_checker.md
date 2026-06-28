---
trigger: glob
globs: colour_checker/**
---

# Colour Checker Tool Guidelines

This document details the usage, requirements, and execution details for the scripts under `colour_checker/`.

## Active Scripts & Usage

### 1. Color Identity Counter (`colour_checker.py`)
Counts MTG card lists by commander color identity.
- **Dependency**: Imports caching and fetching routines from `scryfall_core.py` (via `core_tools`).
- **Input File**: `input.txt` (List of cards in the format: `Quantity Name (Set) CollectorNumber`)
- **Key Logic**:
  - Aggregates constituent color identity counts (individual W, U, B, R, G tallies, ignoring multi-color groupings).
  - Aggregates distinct color identity groupings (e.g. URG, G, Colorless).
- **Execution**:
  ```bash
  cd colour_checker
  python colour_checker.py
  ```

### 2. Golgari Deck Helper (`golgari_deck_helper.py`)
Filters collection cards to find eligible Golgari cards that are not already owned or excluded.
- **Dependency**: Imports caching and fetching routines from `scryfall_core.py` (via `core_tools`).
- **Input File**: `collection.csv` (Moxfield CSV collection export).
- **Exclusion Files**:
  - `input.txt` (Excludes cards already present in the deck/list).
  - `ignore/*.csv` (Parses any CSV files inside `ignore/` directory and excludes card names listed inside them).
- **Key Logic**:
  - Filters out any card listed in `input.txt` or `ignore/*.csv` (case-insensitive name match).
  - Batch-resolves Scryfall details for the rest.
  - Keeps cards only if their color identity is a subset of `{B, G}` (Colorless, G, B, and GB combinations).
  - Writes unique sorted names to `output.txt` (one per line).
- **Execution**:
  ```bash
  cd colour_checker
  python golgari_deck_helper.py
  ```
