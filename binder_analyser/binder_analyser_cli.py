import os
import sys
import argparse
from binder_analyser_logic import BinderAnalyser, logger

def main():
    parser = argparse.ArgumentParser(description="MTG Binder Analyser CLI")
    parser.add_argument("csv_file", help="Path to Moxfield collection CSV file.")
    parser.add_argument("-s", "--set", help="The specific set code (edition) to count (e.g. dsc, mh2).", default=None)
    
    args = parser.parse_args()
    
    csv_path = args.csv_file
    
    # If the file doesn't exist directly, check the local 'input/' folder
    if not os.path.exists(csv_path):
        local_input_path = os.path.join(os.path.dirname(__file__), 'input', csv_path)
        if os.path.exists(local_input_path):
            csv_path = local_input_path
            
    analyser = BinderAnalyser()
    try:
        summary = analyser.run_analysis(csv_path, target_set=args.set)
        print(summary)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
