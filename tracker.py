import copy
from datetime import datetime
from pathlib import Path

from backend.storage import Storage


DATA_FILE = Path(__file__).with_name("data.json")
BACKUP_FILE = Path(__file__).with_name("data.json.bak")


DEFAULT_DATA = {
    "settings": {
        "gold_rate": {
            "gold_amount": 1_000_000,
            "chaos_value": 200,
            "history": []
        },
        "divine_rate": {
            "divine_amount": 1,
            "chaos_value": 180,
            "history": []
        }
    },

    "items": [
        {
            "id": 1,
            "name": "Exalted Orb",
            "active": True
        },
        {
            "id": 2,
            "name": "Reflecting Mist",
            "active": True
        }
    ],

    "transactions": [],

    "next_transaction_id": 1
}


class Tracker:

    def __init__(self):
        self.storage = Storage(
            DATA_FILE,
            BACKUP_FILE,
            DEFAULT_DATA
        )

        self.data = self.storage.load()

        self._validate_data()

    # =========================================================
    # GENERAL
    # =========================================================

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def save(self):
        self.storage.save(self.data)

    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_data(self):
        if not isinstance(self.data, dict):
            raise RuntimeError(
                "data.json must contain a JSON object."
            )

        required_keys = [
            "settings",
            "items",
            "transactions",
            "next_transaction_id"
        ]

        for key in required_keys:
            if key not in self.data:
                raise RuntimeError(
                    f"data.json is missing required field: {key}"
                )

        if not isinstance(self.data["items"], list):
            raise RuntimeError(
                "data.json 'items' must be a list."
            )

        if not isinstance(self.data["transactions"], list):
            raise RuntimeError(
                "data.json 'transactions' must be a list."
            )

        if not isinstance(
            self.data["next_transaction_id"],
            int
        ):
            raise RuntimeError(
                "data.json 'next_transaction_id' "
                "must be an integer."
            )

        # Validate items
        for item in self.data["items"]:

            if "id" not in item:
                raise RuntimeError(
                    "An item is missing its ID."
                )

            if "name" not in item:
                raise RuntimeError(
                    f"Item {item['id']} is missing its name."
                )

            if "active" not in item:
                raise RuntimeError(
                    f"Item {item['id']} is missing 'active'."
                )

        # Validate transactions
        required_transaction_keys = [
            "id",
            "type",
            "item_id",
            "item_name",
            "quantity",
            "payment_currency",
            "entered_price",
            "unit_price_chaos",
            "total_chaos",
            "gold_spent",
            "gold_chaos",
            "gold_rate",
            "divine_rate",
            "timestamp"
        ]

        for transaction in self.data["transactions"]:

            for key in required_transaction_keys:

                if key not in transaction:
                    raise RuntimeError(
                        f"Transaction "
                        f"{transaction.get('id', '?')} "
                        f"is missing '{key}'."
                    )

            if transaction["type"] not in (
                "BUY",
                "SELL"
            ):
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid type: "
                    f"{transaction['type']}"
                )

            if transaction["quantity"] <= 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid quantity."
                )

            if transaction["entered_price"] < 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid entered price."
                )

            if transaction["unit_price_chaos"] < 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid Chaos price."
                )

            if transaction["total_chaos"] < 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid total Chaos value."
                )

            if transaction["gold_spent"] < 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid Gold amount."
                )

            if transaction["gold_chaos"] < 0:
                raise RuntimeError(
                    f"Transaction "
                    f"{transaction['id']} "
                    f"has invalid Gold Chaos value."
                )

    # =========================================================
    # INPUT HELPERS
    # =========================================================

    def _ask_menu_choice(
        self,
        prompt,
        minimum,
        maximum
    ):
        while True:
            value = input(prompt).strip()

            try:
                choice = int(value)

                if minimum <= choice <= maximum:
                    return choice

            except ValueError:
                pass

            print(
                f"Invalid choice. "
                f"Enter a number from "
                f"{minimum} to {maximum}."
            )

    def _ask_positive_int(self, prompt):
        while True:
            value = input(prompt).strip()

            try:
                number = int(value)

                if number >= 1:
                    return number

            except ValueError:
                pass

            print(
                "Please enter a whole number "
                "greater than 0."
            )

    def _ask_nonnegative_int(self, prompt):
        while True:
            value = input(prompt).strip()

            try:
                number = int(value)

                if number >= 0:
                    return number

            except ValueError:
                pass

            print(
                "Please enter a whole number "
                "of 0 or more."
            )

    # =========================================================
    # TRANSACTION HELPERS
    # =========================================================

    def _get_transaction(self, transaction_id):
        for transaction in self.data["transactions"]:
            if transaction["id"] == transaction_id:
                return transaction

        return None

    def _next_transaction_id(self):
        transaction_id = self.data["next_transaction_id"]

        self.data["next_transaction_id"] += 1

        return transaction_id

    def _buy_has_been_sold(self, buy_transaction_id):
        for transaction in self.data["transactions"]:

            if transaction["type"] != "SELL":
                continue

            for allocation in transaction.get(
                "fifo_allocations",
                []
            ):
                if (
                    allocation["buy_transaction_id"]
                    == buy_transaction_id
                ):
                    return True

        return False

    # =========================================================
    # ITEMS
    # =========================================================

    def _active_items(self):
        return [
            item
            for item in self.data["items"]
            if item.get("active", True)
        ]

    def _select_item(self):
        items = self._active_items()

        if not items:
            print("No active tradable items.")
            return None

        print("\nSelect item:")

        for index, item in enumerate(items, 1):
            print(
                f"{index}. {item['name']}"
            )

        choice = self._ask_menu_choice(
            "> ",
            1,
            len(items)
        )

        return items[choice - 1]

    # =========================================================
    # CURRENCY
    # =========================================================

    def _select_currency(self):
        print("\nPayment currency:")
        print("1. Chaos")
        print("2. Divine")

        choice = self._ask_menu_choice(
            "> ",
            1,
            2
        )

        if choice == 1:
            return "CHAOS"

        return "DIVINE"

    # =========================================================
    # RATES
    # =========================================================

    def _current_gold_rate(self):
        return self.data["settings"]["gold_rate"]

    def _current_divine_rate(self):
        return self.data["settings"]["divine_rate"]

    def _gold_to_chaos(self, gold_amount):
        rate = self._current_gold_rate()

        return (
            gold_amount * rate["chaos_value"]
            // rate["gold_amount"]
        )

    def _divine_to_chaos(self, divine_amount):
        rate = self._current_divine_rate()

        return (
            divine_amount * rate["chaos_value"]
            // rate["divine_amount"]
        )

    def _edit_gold_rate(self):
        current = self._current_gold_rate()

        print()
        print("GOLD RATE")
        print("---------")
        print(
            f"Current: "
            f"{current['gold_amount']:,} Gold "
            f"= {current['chaos_value']} Chaos"
        )

        gold_amount = self._ask_positive_int(
            "\nGold amount: "
        )

        chaos_value = self._ask_positive_int(
            "Chaos value: "
        )

        now = self._now()

        current["gold_amount"] = gold_amount
        current["chaos_value"] = chaos_value

        current["history"].append({
            "timestamp": now,
            "gold_amount": gold_amount,
            "chaos_value": chaos_value
        })

        self.save()

        print()
        print("Gold rate updated:")
        print(
            f"{gold_amount:,} Gold = "
            f"{chaos_value} Chaos"
        )

        input(
            "\nPress Enter to continue..."
        )

    def _edit_divine_rate(self):
        current = self._current_divine_rate()

        print()
        print("DIVINE RATE")
        print("-----------")
        print(
            f"Current: "
            f"1 Divine = "
            f"{current['chaos_value']} Chaos"
        )

        chaos_value = self._ask_positive_int(
            "\nChaos value per Divine: "
        )

        now = self._now()

        current["divine_amount"] = 1
        current["chaos_value"] = chaos_value

        current["history"].append({
            "timestamp": now,
            "divine_amount": 1,
            "chaos_value": chaos_value
        })

        self.save()

        print()
        print("Divine rate updated:")
        print(
            f"1 Divine = "
            f"{chaos_value} Chaos"
        )

        input(
            "\nPress Enter to continue..."
        )

    # =========================================================
    # INVENTORY
    # =========================================================

    def _build_inventory(self):
        inventory = {}

        transactions = sorted(
            self.data["transactions"],
            key=lambda transaction: (
                transaction["timestamp"],
                transaction["id"]
            )
        )

        for transaction in transactions:

            item_id = transaction["item_id"]

            if item_id not in inventory:
                inventory[item_id] = []

            # BUY
            if transaction["type"] == "BUY":

                inventory[item_id].append({
                    "buy_transaction_id":
                        transaction["id"],

                    "quantity":
                        transaction["quantity"],

                    "remaining":
                        transaction["quantity"],

                    "unit_cost_chaos":
                        transaction["unit_price_chaos"],

                    "timestamp":
                        transaction["timestamp"]
                })

            # SELL
            elif transaction["type"] == "SELL":

                quantity_to_remove = (
                    transaction["quantity"]
                )

                for batch in inventory[item_id]:

                    if quantity_to_remove <= 0:
                        break

                    available = batch["remaining"]

                    if available <= 0:
                        continue

                    amount = min(
                        available,
                        quantity_to_remove
                    )

                    batch["remaining"] -= amount

                    quantity_to_remove -= amount

        return inventory

    def _available_quantity(self, item_id):
        inventory = self._build_inventory()

        if item_id not in inventory:
            return 0

        return sum(
            batch["remaining"]
            for batch in inventory[item_id]
        )

    def _inventory_cost(self):
        inventory = self._build_inventory()

        total_cost = 0

        for batches in inventory.values():

            for batch in batches:

                if batch["remaining"] <= 0:
                    continue

                total_cost += (
                    batch["remaining"]
                    * batch["unit_cost_chaos"]
                )

        return total_cost

    # =========================================================
    # FIFO
    # =========================================================

    def _calculate_fifo(
        self,
        item_id,
        quantity
    ):
        inventory = self._build_inventory()

        if item_id not in inventory:
            return None

        available = sum(
            batch["remaining"]
            for batch in inventory[item_id]
        )

        if quantity > available:
            return None

        remaining_to_sell = quantity

        allocations = []

        total_cost = 0

        for batch in inventory[item_id]:

            if remaining_to_sell <= 0:
                break

            if batch["remaining"] <= 0:
                continue

            amount = min(
                batch["remaining"],
                remaining_to_sell
            )

            cost = (
                amount
                * batch["unit_cost_chaos"]
            )

            allocations.append({
                "buy_transaction_id":
                    batch["buy_transaction_id"],

                "quantity":
                    amount,

                "unit_cost_chaos":
                    batch["unit_cost_chaos"],

                "total_cost_chaos":
                    cost
            })

            total_cost += cost

            remaining_to_sell -= amount

        return allocations, total_cost

    # =========================================================
    # ADD TRANSACTION
    # =========================================================

    def _select_transaction_type(self):
        print("\nTransaction type:")
        print("1. Buy")
        print("2. Sell")

        choice = self._ask_menu_choice(
            "> ",
            1,
            2
        )

        if choice == 1:
            return "BUY"

        return "SELL"

    def add_transaction(self):
        item = self._select_item()

        if item is None:
            return

        transaction_type = (
            self._select_transaction_type()
        )

        quantity = self._ask_positive_int(
            "\nQuantity: "
        )

        currency = self._select_currency()

        if currency == "CHAOS":

            price = self._ask_positive_int(
                "\nPrice per item in Chaos: "
            )

            chaos_price = price
            divine_rate = None

        else:

            price = self._ask_positive_int(
                "\nPrice per item in Divine: "
            )

            divine_rate = copy.deepcopy(
                self._current_divine_rate()
            )

            chaos_price = self._divine_to_chaos(
                price
            )

        gold_spent = self._ask_nonnegative_int(
            "\nGold spent: "
        )

        gold_rate = copy.deepcopy(
            self._current_gold_rate()
        )

        gold_chaos = self._gold_to_chaos(
            gold_spent
        )

        total_chaos = (
            chaos_price * quantity
        )

        fifo_allocations = []
        fifo_cost = 0
        profit = 0

        if transaction_type == "SELL":

            fifo_result = self._calculate_fifo(
                item["id"],
                quantity
            )

            if fifo_result is None:

                available = (
                    self._available_quantity(
                        item["id"]
                    )
                )

                print()
                print("Not enough inventory.")
                print(
                    f"Available: {available}"
                )

                input(
                    "\nPress Enter to return "
                    "to the menu..."
                )

                return

            fifo_allocations, fifo_cost = (
                fifo_result
            )

            profit = (
                total_chaos
                - fifo_cost
            )

        # -------------------------
        # Confirmation
        # -------------------------

        print()
        print("Transaction information")
        print("-----------------------")

        print(
            f"Item: {item['name']}"
        )

        print(
            f"Type: {transaction_type}"
        )

        print(
            f"Quantity: {quantity}"
        )

        if currency == "CHAOS":

            print(
                f"Price: {price:,}c each"
            )

        else:

            print(
                f"Price: {price} Divine each "
                f"({chaos_price:,}c each)"
            )

        print(
            f"Total: {total_chaos:,}c"
        )

        if transaction_type == "SELL":

            print(
                f"FIFO Cost: {fifo_cost:,}c"
            )

            print(
                f"Profit: {profit:+,}c"
            )

            print()
            print("FIFO allocation:")

            for allocation in fifo_allocations:

                print(
                    f"  "
                    f"{allocation['quantity']} x "
                    f"{allocation['unit_cost_chaos']:,}c"
                )

        print(
            f"Gold spent: {gold_spent:,} "
            f"({gold_chaos:,}c equivalent)"
        )

        print()

        confirm = input(
            "Save this transaction? (y/n): "
        ).strip().lower()

        if confirm not in ("y", "yes"):

            print("Transaction cancelled.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        transaction = {
            "id":
                self._next_transaction_id(),

            "type":
                transaction_type,

            "item_id":
                item["id"],

            "item_name":
                item["name"],

            "quantity":
                quantity,

            "payment_currency":
                currency,

            "entered_price":
                price,

            "unit_price_chaos":
                chaos_price,

            "total_chaos":
                total_chaos,

            "gold_spent":
                gold_spent,

            "gold_chaos":
                gold_chaos,

            "gold_rate":
                gold_rate,

            "divine_rate":
                divine_rate,

            "fifo_allocations":
                fifo_allocations,

            "fifo_cost":
                fifo_cost,

            "profit":
                profit,

            "timestamp":
                self._now()
        }

        self.data["transactions"].append(
            transaction
        )

        self.save()

        print()
        print(
            f"Transaction "
            f"#{transaction['id']} saved."
        )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # SHOW TRANSACTIONS
    # =========================================================

    def show_transactions(self):
        print("\nTRANSACTIONS")
        print("------------")

        transactions = sorted(
            self.data["transactions"],
            key=lambda transaction: (
                transaction["timestamp"],
                transaction["id"]
            ),
            reverse=True
        )

        if not transactions:
            print("No transactions.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        for transaction in transactions:

            print()
            print(
                f"#{transaction['id']} "
                f"{transaction['timestamp']}"
            )

            print(
                f"{transaction['type']} "
                f"{transaction['quantity']} "
                f"{transaction['item_name']}"
            )

            print(
                f"Price: "
                f"{transaction['unit_price_chaos']:,}c each"
            )

            if transaction["type"] == "BUY":

                print(
                    f"Cost: "
                    f"{transaction['total_chaos']:,}c"
                )

            else:

                print(
                    f"Revenue: "
                    f"{transaction['total_chaos']:,}c"
                )

                print(
                    f"FIFO Cost: "
                    f"{transaction['fifo_cost']:,}c"
                )

                print(
                    f"Profit: "
                    f"{transaction['profit']:+,}c"
                )

            print(
                f"Gold: "
                f"{transaction['gold_spent']:,}"
            )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # INVENTORY DISPLAY
    # =========================================================

    def show_inventory(self):
        inventory = self._build_inventory()

        print("\nINVENTORY")
        print("---------")

        if not inventory:

            print("Inventory is empty.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        found_inventory = False

        for item_id, batches in inventory.items():

            total_quantity = sum(
                batch["remaining"]
                for batch in batches
            )

            if total_quantity <= 0:
                continue

            found_inventory = True

            item = next(
                (
                    item
                    for item in self.data["items"]
                    if item["id"] == item_id
                ),
                None
            )

            if item is None:
                continue

            print()
            print(item["name"])
            print(
                f"Total: {total_quantity}"
            )

            for batch in batches:

                if batch["remaining"] <= 0:
                    continue

                print(
                    f"  "
                    f"{batch['remaining']} x "
                    f"{batch['unit_cost_chaos']:,}c"
                )

        if not found_inventory:
            print("Inventory is empty.")

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # INVENTORY VALUE
    # =========================================================

    def show_inventory_value(self):
        inventory = self._build_inventory()

        print()
        print("INVENTORY VALUE")
        print("---------------")

        total_quantity = 0
        total_cost = 0

        for item_id, batches in inventory.items():

            remaining_quantity = sum(
                batch["remaining"]
                for batch in batches
            )

            if remaining_quantity <= 0:
                continue

            item = next(
                (
                    item
                    for item in self.data["items"]
                    if item["id"] == item_id
                ),
                None
            )

            if item is None:
                continue

            item_cost = sum(
                batch["remaining"]
                * batch["unit_cost_chaos"]
                for batch in batches
                if batch["remaining"] > 0
            )

            print()
            print(item["name"])
            print(
                f"Quantity: "
                f"{remaining_quantity}"
            )

            print(
                f"Cost basis: "
                f"{item_cost:,}c"
            )

            total_quantity += remaining_quantity
            total_cost += item_cost

        print()
        print("-----------------------")
        print(
            f"Total items: "
            f"{total_quantity}"
        )

        print(
            f"Inventory cost: "
            f"{total_cost:,}c"
        )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # UNREALIZED PROFIT
    # =========================================================

    def show_unrealized_profit(self):
        inventory = self._build_inventory()

        print()
        print("UNREALIZED PROFIT")
        print("-----------------")

        found_inventory = False

        total_cost = 0
        total_revenue = 0

        for item_id, batches in inventory.items():

            quantity = sum(
                batch["remaining"]
                for batch in batches
                if batch["remaining"] > 0
            )

            if quantity <= 0:
                continue

            item = next(
                (
                    item
                    for item in self.data["items"]
                    if item["id"] == item_id
                ),
                None
            )

            if item is None:
                continue

            found_inventory = True

            cost = sum(
                batch["remaining"]
                * batch["unit_cost_chaos"]
                for batch in batches
                if batch["remaining"] > 0
            )

            print()
            print(item["name"])
            print(
                f"Quantity: {quantity}"
            )

            print(
                f"Cost basis: {cost:,}c"
            )

            market_price = self._ask_positive_int(
                "Current market price per item in Chaos: "
            )

            revenue = (
                quantity * market_price
            )

            profit = revenue - cost

            print(
                f"Potential revenue: "
                f"{revenue:,}c"
            )

            print(
                f"Unrealized profit: "
                f"{profit:+,}c"
            )

            total_cost += cost
            total_revenue += revenue

        if not found_inventory:

            print("Inventory is empty.")

        else:

            print()
            print("-----------------")

            print(
                f"Total cost: "
                f"{total_cost:,}c"
            )

            print(
                f"Potential revenue: "
                f"{total_revenue:,}c"
            )

            print(
                f"Unrealized profit: "
                f"{total_revenue - total_cost:+,}c"
            )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # PROFIT
    # =========================================================

    def show_profit(self):
        transactions = self.data["transactions"]

        total_sell_revenue = 0
        total_fifo_cost = 0
        realized_profit = 0

        total_gold_spent = 0
        total_gold_chaos = 0

        for transaction in transactions:

            if transaction["type"] == "SELL":

                total_sell_revenue += (
                    transaction["total_chaos"]
                )

                total_fifo_cost += (
                    transaction["fifo_cost"]
                )

                realized_profit += (
                    transaction["profit"]
                )

            total_gold_spent += transaction.get(
                "gold_spent",
                0
            )

            total_gold_chaos += transaction.get(
                "gold_chaos",
                0
            )

        # Inventory
        inventory = self._build_inventory()

        total_inventory_quantity = 0
        total_inventory_cost = 0

        for batches in inventory.values():

            for batch in batches:

                if batch["remaining"] <= 0:
                    continue

                total_inventory_quantity += (
                    batch["remaining"]
                )

                total_inventory_cost += (
                    batch["remaining"]
                    * batch["unit_cost_chaos"]
                )

        # Display
        print()
        print("FLIP SUMMARY")
        print("------------")

        print()
        print("REALIZED")
        print("--------")

        print(
            f"Revenue:          "
            f"{total_sell_revenue:,}c"
        )

        print(
            f"Item cost:       "
            f"-{total_fifo_cost:,}c"
        )

        print(
            f"Profit:          "
            f"{realized_profit:+,}c"
        )

        print()
        print("INVENTORY")
        print("---------")

        print(
            f"Items:            "
            f"{total_inventory_quantity}"
        )

        print(
            f"Cost basis:       "
            f"{total_inventory_cost:,}c"
        )

        print()
        print("GOLD")
        print("----")

        print(
            f"Spent:            "
            f"{total_gold_spent:,}"
        )

        print(
            f"Value:            "
            f"{total_gold_chaos:,}c"
        )

        print()
        print("----------------------------")

        print(
            f"REALIZED PROFIT: "
            f"{realized_profit:+,}c"
        )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # EDIT / DELETE TRANSACTIONS
    # =========================================================

    def delete_transaction(self, transaction_id):
        transaction = self._get_transaction(
            transaction_id
        )

        if transaction is None:
            print("Transaction not found.")
            return

        # BUY
        if transaction["type"] == "BUY":

            if self._buy_has_been_sold(
                transaction_id
            ):

                print()
                print(
                    "This BUY cannot be deleted."
                )

                print(
                    "Some of its inventory has "
                    "already been sold."
                )

                input(
                    "\nPress Enter to return "
                    "to the menu..."
                )

                return

        # Confirmation
        print()
        print("Transaction to delete")
        print("----------------------")

        print(
            f"#{transaction['id']} "
            f"{transaction['timestamp']}"
        )

        print(
            f"{transaction['type']} "
            f"{transaction['quantity']} "
            f"{transaction['item_name']}"
        )

        if transaction["type"] == "BUY":

            print(
                f"Cost: "
                f"{transaction['total_chaos']:,}c"
            )

        else:

            print(
                f"Revenue: "
                f"{transaction['total_chaos']:,}c"
            )

            print(
                f"Profit: "
                f"{transaction['profit']:+,}c"
            )

        print()

        confirmation = input(
            "Delete this transaction? (y/n): "
        ).strip().lower()

        if confirmation not in ("y", "yes"):

            print("Deletion cancelled.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        self.data["transactions"].remove(
            transaction
        )

        self.save()

        print()
        print(
            f"Transaction "
            f"#{transaction_id} deleted."
        )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    def edit_transaction(self, transaction_id):
        transaction = self._get_transaction(
            transaction_id
        )

        if transaction is None:

            print("Transaction not found.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        if transaction["type"] == "BUY":

            if self._buy_has_been_sold(
                transaction_id
            ):

                print()
                print(
                    "This BUY cannot be edited."
                )

                print(
                    "Some of its inventory has "
                    "already been sold."
                )

                print()
                print(
                    "Delete/edit the dependent "
                    "SELL transactions first "
                    "if you want to change this BUY."
                )

                input(
                    "\nPress Enter to return "
                    "to the menu..."
                )

                return

        print()
        print("Editing transaction")
        print("-------------------")

        print(
            f"#{transaction['id']} "
            f"{transaction['type']} "
            f"{transaction['quantity']} "
            f"{transaction['item_name']}"
        )

        print()
        print(
            "The original transaction will be "
            "deleted and replaced with a new "
            "transaction."
        )

        confirmation = input(
            "\nContinue? (y/n): "
        ).strip().lower()

        if confirmation not in ("y", "yes"):

            print("Edit cancelled.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        self.data["transactions"].remove(
            transaction
        )

        self.save()

        print()
        print("Original transaction removed.")
        print(
            "Enter the replacement transaction."
        )
        print()

        self.add_transaction()

    def manage_transactions(self):
        self.show_transactions()

        if not self.data["transactions"]:
            return

        print()
        print(
            "Enter transaction ID to manage "
            "(0 to go back):"
        )

        transaction_id = (
            self._ask_nonnegative_int("> ")
        )

        if transaction_id == 0:
            return

        transaction = self._get_transaction(
            transaction_id
        )

        if transaction is None:

            print("Transaction not found.")

            input(
                "\nPress Enter to return "
                "to the menu..."
            )

            return

        print()
        print(
            f"Transaction #{transaction['id']}"
        )

        print("----------------------")
        print("1. Edit")
        print("2. Delete")
        print("3. Back")

        choice = self._ask_menu_choice(
            "> ",
            1,
            3
        )

        if choice == 1:

            self.edit_transaction(
                transaction_id
            )

        elif choice == 2:

            self.delete_transaction(
                transaction_id
            )

    # =========================================================
    # SETTINGS
    # =========================================================

    def show_settings(self):
        while True:

            print()
            print("SETTINGS")
            print("--------")

            print("1. Gold Rate")
            print("2. Divine Rate")
            print("3. Back")

            choice = self._ask_menu_choice(
                "> ",
                1,
                3
            )

            if choice == 1:

                self._edit_gold_rate()

            elif choice == 2:

                self._edit_divine_rate()

            elif choice == 3:

                return

    # =========================================================
    # BACKUP
    # =========================================================

    def export_backup(self):
        backup_file = self.storage.export_backup(
            self.data
        )

        print()
        print("BACKUP CREATED")
        print("--------------")

        print(
            f"File: "
            f"{backup_file.name}"
        )

        print(
            f"Location: "
            f"{backup_file.parent}"
        )

        input(
            "\nPress Enter to return "
            "to the menu..."
        )

    # =========================================================
    # MAIN CLI
    # =========================================================

    def run(self):
        print("POE FLIP TRACKER")
        print("================")
        print("Data loaded successfully.")

        while True:

            print()
            print("1. Add Transaction")
            print("2. Inventory")
            print("3. Transactions")
            print("4. Profit")
            print("5. Inventory Value")
            print("6. Unrealized Profit")
            print("7. Settings")
            print("8. Export Backup")
            print("9. Exit")

            choice = self._ask_menu_choice(
                "> ",
                1,
                9
            )

            if choice == 1:

                self.add_transaction()

            elif choice == 2:

                self.show_inventory()

            elif choice == 3:

                self.manage_transactions()

            elif choice == 4:

                self.show_profit()

            elif choice == 5:

                self.show_inventory_value()

            elif choice == 6:

                self.show_unrealized_profit()

            elif choice == 7:

                self.show_settings()

            elif choice == 8:

                self.export_backup()

            elif choice == 9:

                print("Goodbye.")
                break