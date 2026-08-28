import sys
import random
import math
from pathlib import Path

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
    QCompleter,
    QAbstractSpinBox,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QSize, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QFontDatabase, QIcon, QPixmap, QPainter, QColor, QTransform,
    QPainterPath, QFont, QFontMetrics, QPen, QLinearGradient, QBrush,
)

from backend.trades import TradeService, TradeHasSalesError
from backend.assets_service import AssetService
from backend.gold_fees import gold_cost_for, is_gold_exchange_eligible
from backend.backup import BackupManager
from backend.migrations import run_migrations
from ui.sound_player import SoundPlayer


SIDEBAR_SECTIONS = [
    "FAUSTUS",
    "STASH",
    "TRADES",
    "ANALYTICS",
    "SETTINGS",
]

SIDEBAR_ICONS = {
    "FAUSTUS": "💰",
    "STASH": "📦",
    "TRADES": "🤝",
    "ANALYTICS": "📈",
    "SETTINGS": "🛠",
}

# Display text for a completed transaction's type — "BUY"/"SELL"
# stays the internal data value (matches backend/trades.py and the
# Trades page filter), only how it's shown changes (Hugo's request).
TRANSACTION_TYPE_DISPLAY = {
    "BUY": "BOUGHT",
    "SELL": "SOLD",
}

SIDEBAR_WIDTH_EXPANDED = 180
SIDEBAR_WIDTH_COLLAPSED = 64

# Overlay covers this fraction of the content area, centered,
# leaving a Hideout border visible around it.
OVERLAY_SIZE_RATIO = 0.90

# Display font for headings only (directive Q48) — body text stays on
# the system font for readability. Cinzel is SIL Open Font License
# (assets/fonts/OFL.txt), safe to bundle; falls back to a generic
# serif if the font file is ever missing rather than failing to start.
FONT_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
DISPLAY_FONT_FALLBACK = "Georgia, 'Times New Roman', serif"


def load_display_font():
    font_path = FONT_ASSETS_DIR / "Cinzel-Variable.ttf"

    if not font_path.exists():
        return DISPLAY_FONT_FALLBACK

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)

    if not families:
        return DISPLAY_FONT_FALLBACK

    return f"'{families[0]}', {DISPLAY_FONT_FALLBACK}"


TITLE_FONT_FALLBACK = "Impact, 'Arial Black', sans-serif"


def load_title_font():
    """The Hideout's "MY HIDEOUT" neon title uses its own ornate
    display font (Pirata One) rather than the app-wide one."""

    font_path = FONT_ASSETS_DIR / "PirataOne.ttf"

    if not font_path.exists():
        return TITLE_FONT_FALLBACK

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)

    if not families:
        return TITLE_FONT_FALLBACK

    return f"'{families[0]}', {TITLE_FONT_FALLBACK}"


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
    card.setFixedWidth(210)
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


