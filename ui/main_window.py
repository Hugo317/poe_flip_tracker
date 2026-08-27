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
    QLineEdit,
    QScrollArea,
    QDialog,
    QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from backend.trades import TradeService
from backend.assets_service import AssetService


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


def build_summary_box(title):

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
        self.asset_service = AssetService(session=self.trade_service.session)

        # Catalog refresh at startup (directive Q34) — also gives us
        # the live Divine rate for free, or None if unreachable, in
        # which case we simply carry on with whatever's cached
        # (directive Q28/36.9: never require internet for core use).
        self.live_divine_rate = self.asset_service.refresh_catalog(
            self.trade_service.league.name
        )

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
            asset_service=self.asset_service,
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
            build_summary_box("TODAY'S PROFIT")
        )

        self.hud_trades_box, self.hud_trades_value = (
            build_summary_box("OPEN TRADES")
        )

        self.hud_stash_box, self.hud_stash_value = (
            build_summary_box("STASH")
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

            QPushButton#transactionRow {
                color: #aaaac8;
                background: transparent;
                border: none;
                text-align: left;
                font-size: 13px;
                font-family: monospace;
            }

            QPushButton#transactionRow:hover {
                color: #eeeeff;
            }

            #tradesScroll {
                background: transparent;
                border: none;
            }

            QComboBox, QSpinBox, QLineEdit {
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

    def __init__(
        self,
        trade_service,
        asset_service,
        on_trade_changed,
        on_close,
        parent=None
    ):
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

        self.faustus_page = FaustusPage(
            trade_service, asset_service, on_trade_changed
        )
        self._pages["FAUSTUS"] = self.faustus_page
        self.stack.addWidget(self.faustus_page)

        self.stash_page = StashPage(trade_service)
        self._pages["STASH"] = self.stash_page
        self.stack.addWidget(self.stash_page)

        self.trades_page = TradesPage(trade_service)
        self._pages["TRADES"] = self.trades_page
        self.stack.addWidget(self.trades_page)

        self.analytics_page = AnalyticsPage(trade_service)
        self._pages["ANALYTICS"] = self.analytics_page
        self.stack.addWidget(self.analytics_page)

        self.settings_page = SettingsPage(trade_service, on_trade_changed)
        self._pages["SETTINGS"] = self.settings_page
        self.stack.addWidget(self.settings_page)

        for section in SIDEBAR_SECTIONS:
            if section in (
                "FAUSTUS", "STASH", "TRADES", "ANALYTICS", "SETTINGS"
            ):
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
        self.trades_page.refresh()
        self.analytics_page.refresh()
        self.settings_page.refresh()

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

    def __init__(self, trade_service, asset_service, on_trade_changed, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service
        self.asset_service = asset_service
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
        self._populate_item_input()

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

    def _populate_item_input(self):
        # Sourced entirely from the live poe.ninja catalog (Hugo's
        # call) — no free-text/custom entries, so item_input is a
        # picker, not an editable combo box.
        for asset in self.asset_service.active_assets():
            icon_path = self.asset_service.icon_file_path(asset)
            icon = QIcon(QPixmap(str(icon_path))) if icon_path else QIcon()

            self.item_input.addItem(icon, asset.name, userData=asset.id)

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

        asset_id = self.item_input.currentData()

        if asset_id is None:
            return

        item_name = self.item_input.currentText()
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

        asset_id = self.item_input.currentData()

        if asset_id is None:
            return

        item_name = self.item_input.currentText()
        quantity = self.quantity_input.value()
        currency = self.currency_input.currentText()
        price = self.price_input.value()
        gold = self.gold_input.value()

        self.trade_service.open_trade(
            item_name=item_name,
            quantity=quantity,
            currency=currency,
            entered_price=price,
            gold_spent=gold,
            asset_id=asset_id
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


# =============================================================
# TRADES PAGE — complete historical BUY/SELL activity
# =============================================================

class TransactionRow(QFrame):

    def __init__(self, transaction, parent=None):
        super().__init__(parent)

        self.setObjectName("tradeCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.toggle_button = QPushButton(self._summary_text(transaction))
        self.toggle_button.setObjectName("transactionRow")
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_button)

        self.detail_label = QLabel(self._detail_text(transaction))
        self.detail_label.setObjectName("tradeInfo")
        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

    def _toggle(self):
        self.detail_label.setVisible(not self.detail_label.isVisible())

    @staticmethod
    def _summary_text(transaction):
        profit_part = (
            f"  ({transaction['profit']:+,}c)"
            if transaction["profit"] is not None
            else ""
        )

        return (
            f"{transaction['type']:<5} "
            f"{transaction['item']} x{transaction['quantity']}    "
            f"{transaction['total_chaos']:,}c{profit_part}    "
            f"{transaction['timestamp']}"
        )

    @staticmethod
    def _detail_text(transaction):
        lines = [f"Currency: {transaction['currency']}"]

        if transaction["currency"] == "DIVINE":
            lines.append(
                f"Price: {transaction['entered_price']} Divine each "
                f"({transaction['unit_price_chaos']:,}c each)"
            )
        else:
            lines.append(
                f"Price: {transaction['unit_price_chaos']:,}c each"
            )

        if transaction["type"] == "SELL":
            lines.append(f"Cost basis: {transaction['cost_chaos']:,}c")
            lines.append(f"Profit: {transaction['profit']:+,}c")
            lines.append(f"Gold received: {transaction['gold']:,}")
        else:
            lines.append(f"Gold spent: {transaction['gold']:,}")

        lines.append(f"Trade #{transaction['trade_id']}")

        return "\n".join(lines)


class TradesPage(QWidget):

    def __init__(self, trade_service, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        filters_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search item...")
        self.search_input.textChanged.connect(self.refresh)

        self.type_filter = QComboBox()
        self.type_filter.addItems(["ALL", "BUY", "SELL"])
        self.type_filter.currentTextChanged.connect(self.refresh)

        filters_layout.addWidget(self.search_input)
        filters_layout.addWidget(self.type_filter)

        layout.addLayout(filters_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("tradesScroll")

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setSpacing(8)

        scroll_area.setWidget(self.rows_container)

        layout.addWidget(scroll_area)

    def refresh(self):
        clear_layout(self.rows_layout)

        query = self.search_input.text().strip().lower()
        type_filter = self.type_filter.currentText()

        transactions = [
            transaction
            for transaction in self.trade_service.all_transactions()
            if (
                type_filter == "ALL"
                or transaction["type"] == type_filter
            )
            and query in transaction["item"].lower()
        ]

        if not transactions:
            self.rows_layout.addWidget(
                build_empty_state("No transactions match.")
            )
        else:
            for transaction in transactions:
                self.rows_layout.addWidget(
                    TransactionRow(transaction)
                )

        self.rows_layout.addStretch()


# =============================================================
# ANALYTICS PAGE — deep statistics for the current Trading Day
# =============================================================
# Time-period selection and Trading Day history are structurally
# present but only ever show "Today" / empty for now: without real
# persistence (later build step), there is no previous Trading Day to
# select or look back on yet. No fake data is shown in the meantime.
# =============================================================

class AnalyticsPage(QWidget):

    def __init__(self, trade_service, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service

        outer_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("tradesScroll")

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(20)

        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

        # ---------------------------------------------------------
        # SUMMARY ROW
        # ---------------------------------------------------------

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        self.profit_box, self.profit_value = build_summary_box("PROFIT")
        self.roi_box, self.roi_value = build_summary_box("ROI")
        self.volume_box, self.volume_value = (
            build_summary_box("TRADING VOLUME")
        )
        self.tx_box, self.tx_value = build_summary_box("TRANSACTIONS")

        for box in (
            self.profit_box, self.roi_box, self.volume_box, self.tx_box
        ):
            summary_layout.addWidget(box)

        self.content_layout.addLayout(summary_layout)

        # ---------------------------------------------------------
        # NEW TRADES VS CARRY-OVER SALES
        # ---------------------------------------------------------

        new_vs_carryover_title = QLabel("NEW TRADES VS CARRY-OVER SALES")
        new_vs_carryover_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(new_vs_carryover_title)

        self.new_vs_carryover_label = QLabel("")
        self.new_vs_carryover_label.setObjectName("activity")
        self.content_layout.addWidget(self.new_vs_carryover_label)

        # ---------------------------------------------------------
        # ITEM PERFORMANCE
        # ---------------------------------------------------------

        item_performance_title = QLabel("ITEM PERFORMANCE (TODAY)")
        item_performance_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(item_performance_title)

        self.item_performance_grid = QGridLayout()
        self.item_performance_grid.setSpacing(10)
        self.content_layout.addLayout(self.item_performance_grid)

        # ---------------------------------------------------------
        # GOLD / AVERAGES
        # ---------------------------------------------------------

        gold_averages_title = QLabel("GOLD & AVERAGES")
        gold_averages_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(gold_averages_title)

        self.gold_averages_label = QLabel("")
        self.gold_averages_label.setObjectName("activity")
        self.content_layout.addWidget(self.gold_averages_label)

        # ---------------------------------------------------------
        # TRADING DAY HISTORY
        # ---------------------------------------------------------

        history_title = QLabel("TRADING DAY HISTORY")
        history_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(history_title)

        self.history_label = build_empty_state(
            "No previous Trading Days yet."
        )
        self.content_layout.addWidget(self.history_label)

        self.content_layout.addStretch()

    def refresh(self):
        summary = self.trade_service.analytics_summary()

        self.profit_value.setText(f"{summary['today_profit']:+,}c")
        self.roi_value.setText(f"{summary['roi'] * 100:+.1f}%")
        self.volume_value.setText(
            f"{summary['trading_volume_chaos']:,}c"
        )
        self.tx_value.setText(str(summary["transaction_count_today"]))

        self.new_vs_carryover_label.setText(
            f"New Trade Sales:   {summary['new_trade_sales_count']}"
            f"    ({summary['new_trade_sales_profit']:+,}c)\n"
            f"Carry-over Sales:  {summary['carryover_sales_count']}"
            f"    ({summary['carryover_sales_profit']:+,}c)"
        )

        clear_layout(self.item_performance_grid)

        if not summary["item_performance"]:
            self.item_performance_grid.addWidget(
                build_empty_state("No sales yet today."),
                0, 0, 1, 4
            )
        else:
            headers = ["ITEM", "QTY SOLD", "REVENUE", "PROFIT"]

            for column, text in enumerate(headers):
                header_label = QLabel(text)
                header_label.setObjectName("formLabel")
                self.item_performance_grid.addWidget(
                    header_label, 0, column
                )

            for row, entry in enumerate(
                summary["item_performance"], start=1
            ):
                item_label = QLabel(entry["item_name"])
                item_label.setObjectName("tradeTitle")

                quantity_label = QLabel(str(entry["quantity_sold"]))
                quantity_label.setObjectName("tradeInfo")

                revenue_label = QLabel(f"{entry['revenue']:,}c")
                revenue_label.setObjectName("tradeInfo")

                profit_label = QLabel(f"{entry['profit']:+,}c")
                profit_label.setObjectName("tradeInfo")

                self.item_performance_grid.addWidget(item_label, row, 0)
                self.item_performance_grid.addWidget(
                    quantity_label, row, 1
                )
                self.item_performance_grid.addWidget(
                    revenue_label, row, 2
                )
                self.item_performance_grid.addWidget(
                    profit_label, row, 3
                )

        self.gold_averages_label.setText(
            f"Gold spent today:      {summary['gold_spent_today']:,}\n"
            f"Gold received today:   {summary['gold_received_today']:,}\n"
            f"Completed trades today: "
            f"{summary['completed_trades_today']}\n"
            f"Average profit/trade:  "
            f"{summary['average_profit_per_trade']:+,.0f}c\n"
            f"Total realized profit (lifetime): "
            f"{summary['total_realized_profit']:+,}c"
        )


# =============================================================
# SETTINGS PAGE
# =============================================================
# General and Rates are real and functional. Assets/Cache Management
# and Appearance are honest placeholders: there is no asset/cache
# system yet (a later build step), and styling is deferred by Hugo's
# own call until the app is functionally complete — showing fake
# controls for either would be dishonest UI.
# =============================================================

class SettingsPage(QWidget):

    def __init__(self, trade_service, on_settings_changed, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service
        self.on_settings_changed = on_settings_changed

        outer_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("tradesScroll")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)

        content_layout.addWidget(self._build_general_section())
        content_layout.addWidget(self._build_trading_day_section())
        content_layout.addWidget(self._build_rates_section())
        content_layout.addWidget(self._build_assets_section())
        content_layout.addWidget(self._build_appearance_section())
        content_layout.addStretch()

        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)

    # -----------------------------------------------------
    # GENERAL
    # -----------------------------------------------------

    def _build_general_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("GENERAL")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.volume_input = QSpinBox()
        self.volume_input.setRange(0, 100)
        self.volume_input.setValue(self.trade_service.sound_master_volume)
        self.volume_input.valueChanged.connect(
            self.trade_service.set_sound_master_volume
        )
        form.addRow("Master volume", self.volume_input)

        self.tink_checkbox = QCheckBox("Enable TINK (profit sound)")
        self.tink_checkbox.setChecked(
            self.trade_service.sound_tink_enabled
        )
        self.tink_checkbox.toggled.connect(
            self.trade_service.set_sound_tink_enabled
        )
        form.addRow("", self.tink_checkbox)

        self.warnings_checkbox = QCheckBox("Enable warning sound")
        self.warnings_checkbox.setChecked(
            self.trade_service.sound_warnings_enabled
        )
        self.warnings_checkbox.toggled.connect(
            self.trade_service.set_sound_warnings_enabled
        )
        form.addRow("", self.warnings_checkbox)

        layout.addLayout(form)

        note = QLabel(
            "Sound playback isn't implemented yet — these "
            "preferences are saved for when it is."
        )
        note.setObjectName("tradeInfo")
        layout.addWidget(note)

        return section

    # -----------------------------------------------------
    # TRADING DAY
    # -----------------------------------------------------

    def _build_trading_day_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("TRADING DAY")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.trading_day_label = QLabel("")
        self.trading_day_label.setObjectName("tradeInfo")
        layout.addWidget(self.trading_day_label)

        start_new_day_button = QPushButton("START NEW TRADING DAY")
        start_new_day_button.setObjectName("primaryButton")
        start_new_day_button.clicked.connect(
            self._start_new_trading_day
        )
        layout.addWidget(start_new_day_button)

        note = QLabel(
            "Resets Today's Profit tracking going forward. Does not "
            "affect lifetime totals or past trades."
        )
        note.setObjectName("tradeInfo")
        layout.addWidget(note)

        return section

    def _start_new_trading_day(self):
        self.trade_service.start_new_trading_day()
        self.refresh()
        self.on_settings_changed()

    # -----------------------------------------------------
    # RATES
    # -----------------------------------------------------

    def _build_rates_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("RATES")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.divine_current_label = QLabel("")
        self.divine_current_label.setObjectName("tradeInfo")
        layout.addWidget(self.divine_current_label)

        divine_row = QHBoxLayout()

        self.divine_rate_input = QSpinBox()
        self.divine_rate_input.setRange(1, 10_000_000)

        update_divine_button = QPushButton("UPDATE")
        update_divine_button.setObjectName("secondaryButton")
        update_divine_button.clicked.connect(self._update_divine_rate)

        divine_row.addWidget(QLabel("1 Divine ="))
        divine_row.addWidget(self.divine_rate_input)
        divine_row.addWidget(QLabel("Chaos"))
        divine_row.addWidget(update_divine_button)

        layout.addLayout(divine_row)

        self.gold_current_label = QLabel("")
        self.gold_current_label.setObjectName("tradeInfo")
        layout.addWidget(self.gold_current_label)

        gold_row = QHBoxLayout()

        self.gold_amount_input = QSpinBox()
        self.gold_amount_input.setRange(1, 100_000_000)

        self.gold_chaos_input = QSpinBox()
        self.gold_chaos_input.setRange(1, 10_000_000)

        update_gold_button = QPushButton("UPDATE")
        update_gold_button.setObjectName("secondaryButton")
        update_gold_button.clicked.connect(self._update_gold_rate)

        gold_row.addWidget(self.gold_amount_input)
        gold_row.addWidget(QLabel("Gold ="))
        gold_row.addWidget(self.gold_chaos_input)
        gold_row.addWidget(QLabel("Chaos"))
        gold_row.addWidget(update_gold_button)

        layout.addLayout(gold_row)

        note = QLabel(
            "Changing a rate does not affect past transactions — "
            "each transaction keeps the rate that was active when "
            "it was made."
        )
        note.setObjectName("tradeInfo")
        layout.addWidget(note)

        return section

    def _update_divine_rate(self):
        self.trade_service.set_divine_rate(self.divine_rate_input.value())
        self.refresh()
        self.on_settings_changed()

    def _update_gold_rate(self):
        self.trade_service.set_gold_rate(
            self.gold_amount_input.value(),
            self.gold_chaos_input.value()
        )
        self.refresh()
        self.on_settings_changed()

    # -----------------------------------------------------
    # ASSETS / CACHE MANAGEMENT
    # -----------------------------------------------------

    def _build_assets_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("ASSETS / CACHE MANAGEMENT")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        layout.addWidget(
            build_empty_state(
                "Not built yet — the asset/cache system is a "
                "later build step."
            )
        )

        return section

    # -----------------------------------------------------
    # APPEARANCE
    # -----------------------------------------------------

    def _build_appearance_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("APPEARANCE")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        layout.addWidget(
            build_empty_state(
                "Styling is intentionally deferred until the app "
                "is fully functional."
            )
        )

        return section

    # -----------------------------------------------------
    # REFRESH
    # -----------------------------------------------------

    def refresh(self):
        self.trading_day_label.setText(
            f"Current Trading Day started: "
            f"{self.trade_service.trading_day.started_at}"
        )

        self.divine_current_label.setText(
            f"Current: 1 Divine = {self.trade_service.divine_rate}c"
        )
        self.divine_rate_input.setValue(self.trade_service.divine_rate)

        self.gold_current_label.setText(
            f"Current: "
            f"{self.trade_service.gold_rate_gold_amount:,} Gold = "
            f"{self.trade_service.gold_rate_chaos_value}c"
        )
        self.gold_amount_input.setValue(
            self.trade_service.gold_rate_gold_amount
        )
        self.gold_chaos_input.setValue(
            self.trade_service.gold_rate_chaos_value
        )


# =============================================================
# STARTUP — mandatory Divine Rate prompt
# =============================================================
# Per the locked startup flow, the Divine rate is asked at launch and
# is mandatory to answer (no skip). The NEW DAY / CONTINUE step is
# intentionally omitted for now: with no persistence yet, a Trading
# Day never actually carries over between launches, so there is
# nothing real to "continue" to. That step belongs here once real
# persistence exists.
# =============================================================

class StartupDialog(QDialog):

    def __init__(self, default_rate, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Divine Rate")
        self.setModal(True)
        self._confirmed = False
        self.chosen_rate = default_rate

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        title = QLabel("DIVINE RATE")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        instructions = QLabel("1 Divine = [ ___ ] Chaos")
        layout.addWidget(instructions)

        self.rate_input = QSpinBox()
        self.rate_input.setRange(1, 10_000_000)
        self.rate_input.setValue(default_rate)
        layout.addWidget(self.rate_input)

        confirm_button = QPushButton("CONFIRM")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self._confirm)
        layout.addWidget(confirm_button)

        self.setStyleSheet("""
            QDialog {
                background: #14141f;
            }

            QLabel {
                color: #aaaac8;
                font-size: 14px;
            }

            #sectionTitle {
                font-size: 18px;
                font-weight: bold;
                color: #d8d8ff;
            }

            QSpinBox {
                color: #eeeeff;
                background: #181824;
                border: 1px solid #303044;
                border-radius: 5px;
                padding: 6px;
                font-size: 13px;
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
        """)

    def _confirm(self):
        self.chosen_rate = self.rate_input.value()
        self._confirmed = True
        self.accept()

    def closeEvent(self, event):
        if self._confirmed:
            event.accept()
        else:
            event.ignore()


def main():

    app = QApplication(sys.argv)

    window = GalaxyHideout()

    # Prefer the live poe.ninja rate fetched during catalog refresh
    # (still just a pre-fill — the user can override it, Q26); fall
    # back to the last persisted rate if that fetch was unreachable.
    if window.live_divine_rate is not None:
        default_rate = round(window.live_divine_rate)
    else:
        default_rate = window.trade_service.divine_rate

    startup_dialog = StartupDialog(default_rate=default_rate)
    startup_dialog.exec()

    window.trade_service.set_divine_rate(startup_dialog.chosen_rate)
    window.refresh_all()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
