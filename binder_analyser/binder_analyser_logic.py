import os
import csv
import logging
from typing import List, Dict, Any, Optional

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


class SetCounterMetric(BaseAnalyserMetric):
    """Metric that counts the number of cards grouped by set code (Edition)."""
    def __init__(self):
        super().__init__()
        self.counts = {}  # set_code (lowercase) -> total count

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


class BinderAnalyser:
    """Coordinator class that reads Moxfield CSV files and runs metrics."""
    def __init__(self):
        self.metrics: Dict[str, BaseAnalyserMetric] = {
            'set_count': SetCounterMetric()
        }

    def add_metric(self, name: str, metric: BaseAnalyserMetric) -> None:
        """Enables extensibility to register new analysis metrics."""
        self.metrics[name] = metric
        logger.debug(f"Registered metric: {name}")

    def run_analysis(self, csv_path: str, target_set: Optional[str] = None) -> str:
        """
        Reads CSV and executes all registered metrics.
        Returns a formatted full summary string and saves it.
        """
        logger.info(f"Starting binder analysis on: {csv_path}")
        
        if not os.path.exists(csv_path):
            err_msg = f"CSV file not found: {csv_path}"
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        # Reset metrics to clear previous runs
        for metric in self.metrics.values():
            if hasattr(metric, 'counts'):
                metric.counts = {}

        total_rows = 0
        total_cards = 0

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
                        
                for row in reader:
                    total_rows += 1
                    # Normalize card dict
                    card = {
                        'name': row.get(header_map.get('name', 'Name'), '').strip(),
                        'edition': row.get(header_map.get('edition', 'Edition'), '').strip(),
                        'count': row.get(header_map.get('count', 'Count'), '1')
                    }
                    
                    try:
                        c_val = int(card['count'])
                    except ValueError:
                        c_val = 1
                    total_cards += c_val

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
