import os
import csv
import logging
import sys
from typing import List, Dict, Any, Optional, Tuple

# Add core_tools directory to sys.path to resolve scryfall_core and yellow_binder_logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "_core_tools")))
import scryfall_core
import yellow_binder_logic
import meta_scrub_logic

def setup_logger() -> logging.Logger:
    """Sets up logging to write to both console and a log file in the logs/ directory."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'binder_analyser.log')
    
    logger = logging.getLogger('binder_analyser')
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers if any
    if logger.handlers:
        logger.handlers.clear()
        
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

class BaseAnalyserMetric:
    """Base class for binder analysis metrics."""
    def __init__(self):
        pass

    def process_card(self, card: Dict[str, Any]) -> None:
        """Processes a single card dictionary representation."""
        raise NotImplementedError("Subclasses must implement process_card")

    def get_summary(self) -> str:
        """Returns a string representation of the metric's results."""
        raise NotImplementedError("Subclasses must implement get_summary")

    def get_data(self) -> Dict[str, Any]:
        """Returns the raw processed data for programmatic access."""
        raise NotImplementedError("Subclasses must implement get_data")

    def reset(self) -> None:
        """Resets the metric's internal state."""
        pass

    def get_table_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        """Returns Dict mapping sub-tab name -> (headers, list_of_rows) for GUI Treeview tables."""
        return {}


class SetCounterMetric(BaseAnalyserMetric):
    """Metric that counts the number of cards grouped by set code (Edition)."""
    def __init__(self):
        super().__init__()
        self.counts = {}  # set_code (lowercase) -> total count

    def reset(self) -> None:
        self.counts = {}

    def process_card(self, card: Dict[str, Any]) -> None:
        edition = card.get('edition', '').strip().lower()
        if not edition:
            edition = 'unknown'
        
        # Determine quantity, default to 1 if count is invalid or missing
        try:
            count = int(card.get('count', 1))
        except (ValueError, TypeError):
            count = 1
            
        self.counts[edition] = self.counts.get(edition, 0) + count

    def get_summary(self) -> str:
        if not self.counts:
            return "No set data recorded."
        
        sorted_counts = sorted(self.counts.items(), key=lambda x: x[1], reverse=True)
        lines = [
            "Set Code | Total Cards",
            "---------|------------"
        ]
        for set_code, total in sorted_counts:
            lines.append(f"{set_code.upper():8} | {total}")
        return "\n".join(lines)

    def get_data(self) -> Dict[str, int]:
        return self.counts

    def get_table_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        sorted_counts = sorted(self.counts.items(), key=lambda x: x[1], reverse=True)
        headers = ["Set Code", "Total Cards"]
        rows = [[set_code.upper(), total] for set_code, total in sorted_counts]
        return {"Set Counts": (headers, rows)}


class ArtistSpotlightMetric(BaseAnalyserMetric):
    """Metric that tallies cards by illustrator/artist."""
    def __init__(self):
        super().__init__()
        self.counts = {}  # artist_name -> total cards

    def reset(self) -> None:
        self.counts = {}

    def process_card(self, card: Dict[str, Any]) -> None:
        try:
            count = int(card.get('count', 1))
        except (ValueError, TypeError):
            count = 1
            
        scry_data, _ = scryfall_core.load_from_cache(card)
        if scry_data:
            artist = scry_data.get('artist', '').strip()
            if artist:
                self.counts[artist] = self.counts.get(artist, 0) + count
            else:
                self.counts['Unknown Artist'] = self.counts.get('Unknown Artist', 0) + count
        else:
            self.counts['Unresolved Card'] = self.counts.get('Unresolved Card', 0) + count

    def get_summary(self) -> str:
        if not self.counts:
            return "No artist data recorded."
        
        sorted_artists = sorted(self.counts.items(), key=lambda x: x[1], reverse=True)
        lines = [
            "Artist | Total Cards",
            "-------|------------"
        ]
        # Show top 15 artists
        for artist, total in sorted_artists[:15]:
            lines.append(f"{artist[:25]:25} | {total}")
        if len(sorted_artists) > 15:
            lines.append(f"... and {len(sorted_artists) - 15} more artists.")
        return "\n".join(lines)

    def get_data(self) -> Dict[str, int]:
        return self.counts

    def get_table_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        sorted_artists = sorted(self.counts.items(), key=lambda x: x[1], reverse=True)
        headers = ["Artist", "Total Cards"]
        rows = [[artist, total] for artist, total in sorted_artists]
        return {"Artist Counts": (headers, rows)}


