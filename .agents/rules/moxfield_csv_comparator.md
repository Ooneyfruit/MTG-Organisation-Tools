---
trigger: glob
globs: moxfield_csv_comparator/**
---

# Moxfield CSV Comparator Guidelines

This document details the usage, requirements, and execution details for the scripts under `moxfield_csv_comparator/`.

## Active Scripts & Usage

### Moxfield CSV Comparator (`main.py`)
Compares new card imports against the existing base collection.
- **Inputs**: Placed inside `/input/` folder (Destination CSV and New/Awaiting CSV).
- **Outputs**: Output difference lists are placed inside `/outputs/`.
- **Logs**: Process logs are written to `/logs/`.
- **Execution**:
  ```bash
  cd moxfield_csv_comparator
  python main.py
  ```
