# Recurring Expenses TUI

Recurring Expenses TUI is a keyboard-first terminal application for Arch Linux that tracks recurring personal expenditures such as rent, subscriptions, insurance, and other base costs.

## Features

- Automatically load recurring expenses from JSON under the user config directory
- View monthly and yearly base costs in a Textual Overview tab
- Add, edit, and delete recurring expenses from a dedicated Edit tab
- Read keyboard shortcuts from the Help tab
- Switch between tabs with visible tab navigation and keyboard shortcuts
- Validate expense names, amounts, and allowed frequencies before saving
- Reload data from disk without restarting the app

## Requirements

- Arch Linux
- Python 3.12 or newer

## Installation

Install the base Python toolchain on Arch Linux:

```bash
sudo pacman -S python python-pip
```

Create a virtual environment and install the project:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If you use `uv`, the equivalent install is:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .[dev]
```

## Usage

Run the application with:

```bash
recurring-expenses-tui
```

The app stores its data in:

```text
~/.config/recurring-expenses-tui/expenses.json
```

On startup, the app automatically loads this file. If the file does not exist,
the app creates it with an empty JSON object:

```json
{}
```

If the file contains invalid JSON, the app shows a clear error in the TUI and
continues with an empty in-memory expense list where possible.

## Navigation

The TUI has three visible tabs:

- `Overview` shows all saved expenses and monthly/yearly totals.
- `Edit` uses a modal workflow for create, edit, and delete operations.
- `Help` lists the available keyboard shortcuts.

Use `o`, `h`, and `e` to open Overview, Help, and Edit directly. The active tab
is highlighted by Textual's tab widget.

## Keyboard Shortcuts

- `q` quit the application
- `r` reload the JSON file from disk
- `o` open the Overview tab
- `h` open the Help tab
- `e` open the Edit tab
- `j` / `k` move the selected Edit row down or up
- `a` / `A` open create mode in Edit
- `e` / `E` open edit mode for the selected row in Edit
- `d` / `D` open delete confirmation for the selected row in Edit
- `tab` / `shift+tab` move between fields while creating or editing
- `enter` advance fields and submit from the final field while creating or editing
- `y` / `n` confirm or cancel deletion in Edit
- `esc` cancel the active Edit modal, or return to Overview from Edit or Help

## JSON Format

The stored file uses this shape:

```json
{
  "rent": {
    "amount": 1200.0,
    "frequency": "monthly"
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

Amounts must be non-negative and use at most two decimal places. Expense names
must be non-empty strings.

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

## Arch Linux Notes

Install Python and pip with pacman, then install the project in a virtual
environment:

```bash
sudo pacman -S python python-pip
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
recurring-expenses-tui
```

## Development

Run the test suite with:

```bash
pytest
```