class RichStapleAuditMetric(BaseAnalyserMetric):
    """
    Metric that groups cards into playability/value brackets using EDHREC rank,
    rarity, and GBP price from yellow_binder_logic.
    """
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self.categories = {
            'High-Value Staples': 0,
            'Budget Staples': 0,
            'Bulk Rares': 0,
            'Hidden Gems': 0,
            'Generic Playable': 0,
            'True Draft Chaff': 0,
            'Unresolved': 0
        }
        self.categories_cards = {
            'High-Value Staples': [],
            'Budget Staples': [],
            'Bulk Rares': [],
            'Hidden Gems': [],
            'Generic Playable': [],
            'True Draft Chaff': [],
            'Unresolved': []
        }
        self.all_processed_cards = []
        self.total_tracked_cards = 0
        self.high_utility_count = 0
        self.cards_by_name = {}
        self.post_processed = False

    def process_card(self, card: Dict[str, Any]) -> None:
        try:
            count = int(card.get('count', 1))
        except (ValueError, TypeError):
            count = 1

        name = card['name'].strip()
        if not name:
            return

        scry_data, _ = scryfall_core.load_from_cache(card)
        is_foil_card = yellow_binder_logic.is_foil(card)

        if scry_data:
            _, _, gbp_price = yellow_binder_logic.get_card_prices(scry_data, is_foil_card)
            try:
                rank = scry_data.get('edhrec_rank')
                if rank is not None:
                    rank = int(rank)
            except (ValueError, TypeError):
                rank = None
            rarity = scry_data.get('rarity', '').strip().lower()
            resolved = True
        else:
            gbp_price = 0.0
            rank = None
            rarity = 'unknown'
            resolved = False

        if name not in self.cards_by_name:
            self.cards_by_name[name] = {
                'count': 0,
                'prices': [],
                'foils': [],
                'editions': [],
                'collector_numbers': [],
                'rarities': [],
                'resolved': resolved,
                'rank': rank
            }

        entry = self.cards_by_name[name]
        entry['count'] += count
        if resolved:
            entry['prices'].append(gbp_price)
            entry['foils'].append(is_foil_card)
            entry['editions'].append(card['edition'].upper())
            entry['collector_numbers'].append(card.get('collector_number', ''))
            entry['rarities'].append(rarity)

    def post_process(self) -> None:
        if self.post_processed:
            return
        self.post_processed = True

        for name, data in self.cards_by_name.items():
            count = data['count']
            self.total_tracked_cards += count

            if not data['resolved']:
                category = 'Unresolved'
                avg_price = 0.0
                foil_state = 'No'
                edition_str = ""
                cn_str = ""
                rarity = "Unknown"
                rank = None
            else:
                prices = data['prices']
                avg_price = sum(prices) / len(prices) if prices else 0.0

                if len(prices) == 1:
                    foil_state = 'Yes' if data['foils'][0] else 'No'
                    edition_str = data['editions'][0]
                    cn_str = data['collector_numbers'][0]
                    rarity = data['rarities'][0].capitalize()
                else:
                    foil_state = 'Mixed' if (any(data['foils']) and not all(data['foils'])) else ('Yes' if all(data['foils']) else 'No')
                    edition_str = ", ".join(sorted(list(set(data['editions']))))
                    cn_str = ", ".join(sorted(list(set(data['collector_numbers']))))
                    rarity = data['rarities'][0].capitalize() if data['rarities'] else 'Unknown'

                rank = data['rank']

                category = 'True Draft Chaff'
                if rank is not None and rank <= 1500 and avg_price >= 4.00:
                    category = 'High-Value Staples'
                    self.high_utility_count += count
                elif rank is not None and rank <= 1500 and avg_price < 0.80:
                    category = 'Budget Staples'
                    self.high_utility_count += count
                elif rarity.lower() in ('rare', 'mythic') and (rank is None or rank > 5000) and avg_price < 0.80:
                    category = 'Bulk Rares'
                elif rarity.lower() in ('common', 'uncommon') and rank is not None and rank <= 3000 and avg_price >= 0.80:
                    category = 'Hidden Gems'
                    self.high_utility_count += count
                elif (rank is not None and rank <= 5000) or avg_price >= 0.80:
                    category = 'Generic Playable'
                    self.high_utility_count += count

            self.categories[category] += count

            c_info = {
                'name': name,
                'set': edition_str,
                'collector_number': cn_str,
                'foil': foil_state,
                'count': count,
                'gbp_price': avg_price,
                'rank': rank,
                'rarity': rarity,
                'category': category
            }
            self.categories_cards[category].append(c_info)
            self.all_processed_cards.append(c_info)

    def get_summary(self) -> str:
        self.post_process()
        if self.total_tracked_cards == 0:
            return "No playability data recorded."

        lines = [
            "Category             | Count | Percentage",
            "---------------------|-------|-----------"
        ]
        for cat, count in self.categories.items():
            pct = (count / self.total_tracked_cards) * 100
            lines.append(f"{cat:20} | {count:5} | {pct:.1f}%")

        utility_rate = 0.0
        if self.total_tracked_cards > 0:
            utility_rate = (self.high_utility_count / self.total_tracked_cards) * 100

        lines.append("")
        lines.append(f"Binder Utility Rate: {utility_rate:.1f}%")
        lines.append("*(Binder Utility Rate represents the percentage of cards classified as Staples, Hidden Gems, or generic playables.)*")
        lines.append("")

        lines.append("--- Top Cards by Category (Staples Audit) ---")
        interesting_categories = ['High-Value Staples', 'Budget Staples', 'Bulk Rares', 'Hidden Gems']
        for cat in interesting_categories:
            cat_list = self.categories_cards.get(cat, [])
            lines.append(f"\n* {cat} (Top 15):")
            if not cat_list:
                lines.append("  (None found)")
                continue

            sorted_list = sorted(cat_list, key=lambda x: (x['rank'] if x['rank'] is not None else 999999, -x['gbp_price']))

            for idx, c in enumerate(sorted_list[:15], 1):
                rank_str = f"Rank #{c['rank']}" if c['rank'] is not None else "Unranked"
                price_str = f"£{c['gbp_price']:.2f}"
                lines.append(f"  {idx:2}. {c['name']} ({c['count']}x) [{c['set']}] - {price_str} ({rank_str})")

        return "\n".join(lines)

    def get_data(self) -> Dict[str, Any]:
        self.post_process()
        return {
            'categories': self.categories,
            'total_tracked_cards': self.total_tracked_cards,
            'high_utility_count': self.high_utility_count,
            'categories_cards': self.categories_cards
        }

    def get_table_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        self.post_process()
        headers = ["Rank Index", "Name", "Set", "CN", "Foil", "Qty", "GBP Price", "EDHREC Rank", "Rarity", "Category"]

        def row_conv(c, rank_idx):
            return [
                rank_idx,
                c['name'],
                c['set'],
                c['collector_number'],
                c['foil'],
                c['count'],
                c['gbp_price'],
                c['rank'] if c['rank'] is not None else 999999,
                c['rarity'],
                c['category']
            ]

        def build_table_rows(cards_list):
            sorted_cards = sorted(cards_list, key=lambda x: (x['rank'] if x['rank'] is not None else 999999, -x['gbp_price']))
            return [row_conv(c, idx) for idx, c in enumerate(sorted_cards, 1)]

        tables = {}
        tables["All Cards"] = (headers, build_table_rows(self.all_processed_cards))

        for cat_name, cards in self.categories_cards.items():
            if cat_name != 'Unresolved' or cards:
                tables[cat_name] = (headers, build_table_rows(cards))

        return tables


