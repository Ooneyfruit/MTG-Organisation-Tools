# Core Tools (`core_tools/`)

This directory contains internal shared utilities, libraries, and core API modules used by the scripts in this workspace.

## Files

### 1. `__init__.py`
Initializes `core_tools` as a Python package.

### 2. [`scryfall_core.py`](file:///c:/Users/dougl/Documents/Code/_MTG/core_tools/scryfall_core.py)
A shared library containing API connectors, caching logic, and set classification functions.
- **Cache Storage**: Resolves Scryfall details by reading/writing to the global `../cache` folder.
- **Throttling**: Enforces a polite 0.3s request rate-limit window.
- **TLS Fix**: Configures requests sessions to set `trust_env = False` to bypass environment-specific Postgres certificate resolution failures.
- **Key Functions**:
  - `resolve_cards(cards)`: Batches and requests data for list of card dictionaries (using `POST /cards/collection`).
  - `load_from_cache(card)`: Evaluates local file exists hierarchy (`set_code_cn` -> `name_set` -> `name`).
  - `is_token_set(set_code)`: Verifies if a set code corresponds to token or memorabilia layouts.

### 3. [`sorting_logic.py`](file:///c:/Users/dougl/Documents/Code/_MTG/core_tools/sorting_logic.py)
A shared library implementing Magic: The Gathering (MTG) WUBRG-based ordering rules.
- **Unified Sort Sorting**: Sorts non-land spells first (ordered by WUBRG color identity), utility/non-basic lands second, and basic lands last.
- **Key Functions**:
  - `get_card_wubrg_sort_key(name, type_line, color_identity)`: Generates a compound tuple key designed for Python list sorting.
  - `get_non_land_wubrg_key(color_list)`: Generates sorting weights for spells.
  - `get_land_sort_key(color_list, card_name)`: Arranges lands by mono-color, dual-color guilds, and shards.

## Usage in Scripts
To import core tools from scripts located in other directories, append `core_tools` to your system path:
```python
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core_tools")))
import scryfall_core
from sorting_logic import get_card_wubrg_sort_key
```
