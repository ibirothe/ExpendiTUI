# ExpendiTUI

ExpendiTUI is a keyboard-first terminal application for Arch Linux that tracks recurring expenses and income such as rent, subscriptions, salary, insurance, and other core financial flows.

## Features

- Automatically load expenses and income from JSON under the user config directory
- View monthly and yearly expense, income, and savings totals in a Textual Overview tab
- Add, edit, and delete expense and income entries from a dedicated Edit tab
- Read keyboard shortcuts from the Help tab
- Switch between tabs with visible tab navigation and keyboard shortcuts
- Load and switch color themes at runtime with persisted theme selection
- Validate entry names, amounts, tags, and allowed frequencies before saving
- Reload data from disk without restarting the app

## Requirements

- Python 3.12 or newer

## Installation

Start in the project directory that contains `pyproject.toml`:

```bash
cd ExpendiTUI
```

Create a fresh virtual environment, activate it, and install the package:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If you use `uv`, the equivalent setup is:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Activation alone is not enough. The `expenditui` command is only
added to the virtual environment after `pip install -e ".[dev]"` or
`uv pip install -e ".[dev]"` succeeds.

## Usage

Run the application from the activated virtual environment:

```bash
expenditui
```

If you want to verify the package import path directly, the app can also be
started with:

```bash
python -m expenditui
```

If `python -m expenditui` works but `expenditui` does
not, your virtual environment activation or install step is wrong.

## Troubleshooting

If you see `bash: command not found: expenditui`, check these first:

- Make sure you are in the directory that contains `pyproject.toml` before you install.
- Make sure the environment is activated before you run the command.
- Verify that the console script exists on your `PATH`:

```bash
command -v expenditui
```

If that command prints nothing, recreate the environment and reinstall:

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then run:

```bash
expenditui
```

The app stores its data in:

```text
~/.config/expenditui/expenses.json
```

Income is stored in:

```text
~/.config/expenditui/income.json
```

Optional theme configuration is loaded from:

```text
~/.config/expenditui/themes.json
```

On startup, the app automatically loads this file. If the file does not exist,
the app creates it with an empty JSON object:

```json
{}
```

If the file contains invalid JSON, the app shows a clear error in the TUI and
continues with an empty in-memory entry list where possible.

If `themes.json` is missing, malformed, empty, or contains only invalid theme
rows, the app falls back to built-in themes and remains usable.

Built-in themes include `Dreamy`, `Sandstone`, and `Nord`.

## Navigation

ExpendiTUI has three visible tabs:

- `Overview` shows all saved expense and income entries with monthly and yearly totals and savings.
- `Edit` uses a modal workflow for create, edit, and delete operations.
- `Help` lists the available keyboard shortcuts.

Use `o`, `h`, and `e` to open Overview, Help, and Edit directly. The active tab
is highlighted by Textual's tab widget.

## Keyboard Shortcuts

- `q` quit the application
- `r` reload the JSON file from disk
- `t` cycle themes globally, except while typing in Edit create or edit forms
- `o` open the Overview tab
- `h` open the Help tab
- `e` open the Edit tab
- `j` / `k` move the selected Edit row down or up
- `i` toggle between expenses and income while in Edit navigation mode
- `a` / `A` open create mode in Edit
- `e` / `E` open edit mode for the selected row in Edit
- `d` / `D` open delete confirmation for the selected row in Edit
- `tab` / `shift+tab` move between fields while creating or editing
- `enter` advance fields and submit from the final field while creating or editing
- `y` / `n` confirm or cancel deletion in Edit
- `esc` cancel the active Edit modal, or return to Overview from Edit or Help

## JSON Format

Each data file uses this shape:

```json
{
  "rent": {
    "amount": 1200.0,
    "frequency": "monthly",
    "tags": ["Housing"]
  },
  "netflix": {
    "amount": 12.5,
    "frequency": "monthly"
  },
  "insurance": {
    "amount": 600.0,
    "frequency": "annual"
  }
}
```

Amounts must be non-negative and use at most two decimal places. Entry names
must be non-empty strings. Tags are optional, stored as string arrays, limited
to 10 values per entry, and each tag must be non-empty after trimming.

Supported frequencies are:

- `daily`
- `weekly`
- `biweekly`
- `monthly`
- `quarterly`
- `semiannual`
- `annual`

Monthly equivalents are calculated as:

- `daily`: `amount * 365 / 12`
- `weekly`: `amount * 52 / 12`
- `biweekly`: `amount * 26 / 12`
- `monthly`: `amount`
- `quarterly`: `amount / 3`
- `semiannual`: `amount / 6`
- `annual`: `amount / 12`

The yearly total is the monthly total multiplied by 12.

Savings are calculated from recurring equivalents:

- `monthly savings = monthly income - monthly expenses`
- `yearly savings = yearly income - yearly expenses`

## Theme Format

Themes use a JSON array of arrays in `~/.config/expenditui/themes.json`.
Each theme row must contain a name followed by eight hex colors in this order:

1. `background`
2. `foreground`
3. `surface`
4. `accent`
5. `success`
6. `warning`
7. `error`
8. `muted`

Example:

```json
[
  ["Dark", "#121212", "#F5F5F5", "#1E1E1E", "#BB86FC", "#03DAC6", "#F4C95D", "#CF6679", "#8E8E93"],
  ["Light", "#FFFFFF", "#111111", "#F5F5F5", "#6200EE", "#0F9D58", "#B26A00", "#C62828", "#6B7280"]
]
```

The last selected theme is persisted automatically across restarts.

## Arch Linux Notes

Install Python and pip with pacman, then follow the installation steps above:

```bash
sudo pacman -S python python-pip
cd ExpendiTUI
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
expenditui
```

## Development

Run the same checks locally that CI runs:

```bash
black --check .
pytest
```

To apply formatting locally before committing, run:

```bash
black .
```
