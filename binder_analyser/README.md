# MTG Binder Analyser

The MTG Binder Analyser parses Moxfield collection CSV files, counts the total cards belonging to each MTG set code (edition), and allows focusing on specific sets. It is built to be modular and extensible for future analytical metrics.

## Features

- **Extensible Architecture**: Built with a modular metric base class (`BaseAnalyserMetric` in `binder_analyser_logic.py`) to easily add more stats (e.g., color identity, rarity, price).
- **CLI Interface**: Perform quick analyses from the terminal.
- **GUI Interface**: Use a simple, native OS-styled window to select files, specify parameters, and view results.
- **Automatic Logging**: Records processing steps and debugging details in `logs/binder_analyser.log`.
- **Output Summaries**: Outputs markdown/text summary files to the `outputs/` directory.

## File Structure

- [binder_analyser_logic.py](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/binder_analyser_logic.py): The core logic containing the analysis runner and metric definitions.
- [binder_analyser_cli.py](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/binder_analyser_cli.py): CLI interface using standard `argparse`.
- [binder_analyser_gui.py](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/binder_analyser_gui.py): Native Tkinter visual layout.
- [input/](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/input/): Put your input Moxfield CSV files here.
- [logs/](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/logs/): Program execution logs are written here.
- [outputs/](file:///c:/Users/dougl/Documents/Code/_MTG/binder_analyser/outputs/): Analysis summaries are written here.

## Usage

### Command-Line Interface (CLI)

Run `binder_analyser_cli.py` passing the CSV filename (or absolute path). You can optionally highlight/filter a target set code using `-s` or `--set`:

```bash
# Run analysis on a file in the input directory and count cards for 'dsc'
python binder_analyser_cli.py test_collection.csv -s dsc
```

### Graphical User Interface (GUI)

Start the graphical window:

```bash
python binder_analyser_gui.py
```

1. Click **Browse...** to select your Moxfield CSV file (defaults to starting inside the `input/` folder).
2. (Optional) Type a **Target Set Code** (e.g. `dsc`, `mh2`).
3. Click **Run Analysis** to execute. The output summary will appear in the text panel.
4. Click **Open Outputs Folder** to open the outputs summaries directory in your OS file manager.

## Extending the Stats

To add a new metric:
1. Inherit from `BaseAnalyserMetric` in `binder_analyser_logic.py`.
2. Implement `process_card(card)`, `get_summary()`, and `get_data()`.
3. Register the new metric in the `BinderAnalyser.__init__` method (e.g., `self.add_metric('your_metric_name', YourMetricClass())`).
