# Agent Guidelines & Codebase Rulebook (`_MTG`)

> [!IMPORTANT]
> **CRITICAL LOCATION RULE**: These agent instruction/rule files MUST remain in the `_MTG/.agents/rules/` directory. Under no circumstances should they be moved, renamed, or relocated from this folder, as the agent system relies on this specific path to load local guidelines.

Welcome, Agent. This workspace contains a suite of automation tools for Magic: The Gathering card collections. Please adhere to the following directory structure, script rules, and development guidelines.

---

## Workspace Directory Structure

- `_MTG/` (Root)
  - `cache/` - **Shared JSON Cache Store** for Scryfall API queries.
  - `_core_tools/` - Core shared utility modules (e.g., `scryfall_core.py`).
  - `colour_checker/` - Commander color identity counter and deck helper.
  - `moxfield_fast_import/` - Moxfield list and token import tool.
  - `moxfield_csv_comparator/` - Collection list difference comparator.
  - `yyy_testing_suite/` - **Centralized Regression Testing Suite** and master controller.

---

## Development Guidelines & File Placement

### 1. Where Stuff Gets Put
- **Shared Libraries & Modules**: Place general utility scripts that are used by multiple tools in [_core_tools/](file:///c:/Users/dougl/Documents/Code/_MTG/_core_tools/).
  - *Example*: `scryfall_core.py` (caching, API throttling, TLS session fix).
- **Feature-Specific Tools**: Place user-facing scripts, GUIs, or command-line apps in dedicated root directories (e.g., [colour_checker/](file:///c:/Users/dougl/Documents/Code/_MTG/colour_checker/), [moxfield_fast_import/](file:///c:/Users/dougl/Documents/Code/_MTG/moxfield_fast_import/)).
- **Temporary / Local Outputs**: Output logs, dry-runs, or generated lists should stay in the script's local subdirectories or inside specific output directories (e.g., `colour_checker/output.txt`).
- **Global Cache**: Always use the global [cache/](file:///c:/Users/dougl/Documents/Code/_MTG/cache/) directory for Scryfall JSON cache files to share queried results across all tools.
- **Obsolete / Retired Code**: Move unused or deprecated tools into folders prefixed with `zzz_obselete_` (e.g., [zzz_obselete_moxfield_fast_import/](file:///c:/Users/dougl/Documents/Code/_MTG/zzz_obselete_moxfield_fast_import/)) to keep the root directory clean.

### 2. How to Develop New Files
When creating or modifying scripts in this workspace, follow these rules:
- **Importing Core Tools**:
  - Always resolve `_core_tools` relative to the current script directory using `sys.path`. Do not hardcode absolute system paths.
  - *Recommended pattern*:
    ```python
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "_core_tools")))
    import scryfall_core
    ```
- **Handling API / Caching**:
  - Integrate with `scryfall_core` caching routines rather than writing custom HTTP fetch/cache handlers from scratch.
  - Handle rate limiting (`time.sleep(0.3)`) and TLS certificate bypass (`trust_env = False` on requests session) as specified in the API guidelines.
- **Decoupled Architecture & Naming Conventions**:
  - Separate parsing logic, file I/O, and front-end interface wrappers (CLI / GUI) into clean files.
  - Follow the workspace-wide naming scheme for files in each tool directory `<feature_name>`:
    - **Logic module**: `<feature_name>_logic.py` (contains the core processing engine).
    - **CLI wrapper**: `<feature_name>_cli.py` (accepts arguments and runs from CLI).
    - **GUI wrapper**: `<feature_name>_gui.py` (contains native Tkinter interface).
  - Use spelling style consistent with the folder name (e.g., British English `analyser` rather than `analyzer`, `colour` rather than `color`).
  - Output directories for generated summaries or artifacts should be named `outputs/` instead of `output/`.
- **Documentation**:
  - Every project/tool directory must contain a folder-specific `README.md` explaining the purpose, script usage, configuration parameters, and inputs/outputs.

### 3. Testing & Verification (Critical)
- **Master Test Suite**: All testing suites are located in [yyy_testing_suite/](file:///c:/Users/dougl/Documents/Code/_MTG/yyy_testing_suite/).
- **Run Tests Regularly**: Whenever changes are made to `_core_tools`, moxfield importers, sorting logic, or any system logic in the workspace, you **MUST** run the master test runner [yyy_testing_suite/run_all_tests.py](file:///c:/Users/dougl/Documents/Code/_MTG/yyy_testing_suite/run_all_tests.py) to verify that all regression tests pass successfully before declaring a task complete.

---

## Specialized Rule Modules
More detailed guidelines will automatically load into your system context when you edit files in specific directories:
- **Scryfall APIs & Cache**: [caching_api.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/caching_api.md) triggers when working on any Python script (`**/*.py`).
- **Moxfield Fast Import**: [moxfield_fast_import.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/moxfield_fast_import.md) triggers when working in `moxfield_fast_import/`.
- **Colour Checker**: [colour_checker.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/colour_checker.md) triggers when working in `colour_checker/`.
- **Moxfield CSV Comparator**: [moxfield_csv_comparator.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/moxfield_csv_comparator.md) triggers when working in `moxfield_csv_comparator/`.
- **Regression Testing**: [tests.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/tests.md) triggers when writing tests or running runners.
- **GUI Style Guide**: [gui_style.md](file:///c:/Users/dougl/Documents/Code/_MTG/.agents/rules/gui_style.md) triggers when designing/modifying visual desktop layouts.
