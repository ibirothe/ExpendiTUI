# ExpendiTUI Terminology

This document defines the approved user-facing terminology and branding for ExpendiTUI.

## Branding

- Project name: `ExpendiTUI`
- CLI command: `expenditui`
- Python package: `expenditui`
- Config directory: `~/.config/expenditui/`

Use `ExpendiTUI` in titles, documentation, package metadata, and other branded surfaces.
Use `expenditui` for command names, import paths, and filesystem naming.

## Approved Terms

- `Expense`: recurring outgoing money
- `Income`: recurring incoming money
- `Entry`: a single saved financial item
- `Overview`: the summary screen
- `Edit`: the editing screen
- `Tags`: optional labels attached to an entry

## Avoid

- `Expenditure` or `Expenditures`
- `Earnings`
- `Record`
- `Recurring Finance TUI`
- `Recurring Expenses TUI`
- `recurring-expenses-tui`
- `recurring_expenses_tui`

## Usage Rules

- Use `Expense`, `Income`, and `Entry` consistently in UI labels, dialogs, help text, status messages, and documentation.
- Prefer `expenses and income` when referring to the two datasets together.
- Use `entry` when describing create, edit, delete, validation, or selection behavior.
- Keep internal names aligned with the public terminology when a rename improves clarity and does not add compatibility burden.