class MetaFulfillmentMetric(BaseAnalyserMetric):
    """
    Metric that compares user's binder inventory against top metagame archetype decklists
    across non-commander formats (Standard, Pioneer, Modern, Pauper, Legacy, Vintage).
    Uses sideboard stitching rules to find realistic deck building viability.
    """
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self.binder_inventory = {}
        self.results = {}
        self.post_processed = False

    def process_card(self, card: Dict[str, Any]) -> None:
        name = card['name'].strip()
        if not name:
            return
        try:
            count = int(card.get('count', 1))
        except (ValueError, TypeError):
            count = 1
        self.binder_inventory[name] = self.binder_inventory.get(name, 0) + count

    def post_process(self) -> None:
        if self.post_processed:
            return
        self.post_processed = True
        
        for fmt in meta_scrub_logic.FORMATS:
            try:
                meta_data = meta_scrub_logic.get_format_meta_data(fmt)
            except Exception as e:
                logger.error(f"Failed to load metagame data for {fmt}: {e}")
                meta_data = {'format': fmt, 'archetypes': []}
                
            self.results[fmt] = []
            
            for arch in meta_data.get('archetypes', []):
                if not arch.get('crawled'):
                    continue
                deck_data = arch.get('decklist', {})
                if 'pool' in deck_data:
                    pool = deck_data['pool']
                    typical = deck_data['typical']
                else:
                    pool = deck_data
                    typical = deck_data
                    
                # Ignore basic lands
                BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
                def filter_basics(d):
                    return {name: qty for name, qty in d.items() if name.strip().lower() not in BASIC_LANDS}
                    
                pool_main = filter_basics(pool.get('main', {}))
                pool_side = filter_basics(pool.get('side', {}))
                typical_main = filter_basics(typical.get('main', {}))
                typical_side = filter_basics(typical.get('side', {}))
                
                available_binder = self.binder_inventory.copy()
                
                # Match mainboard first
                main_matched = 0
                main_missing = {}
                main_matched_cards = {}
                for card_name, required_qty in pool_main.items():
                    have_qty = available_binder.get(card_name, 0)
                    matched = min(have_qty, required_qty)
                    main_matched += matched
                    available_binder[card_name] = have_qty - matched
                    if matched > 0:
                        main_matched_cards[card_name] = matched
                    if matched < required_qty:
                        main_missing[card_name] = required_qty - matched
                        
                # Match sideboard next
                side_matched = 0
                side_missing = {}
                side_matched_cards = {}
                for card_name, required_qty in pool_side.items():
                    have_qty = available_binder.get(card_name, 0)
                    matched = min(have_qty, required_qty)
                    side_matched += matched
                    available_binder[card_name] = have_qty - matched
                    if matched > 0:
                        side_matched_cards[card_name] = matched
                    if matched < required_qty:
                        side_missing[card_name] = required_qty - matched
                        
                target_main = sum(typical_main.values())
                target_side = sum(typical_side.values())
                target_total = target_main + target_side
                
                matched_main_score = min(main_matched, target_main)
                matched_side_score = min(side_matched, target_side)
                total_matched_score = matched_main_score + matched_side_score
                
                fulfillment_pct = (total_matched_score / target_total) * 100 if target_total > 0 else 0.0
                
                self.results[fmt].append({
                    'name': arch['name'],
                    'pct': arch['pct'],
                    'url': arch['url'],
                    'main_matched': main_matched,
                    'side_matched': side_matched,
                    'target_total': target_total,
                    'matched_score': total_matched_score,
                    'fulfillment_pct': fulfillment_pct,
                    'main_missing': main_missing,
                    'side_missing': side_missing,
                    'main_matched_cards': main_matched_cards,
                    'side_matched_cards': side_matched_cards
                })

    def get_summary(self) -> str:
        self.post_process()
        lines = []
        for fmt, arches in self.results.items():
            lines.append(f"Format: {fmt.upper()}")
            lines.append("-" * 30)
            if not arches:
                lines.append("  No metagame data available.")
                lines.append("")
                continue
                
            avg_fulfillment = sum(a['fulfillment_pct'] for a in arches) / len(arches)
            lines.append(f"Average Meta Fulfillment: {avg_fulfillment:.1f}%")
            lines.append("Top Decks:")
            for idx, a in enumerate(arches[:5], 1):
                lines.append(f"  {idx:2}. {a['name']} ({a['pct']} meta share) - {a['matched_score']}/{a['target_total']} ({a['fulfillment_pct']:.1f}%)")
            lines.append("")
        return "\n".join(lines)

    def get_data(self) -> Dict[str, Any]:
        self.post_process()
        return {
            'results': self.results,
            'binder_inventory': self.binder_inventory
        }

    def get_table_data(self) -> Dict[str, Tuple[List[str], List[List[Any]]]]:
        self.post_process()
        tables = {}
        headers = ["Rank", "Archetype", "Meta Share", "Fulfillment", "Fulfillment %", "Matched Main", "Matched Side"]
        
        for fmt, arches in self.results.items():
            rows = []
            for idx, a in enumerate(arches, 1):
                rows.append([
                    idx,
                    a['name'],
                    a['pct'],
                    f"{a['matched_score']} / {a['target_total']}",
                    f"{a['fulfillment_pct']:.1f}%",
                    a['main_matched'],
                    a['side_matched']
                ])
            tables[f"{fmt.capitalize()} Meta"] = (headers, rows)
            
        return tables

    def load_more_decks(self, format_name: str, count: int = 10) -> None:
        """Loads more decks for the given format, recalculates, and updates results."""
        import meta_scrub_logic
        meta_scrub_logic.load_more_format_decks(format_name, count)
        self.post_processed = False


