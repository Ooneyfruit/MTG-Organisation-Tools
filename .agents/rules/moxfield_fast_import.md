---
trigger: glob
globs: moxfield_fast_import/**
---

# Development Guidelines: Moxfield Fast Import Tool

This guide defines the code architecture, dependencies, style rules, and development safety patterns for files under `moxfield_fast_import/`. Adhere to these principles whenever modifying code in this directory.

---

## 1. Code Architecture & Layout

The tool uses a modular, decoupled architecture separating business parsing rules from presentation wrappers:

- **Core Engine**: [moxfield_importer_logic.py](file:///C:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_importer_logic.py)
  - Processes input lists, parses token/card regexes, handles duplication and foil upgrades, retrieves Scryfall data, sorts elements (WUBRG & Guilds), and yields formatted tables/outputs.
  - *Must remain independent of GUI components* so it can be safely imported by either the CLI or GUI.
- **GUI Frontend**: [moxfield_import_gui.py](file:///C:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_import_gui.py)
  - Tkinter-based desktop interface. Houses options toggles, loads/saves local settings, displays the help pop-out syntax tester, and draws ASCII reports.
- **CLI Frontend**: [moxfield_import_cli.py](file:///C:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/moxfield_import_cli.py)
  - Lightweight console command-line runner that reads files or prompts directly, and prints reports to standard output.
- **Scryfall Integrator**: [scryfall_core.py](file:///C:/Users/dougl/Documents/Code/_MTG/core_tools/scryfall_core.py)
  - Shared resolver dependency providing color identity, type lines, and caching logic.

---

## 2. Dependencies & API Manners

- **Bypassing Proxies**: Scryfall calls must set `trust_env = False` on their `requests.Session` instances to prevent environment TLS check failures.
- **Rate Limits & Headers**: Respect Scryfall guidelines by maintaining appropriate query delays and headers (`User-Agent`).
- **Scryfall Caching**: Keep caches local and optimized:
  - Cache set maps to `moxfield_fast_import/scryfall_cache/`.
  - Cache cards globally using `scryfall_core.py` configurations.

---

## 3. Style & Visual Guidelines

- **Standard Tkinter Appearance**: Maintain native system default widgets and colors. Avoid applying custom themes or overrides (e.g., ttkthemes, custom styles) unless explicitly requested.
- **Detailed Logging**: Implement standard Python `logging`. Output logs to both `sys.stdout` and file paths under `moxfield_fast_import/logs/`.
- **ASCII Tables**: Always use the dynamic ASCII separator format when outputting tables to ensure aligned columns regardless of text length.

---

## 4. Safe Development & Verification

- **Regression Tests**: Before and after committing any changes, run the regression suite to ensure logic remains intact:
  ```powershell
  python moxfield_fast_import/regression_test_suite.py
  ```
- **File Writes**: Implement dry-run guards. File writing operations (such as generating output CSVs) must only execute if `dry_run` is explicitly set to `False`.