def build_transaction_card(transaction, asset_service):

    card = QFrame()
    card.setObjectName("tradeCard")
    card.setFixedWidth(190)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)

    header_row = QHBoxLayout()

    item_asset = asset_service.get_asset_by_name(transaction["item"])
    icon_path = (
        asset_service.icon_file_path(item_asset)
        if item_asset is not None else None
    )

    if icon_path is not None:
        header_icon = QLabel()
        header_icon.setPixmap(
            QPixmap(str(icon_path)).scaled(
                20, 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        header_row.addWidget(header_icon)

    type_text = TRANSACTION_TYPE_DISPLAY[transaction["type"]].capitalize()
    type_label = QLabel(type_text)
    type_label.setObjectName("tradeTitle")
    header_row.addWidget(type_label)
    header_row.addStretch()

    layout.addLayout(header_row)

    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setObjectName("cardDivider")
    layout.addWidget(divider)

    item_name = QLabel(transaction["item"])
    item_name.setObjectName("tradeInfo")
    item_name.setWordWrap(True)
    layout.addWidget(item_name)

    price_row = QHBoxLayout()
    price_row.setSpacing(4)

    quantity_label = QLabel(str(transaction["quantity"]))
    quantity_label.setObjectName("tradeInfo")
    price_row.addWidget(quantity_label)

    if icon_path is not None:
        price_icon = QLabel()
        price_icon.setPixmap(
            QPixmap(str(icon_path)).scaled(
                20, 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        price_row.addWidget(price_icon)

    if transaction["currency"] == "DIVINE":
        price_text = f"@ {transaction['entered_price']} Divine each"
    else:
        price_text = f"@ {transaction['entered_price']:,}c each"

    price_label = QLabel(price_text)
    price_label.setObjectName("tradeInfo")
    price_row.addWidget(price_label)
    price_row.addStretch()

    layout.addLayout(price_row)

    total_text = f"Total: {transaction['total_chaos']:,}c"
    if transaction["profit"] is not None:
        total_text += f"  ({transaction['profit']:+,}c)"

    total_line = QLabel(total_text)
    total_line.setObjectName("tradeInfo")
    layout.addWidget(total_line)

    return card


def populate_confirm_card(layout, asset_service, item_name, type_label, price_line, stat_rows):
    clear_layout(layout)

    header_row = QHBoxLayout()

    icon_path = None
    asset = asset_service.get_asset_by_name(item_name)
    if asset is not None:
        icon_path = asset_service.icon_file_path(asset)

    if icon_path is not None:
        icon_label = QLabel()
        icon_label.setPixmap(
            QPixmap(str(icon_path)).scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        header_row.addWidget(icon_label)

    item_label = QLabel(item_name)
    item_label.setObjectName("tradeTitle")
    header_row.addWidget(item_label)
    header_row.addStretch()

    type_badge = QLabel(type_label)
    type_badge.setObjectName("tradeTitle")
    header_row.addWidget(type_badge)

    layout.addLayout(header_row)

    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setObjectName("cardDivider")
    layout.addWidget(divider)

    price_label = QLabel(price_line)
    price_label.setObjectName("tradeInfo")
    layout.addWidget(price_label)

    layout.addSpacing(6)

    for label_text, value_text in stat_rows:
        row = QHBoxLayout()

        label = QLabel(label_text)
        label.setObjectName("formLabel")
        row.addWidget(label)
        row.addStretch()

        value = QLabel(value_text)
        value.setObjectName("tradeInfo")
        row.addWidget(value)

        layout.addLayout(row)


def build_history_day_card(trading_day, on_click):

    card = QFrame()
    card.setObjectName("tradeCard")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)

    date_label = QLabel(trading_day.started_at.split(" ")[0])
    date_label.setObjectName("tradeTitle")
    layout.addWidget(date_label)

    profit = trading_day.snapshot_realized_profit or 0
    profit_label = QLabel(f"Profit: {profit:+,}c")
    profit_label.setObjectName("tradeInfo")
    layout.addWidget(profit_label)

    roi_percent = (trading_day.snapshot_roi or 0) * 100
    roi_label = QLabel(f"% Return: {roi_percent:+.1f}%")
    roi_label.setObjectName("tradeInfo")
    layout.addWidget(roi_label)

    view_button = QPushButton("VIEW")
    view_button.setObjectName("fauxTab")
    view_button.clicked.connect(lambda: on_click(trading_day))
    layout.addWidget(view_button)

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


def _is_market_league(name):
    # SSF (Solo Self-Found) has no trade with other players, so it
    # has no market/pricing at all — Faustus can't function there.
    # poe.ninja's own economy-leagues list already excludes these,
    # this is just a defensive second layer.
    lowered = name.lower()
    return "ssf" not in lowered and "solo self-found" not in lowered


def available_league_names(trade_service, asset_service):
    """Live leagues from poe.ninja first (in its own order — current
    temp league, Standard, Hardcore, etc.), then any locally-known
    league not in that list (e.g. a league that has since ended but
    still has local trade history). SSF leagues are excluded — no
    market means no Faustus."""

    live = asset_service.available_leagues()
    local = trade_service.local_league_names()

    merged = list(live)
    for name in local:
        if name not in merged:
            merged.append(name)

    result = [name for name in merged if _is_market_league(name)]

    return result or [name for name in local if _is_market_league(name)]


class QuantityPriceTotalLinker:
    """Keeps Quantity / Price-per-item / Total mutually in sync in a
    BUY or SELL form (Hugo's request). Normally Total is just a live
    readout of quantity x price; editing Total directly instead
    back-solves Price, with Quantity always treated as the fixed
    anchor either way."""

    def __init__(self, quantity_input, price_input, total_input):
        self.quantity_input = quantity_input
        self.price_input = price_input
        self.total_input = total_input
        self._updating = False

        quantity_input.valueChanged.connect(self._recompute_total)
        price_input.valueChanged.connect(self._recompute_total)
        total_input.valueChanged.connect(self._recompute_price)

        self._recompute_total()

    def _recompute_total(self):
        if self._updating:
            return

        self._updating = True
        self.total_input.setValue(
            self.quantity_input.value() * self.price_input.value()
        )
        self._updating = False

    def _recompute_price(self):
        if self._updating:
            return

        self._updating = True

        quantity = self.quantity_input.value()

        if quantity > 0:
            self.price_input.setValue(
                round(self.total_input.value() / quantity)
            )

        self._updating = False

    def reset(self, quantity=1, price=1):
        self._updating = True
        self.quantity_input.setValue(quantity)
        self.price_input.setValue(price)
        self.total_input.setValue(quantity * price)
        self._updating = False


class GoldEstimator:
    """Auto-calculates Gold spent/received (Hugo's request — Gold is
    never manually typed). Every Currency Exchange trade charges Gold
    twice — once for the item leg, once for the currency leg — each
    using that item's own Base Gold Fee (poedb.tw) times the quantity
    of it changing hands. There's no chaos-equivalent conversion
    involved; each leg is its own flat per-unit fee."""

    def __init__(
        self,
        quantity_input,
        total_input,
        chaos_button,
        divine_button,
        gold_display,
        item_name_getter,
        item_change_signal=None
    ):
        self.quantity_input = quantity_input
        self.total_input = total_input
        self.chaos_button = chaos_button
        self.divine_button = divine_button
        self.gold_display = gold_display
        self.item_name_getter = item_name_getter

        quantity_input.valueChanged.connect(self.recompute)
        total_input.valueChanged.connect(self.recompute)
        chaos_button.toggled.connect(self.recompute)
        divine_button.toggled.connect(self.recompute)

        if item_change_signal is not None:
            item_change_signal.connect(self.recompute)

        self.recompute()

    def current_gold_estimate(self):
        item_name = self.item_name_getter()
        quantity = self.quantity_input.value()
        total = self.total_input.value()

        currency_name = (
            "Divine Orb" if self.divine_button.isChecked() else "Chaos Orb"
        )

        item_leg = gold_cost_for(item_name, quantity)
        currency_leg = gold_cost_for(currency_name, total)

        if item_leg is None or currency_leg is None:
            return None

        return item_leg + currency_leg

    def recompute(self):
        gold = self.current_gold_estimate()

        if gold is None:
            self.gold_display.setText("N/A")
        else:
            self.gold_display.setText(f"{gold:,}")


class NeonTitleLabel(QWidget):
    """Engraved-metal title treatment (Hugo's request, replacing an
    earlier flat-fill+glow "neon sign" look that read as cheap):
    a vertical gold-to-bronze gradient fill, a carved bevel (a
    highlight sliver top-left, a shadow sliver bottom-right — like
    light catching a cast/engraved metal logo), and a tight hard
    drop shadow instead of an ambient glow. QSS/QLabel can't do any
    of this on their own, so the glyphs are painted directly via
    QPainterPath (fill + stroke)."""

    GRADIENT_TOP = QColor("#f5ecd8")
    GRADIENT_BOTTOM = QColor("#e0d0a8")
    OUTLINE_GRADIENT_TOP = QColor("#c49a3a")
    OUTLINE_GRADIENT_BOTTOM = QColor("#9a7526")
    # Calibrated at REFERENCE_HEIGHT (HIDEOUT's size) — scaled down
    # proportionally for smaller titles (e.g. "OPEN TRADES") in
    # set_target_height, so the outline doesn't look proportionally
    # thick at small sizes (Hugo's request).
    OUTLINE_WIDTH = 1.2
    REFERENCE_HEIGHT = 90
    MIN_OUTLINE_WIDTH = 0.3
    BEVEL_HIGHLIGHT = QColor("#fffaf0")
    BEVEL_SHADOW = QColor("#9c8f6c")
    BEVEL_OFFSET = 1.2
    DROP_SHADOW_COLOR = QColor(10, 8, 6, 200)
    DROP_SHADOW_BLUR_RADIUS = 10
    DROP_SHADOW_OFFSET = QPointF(3, 4)

    # Procedural crack/grain texture (Hugo's request, referencing a
    # "Curse of the Allflame"-style weathered engraved look) — drawn
    # directly rather than sourced from an image, so there's no
    # licensing question at all. Deterministic (fixed seed) so it
    # doesn't flicker/change between repaints.
    TEXTURE_ENABLED = True
    TEXTURE_SEED = 42
    CRACK_COLOR = QColor(40, 32, 16, 60)
    CRACK_COUNT = 42
    NOISE_COLOR = QColor(40, 32, 16, 25)
    NOISE_DENSITY = 200
    # Fraction of cracks that also carve an actual missing chunk (a
    # real hole in the glyph path, revealing the background behind)
    # rather than just a drawn line — Hugo's request for MORE actual
    # broken-off pieces, LESS dark crack/grain texture, and deeper
    # (bigger) bites.
    CHIP_PROBABILITY = 0.85
    CHIP_MIN_RADIUS = 6.0
    CHIP_MAX_RADIUS = 15.0

    # Extra px inserted before the second letter of a specific pair
    # only — e.g. {("U", "T"): 6} widens the U→T gap without touching
    # any other letter spacing (Hugo: "spread the T from the U", not
    # a global letter-spacing change).
    EXTRA_GAP_PAIRS = {("U", "T"): 6}

    def __init__(self, text, font_family_qss, target_height=90, parent=None):
        super().__init__(parent)

        self._text = text
        self._primary_family = (
            font_family_qss.split(",")[0].strip().strip("'\"")
        )
        self._font = QFont(self._primary_family)

        # Kept as self._shadow, not a local var — PySide6 will garbage
        # collect the Python wrapper (silently dropping the effect)
        # if nothing keeps a live reference, even though Qt's C++
        # side parents it via setGraphicsEffect().
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setColor(self.DROP_SHADOW_COLOR)
        self._shadow.setBlurRadius(self.DROP_SHADOW_BLUR_RADIUS)
        self._shadow.setOffset(self.DROP_SHADOW_OFFSET)
        self.setGraphicsEffect(self._shadow)

        self.set_target_height(target_height)

    def set_target_height(self, target_height, max_width=None):
        """Resizes the widget so the painted glyphs' cap-height equals
        `target_height` px, back-solving the QFont point size from a
        reference size (font-metric height scales ~linearly with
        point size for a given family). If the resulting text would be
        wider than `max_width`, scales back down to fit — different
        fonts have very different width-to-cap-height ratios, so a
        height-only fit can otherwise run off the window edge."""

        reference_point_size = 100
        reference_font = QFont(self._primary_family)
        reference_font.setPointSize(reference_point_size)
        reference_font.setBold(True)
        reference_metrics = QFontMetrics(reference_font)
        reference_cap_height = (
            reference_metrics.capHeight() or reference_metrics.ascent()
        )

        scale = target_height / reference_cap_height
        point_size = max(10, round(reference_point_size * scale))

        self._outline_width = max(
            self.MIN_OUTLINE_WIDTH,
            self.OUTLINE_WIDTH * (target_height / self.REFERENCE_HEIGHT)
        )

        margin = (
            self._outline_width * 2
            + self.BEVEL_OFFSET * 2
            + self.DROP_SHADOW_BLUR_RADIUS
        )

        def build(point_size):
            font = QFont(self._primary_family)
            font.setPointSize(point_size)
            font.setWeight(QFont.Weight.Normal)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
            metrics = QFontMetrics(font)
            text_rect = metrics.boundingRect(self._text)
            return font, text_rect

        self._font, text_rect = build(point_size)

        if max_width is not None:
            full_width = text_rect.width() + margin * 2
            if full_width > max_width:
                point_size = max(
                    10, round(point_size * (max_width / full_width))
                )
                self._font, text_rect = build(point_size)

        self.setFixedSize(
            text_rect.width() + margin * 2 + self._extra_gap_total(),
            text_rect.height() + margin * 2
        )
        self.update()

    def _extra_gap_total(self):
        total = 0
        for i in range(1, len(self._text)):
            pair = (self._text[i - 1], self._text[i])
            total += self.EXTRA_GAP_PAIRS.get(pair, 0)
        return total

    def _gap_split(self):
        """Index/gap-width of the first EXTRA_GAP_PAIRS match in the
        text, so paintEvent can draw it as two separate runs with a
        manual gap between them — everything else stays a single
        Qt-shaped run, so normal letter-spacing is untouched."""

        for i in range(1, len(self._text)):
            pair = (self._text[i - 1], self._text[i])
            if pair in self.EXTRA_GAP_PAIRS:
                return i, self.EXTRA_GAP_PAIRS[pair]
        return None, 0

    def paintEvent(self, event):
        painter = QPainter(self)

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            metrics = QFontMetrics(self._font)
            # Centered from the same ink bounding box used to size the
            # widget in set_target_height — using horizontalAdvance()
            # here instead (which includes the letter-spacing tail
            # after the last glyph) previously clipped the last
            # character(s), since the box was never sized to fit it.
            text_rect = metrics.boundingRect(self._text)
            extra_gap_total = self._extra_gap_total()
            x = (
                (self.width() - text_rect.width() - extra_gap_total) / 2
                - text_rect.left()
            )
            y = (
                (self.height() + metrics.ascent() - metrics.descent())
                / 2
            )

            path = QPainterPath()
            split_index, gap = self._gap_split()
            if split_index is None:
                path.addText(x, y, self._font, self._text)
            else:
                first, second = (
                    self._text[:split_index], self._text[split_index:]
                )
                path.addText(x, y, self._font, first)
                second_x = x + metrics.horizontalAdvance(first) + gap
                path.addText(second_x, y, self._font, second)

            cracks = []
            visible_path = path
            if self.TEXTURE_ENABLED:
                cracks, chips = self._build_texture(path)
                if not chips.isEmpty():
                    visible_path = path.subtracted(chips)

            painter.setPen(Qt.PenStyle.NoPen)

            shadow_path = QPainterPath(visible_path)
            shadow_path.translate(self.BEVEL_OFFSET, self.BEVEL_OFFSET)
            painter.setBrush(self.BEVEL_SHADOW)
            painter.drawPath(shadow_path)

            highlight_path = QPainterPath(visible_path)
            highlight_path.translate(
                -self.BEVEL_OFFSET, -self.BEVEL_OFFSET
            )
            painter.setBrush(self.BEVEL_HIGHLIGHT)
            painter.drawPath(highlight_path)

            gradient = QLinearGradient(
                0, path.boundingRect().top(),
                0, path.boundingRect().bottom()
            )
            gradient.setColorAt(0, self.GRADIENT_TOP)
            gradient.setColorAt(1, self.GRADIENT_BOTTOM)

            outline_gradient = QLinearGradient(
                0, path.boundingRect().top(),
                0, path.boundingRect().bottom()
            )
            outline_gradient.setColorAt(0, self.OUTLINE_GRADIENT_TOP)
            outline_gradient.setColorAt(1, self.OUTLINE_GRADIENT_BOTTOM)

            painter.setPen(
                QPen(QBrush(outline_gradient), self._outline_width)
            )
            painter.setBrush(gradient)
            painter.drawPath(visible_path)

            if self.TEXTURE_ENABLED:
                self._paint_texture_overlay(painter, visible_path, cracks)
        finally:
            painter.end()

    def _build_texture(self, path):
        """Deterministically builds the crack lines and, for a subset
        of them, an actual chip hole where the crack meets the glyph's
        edge — a small wedge subtracted from the glyph path so the
        real background shows through, like a piece broke off the
        rim (Hugo's reference: a cracked stone sphere with wedge-shaped
        notches bitten out along the edge), rather than a floating
        round hole in the middle of a letter."""

        rng = random.Random(self.TEXTURE_SEED)
        rect = path.boundingRect()
        cracks = []
        chips = QPainterPath()

        for _ in range(self.CRACK_COUNT):
            x, y, outward_angle = self._find_edge_point(path, rect, rng)
            crack = QPainterPath()
            crack.moveTo(x, y)
            cx, cy = x, y
            for _ in range(rng.randint(3, 6)):
                cx += rng.uniform(-9, 9)
                cy += rng.uniform(-9, 9)
                crack.lineTo(cx, cy)
            cracks.append(crack)

            wants_chip = rng.random() < self.CHIP_PROBABILITY
            if wants_chip and self._has_room_for_chip(
                path, x, y, outward_angle
            ):
                chips.addPath(
                    self._build_chip_wedge(x, y, outward_angle, rng)
                )

        return cracks, chips

    def _has_room_for_chip(self, path, x, y, outward_angle, probe=6.0):
        """True only if there's solid material behind this edge point
        (checked back along the inward direction) — skips thin serif
        tips/flourishes where a chip would sever a sliver off into a
        disconnected-looking fragment instead of biting cleanly into
        the letter (the artifact Hugo flagged as looking like broken
        clipping rather than a deliberate chip)."""

        inward = QPointF(
            x - probe * math.cos(outward_angle),
            y - probe * math.sin(outward_angle)
        )
        return path.contains(inward)

    def _find_edge_point(self, path, rect, rng, attempts=40, probe=4.0):
        """Finds a point just inside the glyph that sits near its
        outer boundary, returning it plus the direction that steps
        outside the shape — so a chip built there reads as a bite
        out of the actual edge, not a hole floating mid-letter."""

        for _ in range(attempts):
            x = rect.left() + rng.random() * rect.width()
            y = rect.top() + rng.random() * rect.height()
            if not path.contains(QPointF(x, y)):
                continue
            for step in range(8):
                angle = (2 * math.pi / 8) * step
                probe_point = QPointF(
                    x + probe * math.cos(angle),
                    y + probe * math.sin(angle)
                )
                if not path.contains(probe_point):
                    return x, y, angle

        x = rect.left() + rng.random() * rect.width()
        y = rect.top() + rng.random() * rect.height()
        return x, y, rng.random() * 2 * math.pi

    def _build_chip_wedge(self, cx, cy, outward_angle, rng):
        """A jagged wedge fanning outward from (cx, cy) — an inner
        pinch point plus a spread of irregular outer points, like a
        shard broken away from the edge."""

        radius = rng.uniform(self.CHIP_MIN_RADIUS, self.CHIP_MAX_RADIUS)
        spread = math.radians(rng.uniform(50, 90))
        point_count = 3

        wedge = QPainterPath()
        wedge.moveTo(cx, cy)
        for i in range(point_count):
            angle = (
                outward_angle - spread / 2
                + spread * (i / (point_count - 1))
            )
            r = radius * rng.uniform(0.5, 1.5)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            wedge.lineTo(px, py)
        wedge.closeSubpath()
        return wedge

    def _paint_texture_overlay(self, painter, clip_path, cracks):
        """Grain dots + the crack lines built in `_build_texture`,
        clipped to the (possibly chip-holed) glyph shape."""

        rng = random.Random(self.TEXTURE_SEED + 1)
        rect = clip_path.boundingRect()

        painter.save()
        painter.setClipPath(clip_path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.NOISE_COLOR)
        for _ in range(self.NOISE_DENSITY):
            x = rect.left() + rng.random() * rect.width()
            y = rect.top() + rng.random() * rect.height()
            r = rng.uniform(0.3, 1.1)
            painter.drawEllipse(QPointF(x, y), r, r)

        painter.setPen(QPen(self.CRACK_COLOR, 1.0))
        for crack in cracks:
            painter.drawPath(crack)
        painter.restore()


class HoverSidebar(QFrame):
    """Expands on mouse-over, collapses back to icons-only when the
    mouse leaves (Hugo's request — no manual toggle button)."""

    def __init__(self, on_enter, on_leave, parent=None):
        super().__init__(parent)
        self._on_enter = on_enter
        self._on_leave = on_leave

    def enterEvent(self, event):
        self._on_enter()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._on_leave()
        super().leaveEvent(event)


IMAGES_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"


class NebulaBackground(QWidget):
    """Directive Q45 — permanent animated Hideout background: a
    static galaxy backdrop with a dust haze and two star layers
    slowly drifting over it at different speeds/directions for a
    parallax depth effect. All four images are public-domain/CC0
    (see assets/images/LICENSES.txt)."""

    # (dx, dy) per tick, and paint opacity, for each drifting layer —
    # distinct directions/speeds so the layers read as separate depths
    # rather than one flat scrolling image. Slow but visibly moving.
    STARS_SMALL_DRIFT = QPointF(0.06, 0.02)
    STARS_SMALL_OPACITY = 0.75

    DUST_DRIFT = QPointF(-0.15, 0.08)
    DUST_OPACITY = 0.08

    STARS_BRIGHT_DRIFT = QPointF(0.25, -0.12)
    STARS_BRIGHT_OPACITY = 0.95

    # Star sprites downscaled to 1/5 size so individual stars read as
    # small bright points ("little blinks") rather than big soft blobs.
    STAR_SPRITE_SCALE = 0.2

    TICK_MS = 40

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # The source photo is portrait (1155x2000); rotating it 90°
        # left turns it landscape, which is a much closer aspect-ratio
        # match to the window — "cover" then crops far less while
        # still filling every pixel (no void bars).
        raw_galaxy = QPixmap(str(IMAGES_DIR / "galaxy_pillars_of_creation.png"))
        self._galaxy = raw_galaxy.transformed(
            QTransform().rotate(-90), Qt.TransformationMode.SmoothTransformation
        )
        self._dust = QPixmap(str(IMAGES_DIR / "dust_vapor.png"))

        raw_stars_small = QPixmap(str(IMAGES_DIR / "stars_small.png"))
        raw_stars_bright = QPixmap(str(IMAGES_DIR / "stars_bright.png"))
        self._stars_small = raw_stars_small.scaled(
            int(raw_stars_small.width() * self.STAR_SPRITE_SCALE),
            int(raw_stars_small.height() * self.STAR_SPRITE_SCALE),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._stars_bright = raw_stars_bright.scaled(
            int(raw_stars_bright.width() * self.STAR_SPRITE_SCALE),
            int(raw_stars_bright.height() * self.STAR_SPRITE_SCALE),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self._stars_small_offset = QPointF(0, 0)
        self._dust_offset = QPointF(0, 0)
        self._stars_bright_offset = QPointF(0, 0)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(self.TICK_MS)

    def _advance(self):
        self._stars_small_offset += self.STARS_SMALL_DRIFT
        self._dust_offset += self.DUST_DRIFT
        self._stars_bright_offset += self.STARS_BRIGHT_DRIFT
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            rect_f = QRectF(self.rect())

            # Safety-net fill in case of any 1px rounding seam at the
            # edges — the rotated image's aspect ratio is close enough
            # to the window's that "cover" below leaves no real gap.
            painter.fillRect(self.rect(), QColor("#08070f"))

            if not self._galaxy.isNull() and self.width() and self.height():
                scaled = self._galaxy.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)

            if not self._stars_small.isNull():
                painter.setOpacity(self.STARS_SMALL_OPACITY)
                painter.drawTiledPixmap(
                    rect_f, self._stars_small, self._stars_small_offset
                )

            if not self._dust.isNull():
                painter.setOpacity(self.DUST_OPACITY)
                painter.drawTiledPixmap(
                    rect_f, self._dust, self._dust_offset
                )

            if not self._stars_bright.isNull():
                painter.setOpacity(self.STARS_BRIGHT_OPACITY)
                painter.drawTiledPixmap(
                    rect_f, self._stars_bright, self._stars_bright_offset
                )
        finally:
            painter.end()


class GalaxyHideout(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DivineFlipper")
        self.resize(1400, 850)
        self.setMinimumSize(1400, 850)

        self.display_font = load_display_font()
        self.title_font = load_title_font()

        self.trade_service = TradeService()
        self.asset_service = AssetService(session=self.trade_service.session)
        self.sound_player = SoundPlayer(self.trade_service)
        self.backup_manager = BackupManager()

        # Directive Q4/Q5: one automatic backup per day, no user
        # action required.
        self.backup_manager.run_daily_backup_if_needed()

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
        self._central = central

        # Covers the entire window — outer margins, sidebar gutter,
        # everything — not just the Hideout panel (Hugo's request).
        # Sized/repositioned in resizeEvent, same as the sidebar.
        self.nebula_background = NebulaBackground(central)
        self.nebula_background.lower()

        # The sidebar is NOT part of this layout — it floats on top as
        # an overlay (Hugo's request), positioned manually in
        # _position_sidebar(). The layout only reserves a permanent
        # right-hand gutter the width of the collapsed sidebar, so
        # content never sits underneath the always-visible icons, and
        # expanding the sidebar never reflows/resizes the rest of the
        # app.
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(
            20, 20, 20 + SIDEBAR_WIDTH_COLLAPSED + 15, 20
        )
        main_layout.setSpacing(15)

        self.content_area = ContentArea(
            overlay_ratio=OVERLAY_SIZE_RATIO
        )

        self.hideout = self._build_hideout()
        self.content_area.set_hideout(self.hideout)

        self.overlay = OverlayPanel(
            trade_service=self.trade_service,
            asset_service=self.asset_service,
            sound_player=self.sound_player,
            backup_manager=self.backup_manager,
            on_trade_changed=self.refresh_all,
            on_close=self._close_overlay
        )
        self.content_area.set_overlay(self.overlay)

        main_layout.addWidget(self.content_area)

        sidebar = self._build_sidebar()
        sidebar.setParent(central)
        sidebar.raise_()
        self._position_sidebar()

        self.nebula_background.setGeometry(central.rect())
        self.nebula_background.lower()

        self._apply_stylesheet()

        # Deferred one frame so the initial layout pass has already run
        # and hud_profit_box has a real, laid-out position to measure
        # (Hugo's request: title fills 90% of the gap between the
        # window's top edge and the first HUD card).
        QTimer.singleShot(0, self._fit_hideout_title)

    def _fit_hideout_title(self):
        gap = self.hud_profit_box.mapTo(
            self._central, self.hud_profit_box.rect().topLeft()
        ).y()
        # 25% / 50% / 25% split (Hugo's request): title is constrained
        # to the center half of the hideout's width, with empty gutters
        # on either side.
        max_width = self.hideout.width() * 0.5
        self.hideout_title.set_target_height(
            gap * 0.9 * 0.65 * 0.7, max_width=max_width
        )

    def _position_sidebar(self):
        central = self._central
        width = self.sidebar.width()

        self.sidebar.setGeometry(
            central.width() - width, 0, width, central.height()
        )
        self.sidebar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_sidebar()
        self.nebula_background.setGeometry(self._central.rect())

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

        # Top-left corner block (Hugo's request, replacing the old
        # bottom-right rate chip): gold spent this league (icon +
        # number, no label text) above the divine:chaos rate (real
        # icons either side of the ratio). Each row is its own card
        # (Hugo's request), same black see-through look as the rest
        # of the Hideout's cards, white text.
        corner_layout = QVBoxLayout()
        corner_layout.setSpacing(6)

        gold_card = QFrame()
        gold_card.setObjectName("tradeCard")
        gold_row = QHBoxLayout(gold_card)
        gold_row.setContentsMargins(10, 6, 10, 6)
        gold_row.setSpacing(4)

        gold_asset = self.asset_service.get_asset_by_name("Gold")
        gold_icon_path = (
            self.asset_service.icon_file_path(gold_asset)
            if gold_asset is not None else None
        )
        if gold_icon_path is not None:
            gold_icon = QLabel()
            gold_icon.setPixmap(
                QPixmap(str(gold_icon_path)).scaled(
                    16, 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            gold_row.addWidget(gold_icon)

        gold_colon_label = QLabel(":")
        gold_colon_label.setObjectName("divineRateCorner")
        gold_row.addWidget(gold_colon_label)

        self.gold_spent_label = QLabel("0")
        self.gold_spent_label.setObjectName("divineRateCorner")
        gold_row.addWidget(self.gold_spent_label)
        gold_row.addStretch()
        corner_layout.addWidget(gold_card, alignment=Qt.AlignmentFlag.AlignLeft)

        rate_card = QFrame()
        rate_card.setObjectName("tradeCard")
        rate_row = QHBoxLayout(rate_card)
        rate_row.setContentsMargins(10, 6, 10, 6)
        rate_row.setSpacing(4)

        divine_asset = self.asset_service.get_asset_by_name("Divine Orb")
        divine_icon_path = (
            self.asset_service.icon_file_path(divine_asset)
            if divine_asset is not None else None
        )
        if divine_icon_path is not None:
            divine_icon = QLabel()
            divine_icon.setPixmap(
                QPixmap(str(divine_icon_path)).scaled(
                    16, 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            rate_row.addWidget(divine_icon)

        colon_label = QLabel(":")
        colon_label.setObjectName("divineRateCorner")
        rate_row.addWidget(colon_label)

        self.divine_rate_label = QLabel("")
        self.divine_rate_label.setObjectName("divineRateCorner")
        rate_row.addWidget(self.divine_rate_label)

        chaos_asset = self.asset_service.get_asset_by_name("Chaos Orb")
        chaos_icon_path = (
            self.asset_service.icon_file_path(chaos_asset)
            if chaos_asset is not None else None
        )
        if chaos_icon_path is not None:
            chaos_icon = QLabel()
            chaos_icon.setPixmap(
                QPixmap(str(chaos_icon_path)).scaled(
                    16, 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            rate_row.addWidget(chaos_icon)

        # Directive Q32: a small attribution indicator wherever
        # market data is shown.
        attribution_label = QLabel("via poe.ninja")
        attribution_label.setObjectName("attribution")
        rate_row.addWidget(attribution_label)
        rate_row.addStretch()

        corner_layout.addWidget(rate_card, alignment=Qt.AlignmentFlag.AlignLeft)

        header_layout.addLayout(corner_layout)
        header_layout.setAlignment(
            corner_layout, Qt.AlignmentFlag.AlignTop
        )

        self.hideout_title = NeonTitleLabel(
            "HIDEOUT", self.title_font, target_height=90
        )

        header_layout.addStretch()
        header_layout.addWidget(self.hideout_title)
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

        # Matches the "HIDEOUT" title's font/treatment (Hugo's
        # request), at a much smaller size — texture chips are fixed
        # in absolute px so they'd swamp text this small, hence
        # disabled per-instance here. Outline bumped 25% over the
        # plain proportional scale-down, per-instance only (doesn't
        # affect HIDEOUT's own outline).
        trades_title = NeonTitleLabel(
            "OPEN TRADES", self.title_font, target_height=25
        )
        trades_title.TEXTURE_ENABLED = False
        trades_title.OUTLINE_WIDTH = NeonTitleLabel.OUTLINE_WIDTH * 1.25
        trades_title.set_target_height(25)

        layout.addWidget(trades_title)

        self.hideout_trades_grid = QGridLayout()
        self.hideout_trades_grid.setSpacing(12)

        layout.addLayout(self.hideout_trades_grid)

        # -----------------------------------------------------
        # RECENT ACTIVITY (last 5 BUY/SELL only)
        # -----------------------------------------------------

        # Same NeonTitleLabel treatment as OPEN TRADES (Hugo's
        # request — overrides the earlier plain-QLabel font/color).
        activity_title = NeonTitleLabel(
            "RECENT ACTIVITY", self.title_font, target_height=25
        )
        activity_title.TEXTURE_ENABLED = False
        activity_title.OUTLINE_WIDTH = NeonTitleLabel.OUTLINE_WIDTH * 1.25
        activity_title.set_target_height(25)

        layout.addWidget(activity_title)

        self.activity_grid = QGridLayout()
        self.activity_grid.setSpacing(12)

        layout.addLayout(self.activity_grid)

        # Space reserved for future Hideout additions.
        layout.addStretch()

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

        latest_trades = service.latest_open_trades(8)

        if not latest_trades:
            self.hideout_trades_grid.addWidget(
                build_empty_state("No open trades yet."),
                0, 0, 1, 3
            )
        else:
            last_column = 0
            for index, trade in enumerate(latest_trades):
                card = build_trade_card(trade, interactive=False)

                row = index // 3
                column = index % 3
                last_column = max(last_column, column)

                self.hideout_trades_grid.addWidget(card, row, column)

            # Same left-pin fix as Recent Activity — a trailing stretch
            # column absorbs leftover width instead of the grid
            # spreading real cards across the full row.
            self.hideout_trades_grid.setColumnStretch(last_column + 1, 1)

        clear_layout(self.activity_grid)

        activity = service.recent_activity(6)

        if not activity:
            self.activity_grid.addWidget(
                build_empty_state("No activity yet."),
                0, 0, 1, 3
            )
        else:
            # Column-major fill (Hugo's request: 1357 / 2468) — down
            # each column before moving to the next, 2 rows tall.
            last_column = 0
            for index, entry in enumerate(activity):
                card = build_transaction_card(entry, self.asset_service)
                row = index % 2
                column = index // 2
                last_column = max(last_column, column)
                self.activity_grid.addWidget(card, row, column)

            # A trailing stretch column absorbs the leftover width so
            # the cards hug the left instead of QGridLayout spreading
            # them evenly across the full row (Hugo's request).
            self.activity_grid.setColumnStretch(last_column + 1, 1)

        self.divine_rate_label.setText(str(service.divine_rate))
        self.gold_spent_label.setText(
            f"{service.total_gold_spent_this_league():,}"
        )

    # =========================================================
    # SIDEBAR (only navigation mechanism)
    # =========================================================

    def _build_sidebar(self):

        self.sidebar_collapsed = True
        self.sidebar_buttons = {}

        sidebar = HoverSidebar(
            on_enter=self._expand_sidebar,
            on_leave=self._collapse_sidebar
        )
        sidebar.setObjectName("sidebar")
        self.sidebar = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QLabel("")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_title = title

        layout.addWidget(title)
        layout.addSpacing(20)

        self.sidebar_group = QButtonGroup(self)
        self.sidebar_group.setExclusive(True)

        for section in SIDEBAR_SECTIONS:

            button = QPushButton()
            button.setObjectName("sidebarItem")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.clicked.connect(
                lambda checked, name=section: self._on_sidebar_clicked(name)
            )

            self.sidebar_group.addButton(button)
            self.sidebar_buttons[section] = button
            layout.addWidget(button)

        layout.addStretch()

        self._apply_sidebar_state()

        return sidebar

    def _sidebar_button_text(self, section):
        icon = SIDEBAR_ICONS[section]

        if self.sidebar_collapsed:
            return icon

        return f"{icon}  {section}"

    def _expand_sidebar(self):
        self.sidebar_collapsed = False
        self._apply_sidebar_state()

    def _collapse_sidebar(self):
        self.sidebar_collapsed = True
        self._apply_sidebar_state()

    def _apply_sidebar_state(self):
        if self.sidebar_collapsed:
            self.sidebar.setFixedWidth(SIDEBAR_WIDTH_COLLAPSED)
            self.sidebar_title.setText("DF")
        else:
            self.sidebar.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
            self.sidebar_title.setText("DIVINE\nFLIPPER")

        for section, button in self.sidebar_buttons.items():
            button.setText(self._sidebar_button_text(section))
            button.setProperty("collapsed", self.sidebar_collapsed)
            button.style().unpolish(button)
            button.style().polish(button)

        self._position_sidebar()

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.overlay.isVisible():
            self._close_overlay()
            return

        super().keyPressEvent(event)

    # =========================================================
    # STYLE
    # =========================================================

    def _apply_stylesheet(self):

        stylesheet = """

            QMainWindow {
                background: #08070f;
            }

            #sidebar {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #14121f, stop:1 #0d0c16
                );
                border: 1px solid #35304f;
                border-radius: 10px;
            }

            #hideout {
                background: transparent;
            }

            #title {
                font-family: __DISPLAY_FONT__;
                font-size: 21px;
                font-weight: bold;
                color: #d0c8ff;
                letter-spacing: 2px;
            }

            QLabel {
                color: #aaaac8;
                font-size: 14px;
            }

            #tradeCard {
                background: #181828;
                border: 1px solid #35304f;
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

            #cardDivider {
                background: #35304f;
                max-height: 1px;
                border: none;
            }

            #sectionTitle {
                font-family: __DISPLAY_FONT__;
                font-size: 17px;
                font-weight: bold;
                color: #c7bdff;
                letter-spacing: 1px;
                margin-top: 10px;
            }

            #summaryBox {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1c1a30, stop:1 #161425
                );
                border: 1px solid #3a3560;
                border-radius: 6px;
            }

            /* Hideout-only: black with a bit of see-through, so the
               nebula background shows faintly behind them (Hugo's
               request) — scoped so Faustus/Trades/Analytics cards
               elsewhere, sitting on a solid panel, are untouched. */
            #hideout #summaryBox,
            #hideout #tradeCard {
                background: rgba(0, 0, 0, 0.78);
                border: 1px solid rgba(53, 48, 79, 0.6);
            }

            #summaryTitle {
                color: #d4af6a;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            #summaryValue {
                color: #f0ecff;
                font-size: 22px;
                font-weight: bold;
            }

            #activity {
                background: #161425;
                border: 1px solid #35304f;
                border-radius: 6px;
                padding: 12px;
                color: #aaaac8;
                font-size: 13px;
            }

            #divineRateCorner {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }

            #attribution {
                color: #ffffff;
                font-size: 10px;
                margin-left: 6px;
            }

            #rateChip {
                background: rgba(10, 9, 18, 0.7);
                border: 1px solid #35304f;
                border-radius: 6px;
            }

            QPushButton#sidebarItem {
                color: #a8a4c8;
                background: transparent;
                border: 1px solid transparent;
                border-left: 3px solid transparent;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 10px;
                padding-left: 12px;
                text-align: left;
            }

            QPushButton#sidebarItem:hover {
                color: #eeeeff;
                background: #1c1a30;
                border: 1px solid #3a3560;
                border-left: 3px solid #6a5fd8;
            }

            QPushButton#sidebarItem:checked {
                color: #f0ecff;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2a2650, stop:1 #1c1a30
                );
                border: 1px solid #5a4fc8;
                border-left: 3px solid #9a8fff;
            }

            QPushButton#sidebarItem[collapsed="true"] {
                text-align: center;
                padding-left: 0px;
                font-size: 20px;
            }

            #overlayPanel {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #17152a, stop:1 #100e1c
                );
                border: 1px solid #5a4fc8;
                border-radius: 12px;
            }

            #overlayTitleBar {
                border-bottom: 1px solid #3a3560;
                padding-bottom: 12px;
            }

            #overlayTitle {
                font-family: __DISPLAY_FONT__;
                font-size: 19px;
                font-weight: bold;
                color: #f0ecff;
                letter-spacing: 2px;
            }

            QPushButton#overlayCloseButton {
                color: #aaaac8;
                background: #181828;
                border: 1px solid #3a3560;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 12px;
            }

            QPushButton#overlayCloseButton:hover {
                color: #eeeeff;
                border: 1px solid #6a5fd8;
            }

            #overlayPlaceholder {
                color: #8888a8;
                font-size: 15px;
            }

            QPushButton#fauxTab {
                color: #aaaac8;
                background: #181828;
                border: 1px solid #35304f;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 20px;
            }

            QPushButton#fauxTab:checked {
                color: #f0ecff;
                background: #292450;
                border: 1px solid #6a5fd8;
            }

            QPushButton#fauxTab:disabled {
                color: #55506f;
            }

            QPushButton#currencyToggle {
                color: #aaaac8;
                background: #181828;
                border: 1px solid #35304f;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 16px;
            }

            QPushButton#currencyToggle:hover {
                color: #eeeeff;
                border: 1px solid #6a5fd8;
            }

            QPushButton#currencyToggle:checked {
                color: #f0ecff;
                background: #292450;
                border: 1px solid #9a8bff;
            }

            QPushButton#primaryButton {
                color: #0b0b12;
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #b0a4ff, stop:1 #9a8bff
                );
                border: 1px solid #9a8bff;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 10px 20px;
            }

            QPushButton#primaryButton:hover {
                background: #c4baff;
            }

            QPushButton#secondaryButton {
                color: #aaaac8;
                background: transparent;
                border: 1px solid #35304f;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }

            QPushButton#secondaryButton:hover {
                color: #eeeeff;
                border: 1px solid #6a5fd8;
            }

            QPushButton#dangerButton {
                color: #ff9a9a;
                background: transparent;
                border: 1px solid #6a3535;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
            }

            QPushButton#dangerButton:hover {
                color: #ffffff;
                background: #5a1f1f;
                border: 1px solid #c85a5a;
            }

            #formLabel {
                color: #8888a8;
                font-size: 12px;
                font-weight: bold;
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
                background: #181828;
                border: 1px solid #35304f;
                border-radius: 5px;
                padding: 6px;
                font-size: 13px;
            }

            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
                border: 1px solid #6a5fd8;
            }

            QComboBox#itemPicker {
                font-size: 18px;
                padding: 10px;
            }

            QLineEdit:read-only {
                color: #8888a8;
                background: #12111f;
            }

        """

        self.setStyleSheet(
            stylesheet.replace("__DISPLAY_FONT__", self.display_font)
        )


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
        sound_player,
        backup_manager,
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

        title_bar_widget = QWidget()
        title_bar_widget.setObjectName("overlayTitleBar")

        title_bar = QHBoxLayout(title_bar_widget)
        title_bar.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("")
        self.title_label.setObjectName("overlayTitle")
        title_bar.addWidget(self.title_label)

        title_bar.addStretch()

        close_button = QPushButton("CLOSE")
        close_button.setObjectName("overlayCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self._handle_close)

        title_bar.addWidget(close_button)

        layout.addWidget(title_bar_widget)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self._pages = {}

        self.faustus_page = FaustusPage(
            trade_service, asset_service, sound_player, on_trade_changed
        )
        self._pages["FAUSTUS"] = self.faustus_page
        self.stack.addWidget(self.faustus_page)

        self.stash_page = StashPage(
            trade_service, asset_service, on_sell=self._sell_from_stash
        )
        self._pages["STASH"] = self.stash_page
        self.stack.addWidget(self.stash_page)

        self.trades_page = TradesPage(trade_service, on_trade_changed)
        self._pages["TRADES"] = self.trades_page
        self.stack.addWidget(self.trades_page)

        self.analytics_page = AnalyticsPage(trade_service)
        self._pages["ANALYTICS"] = self.analytics_page
        self.stack.addWidget(self.analytics_page)

        self.settings_page = SettingsPage(
            trade_service, asset_service, backup_manager, on_trade_changed
        )
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

        if section_name == "TRADES":
            self.trades_page.reset_filters()

        if section_name == "ANALYTICS":
            self.analytics_page.show_today()

    def _sell_from_stash(self, trade):
        self.faustus_page._start_close_trade(trade)
        self.show_section("FAUSTUS")

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

    def __init__(
        self,
        trade_service,
        asset_service,
        sound_player,
        on_trade_changed,
        parent=None
    ):
        super().__init__(parent)

        self.trade_service = trade_service
        self.asset_service = asset_service
        self.sound_player = sound_player
        self.on_trade_changed = on_trade_changed
        self._active_trade = None

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
        outer.setSpacing(15)

        self.item_input = QComboBox()
        self.item_input.setObjectName("itemPicker")
        self._setup_item_input(self.item_input)
        outer.addWidget(self.item_input)

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 100_000)
        self.quantity_input.setValue(1)
        self.quantity_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.price_input = QSpinBox()
        self.price_input.setRange(1, 10_000_000)
        self.price_input.setValue(1)
        self.price_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.total_input = QSpinBox()
        self.total_input.setRange(1, 2_000_000_000)
        self.total_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.buy_calc_linker = QuantityPriceTotalLinker(
            self.quantity_input, self.price_input, self.total_input
        )

        calc_row = QHBoxLayout()
        calc_row.setSpacing(15)
        calc_row.addLayout(
            self._build_labeled_field("QUANTITY", self.quantity_input)
        )
        calc_row.addLayout(
            self._build_labeled_field(
                "PRICE PER ITEM", self.price_input
            )
        )
        calc_row.addLayout(
            self._build_labeled_field("TOTAL", self.total_input)
        )
        outer.addLayout(calc_row)

        (
            currency_row,
            self.chaos_button,
            self.divine_button,
            self.buy_currency_group
        ) = self._build_currency_toggle()
        outer.addWidget(currency_row)

        self.gold_display = QLineEdit()
        self.gold_display.setReadOnly(True)
        self.gold_estimator = GoldEstimator(
            self.quantity_input,
            self.total_input,
            self.chaos_button,
            self.divine_button,
            self.gold_display,
            item_name_getter=lambda: self.item_input.currentText(),
            item_change_signal=self.item_input.currentIndexChanged
        )
        outer.addLayout(
            self._build_labeled_field(
                "GOLD SPENT", self.gold_display
            )
        )

        review_button = QPushButton("REVIEW BUY")
        review_button.setObjectName("primaryButton")
        review_button.clicked.connect(self._show_buy_confirm)

        outer.addWidget(review_button)
        outer.addStretch()

        return form_page

    def _build_labeled_field(self, caption, field_widget):
        column = QVBoxLayout()
        column.setSpacing(4)

        label = QLabel(caption)
        label.setObjectName("formLabel")
        column.addWidget(label)
        column.addWidget(field_widget)

        return column

    def _setup_item_input(self, combo_box):
        # Sourced entirely from the live poe.ninja catalog (Hugo's
        # call) — no free-text/custom entries. Chaos Orb is excluded:
        # it's the base currency everything is priced in, so it can't
        # sensibly be a trade target itself. Editable + a completer in
        # MatchContains mode gives live type-to-filter search over the
        # ~290 remaining items; NoInsert stops typed text becoming a
        # new item, and a fixed-text lookup on selection keeps
        # currentData() (the asset id) resolving correctly.
        combo_box.setEditable(True)
        combo_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo_box.setMaxVisibleItems(15)

        for asset in self.asset_service.active_assets():
            if asset.name == "Chaos Orb":
                continue

            if not is_gold_exchange_eligible(asset.name):
                continue

            icon_path = self.asset_service.icon_file_path(asset)
            icon = QIcon(QPixmap(str(icon_path))) if icon_path else QIcon()

            combo_box.addItem(icon, asset.name, userData=asset.id)

        completer = combo_box.completer()
        completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        def sync_selection(text):
            index = combo_box.findText(
                text, Qt.MatchFlag.MatchFixedString
            )

            if index >= 0:
                combo_box.setCurrentIndex(index)

        completer.activated.connect(sync_selection)

    def _build_currency_toggle(self):
        container = QWidget()

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        chaos_button = self._build_currency_button(
            "CHAOS", self.asset_service.get_asset_by_name("Chaos Orb")
        )
        divine_button = self._build_currency_button(
            "DIVINE", self.asset_service.get_asset_by_name("Divine Orb")
        )

        group = QButtonGroup(container)
        group.setExclusive(True)
        group.addButton(chaos_button)
        group.addButton(divine_button)

        chaos_button.setChecked(True)

        row.addWidget(chaos_button)
        row.addWidget(divine_button)
        row.addStretch()

        return container, chaos_button, divine_button, group

    def _build_currency_button(self, label, asset):
        button = QPushButton(f"  {label}")
        button.setObjectName("currencyToggle")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        if asset is not None:
            icon_path = self.asset_service.icon_file_path(asset)

            if icon_path is not None:
                button.setIcon(QIcon(QPixmap(str(icon_path))))
                button.setIconSize(QSize(20, 20))

        return button

    def _build_buy_confirm(self):

        confirm_page = QWidget()
        layout = QVBoxLayout(confirm_page)
        layout.setSpacing(15)

        self.confirm_card = QFrame()
        self.confirm_card.setObjectName("tradeCard")
        self.confirm_card_layout = QVBoxLayout(self.confirm_card)
        layout.addWidget(self.confirm_card)

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
        currency = self._current_buy_currency()
        price = self.price_input.value()
        gold = self.gold_estimator.current_gold_estimate()
        gold_display = f"{gold:,}" if gold is not None else "N/A"

        if currency == "DIVINE":
            unit_chaos = self.trade_service.divine_to_chaos(price)
            price_line = (
                f"{quantity} @ {price} Divine each "
                f"({unit_chaos:,}c each)"
            )
        else:
            unit_chaos = price
            price_line = f"{quantity} @ {price:,}c each"

        total_chaos = unit_chaos * quantity

        populate_confirm_card(
            self.confirm_card_layout,
            self.asset_service,
            item_name,
            "BUY",
            price_line,
            [
                ("TOTAL", f"{total_chaos:,}c"),
                ("GOLD SPENT", gold_display),
            ]
        )
        self.top_stack.setCurrentIndex(1)

    def _cancel_buy(self):
        self.top_stack.setCurrentIndex(0)

    def _current_buy_currency(self):
        return "DIVINE" if self.divine_button.isChecked() else "CHAOS"

    def _confirm_buy(self):

        asset_id = self.item_input.currentData()

        if asset_id is None:
            return

        item_name = self.item_input.currentText()
        quantity = self.quantity_input.value()
        currency = self._current_buy_currency()
        price = self.price_input.value()
        gold = self.gold_estimator.current_gold_estimate() or 0

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
        self.chaos_button.setChecked(True)
        self.buy_calc_linker.reset(quantity=1, price=1)

    # -----------------------------------------------------
    # SELL / CLOSE TRADE WORKFLOW
    # -----------------------------------------------------

    def _build_close_form(self):

        form_page = QWidget()
        outer = QVBoxLayout(form_page)
        outer.setSpacing(15)

        self.close_trade_title = QLabel("")
        self.close_trade_title.setObjectName("sectionTitle")
        outer.addWidget(self.close_trade_title)

        self.sell_quantity_input = QSpinBox()
        self.sell_quantity_input.setRange(1, 1)
        self.sell_quantity_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.sell_price_input = QSpinBox()
        self.sell_price_input.setRange(1, 10_000_000)
        self.sell_price_input.setValue(1)
        self.sell_price_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.sell_total_input = QSpinBox()
        self.sell_total_input.setRange(1, 2_000_000_000)
        self.sell_total_input.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )

        self.sell_calc_linker = QuantityPriceTotalLinker(
            self.sell_quantity_input,
            self.sell_price_input,
            self.sell_total_input
        )

        calc_row = QHBoxLayout()
        calc_row.setSpacing(15)
        calc_row.addLayout(
            self._build_labeled_field(
                "QUANTITY", self.sell_quantity_input
            )
        )
        calc_row.addLayout(
            self._build_labeled_field(
                "PRICE PER ITEM", self.sell_price_input
            )
        )
        calc_row.addLayout(
            self._build_labeled_field("TOTAL", self.sell_total_input)
        )
        outer.addLayout(calc_row)

        (
            sell_currency_row,
            self.sell_chaos_button,
            self.sell_divine_button,
            self.sell_currency_group
        ) = self._build_currency_toggle()
        outer.addWidget(sell_currency_row)

        self.sell_gold_display = QLineEdit()
        self.sell_gold_display.setReadOnly(True)
        self.sell_gold_estimator = GoldEstimator(
            self.sell_quantity_input,
            self.sell_total_input,
            self.sell_chaos_button,
            self.sell_divine_button,
            self.sell_gold_display,
            item_name_getter=(
                lambda: self._active_trade.item_name
                if self._active_trade else ""
            )
        )
        outer.addLayout(
            self._build_labeled_field(
                "GOLD RECEIVED", self.sell_gold_display
            )
        )

        review_button = QPushButton("REVIEW SELL")
        review_button.setObjectName("primaryButton")
        review_button.clicked.connect(self._show_sell_confirm)

        outer.addWidget(review_button)
        outer.addStretch()

        return form_page

    def _build_close_confirm(self):

        confirm_page = QWidget()
        layout = QVBoxLayout(confirm_page)
        layout.setSpacing(15)

        self.close_confirm_card = QFrame()
        self.close_confirm_card.setObjectName("tradeCard")
        self.close_confirm_card_layout = QVBoxLayout(self.close_confirm_card)
        layout.addWidget(self.close_confirm_card)

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
        self.sell_chaos_button.setChecked(True)
        self.sell_price_input.setValue(1)

        self.sell_tab.setChecked(True)
        self.top_stack.setCurrentIndex(3)

    def _current_sell_currency(self):
        return (
            "DIVINE" if self.sell_divine_button.isChecked() else "CHAOS"
        )

    def _show_sell_confirm(self):

        trade = self._active_trade

        if trade is None:
            return

        quantity = self.sell_quantity_input.value()
        currency = self._current_sell_currency()
        price = self.sell_price_input.value()
        gold = self.sell_gold_estimator.current_gold_estimate()
        gold_display = f"{gold:,}" if gold is not None else "N/A"

        if currency == "DIVINE":
            unit_chaos = self.trade_service.divine_to_chaos(price)
            price_line = (
                f"{quantity} @ {price} Divine each "
                f"({unit_chaos:,}c each)"
            )
        else:
            unit_chaos = price
            price_line = f"{quantity} @ {price:,}c each"

        total_chaos = unit_chaos * quantity
        cost_chaos = trade.unit_price_chaos * quantity
        profit = total_chaos - cost_chaos

        populate_confirm_card(
            self.close_confirm_card_layout,
            self.asset_service,
            trade.item_name,
            "SELL",
            price_line,
            [
                ("TOTAL", f"{total_chaos:,}c"),
                ("COST BASIS", f"{cost_chaos:,}c"),
                ("PROFIT", f"{profit:+,}c"),
                ("GOLD RECEIVED", gold_display),
            ]
        )
        self.top_stack.setCurrentIndex(4)

    def _cancel_sell(self):
        self.top_stack.setCurrentIndex(3)

    def _confirm_sell(self):

        trade = self._active_trade

        if trade is None:
            return

        quantity = self.sell_quantity_input.value()
        currency = self._current_sell_currency()
        price = self.sell_price_input.value()
        gold = self.sell_gold_estimator.current_gold_estimate() or 0

        sale = self.trade_service.sell_from_trade(
            trade_id=trade.id,
            quantity=quantity,
            currency=currency,
            entered_price=price,
            gold_received=gold
        )

        self.sound_player.play_for_profit(sale.profit)

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

    def __init__(self, trade_service, asset_service, on_sell, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service
        self.asset_service = asset_service
        self.on_sell = on_sell
        self._expanded_item = None

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
                0, 0, 1, 4
            )
            return

        headers = ["ITEM", "QUANTITY", "COST BASIS", ""]

        for column, text in enumerate(headers):
            header_label = QLabel(text)
            header_label.setObjectName("formLabel")
            self.grid.addWidget(header_label, 0, column)

        total_quantity = 0
        total_cost = 0

        row = 1

        for entry in summary:
            item_name = entry["item_name"]

            item_row = QHBoxLayout()

            icon_path = self._icon_path_for(item_name)

            if icon_path is not None:
                icon_label = QLabel()
                icon_label.setPixmap(
                    QPixmap(str(icon_path)).scaled(
                        20, 20,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
                item_row.addWidget(icon_label)

            item_label = QLabel(item_name)
            item_label.setObjectName("tradeTitle")
            item_row.addWidget(item_label)
            item_row.addStretch()

            self.grid.addLayout(item_row, row, 0)

            quantity_label = QLabel(str(entry["quantity"]))
            quantity_label.setObjectName("tradeInfo")
            self.grid.addWidget(quantity_label, row, 1)

            cost_label = QLabel(f"{entry['cost_chaos']:,}c")
            cost_label.setObjectName("tradeInfo")
            self.grid.addWidget(cost_label, row, 2)

            details_button = QPushButton(
                "HIDE" if self._expanded_item == item_name else "DETAILS"
            )
            details_button.setObjectName("secondaryButton")
            details_button.clicked.connect(
                lambda checked, name=item_name: self._toggle_details(name)
            )
            self.grid.addWidget(details_button, row, 3)

            total_quantity += entry["quantity"]
            total_cost += entry["cost_chaos"]

            row += 1

            if self._expanded_item == item_name:
                self.grid.addWidget(
                    self._build_detail_panel(item_name), row, 0, 1, 4
                )
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

    def _icon_path_for(self, item_name):
        asset = self.asset_service.get_asset_by_name(item_name)

        if asset is None:
            return None

        return self.asset_service.icon_file_path(asset)

    def _toggle_details(self, item_name):
        if self._expanded_item == item_name:
            self._expanded_item = None
        else:
            self._expanded_item = item_name

        self.refresh()

    def _build_detail_panel(self, item_name):
        panel = QFrame()
        panel.setObjectName("tradeCard")

        layout = QVBoxLayout(panel)

        trades = self.trade_service.open_trades_for_item(item_name)

        title = QLabel(f"{item_name} — {len(trades)} open trade(s)")
        title.setObjectName("formLabel")
        layout.addWidget(title)

        cards_row = QHBoxLayout()

        for trade in trades:
            cards_row.addWidget(
                build_trade_card(trade, interactive=True, on_sell=self.on_sell)
            )

        cards_row.addStretch()
        layout.addLayout(cards_row)

        return panel


# =============================================================
# TRADES PAGE — complete historical BUY/SELL activity
# =============================================================

class TransactionRow(QFrame):

    def __init__(self, transaction, trade_service, on_deleted, parent=None):
        super().__init__(parent)

        self.transaction = transaction
        self.trade_service = trade_service
        self.on_deleted = on_deleted

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

        self.delete_button = QPushButton("DELETE")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setVisible(False)
        self.delete_button.clicked.connect(self._delete)
        layout.addWidget(self.delete_button)

    def _toggle(self):
        expanded = not self.detail_label.isVisible()
        self.detail_label.setVisible(expanded)
        self.delete_button.setVisible(expanded)

    def _delete(self):
        confirm = QMessageBox.question(
            self,
            "Delete transaction",
            f"Delete this {self.transaction['type']} of "
            f"{self.transaction['item']}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            if self.transaction["type"] == "SELL":
                self.trade_service.delete_sale(self.transaction["sale_id"])
            else:
                self.trade_service.delete_trade(
                    self.transaction["trade_id"]
                )
        except TradeHasSalesError as error:
            QMessageBox.warning(self, "Can't delete this BUY", str(error))
            return

        self.on_deleted()

    @staticmethod
    def _summary_text(transaction):
        profit_part = (
            f"  ({transaction['profit']:+,}c)"
            if transaction["profit"] is not None
            else ""
        )

        type_display = TRANSACTION_TYPE_DISPLAY[transaction["type"]]

        return (
            f"{type_display:<6} "
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

    def __init__(self, trade_service, on_trade_changed, parent=None):
        super().__init__(parent)

        self.trade_service = trade_service
        self.on_trade_changed = on_trade_changed

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search item...")
        self.search_input.setMaximumWidth(220)
        self.search_input.textChanged.connect(self.refresh)
        filters_layout.addWidget(self.search_input)

        self.type_filter_group = QButtonGroup(self)
        self.type_filter_group.setExclusive(True)

        self.filter_all_button = QPushButton("ALL")
        self.filter_buy_button = QPushButton("BUY")
        self.filter_sell_button = QPushButton("SELL")

        for button in (
            self.filter_all_button,
            self.filter_buy_button,
            self.filter_sell_button
        ):
            button.setObjectName("fauxTab")
            button.setCheckable(True)
            button.clicked.connect(self.refresh)
            self.type_filter_group.addButton(button)
            filters_layout.addWidget(button)

        self.filter_all_button.setChecked(True)

        filters_layout.addStretch()

        layout.addLayout(filters_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("tradesScroll")

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setSpacing(8)

        scroll_area.setWidget(self.rows_container)

        layout.addWidget(scroll_area)

    def _current_type_filter(self):
        if self.filter_buy_button.isChecked():
            return "BUY"
        if self.filter_sell_button.isChecked():
            return "SELL"
        return "ALL"

    def reset_filters(self):
        self.search_input.clear()
        self.filter_all_button.setChecked(True)
        self.refresh()

    def refresh(self):
        clear_layout(self.rows_layout)

        query = self.search_input.text().strip().lower()
        type_filter = self._current_type_filter()

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
                    TransactionRow(
                        transaction,
                        self.trade_service,
                        on_deleted=self._handle_deleted
                    )
                )

        self.rows_layout.addStretch()

    def _handle_deleted(self):
        self.refresh()
        self.on_trade_changed()


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
        self.roi_box, self.roi_value = build_summary_box("% RETURN")
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
        # VIEWING BANNER (Today vs a selected historical day)
        # ---------------------------------------------------------

        viewing_row = QHBoxLayout()

        self.viewing_label = QLabel("Viewing: TODAY")
        self.viewing_label.setObjectName("sectionTitle")
        viewing_row.addWidget(self.viewing_label)
        viewing_row.addStretch()

        self.back_to_today_button = QPushButton("BACK TO TODAY")
        self.back_to_today_button.setObjectName("secondaryButton")
        self.back_to_today_button.clicked.connect(self.show_today)
        self.back_to_today_button.setVisible(False)
        viewing_row.addWidget(self.back_to_today_button)

        self.content_layout.addLayout(viewing_row)

        self.history_detail_box = QFrame()
        self.history_detail_box.setObjectName("tradeCard")
        self.history_detail_box.setVisible(False)

        detail_layout = QVBoxLayout(self.history_detail_box)

        self.history_detail_stats_label = QLabel("")
        self.history_detail_stats_label.setObjectName("tradeInfo")
        detail_layout.addWidget(self.history_detail_stats_label)

        self.history_detail_counts_label = QLabel("")
        self.history_detail_counts_label.setObjectName("tradeInfo")
        detail_layout.addWidget(self.history_detail_counts_label)

        self.content_layout.addWidget(self.history_detail_box)

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

        self.history_grid = QGridLayout()
        self.history_grid.setSpacing(10)
        self.content_layout.addLayout(self.history_grid)

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

        clear_layout(self.history_grid)

        closed_days = self.trade_service.closed_trading_days()

        if not closed_days:
            self.history_grid.addWidget(
                build_empty_state("No previous Trading Days yet."),
                0, 0, 1, 4
            )
        else:
            for index, day in enumerate(closed_days):
                card = build_history_day_card(
                    day, on_click=self.show_historical_day
                )

                row = index // 4
                column = index % 4

                self.history_grid.addWidget(card, row, column)

    def show_today(self):
        self.viewing_label.setText("Viewing: TODAY")
        self.back_to_today_button.setVisible(False)
        self.history_detail_box.setVisible(False)

    def show_historical_day(self, trading_day):
        date_label = trading_day.started_at.split(" ")[0]

        self.viewing_label.setText(f"Viewing: {date_label} (historical)")
        self.back_to_today_button.setVisible(True)
        self.history_detail_box.setVisible(True)

        roi_percent = (trading_day.snapshot_roi or 0) * 100

        self.history_detail_stats_label.setText(
            f"PROFIT: {trading_day.snapshot_realized_profit:+,}c   "
            f"% RETURN: {roi_percent:+.1f}%   "
            f"REVENUE: {trading_day.snapshot_revenue:,}c\n"
            f"INVENTORY VALUE: "
            f"{trading_day.snapshot_inventory_value:,}c   "
            f"GOLD SPENT: {trading_day.snapshot_gold_spent:,}   "
            f"AVG PROFIT/TRADE: "
            f"{trading_day.snapshot_average_profit_per_trade:+,.0f}c"
        )
        self.history_detail_counts_label.setText(
            f"New Trades: {trading_day.snapshot_new_trades}   "
            f"Carry-over Sales: {trading_day.snapshot_carryover_sales}   "
            f"Completed Trades: {trading_day.snapshot_completed_trades}"
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

    def __init__(
        self, trade_service, asset_service, backup_manager,
        on_settings_changed, parent=None
    ):
        super().__init__(parent)

        self.trade_service = trade_service
        self.asset_service = asset_service
        self.backup_manager = backup_manager
        self.on_settings_changed = on_settings_changed

        outer_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("tradesScroll")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)

        content_layout.addWidget(self._build_general_section())
        content_layout.addWidget(self._build_league_section())
        content_layout.addWidget(self._build_trading_day_section())
        content_layout.addWidget(self._build_rates_section())
        content_layout.addWidget(self._build_backups_section())
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

        self.tier_small_input = QSpinBox()
        self.tier_small_input.setRange(1, 1_000_000)
        self.tier_small_input.setValue(
            self.trade_service.sound_tier_small_max
        )
        self.tier_small_input.valueChanged.connect(
            self._update_sound_tiers
        )
        form.addRow("Small TINK up to (c)", self.tier_small_input)

        self.tier_medium_input = QSpinBox()
        self.tier_medium_input.setRange(1, 1_000_000)
        self.tier_medium_input.setValue(
            self.trade_service.sound_tier_medium_max
        )
        self.tier_medium_input.valueChanged.connect(
            self._update_sound_tiers
        )
        form.addRow("Medium TINK up to (c)", self.tier_medium_input)

        layout.addLayout(form)

        note = QLabel(
            "A SELL's profit picks the TINK tier: below \"small\" is a "
            "small TINK, below \"medium\" a bigger one, at/above it "
            "the biggest. Any loss plays the warning sound instead; "
            "exactly 0 profit is silent."
        )
        note.setObjectName("tradeInfo")
        note.setWordWrap(True)
        layout.addWidget(note)

        return section

    def _update_sound_tiers(self):
        self.trade_service.set_sound_tier_thresholds(
            self.tier_small_input.value(),
            self.tier_medium_input.value()
        )

    # -----------------------------------------------------
    # LEAGUE
    # -----------------------------------------------------

    def _build_league_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("LEAGUE")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.current_league_label = QLabel("")
        self.current_league_label.setObjectName("tradeInfo")
        layout.addWidget(self.current_league_label)

        switch_row = QHBoxLayout()

        self.league_select_input = QComboBox()
        self.league_select_input.addItems(
            available_league_names(self.trade_service, self.asset_service)
        )
        self.league_select_input.setCurrentText(
            self.trade_service.league.name
        )
        switch_row.addWidget(self.league_select_input)

        switch_button = QPushButton("SWITCH")
        switch_button.setObjectName("secondaryButton")
        switch_button.clicked.connect(self._switch_league)
        switch_row.addWidget(switch_button)

        layout.addLayout(switch_row)

        note = QLabel(
            "Switching leagues keeps every league's trades and "
            "history completely separate."
        )
        note.setObjectName("tradeInfo")
        note.setWordWrap(True)
        layout.addWidget(note)

        return section

    def _switch_league(self):
        league_name = self.league_select_input.currentText().strip()

        if not league_name:
            return

        self.trade_service.switch_league(league_name)
        self.asset_service.refresh_catalog(league_name)
        self.refresh()
        self.on_settings_changed()

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

        note = QLabel(
            "Changing the rate does not affect past transactions — "
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

    # -----------------------------------------------------
    # BACKUPS
    # -----------------------------------------------------

    def _build_backups_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("BACKUPS")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.last_backup_label = QLabel("")
        self.last_backup_label.setObjectName("tradeInfo")
        layout.addWidget(self.last_backup_label)

        note = QLabel(
            "One automatic backup is made per day on launch "
            "(database copy + SQL dump). Backups older than 15 days "
            "are pruned automatically."
        )
        note.setObjectName("tradeInfo")
        layout.addWidget(note)

        backup_button = QPushButton("BACK UP NOW")
        backup_button.setObjectName("secondaryButton")
        backup_button.clicked.connect(self._backup_now)
        layout.addWidget(backup_button)

        restore_title = QLabel("RESTORE FROM BACKUP")
        restore_title.setObjectName("formLabel")
        layout.addWidget(restore_title)

        restore_row = QHBoxLayout()

        self.restore_select_input = QComboBox()
        restore_row.addWidget(self.restore_select_input)

        restore_button = QPushButton("RESTORE")
        restore_button.setObjectName("dangerButton")
        restore_button.clicked.connect(self._restore_backup)
        restore_row.addWidget(restore_button)

        layout.addLayout(restore_row)

        restore_note = QLabel(
            "Overwrites all current data with the selected backup. "
            "The app closes immediately after — relaunch it to see "
            "the restored data."
        )
        restore_note.setObjectName("tradeInfo")
        restore_note.setWordWrap(True)
        layout.addWidget(restore_note)

        return section

    def _backup_now(self):
        self.backup_manager.create_backup()
        self.refresh()

    def _restore_backup(self):
        index = self.restore_select_input.currentIndex()

        if index < 0:
            return

        backup_path = self.restore_select_input.itemData(index)

        confirm = QMessageBox.warning(
            self,
            "Restore backup",
            "This will overwrite ALL current data with the selected "
            "backup and immediately close the app. This cannot be "
            "undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.backup_manager.restore_backup(backup_path)

        QMessageBox.information(
            self,
            "Restore complete",
            "The backup has been restored. The app will now close — "
            "relaunch it to see the restored data."
        )

        QApplication.instance().quit()

    # -----------------------------------------------------
    # ASSETS / CACHE MANAGEMENT
    # -----------------------------------------------------

    def _build_assets_section(self):
        section = QWidget()
        layout = QVBoxLayout(section)

        title = QLabel("ASSETS / CACHE MANAGEMENT")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.catalog_status_label = QLabel("")
        self.catalog_status_label.setObjectName("tradeInfo")
        layout.addWidget(self.catalog_status_label)

        button_row = QHBoxLayout()

        refresh_button = QPushButton("REFRESH CACHE")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self._refresh_cache)
        button_row.addWidget(refresh_button)

        rebuild_button = QPushButton("REBUILD CACHE")
        rebuild_button.setObjectName("dangerButton")
        rebuild_button.clicked.connect(self._rebuild_cache)
        button_row.addWidget(rebuild_button)

        layout.addLayout(button_row)

        note = QLabel(
            "Refresh picks up new/changed items from poe.ninja. "
            "Rebuild wipes every cached icon and re-downloads "
            "everything from scratch — only needed if images look "
            "wrong or missing."
        )
        note.setObjectName("tradeInfo")
        note.setWordWrap(True)
        layout.addWidget(note)

        return section

    def _refresh_cache(self):
        self.asset_service.refresh_catalog(self.trade_service.league.name)
        self.refresh()
        self.on_settings_changed()

    def _rebuild_cache(self):
        confirm = QMessageBox.question(
            self,
            "Rebuild cache",
            "This deletes every cached item icon and re-downloads "
            "them all from scratch. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.asset_service.rebuild_image_cache(self.trade_service.league.name)
        self.refresh()
        self.on_settings_changed()

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
        self.current_league_label.setText(
            f"Current league: {self.trade_service.league.name}"
        )

        self.trading_day_label.setText(
            f"Current Trading Day started: "
            f"{self.trade_service.trading_day.started_at}"
        )

        self.divine_current_label.setText(
            f"Current: 1 Divine = {self.trade_service.divine_rate}c"
        )
        self.divine_rate_input.setValue(self.trade_service.divine_rate)

        last_backup = self.backup_manager.last_backup_at()

        if last_backup is None:
            self.last_backup_label.setText("Last backup: never")
        else:
            self.last_backup_label.setText(
                f"Last backup: "
                f"{last_backup.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.restore_select_input.clear()

        for path, timestamp in self.backup_manager.list_backups():
            self.restore_select_input.addItem(
                timestamp.strftime("%Y-%m-%d %H:%M:%S"), userData=path
            )

        catalog_size = len(self.asset_service.active_assets())
        self.catalog_status_label.setText(
            f"Catalog: {catalog_size} items cached for "
            f"{self.trade_service.league.name}"
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

    def __init__(
        self,
        default_rate,
        trading_day_started_at,
        current_league,
        league_choices,
        display_font=None,
        parent=None
    ):
        super().__init__(parent)

        self.setWindowTitle("Divine Rate")
        self.setModal(True)
        self._confirmed = False
        self.chosen_rate = default_rate
        self.chosen_league = current_league
        self.new_day_chosen = False
        self.display_font = display_font or DISPLAY_FONT_FALLBACK

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        league_title = QLabel("LEAGUE")
        league_title.setObjectName("sectionTitle")
        layout.addWidget(league_title)

        self.league_input = QComboBox()

        if current_league not in league_choices:
            league_choices = [current_league] + list(league_choices)

        self.league_input.addItems(league_choices)
        self.league_input.setCurrentText(current_league)
        layout.addWidget(self.league_input)

        title = QLabel("DIVINE RATE")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        instructions = QLabel("1 Divine = [ ___ ] Chaos")
        layout.addWidget(instructions)

        self.rate_input = QSpinBox()
        self.rate_input.setRange(1, 10_000_000)
        self.rate_input.setValue(default_rate)
        layout.addWidget(self.rate_input)

        day_title = QLabel("TRADING DAY")
        day_title.setObjectName("sectionTitle")
        layout.addWidget(day_title)

        day_status = QLabel(f"Current day started: {trading_day_started_at}")
        layout.addWidget(day_status)

        day_row = QHBoxLayout()

        self.continue_button = QPushButton("CONTINUE")
        self.continue_button.setObjectName("dayToggle")
        self.continue_button.setCheckable(True)
        self.continue_button.setChecked(True)

        self.new_day_button = QPushButton("NEW DAY")
        self.new_day_button.setObjectName("dayToggle")
        self.new_day_button.setCheckable(True)

        self._day_group = QButtonGroup(self)
        self._day_group.setExclusive(True)
        self._day_group.addButton(self.continue_button)
        self._day_group.addButton(self.new_day_button)

        day_row.addWidget(self.continue_button)
        day_row.addWidget(self.new_day_button)
        layout.addLayout(day_row)

        confirm_button = QPushButton("CONFIRM")
        confirm_button.setObjectName("primaryButton")
        confirm_button.clicked.connect(self._confirm)
        layout.addWidget(confirm_button)

        stylesheet = """
            QDialog {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #17152a, stop:1 #100e1c
                );
                border: 1px solid #5a4fc8;
            }

            QLabel {
                color: #aaaac8;
                font-size: 14px;
            }

            #sectionTitle {
                font-family: __DISPLAY_FONT__;
                font-size: 19px;
                font-weight: bold;
                color: #c7bdff;
                letter-spacing: 1px;
            }

            QSpinBox {
                color: #eeeeff;
                background: #181828;
                border: 1px solid #35304f;
                border-radius: 5px;
                padding: 6px;
                font-size: 13px;
            }

            QPushButton#primaryButton {
                color: #0b0b12;
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #b0a4ff, stop:1 #9a8bff
                );
                border: 1px solid #9a8bff;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 10px 20px;
            }

            QPushButton#primaryButton:hover {
                background: #c4baff;
            }

            QPushButton#dayToggle {
                color: #a8a4c8;
                background: #181828;
                border: 1px solid #35304f;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
            }

            QPushButton#dayToggle:hover {
                border: 1px solid #6a5fd8;
            }

            QPushButton#dayToggle:checked {
                color: #f0ecff;
                background: #2a2650;
                border: 1px solid #9a8bff;
            }
        """

        self.setStyleSheet(
            stylesheet.replace("__DISPLAY_FONT__", self.display_font)
        )

    def _confirm(self):
        self.chosen_rate = self.rate_input.value()
        self.chosen_league = self.league_input.currentText().strip()
        self.new_day_chosen = self.new_day_button.isChecked()
        self._confirmed = True
        self.accept()

    def closeEvent(self, event):
        if self._confirmed:
            event.accept()
        else:
            event.ignore()


def main():

    run_migrations()

    app = QApplication(sys.argv)

    window = GalaxyHideout()
    window.show()

    # Prefer the live poe.ninja rate fetched during catalog refresh
    # (still just a pre-fill — the user can override it, Q26); fall
    # back to the last persisted rate if that fetch was unreachable.
    if window.live_divine_rate is not None:
        default_rate = round(window.live_divine_rate)
    else:
        default_rate = window.trade_service.divine_rate

    league_choices = available_league_names(
        window.trade_service, window.asset_service
    )

    startup_dialog = StartupDialog(
        default_rate=default_rate,
        trading_day_started_at=window.trade_service.trading_day.started_at,
        current_league=window.trade_service.league.name,
        league_choices=league_choices,
        display_font=window.display_font,
        parent=window
    )
    startup_dialog.exec()

    if startup_dialog.chosen_league != window.trade_service.league.name:
        window.trade_service.switch_league(startup_dialog.chosen_league)
        window.asset_service.refresh_catalog(startup_dialog.chosen_league)

    window.trade_service.set_divine_rate(startup_dialog.chosen_rate)

    if startup_dialog.new_day_chosen:
        window.trade_service.start_new_trading_day()

    window.refresh_all()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
