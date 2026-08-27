import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QFrame,
    QPushButton,
    QButtonGroup,
    QStackedWidget,
    QComboBox,
    QSpinBox,
)
from PySide6.QtCore import Qt

from backend.trades import TradeService


SIDEBAR_SECTIONS = [
    "FAUSTUS",
    "STASH",
    "TRADES",
    "ANALYTICS",
    "SETTINGS",
]

# Overlay covers this fraction of the content area, centered,
# leaving a Hideout border visible around it.
OVERLAY_SIZE_RATIO = 0.90

# Temporary UI-level item list. This will be replaced by the
# downloaded asset catalog later; the combo box stays editable
# so a name outside this list can still be entered.
ITEM_CATALOG = [
    "Reflecting Mist",
    "Divine Orb",
    "Exalted Orb",
    "Scarab of Awakening",
    "Chaos Orb",
]


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()

        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def build_trade_card(trade, interactive, on_sell=None):

    card = QFrame()
    card.setObjectName("tradeCard")
    card.setFixedHeight(150 if interactive else 125)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)

    title = QLabel(trade.item_name)
    title.setObjectName("tradeTitle")
    layout.addWidget(title)

    progress = QLabel(
        f"Bought {trade.quantity_bought} · "
        f"Sold {trade.quantity_sold} · "
        f"Remaining {trade.remaining}"
    )
    progress.setObjectName("tradeInfo")
    layout.addWidget(progress)

    if trade.currency == "DIVINE":
        buy_price = QLabel(
            f"Buy: {trade.entered_price} Divine each "
            f"({trade.unit_price_chaos:,}c each)"
        )
    else:
        buy_price = QLabel(
            f"Buy: {trade.unit_price_chaos:,}c each"
        )

    buy_price.setObjectName("tradeInfo")
    layout.addWidget(buy_price)

    invested = QLabel(
        f"Invested: {trade.invested_chaos:,}c"
    )
    invested.setObjectName("tradeInfo")
    layout.addWidget(invested)

    if interactive:
        sell_button = QPushButton("SELL")
        sell_button.setObjectName("fauxTab")
        sell_button.clicked.connect(lambda: on_sell(trade))
        layout.addWidget(sell_button)

    return card


