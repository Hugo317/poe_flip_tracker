import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt


class GalaxyHideout(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Galaxy Hideout")
        self.resize(1400, 850)

        self._build_ui()

    def _build_ui(self):

        # =====================================================
        # MAIN WINDOW
        # =====================================================

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # =====================================================
        # MAIN CONTENT
        # =====================================================

        content = QFrame()
        content.setObjectName("content")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # Header
        # =====================================================
        # HIDEOUT HEADER
        # =====================================================

        hideout_title = QLabel("GALAXY HIDEOUT")
        hideout_title.setObjectName("hideoutTitle")

        content_layout.addWidget(hideout_title)

        # =====================================================
        # SUMMARY
        # =====================================================

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(15)

        profit_box = self._create_summary_box(
            "PROFIT",
            "+12,450c"
        )

        trades_box = self._create_summary_box(
            "OPEN TRADES",
            "6"
        )
        inventory_box = self._create_summary_box(
            "INVENTORY",
            "15"
        )

        summary_layout.addWidget(profit_box)
        summary_layout.addWidget(trades_box)
        summary_layout.addWidget(inventory_box)

        content_layout.addLayout(summary_layout)

        # =====================================================
        # OPEN TRADES TITLE
        # =====================================================

        trades_title = QLabel("OPEN TRADES")
        trades_title.setObjectName("sectionTitle")

        content_layout.addWidget(trades_title)

        # =====================================================
        # TRADE GRID
        # =====================================================

        trade_grid = QGridLayout()
        trade_grid.setSpacing(12)

        for i in range(6):

            trade = self._create_trade_card(
                i + 1
            )

            row = i // 3
            column = i % 3

            trade_grid.addWidget(
                trade,
                row,
                column
            )

        content_layout.addLayout(trade_grid)

        # =====================================================
        # RECENT ACTIVITY
        # =====================================================

        activity_title = QLabel("RECENT ACTIVITY")
        activity_title.setObjectName("sectionTitle")

        content_layout.addWidget(activity_title)

        activity = QLabel(
            "BUY  10 × Reflecting Mist  —  4,000c\n"
            "SELL 10 × Reflecting Mist  —  6,000c\n"
            "BUY  5 × Reflecting Mist   —  2,250c"
        )

        activity.setObjectName("activity")

        content_layout.addWidget(activity)

        content_layout.addStretch()     

        # =====================================================
        # SIDEBAR
        # =====================================================

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(
            15,
            15,
            15,
            15
        )

        sidebar_layout.setSpacing(12)

        title = QLabel(
            "GALAXY\nHIDEOUT"
        )

        title.setObjectName("title")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        sidebar_layout.addWidget(title)

        sidebar_layout.addSpacing(20)

        sidebar_layout.addWidget(
            QLabel("OVERVIEW")
        )

        sidebar_layout.addWidget(
            QLabel("TRADES")
        )

        sidebar_layout.addWidget(
            QLabel("INVENTORY")
        )

        sidebar_layout.addWidget(
            QLabel("SETTINGS")
        )

        sidebar_layout.addStretch()

        # =====================================================
        # LAYOUT
        # =====================================================

        main_layout.addWidget(content)
        main_layout.addWidget(sidebar)

        # =====================================================
        # STYLE
        # =====================================================

        self.setStyleSheet("""

            QMainWindow {
                background: #0b0b12;
            }

            #sidebar {
                background: #11111c;
                border: 1px solid #303044;
                border-radius: 8px;
            }

            #content {
                background: #11111c;
                border: 1px solid #303044;
                border-radius: 8px;
            }

            #title {
                font-size: 20px;
                font-weight: bold;
                color: #d8d8ff;
            }

            #header {
                font-size: 24px;
                font-weight: bold;
                color: #eeeeff;
            }

            QLabel {
                color: #aaaaC8;
                font-size: 14px;
            }

            #tradeCard {
                background: #181824;
                border: 1px solid #303044;
                border-radius: 6px;
            }

            #tradeTitle {
                color: #eeeeff;
                font-size: 16px;
                font-weight: bold;
            }

            #tradeInfo {
                color: #aaaac8;
                font-size: 13px;
            }

            #tradeProfit {
                color: #d8d8ff;
                font-size: 14px;
                font-weight: bold;
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

        """)

    def _create_summary_box(self, title, value):

        box = QFrame()
        box.setObjectName("summaryBox")

        layout = QVBoxLayout(box)

        layout.setContentsMargins(
            15,
            12,
            15,
            12
        )

        title_label = QLabel(title)
        title_label.setObjectName("summaryTitle")

        value_label = QLabel(value)
        value_label.setObjectName("summaryValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return box

    # =========================================================
    # TRADE CARD
    # =========================================================

    def _create_trade_card(self, trade_number):

        card = QFrame()
        card.setObjectName("tradeCard")

        card.setMinimumHeight(150)

        layout = QVBoxLayout(card)

        layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        layout.setSpacing(6)

        title = QLabel(
            f"TRADE #{trade_number}"
        )

        title.setObjectName(
            "tradeTitle"
        )

        layout.addWidget(title)

        item = QLabel(
            "Reflecting Mist"
        )

        item.setObjectName(
            "tradeInfo"
        )

        layout.addWidget(item)

        quantity = QLabel(
            "10 items"
        )

        quantity.setObjectName(
            "tradeInfo"
        )

        layout.addWidget(quantity)

        buy = QLabel(
            "Buy: 400c each"
        )

        buy.setObjectName(
            "tradeInfo"
        )

        layout.addWidget(buy)

        sell = QLabel(
            "Sell: 600c each"
        )

        sell.setObjectName(
            "tradeInfo"
        )

        layout.addWidget(sell)

        profit = QLabel(
            "Profit: +2,000c"
        )

        profit.setObjectName(
            "tradeProfit"
        )

        layout.addWidget(profit)

        return card


def main():

    app = QApplication(sys.argv)

    window = GalaxyHideout()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()