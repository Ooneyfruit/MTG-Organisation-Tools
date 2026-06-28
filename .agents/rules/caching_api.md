---
trigger: glob
globs: **/*.py
---

# Scryfall API & Caching Rules

Any script querying the Scryfall API or dealing with card details must adhere to these guidelines.

## 1. Scryfall API Guidelines (Critical)

1. **Polite Rate Limiting**: Insert a delay of at least `0.3` seconds (`time.sleep(0.3)`) between HTTP queries.
2. **Postgres TLS Fix**: Ensure requests bypass broken environment-level certificate validation by setting `trust_env = False` on your `requests.Session()` object:
   ```python
   session = requests.Session()
   session.trust_env = False
   ```
3. **Bulk Querying**: When resolving more than one card, always batch the query using the Scryfall batch collection endpoint:
   - **Method**: `POST`
   - **URL**: `https://api.scryfall.com/cards/collection`
   - **Limit**: Max 75 card identifiers per request.
   - **Headers**:
     ```python
     headers = {
         'User-Agent': 'MTGColorCounter/2.0',
         'Accept': 'application/json',
         'Content-Type': 'application/json'
     }
     ```

---

## 2. Shared Caching Protocol

The cache store is located in the root of the workspace at `_MTG/cache/` (or `../cache/` relative to script subdirectories).

### Cache Resolution Flow (How to Lookup and Query)
When a script needs details (such as color identity) for a card, it must check the cache first using a multi-layered lookup key hierarchy:

1. **Construct Sanity Keys**:
   - Sanitize all text fields using lowercase letters, and replace non-alphanumeric characters with underscores (collapsing multiples, e.g. `an_offer_you_can_t_refuse`).
2. **First Search (Best Match)**:
   - If set code and collector number are available, look for a file named `set_{set_code}_{collector_number}.json` (e.g. `set_40k_174.json`).
3. **Second Search (Medium Match)**:
   - If set code and name are available, look for a file named `name_set_{card_name}_{set_code}.json` (e.g. `name_set_aberrant_40k.json`).
4. **Third Search (General Match)**:
   - Look for a file named `name_{card_name}.json` (e.g. `name_aberrant.json`).
5. **Cache Hit**:
   - If any of the above files exist and are valid JSON, load them and read the `scryfall_data` object immediately without calling the API.
6. **Cache Miss**:
   - If none of the files exist, query the Scryfall API using the batched POST collection endpoint (or fallback GET endpoints if single).
   - Once resolved, write the payload back to the cache directory using the query parameters to determine the primary filename, mapping it exactly to the query type that resolved it.

### Cache File Schema
Keep cache payloads **narrow and clean** to save disk space and simplify parsing. Only store the query metadata and the essential card data fields (`name`, `color_identity`, and `type_line`).

```json
{
  "query_metadata": {
    "query_type": "scryfall_card_by_set_and_collector_number",
    "endpoint_template": "https://api.scryfall.com/cards/{set}/{collector_number}",
    "query_params": {
      "set": "40K",
      "collector_number": "86"
    },
    "queried_at": "2026-06-16T17:41:27.237823Z"
  },
  "scryfall_data": {
    "name": "Aberrant",
    "color_identity": [
      "G"
    ],
    "type_line": "Creature — Tyranid Mutant"
  }
}
```