def build_empty_state(message):
    label = QLabel(message)
    label.setObjectName("overlayPlaceholder")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class GalaxyHideout(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Galaxy Hideout")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)

        self.trade_service = TradeService()

        self._build_ui()
        self.refresh_all()

    # =========================================================
    # UI CONSTRUCTION
    # =========================================================

    def _build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.content_area = ContentArea(
            overlay_ratio=OVERLAY_SIZE_RATIO
        )

        self.hideout = self._build_hideout()
        self.content_area.set_hideout(self.hideout)

        self.overlay = OverlayPanel(
            trade_service=self.trade_service,
            on_trade_changed=self.refresh_all,
            on_close=self._close_overlay
        )
        self.content_area.set_overlay(self.overlay)

        sidebar = self._build_sidebar()

        main_layout.addWidget(self.content_area)
        main_layout.addWidget(sidebar)

        self._apply_stylesheet()

    # =========================================================
    # HIDEOUT (permanent background / HUD)
    # =========================================================

    def _build_hideout(self):

        hideout = QFrame()
        hideout.setObjectName("hideout")

        layout = QVBoxLayout(hideout)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

        header_layout = QHBoxLayout()

        hideout_title = QLabel("GALAXY HIDEOUT")
        hideout_title.setObjectName("hideoutTitle")

        header_layout.addWidget(hideout_title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # -----------------------------------------------------
        # HUD SUMMARY
        # -----------------------------------------------------

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        self.hud_profit_box, self.hud_profit_value = (
            self._create_summary_box("TODAY'S PROFIT")
        )

        self.hud_trades_box, self.hud_trades_value = (
            self._create_summary_box("OPEN TRADES")
        )

        self.hud_stash_box, self.hud_stash_value = (
            self._create_summary_box("STASH")
        )

        summary_layout.addWidget(self.hud_profit_box)
        summary_layout.addWidget(self.hud_trades_box)
        summary_layout.addWidget(self.hud_stash_box)

        for index in range(3):
            summary_layout.setStretch(index, 1)

        layout.addLayout(summary_layout)

        # -----------------------------------------------------
        # LATEST OPEN TRADES (display-only, not clickable)
        # -----------------------------------------------------

        trades_title = QLabel("LATEST OPEN TRADES")
        trades_title.setObjectName("sectionTitle")

        layout.addWidget(trades_title)

        self.hideout_trades_grid = QGridLayout()
        self.hideout_trades_grid.setSpacing(12)

        layout.addLayout(self.hideout_trades_grid)

        # -----------------------------------------------------
        # RECENT ACTIVITY (last 5 BUY/SELL only)
        # -----------------------------------------------------

        activity_title = QLabel("RECENT ACTIVITY")
        activity_title.setObjectName("sectionTitle")

        layout.addWidget(activity_title)

        self.activity_label = QLabel("")
        self.activity_label.setObjectName("activity")

        layout.addWidget(self.activity_label)

        # Space reserved for future Hideout additions.
        layout.addStretch()

        # -----------------------------------------------------
        # DIVINE RATE CORNER
        # -----------------------------------------------------

        rate_layout = QHBoxLayout()
        rate_layout.addStretch()

        self.divine_rate_label = QLabel("")
        self.divine_rate_label.setObjectName("divineRateCorner")

        rate_layout.addWidget(self.divine_rate_label)

        layout.addLayout(rate_layout)

        return hideout

    def _create_summary_box(self, title):

        box = QFrame()
        box.setObjectName("summaryBox")

        layout = QVBoxLayout(box)
        layout.setContentsMargins(15, 12, 15, 12)

        title_label = QLabel(title)
        title_label.setObjectName("summaryTitle")

        value_label = QLabel("")
        value_label.setObjectName("summaryValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return box, value_label

    # =========================================================
    # STATE REFRESH
    # =========================================================

    def refresh_all(self):
        self.refresh_hideout()
        self.overlay.refresh()

    def refresh_hideout(self):
        service = self.trade_service

        self.hud_profit_value.setText(
            f"{service.today_profit():+,}c"
        )
        self.hud_trades_value.setText(
            str(service.open_trades_count())
        )
        self.hud_stash_value.setText(
            str(service.stash_count())
        )

        clear_layout(self.hideout_trades_grid)

        latest_trades = service.latest_open_trades(6)

        if not latest_trades:
            self.hideout_trades_grid.addWidget(
                build_empty_state("No open trades yet."),
                0, 0, 1, 3
            )
        else:
            for index, trade in enumerate(latest_trades):
                card = build_trade_card(trade, interactive=False)

                row = index // 3
                column = index % 3

                self.hideout_trades_grid.addWidget(card, row, column)

        activity = service.recent_activity(5)

        if not activity:
            self.activity_label.setText("No activity yet.")
        else:
            lines = []

            for entry in activity:
                line = (
                    f"{entry['type']:<5} "
                    f"{entry['item']} x{entry['quantity']}"
                    f"    {entry['total_chaos']:,}c"
                )

                if entry["profit"] is not None:
                    line += f"  ({entry['profit']:+,}c)"

                lines.append(line)

            self.activity_label.setText("\n".join(lines))

        self.divine_rate_label.setText(
            f"◈ {service.divine_rate}"
        )

    # =========================================================
    # SIDEBAR (only navigation mechanism)
    # =========================================================

    def _build_sidebar(self):

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("GALAXY\nHIDEOUT")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addSpacing(20)

        self.sidebar_group = QButtonGroup(self)
        self.sidebar_group.setExclusive(True)

        for section in SIDEBAR_SECTIONS:

            button = QPushButton(section)
            button.setObjectName("sidebarItem")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.clicked.connect(
                lambda checked, name=section: self._on_sidebar_clicked(name)
            )

            self.sidebar_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()

        return sidebar

    def _on_sidebar_clicked(self, section_name):

        if (
            self.overlay.isVisible()
            and self.overlay.current_section() == section_name
        ):
            self._close_overlay()
            return

        self._open_overlay(section_name)

    # =========================================================
    # OVERLAY CONTROL
    # =========================================================

    def _open_overlay(self, section_name):
        self.overlay.show_section(section_name)
        self.content_area.raise_overlay()

    def _close_overlay(self):
        self.overlay.hide()

        checked_button = self.sidebar_group.checkedButton()
        if checked_button is not None:
            self.sidebar_group.setExclusive(False)
            checked_button.setChecked(False)
            self.sidebar_group.setExclusive(True)

    # =========================================================
    # STYLE
    # =========================================================

    def _apply_stylesheet(self):

        self.setStyleSheet("""

            QMainWindow {
                background: #0b0b12;
            }

            #sidebar {
                background: #11111c;
                border: 1px solid #303044;
                border-radius: 8px;
            }

            #hideout {
                background: #11111c;
                border: 1px solid #303044;
                border-radius: 8px;
            }

            #title {
                font-size: 20px;
                font-weight: bold;
                color: #d8d8ff;
            }

            QLabel {
                color: #aaaac8;
                font-size: 14px;
            }

            #tradeCard {
                background: #181824;
                border: 1px solid #303044;
                border-radius: 6px;
            }

            #tradeTitle {
                color: #eeeeff;
                font-size: 14px;
                font-weight: bold;
            }

            #tradeInfo {
                color: #aaaac8;
                font-size: 12px;
            }

            #hideoutTitle {
                font-size: 26px;
                font-weight: bold;
                color: #eeeeff;
            }

            #sectionTitle {
                font-size: 18px;
                font-weight: bold;
                color: #d8d8ff;
                margin-top: 10px;
            }

            #summaryBox {
                background: #181824;
                border: 1px solid #303044;
                border-radius: 6px;
            }

            #summaryTitle {
                color: #8888a8;
                font-size: 12px;
                font-weight: bold;
            }

            #summaryValue {
                color: #eeeeff;
                font-size: 22px;
                font-weight: bold;
            }

            #activity {
                background: #181824;
                border: 1px solid #303044;
                border-radius: 6px;
                padding: 12px;
                color: #aaaac8;
                font-size: 13px;
            }

            #divineRateCorner {
                color: #8888a8;
                font-size: 12px;
                font-weight: bold;
            }

            QPushButton#sidebarItem {
                color: #aaaac8;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                text-align: left;
            }

            QPushButton#sidebarItem:hover {
                color: #eeeeff;
                background: #181824;
                border: 1px solid #303044;
            }

            QPushButton#sidebarItem:checked {
                color: #eeeeff;
                background: #22223a;
                border: 1px solid #4a4a72;
            }

            #overlayPanel {
                background: #14141f;
                border: 1px solid #4a4a72;
                border-radius: 10px;
            }

            #overlayTitle {
                font-size: 18px;
                font-weight: bold;
                color: #eeeeff;
            }

            QPushButton#overlayCloseButton {
                color: #aaaac8;
                background: #181824;
                border: 1px solid #303044;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 12px;
            }

            QPushButton#overlayCloseButton:hover {
                color: #eeeeff;
                border: 1px solid #4a4a72;
            }

            #overlayPlaceholder {
                color: #8888a8;
                font-size: 15px;
            }

            QPushButton#fauxTab {
                color: #aaaac8;
                background: #181824;
                border: 1px solid #303044;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 20px;
            }

            QPushButton#fauxTab:checked {
                color: #eeeeff;
                background: #22223a;
                border: 1px solid #4a4a72;
            }

            QPushButton#fauxTab:disabled {
                color: #555570;
            }

            QPushButton#primaryButton {
                color: #0b0b12;
                background: #a8a8ff;
                border: 1px solid #a8a8ff;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }

            QPushButton#primaryButton:hover {
                background: #c0c0ff;
            }

            QPushButton#secondaryButton {
                color: #aaaac8;
                background: transparent;
                border: 1px solid #303044;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }

            QPushButton#secondaryButton:hover {
                color: #eeeeff;
                border: 1px solid #4a4a72;
            }

            #formLabel {
                color: #8888a8;
                font-size: 12px;
                font-weight: bold;
            }

            #confirmSummary {
                background: #181824;
                border: 1px solid #303044;
                border-radius: 6px;
                padding: 15px;
                color: #eeeeff;
                font-size: 13px;
            }

            QComboBox, QSpinBox {
                color: #eeeeff;
                background: #181824;
                border: 1px solid #303044;
                border-radius: 5px;
                padding: 6px;
                font-size: 13px;
            }

        """)


# =============================================================
# CONTENT AREA
# =============================================================
# Hosts the permanent Hideout background plus a single overlay
# panel that floats above it. The overlay is a plain child
# widget (outside the layout) so it can be sized/positioned
# independently and re-centered on resize.
# =============================================================

class ContentArea(QWidget):

    def __init__(self, overlay_ratio, parent=None):
        super().__init__(parent)

        self._overlay_ratio = overlay_ratio
        self._overlay = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def set_hideout(self, hideout_widget):
        self._layout.addWidget(hideout_widget)

    def set_overlay(self, overlay_widget):
        self._overlay = overlay_widget
        self._overlay.setParent(self)
        self._overlay.hide()

    def raise_overlay(self):
        if self._overlay is not None:
            self._position_overlay()
            self._overlay.show()
            self._overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self._overlay is not None and self._overlay.isVisible():
            self._position_overlay()

    def _position_overlay(self):
        width = int(self.width() * self._overlay_ratio)
        height = int(self.height() * self._overlay_ratio)

        x = (self.width() - width) // 2
        y = (self.height() - height) // 2

        self._overlay.setGeometry(x, y, width, height)


# =============================================================
# OVERLAY PANEL
# =============================================================

class OverlayPanel(QFrame):

    def __init__(self, trade_service, on_trade_changed, on_close, parent=None):
        super().__init__(parent)

        self.setObjectName("overlayPanel")

        self._on_close = on_close
        self._current_section = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(15)

        title_bar = QHBoxLayout()

        self.title_label = QLabel("")
        self.title_label.setObjectName("overlayTitle")
        title_bar.addWidget(self.title_label)

        title_bar.addStretch()

        close_button = QPushButton("CLOSE")
        close_button.setObjectName("overlayCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self._handle_close)

        title_bar.addWidget(close_button)

        layout.addLayout(title_bar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self._pages = {}

        self.faustus_page = FaustusPage(trade_service, on_trade_changed)
        self._pages["FAUSTUS"] = self.faustus_page
        self.stack.addWidget(self.faustus_page)

        self.stash_page = StashPage(trade_service)
        self._pages["STASH"] = self.stash_page
        self.stack.addWidget(self.stash_page)

        for section in SIDEBAR_SECTIONS:
            if section in ("FAUSTUS", "STASH"):
                continue

            page = self._build_placeholder_page(section)
            self._pages[section] = page
            self.stack.addWidget(page)

    def current_section(self):
        return self._current_section

    def show_section(self, section_name):
        self._current_section = section_name
        self.title_label.setText(section_name)
        self.stack.setCurrentWidget(self._pages[section_name])

    def refresh(self):
        self.faustus_page.refresh()
        self.stash_page.refresh()

    def _handle_close(self):
        self._on_close()

    def hide(self):
        self._current_section = None
        super().hide()

    def _build_placeholder_page(self, section_name):

        page = QWidget()
        layout = QVBoxLayout(page)

        label = QLabel(f"{section_name} — coming soon")
        label.setObjectName("overlayPlaceholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)

        return page


# =============================================================
# FAUSTUS PAGE — active trading desk
# =============================================================

class FaustusPage(QWidget):

    def __init__(self, trade_service, on_trade_changed, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service
        self.on_trade_changed = on_trade_changed

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # -----------------------------------------------------
        # BUY | SELL TABS
        # -----------------------------------------------------

        tab_layout = QHBoxLayout()

        self.buy_tab = QPushButton("BUY")
        self.buy_tab.setObjectName("fauxTab")
        self.buy_tab.setCheckable(True)
        self.buy_tab.setChecked(True)

        self.sell_tab = QPushButton("SELL")
        self.sell_tab.setObjectName("fauxTab")
        self.sell_tab.setCheckable(True)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_group.addButton(self.buy_tab)
        self.tab_group.addButton(self.sell_tab)

        self.buy_tab.clicked.connect(self._show_buy_tab)
        self.sell_tab.clicked.connect(self._show_sell_tab)

        tab_layout.addWidget(self.buy_tab)
        tab_layout.addWidget(self.sell_tab)
        tab_layout.addStretch()

        layout.addLayout(tab_layout)

        # Workflow area: switches between BUY and SELL/CLOSE TRADE
        # sub-steps. The open trades grid below is shared by both
        # tabs (Faustus shows all open trades regardless of which
        # workflow is active).
        self.top_stack = QStackedWidget()
        layout.addWidget(self.top_stack)

        self.top_stack.addWidget(self._build_buy_form())      # 0
        self.top_stack.addWidget(self._build_buy_confirm())   # 1
        self.top_stack.addWidget(
            build_empty_state(
                "Pick an open trade below and click SELL to close it."
            )
        )                                                     # 2
        self.top_stack.addWidget(self._build_close_form())    # 3
        self.top_stack.addWidget(self._build_close_confirm()) # 4

        self._active_trade = None

        trades_title = QLabel("OPEN TRADES")
        trades_title.setObjectName("sectionTitle")
        layout.addWidget(trades_title)

        self.trades_grid = QGridLayout()
        self.trades_grid.setSpacing(12)
        layout.addLayout(self.trades_grid)

        layout.addStretch()

    def _show_buy_tab(self):
        self.top_stack.setCurrentIndex(0)

    def _show_sell_tab(self):
        self._active_trade = None
        self.top_stack.setCurrentIndex(2)

    # -----------------------------------------------------
    # BUY WORKFLOW
    # -----------------------------------------------------

    def _build_buy_form(self):

        form_page = QWidget()
        outer = QVBoxLayout(form_page)

        form = QFormLayout()
        form.setSpacing(10)

        self.item_input = QComboBox()
        self.item_input.setEditable(True)
        self.item_input.addItems(ITEM_CATALOG)

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 100_000)
        self.quantity_input.setValue(1)

        self.currency_input = QComboBox()
        self.currency_input.addItems(["CHAOS", "DIVINE"])

        self.price_input = QSpinBox()
        self.price_input.setRange(1, 10_000_000)
        self.price_input.setValue(1)

        self.gold_input = QSpinBox()
        self.gold_input.setRange(0, 100_000_000)
        self.gold_input.setValue(0)

        form.addRow("Item", self.item_input)
        form.addRow("Quantity", self.quantity_input)
        form.addRow("Currency", self.currency_input)
        form.addRow("Price per item", self.price_input)
        form.addRow("Gold spent", self.gold_input)

        outer.addLayout(form)

        review_button = QPushButton("REVIEW BUY")
        review_button.setObjectName("primaryButton")
        review_button.clicked.connect(self._show_buy_confirm)

        outer.addWidget(review_button)

        return form_page

    def _build_buy_confirm(self):

        confirm_page = QWidget()
        layout = QVBoxLayout(confirm_page)
        layout.setSpacing(15)

        self.confirm_summary = QLabel("")
        self.confirm_summary.setObjectName("confirmSummary")
        layout.addWidget(self.confirm_summary)

        button_row = QHBoxLayout()

        cancel_button = QPushButton("CANCEL")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self._cancel_buy)

        confirm_button = QPushButton("CONFIRM")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self._confirm_buy)

        button_row.addWidget(cancel_button)
        button_row.addWidget(confirm_button)

        layout.addLayout(button_row)
        layout.addStretch()

        return confirm_page

    def _show_buy_confirm(self):

        item_name = self.item_input.currentText().strip()

        if not item_name:
            return

        quantity = self.quantity_input.value()
        currency = self.currency_input.currentText()
        price = self.price_input.value()
        gold = self.gold_input.value()

        if currency == "DIVINE":
            unit_chaos = self.trade_service.divine_to_chaos(price)
            price_line = (
                f"Price: {price} Divine each "
                f"({unit_chaos:,}c each)"
            )
        else:
            unit_chaos = price
            price_line = f"Price: {price:,}c each"

        total_chaos = unit_chaos * quantity

        lines = [
            "Transaction information",
            "-----------------------",
            f"Item: {item_name}",
            "Type: BUY",
            f"Quantity: {quantity}",
            price_line,
            f"Total: {total_chaos:,}c",
            f"Gold spent: {gold:,}",
        ]

        self.confirm_summary.setText("\n".join(lines))
        self.top_stack.setCurrentIndex(1)

    def _cancel_buy(self):
        self.top_stack.setCurrentIndex(0)

    def _confirm_buy(self):

        item_name = self.item_input.currentText().strip()
        quantity = self.quantity_input.value()
        currency = self.currency_input.currentText()
        price = self.price_input.value()
        gold = self.gold_input.value()

        self.trade_service.open_trade(
            item_name=item_name,
            quantity=quantity,
            currency=currency,
            entered_price=price,
            gold_spent=gold
        )

        self._reset_buy_form()
        self.top_stack.setCurrentIndex(0)

        self.on_trade_changed()

    def _reset_buy_form(self):
        self.item_input.setCurrentIndex(0)
        self.quantity_input.setValue(1)
        self.currency_input.setCurrentIndex(0)
        self.price_input.setValue(1)
        self.gold_input.setValue(0)

    # -----------------------------------------------------
    # SELL / CLOSE TRADE WORKFLOW
    # -----------------------------------------------------

    def _build_close_form(self):

        form_page = QWidget()
        outer = QVBoxLayout(form_page)

        self.close_trade_title = QLabel("")
        self.close_trade_title.setObjectName("sectionTitle")
        outer.addWidget(self.close_trade_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.sell_quantity_input = QSpinBox()
        self.sell_quantity_input.setRange(1, 1)

        self.sell_currency_input = QComboBox()
        self.sell_currency_input.addItems(["CHAOS", "DIVINE"])

        self.sell_price_input = QSpinBox()
        self.sell_price_input.setRange(1, 10_000_000)
        self.sell_price_input.setValue(1)

        self.sell_gold_input = QSpinBox()
        self.sell_gold_input.setRange(0, 100_000_000)
        self.sell_gold_input.setValue(0)

        form.addRow("Quantity", self.sell_quantity_input)
        form.addRow("Currency", self.sell_currency_input)
        form.addRow("Price per item", self.sell_price_input)
        form.addRow("Gold received", self.sell_gold_input)

        outer.addLayout(form)

        review_button = QPushButton("REVIEW SELL")
        review_button.setObjectName("primaryButton")
        review_button.clicked.connect(self._show_sell_confirm)

        outer.addWidget(review_button)

        return form_page

    def _build_close_confirm(self):

        confirm_page = QWidget()
        layout = QVBoxLayout(confirm_page)
        layout.setSpacing(15)

        self.close_confirm_summary = QLabel("")
        self.close_confirm_summary.setObjectName("confirmSummary")
        layout.addWidget(self.close_confirm_summary)

        button_row = QHBoxLayout()

        cancel_button = QPushButton("CANCEL")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self._cancel_sell)

        confirm_button = QPushButton("CONFIRM")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self._confirm_sell)

        button_row.addWidget(cancel_button)
        button_row.addWidget(confirm_button)

        layout.addLayout(button_row)
        layout.addStretch()

        return confirm_page

    def _start_close_trade(self, trade):
        self._active_trade = trade

        self.close_trade_title.setText(
            f"Selling: {trade.item_name} "
            f"(remaining {trade.remaining})"
        )

        self.sell_quantity_input.setRange(1, trade.remaining)
        self.sell_quantity_input.setValue(trade.remaining)
        self.sell_currency_input.setCurrentIndex(0)
        self.sell_price_input.setValue(1)
        self.sell_gold_input.setValue(0)

        self.sell_tab.setChecked(True)
        self.top_stack.setCurrentIndex(3)

    def _show_sell_confirm(self):

        trade = self._active_trade

        if trade is None:
            return

        quantity = self.sell_quantity_input.value()
        currency = self.sell_currency_input.currentText()
        price = self.sell_price_input.value()
        gold = self.sell_gold_input.value()

        if currency == "DIVINE":
            unit_chaos = self.trade_service.divine_to_chaos(price)
            price_line = (
                f"Price: {price} Divine each "
                f"({unit_chaos:,}c each)"
            )
        else:
            unit_chaos = price
            price_line = f"Price: {price:,}c each"

        total_chaos = unit_chaos * quantity
        cost_chaos = trade.unit_price_chaos * quantity
        profit = total_chaos - cost_chaos

        lines = [
            "Transaction information",
            "-----------------------",
            f"Item: {trade.item_name}",
            "Type: SELL",
            f"Quantity: {quantity}",
            price_line,
            f"Total: {total_chaos:,}c",
            f"Cost basis: {cost_chaos:,}c",
            f"Profit: {profit:+,}c",
            f"Gold received: {gold:,}",
        ]

        self.close_confirm_summary.setText("\n".join(lines))
        self.top_stack.setCurrentIndex(4)

    def _cancel_sell(self):
        self.top_stack.setCurrentIndex(3)

    def _confirm_sell(self):

        trade = self._active_trade

        if trade is None:
            return

        quantity = self.sell_quantity_input.value()
        currency = self.sell_currency_input.currentText()
        price = self.sell_price_input.value()
        gold = self.sell_gold_input.value()

        self.trade_service.sell_from_trade(
            trade_id=trade.id,
            quantity=quantity,
            currency=currency,
            entered_price=price,
            gold_received=gold
        )

        self._active_trade = None
        self.top_stack.setCurrentIndex(2)

        self.on_trade_changed()

    # -----------------------------------------------------
    # REFRESH
    # -----------------------------------------------------

    def refresh(self):
        clear_layout(self.trades_grid)

        open_trades = self.trade_service.open_trades()

        if not open_trades:
            self.trades_grid.addWidget(
                build_empty_state(
                    "No open trades yet. Use BUY to open one."
                ),
                0, 0, 1, 3
            )
            return

        for index, trade in enumerate(open_trades):
            card = build_trade_card(
                trade,
                interactive=True,
                on_sell=self._start_close_trade
            )

            row = index // 3
            column = index % 3

            self.trades_grid.addWidget(card, row, column)


# =============================================================
# STASH PAGE — read-only current inventory
# =============================================================

class StashPage(QWidget):

    def __init__(self, trade_service, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        layout.addLayout(self.grid)

        layout.addStretch()

    def refresh(self):
        clear_layout(self.grid)

        summary = self.trade_service.stash_summary()

        if not summary:
            self.grid.addWidget(
                build_empty_state("Stash is empty."),
                0, 0, 1, 3
            )
            return

        headers = ["ITEM", "QUANTITY", "COST BASIS"]

        for column, text in enumerate(headers):
            header_label = QLabel(text)
            header_label.setObjectName("formLabel")
            self.grid.addWidget(header_label, 0, column)

        total_quantity = 0
        total_cost = 0

        row = 1

        for entry in summary:
            item_label = QLabel(entry["item_name"])
            item_label.setObjectName("tradeTitle")

            quantity_label = QLabel(str(entry["quantity"]))
            quantity_label.setObjectName("tradeInfo")

            cost_label = QLabel(f"{entry['cost_chaos']:,}c")
            cost_label.setObjectName("tradeInfo")

            self.grid.addWidget(item_label, row, 0)
            self.grid.addWidget(quantity_label, row, 1)
            self.grid.addWidget(cost_label, row, 2)

            total_quantity += entry["quantity"]
            total_cost += entry["cost_chaos"]

            row += 1

        total_item_label = QLabel("TOTAL")
        total_item_label.setObjectName("formLabel")

        total_quantity_label = QLabel(str(total_quantity))
        total_quantity_label.setObjectName("formLabel")

        total_cost_label = QLabel(f"{total_cost:,}c")
        total_cost_label.setObjectName("formLabel")

        self.grid.addWidget(total_item_label, row, 0)
        self.grid.addWidget(total_quantity_label, row, 1)
        self.grid.addWidget(total_cost_label, row, 2)


def main():

    app = QApplication(sys.argv)

    window = GalaxyHideout()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
