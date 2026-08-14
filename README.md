# POE Flip Tracker

A lightweight **Path of Exile 1 currency-flipping tracker** built in Python.

The goal is to track BUY and SELL transactions, calculate FIFO costs and realized profit, manage inventory, track Gold costs separately, and keep historical currency rates.

Currently available as a **CLI application (V1)**, with a GUI planned for V2.

---

## Features

### Transactions

* Record BUY transactions
* Record SELL transactions
* Track quantity and price
* Track payment currency
* Automatically calculate Chaos-equivalent values
* Timestamp every transaction
* Edit eligible transactions
* Delete transactions
* Protect BUY transactions that have already been partially or fully consumed by FIFO sales

### FIFO Accounting

SELL transactions use **FIFO (First In, First Out)** accounting.

For example:

```text
BUY 10 Reflecting Mist @ 400c
BUY  5 Reflecting Mist @ 500c

SELL 12 Reflecting Mist @ 600c
```

The tracker calculates the cost as:

```text
10 × 400c = 4,000c
 2 × 500c = 1,000c
-------------------
FIFO Cost = 5,000c
```

Revenue:

```text
12 × 600c = 7,200c
```

Realized profit:

```text
7,200c - 5,000c = +2,200c
```

---

## Inventory

The tracker automatically maintains remaining inventory based on BUY and SELL transactions.

Inventory shows:

* Item
* Remaining quantity
* FIFO cost basis

Inventory is rebuilt from the transaction history rather than being manually edited.

---

## Gold Tracking

Gold is tracked **separately from Chaos profit**.

Each transaction can record:

* Gold spent
* Gold → Chaos conversion rate
* Historical Gold value

For example:

```text
1,000,000 Gold = 200 Chaos
```

The Gold value used for a transaction is stored with that transaction, meaning changing the current Gold rate does **not** change historical transactions.

Gold is intentionally not subtracted from the normal Chaos flip profit.

Example:

```text
Revenue:       7,200c
FIFO Cost:    -4,900c
--------------------
Profit:       +2,300c

Gold Spent: 1,000,000
Gold Value:      200c
```

---

## Divine Rate

Divine Orbs are tracked using a simple:

```text
1 Divine = X Chaos
```

format.

For example:

```text
1 Divine = 204 Chaos
```

Historical rates are stored so changing the current rate does not alter previous transactions.

---

## Profit

The Profit screen shows:

* Total SELL revenue
* FIFO cost of sold items
* Realized Chaos profit
* Gold spent
* Gold's Chaos-equivalent value

Chaos trading profit and Gold costs are intentionally displayed separately.

---

## Inventory Value

The Inventory Value screen calculates the Chaos cost basis of all currently held inventory.

Example:

```text
Reflecting Mist
Quantity: 10
Cost basis: 4,500c
```

This represents what the remaining inventory cost you, not its current market value.

---

## Unrealized Profit

The Unrealized Profit screen allows you to enter the current market price of your remaining inventory.

Example:

```text
Quantity: 10
Cost basis: 4,500c
Market price: 600c

Potential revenue: 6,000c
Unrealized profit: +1,500c
```

This does not modify your transaction history or inventory.

---

## Data Storage

All application data is stored locally in:

```text
data.json
```

The application does not require a database.

The JSON file contains:

* Settings
* Items
* Transactions
* Currency rates
* Historical rate information
* Transaction IDs

---

## Backups

The tracker automatically creates:

```text
data.json.bak
```

when saving changes.

A manual backup can also be created from the application:

```text
8. Export Backup
```

This creates a timestamped file such as:

```text
poe_flip_tracker_backup_20260814_152400.json
```

---

## Data Validation

On startup, the application validates the structure of `data.json`.

It checks:

* Required top-level fields
* Item structure
* Transaction structure
* Transaction types
* Quantities
* Prices
* Gold values
* Transaction IDs

If the data file is corrupted, the application attempts to load the automatic backup.

---

## Requirements

* Python 3.10+
* No external Python packages are currently required

The application has been tested with Python 3.14.

---

## Installation

Clone the repository:

```bash
git clone <your-repository-url>
```

Enter the project directory:

```bash
cd poe_flip_tracker
```

Run the application:

```bash
python3 main.py
```

---

## Basic Usage

When the application starts:

```text
POE FLIP TRACKER
================

1. Add Transaction
2. Inventory
3. Transactions
4. Profit
5. Inventory Value
6. Unrealized Profit
7. Settings
8. Export Backup
9. Exit
```

### Add a transaction

Select:

```text
1. Add Transaction
```

Then choose:

* BUY or SELL
* Item
* Quantity
* Currency
* Price
* Gold spent

SELL transactions automatically use FIFO inventory costing.

---

## Project Structure

```text
poe_flip_tracker/
│
├── main.py
├── tracker.py
├── data.json
├── data.json.bak
└── README.md
```

### `main.py`

Application entry point.

### `tracker.py`

Contains the main `Tracker` class and application logic.

### `data.json`

Persistent application data.

### `data.json.bak`

Automatic recovery backup.

### `README.md`

Project documentation.

---

## V1 Status

Current V1 includes:

* [x] BUY transactions
* [x] SELL transactions
* [x] FIFO accounting
* [x] Inventory tracking
* [x] Realized profit
* [x] Unrealized profit
* [x] Inventory cost basis
* [x] Gold tracking
* [x] Divine rate tracking
* [x] Historical currency rates
* [x] Transaction editing
* [x] Transaction deletion
* [x] Data validation
* [x] Automatic backup
* [x] Manual backup/export
* [x] Local JSON storage

---

## V2 Roadmap

V2 will focus on replacing the CLI with a proper graphical interface.

Potential V2 features:

* Dashboard
* Interactive transaction table
* Search and filtering
* Item management
* Charts and statistics
* Profit graphs
* Inventory overview
* Gold tracking dashboard
* Currency-rate history
* Better transaction editing
* Import/export
* Improved backup management
* Cleaner and more user-friendly UI

The V1 CLI will remain the foundation for the accounting and FIFO logic.

---

## Disclaimer

This is a personal utility for tracking Path of Exile flipping activity.

Prices, currency values, and market conditions are entered by the user and are not automatically sourced from the Path of Exile trade website.

The application is not affiliated with or endorsed by Grinding Gear Games.