class BinderAnalyser:
    """Coordinator class that reads Moxfield CSV files and runs metrics."""
    def __init__(self):
        self.metrics: Dict[str, BaseAnalyserMetric] = {
            'set_count': SetCounterMetric(),
            'artist_spotlight': ArtistSpotlightMetric(),
            'staple_audit': RichStapleAuditMetric(),
            'meta_fulfillment': MetaFulfillmentMetric()
        }

    def add_metric(self, name: str, metric: BaseAnalyserMetric) -> None:
        """Enables extensibility to register new analysis metrics."""
        self.metrics[name] = metric
        logger.debug(f"Registered metric: {name}")

    def run_analysis(self, csv_path: str, target_set: Optional[str] = None, ignore_proxies: bool = False) -> str:
        """
        Reads CSV and executes all registered metrics.
        Returns a formatted full summary string and saves it.
        """
        logger.info(f"Starting binder analysis on: {csv_path} (ignore_proxies={ignore_proxies})")
        
        if not os.path.exists(csv_path):
            err_msg = f"CSV file not found: {csv_path}"
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        # Reset metrics to clear previous runs
        for metric in self.metrics.values():
            metric.reset()

        total_rows = 0
        total_cards = 0
        cards_list = []

        try:
            with open(csv_path, mode='r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # Check for standard headers (mapping to lowercase)
                headers = [h.strip() for h in reader.fieldnames] if reader.fieldnames else []
                logger.debug(f"Detected headers: {headers}")
                
                # Map headers to standard internal keys
                header_map = {}
                for h in headers:
                    h_lower = h.lower()
                    if 'count' == h_lower:
                        header_map['count'] = h
                    elif 'edition' == h_lower:
                        header_map['edition'] = h
                    elif 'name' == h_lower:
                        header_map['name'] = h
                    elif 'foil' == h_lower:
                        header_map['foil'] = h
                    elif 'collector number' == h_lower:
                        header_map['collector_number'] = h
                    elif 'proxy' == h_lower:
                        header_map['proxy'] = h
                        
                for row in reader:
                    total_rows += 1
                    
                    is_proxy_str = row.get(header_map.get('proxy', 'Proxy'), 'False').strip().lower()
                    if ignore_proxies and is_proxy_str == 'true':
                        continue
                        
                    # Normalize card dict
                    card = {
                        'name': row.get(header_map.get('name', 'Name'), '').strip(),
                        'edition': row.get(header_map.get('edition', 'Edition'), '').strip(),
                        'set': row.get(header_map.get('edition', 'Edition'), '').strip(),
                        'collector_number': row.get(header_map.get('collector_number', 'Collector Number'), '').strip(),
                        'foil': row.get(header_map.get('foil', 'Foil'), '').strip(),
                        'count': row.get(header_map.get('count', 'Count'), '1')
                    }
                    
                    try:
                        c_val = int(card['count'])
                    except ValueError:
                        c_val = 1
                    total_cards += c_val
                    cards_list.append(card)
                    
            logger.info("Resolving card details against cache and Scryfall API...")
            scryfall_core.resolve_cards(cards_list)
            
            logger.info("Running metrics processing...")
            for card in cards_list:
                # Run all registered metrics
                for metric in self.metrics.values():
                    metric.process_card(card)
                        
            logger.info(f"Successfully processed {total_rows} rows representing {total_cards} cards.")
            
        except Exception as e:
            logger.exception(f"Error occurred while parsing CSV file: {e}")
            raise

        # Generate summary report
        summary_lines = [
            "========================================",
            "        MTG BINDER ANALYSIS SUMMARY     ",
            "========================================",
            f"File: {os.path.basename(csv_path)}",
            f"Total Rows: {total_rows}",
            f"Total Cards: {total_cards}",
            ""
        ]

        # Specific target set highlight
        set_metric = self.metrics.get('set_count')
        if target_set and set_metric:
            t_set_clean = target_set.strip().lower()
            counts_dict = set_metric.get_data()
            target_count = counts_dict.get(t_set_clean, 0)
            summary_lines.append(f"TARGET SET: {target_set.upper()}")
            summary_lines.append(f"Total Cards for '{target_set.upper()}': {target_count}")
            summary_lines.append("========================================\n")

        # Metric breakdown
        for name, metric in self.metrics.items():
            summary_lines.append(f"--- Metric: {name} ---")
            summary_lines.append(metric.get_summary())
            summary_lines.append("")

        full_summary = "\n".join(summary_lines)
        
        # Save outputs file in 'outputs' directory
        outputs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'outputs'))
        os.makedirs(outputs_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(csv_path))[0]
        outputs_file = os.path.join(outputs_dir, f"{base_name}_summary.txt")
        
        try:
            with open(outputs_file, 'w', encoding='utf-8') as out_f:
                out_f.write(full_summary)
            logger.info(f"Summary outputs successfully written to: {outputs_file}")
        except Exception as e:
            logger.error(f"Failed to write outputs summary file: {e}")

        return full_summary
