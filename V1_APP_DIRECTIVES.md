# DivineFlipper V1 — App Directives

> **Purpose:** This document is the implementation directive for DivineFlipper V1.
> It is derived from the supplied conversation history. Later explicit decisions override earlier suggestions.
>
> **Rule:** Do not invent behavior that is not specified here. If a requirement is marked `OPEN`, ask before implementing it.

---

## 1. Product Identity

- App name: **DivineFlipper**
- Purpose: Path of Exile currency-flipping/trading tracker.
- Visual identity:
  - PoE-inspired, but **not a copy of the PoE UI**.
  - Dark, cosmic/nebula/Galaxy Hideout atmosphere.
  - Divine Orb + cosmic/nebula identity.
  - Clean enough to remain practical and readable.
  - Loot-filter-inspired visual/audio feedback.
- Logo direction: between ornate PoE styling and a clean modern app icon.

---

## 2. Core Architecture

### 2.1 Galaxy Hideout is the desktop

The **Galaxy Hideout is the permanent background/home screen**.

It is NOT an Overview page and it is NOT a navigational sidebar destination.

The Hideout remains visible behind application overlays.

The Hideout should continue animating behind overlays.

### 2.2 Overlay model

V1 uses an in-app overlay/window system.

Important:

- Overlays do **not** need to be real OS windows.
- They only need to visually behave like application windows.
- They do not need to be movable in V1.
- **Only one overlay is open at a time in V1.**
- Closing an overlay reveals the Galaxy Hideout underneath.
- Overlays should cover roughly **90% of the application at most**, leaving approximately a 10% Hideout border.
- Hideout elements are not dynamically removed when an overlay opens; they are simply naturally covered if the overlay is over them.
- The Hideout continues animating behind overlays.

### 2.3 Navigation

The **right sidebar is the only navigation mechanism in V1**.

Hideout objects are decorative/informational in V1 and are **not clickable**.

Architect the objects so they could become interactive in a future version without redesigning the Hideout.

---

# 3. Right Sidebar

The final V1 sidebar is:

1. **FAUSTUS**
2. **STASH**
3. **TRADES**
4. **ANALYTICS**
5. **SETTINGS**

There is **no Hideout button**.

There is **no Overview button**.

There is **no separate Assets button**.

There is **no separate Rates button**.

Rates live inside Settings.

Assets are primarily backend/internal infrastructure.

---

# 4. Hideout HUD

The Galaxy Hideout has a permanent HUD/information layer.

The intended Hideout information includes:

- Profit
- Inventory/Stash count
- Open Trades count
- Trading Stash summary
- Today's Profit
- ROI
- Gold
- Recent Activity
- Total realized profit / useful profit information
- Recent trading information
- Best flip / high-value feedback where appropriate

The Hideout should answer:

> "How is my flipping going right now?"

quickly, without becoming a full analytics dashboard.

The Hideout should prioritize visual atmosphere + quick information.

### 4.1 Hideout objects are display-only in V1

The following are informational/decorative:

- Stash
- Open Trades
- Today's Profit
- Recent Activity
- Other Hideout stations/objects

They do not open overlays when clicked in V1.

---

# 5. Faustus

**Faustus is the main active trading interface.**

The Faustus overlay represents the user's current open trading desk.

It contains currently open BUY trades and provides the path to sell them.

Conceptually:

```text
Galaxy Hideout
    |
    +-- FAUSTUS overlay
          |
          +-- Open BUY trades
          |
          +-- SELL
```

All currently open BUY trades are represented as compact cards.

Faustus should be optimized for quickly managing active flips.

---

# 6. Faustus BUY / SELL Interface

The original trading interface decision was:

- Use **BUY | SELL tabs** at the top of the trading interface.

Faustus is therefore not just a passive list.

It is the primary trading workflow.

---

# 7. Open Trade Concept

A major architectural distinction was established:

> **Trade = the flip itself**
>
> **Transaction = an individual BUY/SELL event belonging to that flip**

Example:

```text
OPEN TRADE
Reflecting Mist

Bought: 10
Buy price: 400c
Invested: 4,000c

Sold: 6
Remaining: 4

Current target: 600c
Potential profit: +800c
```

A trade may therefore contain multiple SELL transactions.

When all quantity belonging to the trade has been sold, the trade closes.

---

# 8. Open Trade Cards

Open trades should be compact and useful.

Expected information includes:

- Item
- Quantity bought
- Quantity sold
- Remaining quantity
- Buy price
- Current/target sell price
- Invested amount
- Potential profit
- SELL action

The exact final visual styling is implementation work, not a change to the architecture.

---

# 9. BUY Workflow

Opening a BUY trade should be simple.

The BUY flow records at minimum:

- Item
- Quantity
- Buy price
- Currency
- Gold spent where applicable

The transaction confirmation should show the transaction information before saving.

Example information:

```text
Transaction information
-----------------------
Item: Reflecting Mist
Type: BUY
Quantity: 10
Currency: CHAOS
Price: 400
Gold spent: 1,000,000
```

Gold defaults to **0** when appropriate.

---

# 10. SELL / Close Trade Workflow

The agreed V1 interaction is:

**Open Trade → CLOSE TRADE → enter actual sale details → confirm**

Do not silently convert a trade into a SELL without the close-trade interaction.

A SELL records an actual sale transaction.

The backend then calculates realized profit using FIFO.

---

# 11. Partial Sales

Partial selling is supported.

Example:

```text
Bought: 10
Sold: 6
Remaining: 4
```

The trade remains open while quantity remains.

When the remaining quantity reaches zero, the trade closes automatically.

For the SELL window, the default sell quantity should be the **remaining quantity** so selling the whole position is fast, while still allowing the user to reduce the quantity for a partial sale.

---

# 12. Trades Overlay

The **TRADES** sidebar entry opens a dedicated overlay.

V1 TRADES is for **complete historical BUY/SELL activity**.

It is not the same thing as Faustus:

- **Faustus** = currently open active flips.
- **Trades** = historical BUY/SELL activity.

The historical Trades view should support:

- Table/list display
- Filters
- Search
- Expandable transaction details

The user should be able to inspect individual transaction details.

---

# 13. Recent Activity

Hideout Recent Activity shows the **last 5 BUY or SELL transactions**.

Do not include:

- Rate changes
- Gold-only events
- Other non-trading events

For each activity entry, the intended information is:

- BUY/SELL
- Item
- Quantity
- Total price
- Profit for SELL transactions

Example:

```text
RECENT ACTIVITY

BUY   Reflecting Mist ×10    4,000c
SELL  Divine Orb ×2            440c
BUY   Scarab ×30             1,200c
SELL  Reflecting Mist ×5     3,000c
BUY   Essence ×20              800c
```

---

# 14. Stash

The **STASH** sidebar entry opens the trading/inventory stash overlay.

Stash represents currently held inventory.

Inventory is rebuilt from transaction history.

BUY transactions add inventory.

SELL transactions remove inventory using FIFO.

### 14.1 Inventory display

Inventory should prioritize:

- Item
- Quantity
- FIFO cost basis

Cost basis means what the remaining inventory actually cost.

Current market value is a separate valuation concept.

Do not force market value into the basic Inventory view unless the final design explicitly calls for it.

### 14.2 Item visual style

Where item icons are available:

- Use PoE-inspired item presentation.
- Quantity should be visually overlaid on/near the item icon in a PoE-like manner.
- Item details can open an item detail panel.
- Item detail can provide the SELL action where appropriate.

---

# 15. Analytics

The **ANALYTICS** sidebar entry opens the deeper statistics area.

V1 Analytics should be broad and include:

- Profit
- ROI
- Trading volume
- Item performance
- Charts
- Time periods
- Historical trading-day information

Analytics is where detailed information belongs so the Hideout does not become cluttered.

---

# 16. Trading Day

DivineFlipper uses a user-controlled **Trading Day** concept.

A Trading Day does NOT automatically change at midnight.

At startup, the app asks whether to start a new Trading Day or continue the previous one.

Example:

```text
START TRADING DAY?

Previous Day
Profit: +4,250c
Trades: 14

[ START NEW DAY ]    [ CONTINUE ]
```

### 16.1 Startup sequence

The established startup flow is:

```text
STARTUP

1. START NEW TRADING DAY?
   [ NEW DAY ] [ CONTINUE ]

2. DIVINE RATE
   1 Divine = [ ___ ] Chaos
   [ CONFIRM ] [ SKIP ]

3. GALAXY HIDEOUT
```

The Divine rate is asked at app launch.

If continuing the previous Trading Day, the same Trading Day continues.

Starting a new Trading Day resets **Today's Profit** to 0 while preserving total/historical profit.

---

# 17. Trading Day History

Trading Day History lives inside Analytics.

A previous day can be selected and inspected without changing the current day.

Historical day statistics are frozen when the day closes.

The historical record includes the agreed statistical snapshot, including:

- New Trades
- Carry-over Sales
- Realized Profit
- ROI
- Revenue
- Inventory Value
- Gold Spent
- Average Profit per Trade
- Number of trades / relevant trading-day counts

Historical values such as Profit, Revenue, ROI, Average Profit/Trade and Gold Spent are frozen rather than recalculated later.

---

# 18. New Trades vs Carry-over Sales

Analytics distinguishes:

- **New Trades** — trades initiated during the Trading Day.
- **Carry-over Sales** — sales during the day from trades/inventory initiated earlier.

This distinction is important for evaluating a Trading Day fairly.

A partially sold new trade contributes the portion actually sold when calculating that day's ROI, consistent with the established accounting rules.

Incomplete trades do not count as completed trades for Average Profit per Trade.

---

# 19. ROI

ROI is based on **trading profit versus item cost**.

Gold remains a separate statistic.

Gold is NOT subtracted from normal Chaos trading profit when calculating ROI.

Conceptually:

```text
ROI = Trading Profit / Relevant Item Cost
```

The exact aggregation formula for multi-trade/day views must follow the accounting model rather than inventing a new definition.

---

# 20. Profit Accounting

Core profit:

```text
Profit = Sales Revenue - FIFO Purchase Cost
```

SELL transactions use FIFO.

Gold is separate.

Do NOT calculate:

```text
Profit = Revenue - FIFO Cost - Gold
```

Instead:

```text
Profit = Revenue - FIFO Cost
Gold = separate statistic
```

---

# 21. FIFO

FIFO = First In, First Out.

Example:

```text
BUY 10 Reflecting Mist @ 400c
BUY  5 Reflecting Mist @ 500c

SELL 12 @ 600c
```

FIFO cost:

```text
10 × 400c = 4,000c
 2 × 500c = 1,000c

FIFO Cost = 5,000c
```

Revenue:

```text
12 × 600c = 7,200c
```

Profit:

```text
7,200c - 5,000c = +2,200c
```

FIFO is backend/accounting logic.

It should not dominate the user-facing UI.

---

# 22. Gold

Gold is an **independent ledger/statistic**.

Gold is NOT inventory.

There is:

- No Gold inventory.
- No Gold FIFO.
- No Gold cost basis.
- No Gold subtraction from Chaos trading profit.

Gold is calculated from transaction-level Gold amounts.

Conceptually:

```text
Transaction
    |
    +-- Gold spent/received
          |
          v
      Gold statistics
```

Gold totals can be aggregated across BUY and SELL transactions.

Where useful, display:

- Gold on BUYs
- Gold on SELLs
- Total Gold

---

# 23. Gold Rate

Gold conversion is stored with transactions when applicable.

Example:

```text
1,000,000 Gold = 200 Chaos
```

Historical transaction values must not change merely because the current Gold rate changes.

The current Gold rate is a UI/accounting convenience for new entries.

Rates are not a standalone sidebar section.

They belong under:

```text
SETTINGS
  |
  +-- Rates
       +-- Divine Rate
       +-- Gold Rate
```

---

# 24. Divine Rate

Divine conversion uses:

```text
1 Divine = X Chaos
```

Example:

```text
1 Divine = 204 Chaos
```

Historical transaction conversions are preserved.

Changing the current Divine rate must not retroactively alter previous transactions.

The app asks for the Divine rate during startup.

The system should be designed so rate sourcing can be extended later without hard-coding a provider throughout the application.

---

# 25. Currency / Asset Catalog

The application has an internal asset/catalog system.

Assets are backend infrastructure, not a V1 navigation destination.

Conceptually:

```text
AssetProvider
      |
      v
Asset Catalog
      |
      +-- Faustus
      +-- Stash
      +-- Item search
      +-- Images
```

### 25.1 Historical assets

If an asset is no longer active:

- Remove it from the active catalog.
- Preserve it when historical transactions reference it.
- Never destroy historical trade data because PoE changes.

### 25.2 Missing images

If a historical asset has no provider image:

1. Use the locally cached image if available.
2. Otherwise use a generic placeholder.

### 25.3 Image storage

Downloaded item images should be stored in the local application filesystem/cache.

The database should store the image path/reference, not large image blobs.

---

# 26. Currency availability

Unavailable currencies should be hidden from new transaction selection while preserving historical data.

If a currency disappears from the current league:

- It should not be selectable for new trades.
- Historical trades remain intact.
- Usage/favorite/history information remains preserved.
- If it becomes available again, it may return automatically.

---

# 27. Settings

The V1 Settings overlay contains:

```text
SETTINGS

General
Rates
Assets / Cache Management
Appearance
```

However, Assets remain technical/internal.

Settings may expose cache operations such as:

- Refresh cache
- Rebuild cache

Do not expose the raw asset catalog as a user-facing database.

### 27.1 General settings

Do NOT invent separate settings for:

- Currency display
- Startup behavior

Those are defaults/implementation behavior rather than user preference settings.

General should contain only the previously agreed general preferences, especially sound/notification behavior.

---

# 28. Sound & Loot-filter Feedback

The app should feel like:

> **PoE loot filter + trading terminal + custom visual style.**

Possible feedback includes:

- Large profit → strong loot-filter-style **TINK**
- Very good flip → stronger visual/audio feedback
- Bad trade → warning effect
- Profit numbers can animate/pop
- Rare/high-value transactions can have special styling

The user should eventually be able to customize:

- Profit thresholds
- Which effects trigger
- Sound behavior

The exact final sound library and threshold values should be implementation/configuration work unless explicitly locked elsewhere.

---

# 29. Hideout Overlay Visual Rules

When an overlay opens:

- Galaxy Hideout remains behind it.
- Galaxy Hideout continues animating.
- Overlay occupies approximately 90% maximum.
- A clean Hideout border remains visible.
- HUD elements are not programmatically removed merely because they are covered.
- Only one overlay exists at a time in V1.
- Closing the overlay returns directly to the Hideout.

Overlay closing animation can be decided during implementation/visual testing.

---

# 30. Data Integrity

Historical data must be protected.

Important principles:

- Never destroy historical transactions because an item/currency becomes inactive.
- Transaction-level rates preserve historical accounting.
- Trading Day historical snapshots are immutable after closing.
- Deleting transactions requires strong confirmation.
- After deletion, accounting/inventory/statistics must be fully recalculated.
- BUY transactions that are already consumed by FIFO require appropriate protection or dependent transaction handling.

---

# 31. Current Backend Foundation

The existing backend already provides the foundation for:

- Transaction storage
- BUY/SELL records
- FIFO
- Inventory reconstruction
- Gold conversion
- Divine conversion
- Profit calculations
- Backups
- Transaction management
- JSON persistence

The GUI should be connected to this accounting foundation rather than duplicating accounting logic inside the UI.

---

# 32. Technology

Current project stack:

- Python
- PySide6
- Local persistence
- Existing JSON backend during the current V1 implementation stage

The project currently contains backend/storage infrastructure and a PySide6 UI.

The UI should progressively consume the backend rather than creating a second independent data model.

---

# 33. Implementation Priorities

Build in this order:

1. Galaxy Hideout structure
2. Right sidebar
3. Overlay system
4. Faustus/open-trade interface
5. BUY workflow
6. SELL/CLOSE TRADE workflow
7. Stash/inventory overlay
8. Trades/history overlay
9. Analytics
10. Settings
11. Real backend integration
12. Asset/cache system
13. Sounds/loot-filter feedback
14. Final PoE/cosmic visual polish

Functionality comes before final styling.

---

# 34. V1 Scope Boundaries

Do NOT add the following unless explicitly approved:

- Clickable Hideout objects
- Multiple simultaneous overlays
- Movable overlay windows
- Separate Assets sidebar
- Separate Rates sidebar
- Currency display settings
- Startup behavior settings
- Gold as inventory
- Gold FIFO
- Gold deducted from trading profit
- Destructive removal of historical assets
- UI exposure of backend-only asset infrastructure

---

# 35. Important Terminology

Use these terms consistently:

- **Galaxy Hideout** = permanent desktop/home background.
- **Faustus** = active open-trade trading desk.
- **Stash** = current inventory/held items.
- **Trade** = the overall flip.
- **Transaction** = an individual BUY/SELL event.
- **Trades** = historical transaction/activity view.
- **Analytics** = deep statistics/history.
- **Trading Day** = user-controlled trading session/day.
- **Gold** = independent ledger/statistic.
- **FIFO** = backend inventory/profit accounting method.

---

# 36. Technical Foundations

## 36.1 Database — SQLite + SQLAlchemy

The prototype currently uses JSON persistence, but the planned application architecture uses a real relational database:

- **SQLite** is the V1/V2 local database.
- **SQLAlchemy** is the database/ORM layer.
- The database is a local file, intended to be `data/divineflipper.db`.
- No database server is required.
- SQLite is the source of truth for user-created trading data after migration from the prototype JSON backend.
- Database access belongs behind repositories/services; UI code must not contain SQL or accounting rules.
- Enable SQLite foreign-key enforcement.
- Use database transactions for multi-step writes so a trade operation cannot leave partial state.
- Use migrations for schema changes rather than manually rewriting the database.
- Backups must operate on the database/data layer and must not destroy historical records.

The intended conceptual relationship is:

```text
Trading Day
    |
    +-- Trade
          |
          +-- Transactions (BUY / SELL)

Transactions -> FIFO -> Inventory / Profit / ROI

Transactions -> Gold ledger/statistics

Asset Catalog -> item metadata / image references
```

### Prototype compatibility

The current working prototype contains `tracker.py`, `backend/storage.py`, `data.json` and PySide6 UI code. This prototype is allowed to continue working while the UI is built. The JSON backend is **not** the desired final persistence architecture.

The refactor must preserve existing user data during migration. Never silently discard prototype transactions.

## 36.2 Application architecture

Use clear separation of concerns:

```text
PySide6 UI
    |
    v
Application / UI controllers
    |
    v
Services / domain logic
    |
    +--> TradeService
    +--> Inventory/FIFO service
    +--> Analytics service
    +--> TradingDay service
    +--> RateService
    +--> AssetService
    |
    v
Repositories
    |
    v
SQLite / SQLAlchemy
```

Rules:

- UI displays state and collects user input.
- Domain/services perform accounting and business rules.
- Repositories handle persistence.
- Do not duplicate FIFO/profit/ROI calculations inside widgets.
- UI refreshes from backend/domain state after successful operations.

## 36.3 Data model requirements

The database must be designed around the established concepts, not around the prototype's JSON shape.

At minimum the model must be capable of representing:

- Leagues / league context
- Trading Days
- Trades (the overall flip)
- Transactions (BUY / SELL events)
- Items/assets
- FIFO relationships/allocation information
- Gold measurements associated with transactions
- Divine/Chaos rate snapshots used by transactions
- Application/global settings
- Asset/image metadata and cache references
- Historical Trading Day snapshots

The exact normalized schema/table names are implementation work, but the relationships above are architectural requirements.

## 36.4 League separation

The application must distinguish global settings from league-specific economic/accounting data.

Global examples:

- UI preferences
- Sound settings
- Theme/appearance
- Asset/cache settings
- Backup settings

League-specific examples:

- Divine rate history
- Trading Days
- Trades
- Inventory derived from trades
- Profit
- ROI
- Gold measurements
- League asset availability

Historical data must remain associated with the league in which it occurred.

## 36.5 API / rate source

For V1, **poe.ninja is the default automatic market/reference-rate provider** for economy data, while the application must hide the provider behind a `RateService` / provider interface.

Conceptually:

```text
RateService
    |
    +-- PoeNinjaRateProvider   <- V1 default
    |
    +-- Future provider(s)
```

The provider architecture must allow another source to be added later without rewriting UI/accounting code.

The Divine reference rate is represented as:

```text
1 Divine = X Chaos
```

The app asks for/records the Divine rate during startup according to the established Trading Day startup flow. A manually confirmed rate is stored as a transaction/day snapshot as appropriate, so changing the current rate never changes historical accounting.

The exact live endpoint/request implementation is an engineering detail and must be isolated in the provider rather than scattered through the application.

## 36.6 Asset catalog and PoE item data

The asset catalog is backend infrastructure.

The intended design is:

```text
AssetProvider
    |
    v
Asset Catalog
    |
    +-- Faustus item selection
    +-- Stash/inventory
    +-- Search
    +-- Images
```

Catalog categories should come from the downloaded/current catalog rather than being permanently hard-coded. This allows new tradable categories to appear when the catalog updates.

The application must distinguish:

- active/current assets available for new transactions
- historical assets referenced by existing transactions

Inactive assets are removed from new selection but historical references remain valid.

## 36.7 Item images — CDN + local cache

The established image strategy is hybrid:

1. Obtain item image metadata/URLs from the PoE data/catalog source.
2. The actual icon may come from the official PoE CDN referenced by that data.
3. Download the image when first required and cache it locally.
4. Reuse the local cached image on later launches.
5. If offline and the image is cached, use the cache.
6. If no image is available, use a generic placeholder.

The UI must not depend directly on remote image URLs.

Conceptually:

```text
Item requested
      |
      +--> local cache exists? --> use cache
      |
      +--> no cache + internet --> download from PoE CDN --> cache --> use
      |
      +--> no cache + offline --> placeholder
```

The database stores an image reference/path/metadata, **not image blobs**.

Prefer stable asset/item identifiers for cache keys and relative/local references rather than absolute machine-specific filesystem paths.

The application should not require internet access for core operation once required assets are cached.

Before distributing cached/ bundled PoE assets, verify applicable PoE/CDN usage and redistribution terms.

## 36.8 Application assets vs user data

Keep shipped application assets separate from user data.

Intended architecture:

```text
DivineFlipper/
├── app/
├── assets/
│   ├── items/
│   ├── currencies/
│   ├── sounds/
│   ├── fonts/
│   └── ui/
└── data/
    └── divineflipper.db
```

The exact packaged layout may change during desktop packaging, but the separation is mandatory.

User data must survive application updates/reinstallation.

## 36.9 Offline-first behavior

Core application functionality should work without an internet connection:

- viewing existing trades
- viewing inventory
- viewing analytics/history
- viewing cached images
- recording transactions
- using existing rates/settings

Network-dependent features such as refreshing economy/catalog data may be unavailable offline and should fail gracefully rather than breaking the application.

## 36.10 Backup and recovery

The application must provide reliable user-data backup/restore behavior.

Requirements:

- Backups must preserve historical trading data.
- Backup creation must not modify the live accounting state.
- The application should be able to recover from an interrupted/corrupt write without silently losing data.
- Database/schema migrations must be compatible with backup/recovery.
- The final backup format and restore UI remain an implementation detail unless explicitly locked later.

---

# 37. Visual / UX Directives

## 37.1 Overall visual language

DivineFlipper should feel like:

> **Path of Exile loot filter + trading terminal + cosmic desktop application.**

Use:

- dark interface
- cosmic/nebula/galaxy background
- deep purples/blues/dark neutrals as the visual family
- subtle borders and glow
- readable high-contrast text
- restrained ornamentation
- PoE-inspired item presentation without copying the PoE interface

The app should look premium and atmospheric, but remain fast to read while trading.

## 37.2 Galaxy Hideout

The Hideout is the desktop itself.

- Large animated Galaxy/Nebula environment.
- Animation continues constantly.
- No background dimming when an overlay opens.
- Hideout remains visible around overlays.
- HUD remains present unless naturally covered.
- Hideout objects are decorative/display-only in V1.

The Hideout should not look like a conventional dashboard.

## 37.3 Right sidebar

The sidebar is on the **right** side.

V1 entries, top to bottom:

```text
FAUSTUS
STASH
TRADES
ANALYTICS
SETTINGS
```

There is no Overview button and no Hideout button.

The sidebar is the navigation mechanism.

Sidebar item requirements:

- clear selected/active state
- hover state
- readable labels
- consistent spacing
- PoE/cosmic visual treatment
- should remain usable at the application's supported window size

The earlier prototype's simple labels are structural placeholders only; final styling comes later.

## 37.4 Overlay frame

All sidebar destinations open as centered in-app overlays.

Overlay rules:

- centered
- approximately 90% maximum of the application
- approximately 10% Hideout border remains visible
- no OS-level movable/resizable window requirement in V1
- only one overlay at a time
- close button is available and returns directly to the Hideout
- no dimming layer unless explicitly approved later

Exact border ornamentation, title-bar treatment and animation remain visual implementation work.

## 37.5 Faustus controls

Faustus is the active trading desk.

At the top of the trading interface use:

```text
BUY | SELL
```

tabs.

BUY is the workflow for opening a new flip.

SELL is the workflow for selling/closing an existing open trade.

Open trades are displayed as compact cards containing, where applicable:

- item icon/name
- bought quantity
- sold quantity
- remaining quantity
- buy price
- current/target sell price
- invested amount
- potential profit
- SELL action

The primary action must be visually obvious.

## 37.6 BUY controls

BUY must collect at minimum:

- item
- quantity
- buy price
- currency
- Gold spent where applicable

Currency selection must support the established Chaos/Divine workflow.

Gold should default to 0 where appropriate.

Before saving, show a confirmation/summary of the entered transaction.

## 37.7 SELL controls

Selling starts from an open trade and uses:

```text
Open Trade
    -> CLOSE TRADE
    -> enter actual sale details
    -> confirm
```

The default sell quantity is the remaining quantity, but the user can enter a smaller quantity for a partial sale.

Partial sale:

```text
Bought: 10
Sold: 6
Remaining: 4
```

The trade stays open until remaining quantity reaches zero.

## 37.8 Stash controls

Stash is the current held inventory view.

Prioritize:

- item icon/name
- quantity
- FIFO cost basis

Item icons should use PoE-inspired presentation, with quantity visually overlaid/near the icon where practical.

Item details may provide a SELL action.

Do not overload the basic Stash view with every possible market statistic.

## 37.9 Trades controls

Trades is historical activity, not the active trading desk.

Provide:

- table/list of historical BUY/SELL transactions
- search
- filters
- expandable transaction details
- clear transaction type
- item
- quantity
- total price
- profit on SELLs
- date/time

Faustus = open active flips.
Trades = completed/historical BUY/SELL activity.

## 37.10 Analytics controls

Analytics is the detailed statistics area.

It should include the agreed concepts:

- Profit
- ROI
- trading volume
- item performance
- charts
- selectable time periods
- Trading Day history
- New Trades vs Carry-over Sales
- historical snapshots
- Gold statistics
- relevant averages/counts

Analytics should be information-dense but organized, not a wall of numbers.

Exact chart types and final placement remain open until implementation/design testing.

## 37.11 Settings controls

Settings contains:

```text
General
Rates
Assets / Cache Management
Appearance
```

Rates:

- Divine Rate
- Gold Rate
- historical rate handling

Assets/cache management may provide:

- Refresh cache
- Rebuild cache

General should focus on established preferences, especially sound/notification behavior.

Do not create separate settings for currency display or startup behavior unless explicitly approved.

## 37.12 Sound / feedback

The desired feedback language is loot-filter inspired.

Examples:

- large profit -> strong TINK
- very good flip -> stronger effect
- bad trade -> warning effect
- profit values can animate/pop
- high-value/rare transactions can receive special styling

The user should eventually be able to configure:

- profit thresholds
- which effects trigger
- sound behavior

Do not invent exact sound files or threshold values before they are locked.

## 37.13 Buttons and interaction principles

Every interactive action must have a clear primary/secondary hierarchy.

Primary actions:

- BUY
- SELL / CLOSE TRADE
- CONFIRM
- START NEW DAY / CONTINUE where applicable

Secondary actions:

- CANCEL
- BACK
- CLOSE
- SKIP where applicable

Destructive actions such as deleting a transaction require explicit confirmation.

Avoid adding buttons solely because a conventional dashboard would have them. The Hideout is not a navigation dashboard.

---

# 38. Startup / Trading Day UX

Startup sequence:

```text
1. START NEW TRADING DAY?
   [ NEW DAY ] [ CONTINUE ]

2. DIVINE RATE
   1 Divine = [ ___ ] Chaos
   [ CONFIRM ] [ SKIP ]

3. GALAXY HIDEOUT
```

Trading Day does not automatically roll over at midnight.

When continuing, the same Trading Day continues.

When starting a new day, Today's Profit resets to zero while lifetime/historical totals remain intact.

The established discussion also supports starting a Trading Day with the current time by default while allowing a custom date/time where that decision is implemented.

---

# 39. Accounting Directives — Expanded

## 39.1 Profit

```text
Profit = Sales Revenue - FIFO Purchase Cost
```

Do not subtract Gold from Chaos trading profit.

## 39.2 FIFO

SELL transactions consume inventory in First In, First Out order.

Example:

```text
BUY 10 @ 400c
BUY 5  @ 500c
SELL 12 @ 600c

FIFO cost = 10×400 + 2×500 = 5,000c
Revenue   = 12×600 = 7,200c
Profit    = +2,200c
```

FIFO belongs in domain/backend logic, not UI widgets.

## 39.3 Gold

Gold is an independent statistic/ledger.

There is:

- no Gold inventory
- no Gold FIFO
- no Gold cost basis
- no Gold subtraction from trading profit

Gold spent/received is stored at transaction level when applicable.

Historical Gold-to-Chaos conversion must not change when the current Gold rate changes.

## 39.4 Divine conversion

Historical transactions preserve the rate used at the time.

Changing the current Divine rate must not retroactively modify existing transactions.

## 39.5 Inventory

Inventory is derived from transaction history.

BUY adds inventory.

SELL removes inventory via FIFO.

Current market valuation is distinct from FIFO cost basis.

---

# 40. Data / UI Synchronization

The Hideout HUD must update from the same backend state used by Faustus, Stash, Trades and Analytics.

There must not be separate fake/demo state once backend integration begins.

After a successful transaction:

```text
Database update
      |
      v
Domain/accounting recalculation
      |
      v
UI refresh
      |
      +--> Hideout HUD
      +--> Faustus
      +--> Stash
      +--> Trades
      +--> Analytics
```

The UI should never calculate a different profit from the backend.

---

# 41. Packaging / Portability

The long-term V1 desktop goal is a portable desktop application rather than a Python script users must configure manually.

Target characteristics:

- packaged executable/application
- local SQLite database
- local asset cache
- no required SQLite server
- no required Python installation for end users
- no dependence on remote image URLs for normal operation
- user data stored separately from application binaries/assets

The exact packaging technology is open until implementation, but the architecture must not make packaging difficult.

---

# 42. Testing Requirements

Accounting must be testable independently of the GUI.

At minimum test:

- BUY creation
- SELL creation
- partial SELL
- full trade close
- FIFO across multiple BUY batches
- insufficient inventory
- profit calculation
- ROI calculation
- Gold accounting
- historical rate preservation
- Trading Day boundaries
- New Trades vs Carry-over Sales
- deletion protections
- database persistence
- backup/recovery
- asset cache fallback

UI tests should verify navigation/overlay behavior separately from accounting.

---

# 43. Current Prototype vs Target V1

Current prototype status:

- Python backend exists.
- PySide6 UI exists.
- JSON persistence exists.
- `backend/storage.py` exists.
- `tracker.py` contains the current accounting foundation.
- Galaxy Hideout/right sidebar structure is being built.

Target architecture:

- PySide6 application
- SQLite + SQLAlchemy persistence
- service/domain layer
- repository layer
- AssetService/cache
- RateService/provider architecture
- complete overlay UI
- real backend-driven HUD
- tests
- packaged desktop application

Do not confuse a temporary prototype implementation with the final architecture.

---

---

# 36. Open / Verify Before Implementing

These are intentionally NOT guessed here:

- Exact final visual layout of every overlay.
- Exact final chart types and chart placement.
- Exact sound files.
- Exact TINK thresholds if not already configured.
- Exact current-market-price provider for unrealized valuation.
- Exact rate-provider implementation if not already locked.
- Any requirement that conflicts with a later explicit decision in the source conversation.

If the source conversation contains a later explicit decision for one of these, that later decision overrides this section.

---

## Source Note

This directive was reconstructed from the supplied conversation export and cross-checked against the established architecture/accounting decisions. The source conversation contains unrelated conversations as well; only DivineFlipper/project requirements were intended to be extracted.

Key source-confirmed architecture includes the final V1 sidebar (Faustus, Stash, Trades, Analytics, Settings), display-only Hideout objects, the one-overlay V1 model, the permanent animated Hideout background, active Faustus open trades, historical Trades, Trading Day behavior, Analytics history, asset caching, and the separate Gold ledger.


# 44. Open Questions — 50 Decisions to Lock

The following questions were selected after re-checking the conversation against this directive. They are intentionally left open where the conversation contained a recommendation, ambiguity, or no final user decision. Answering them will allow this document to become the implementation source of truth rather than relying on assumptions.

### Database / persistence

1. **Database migration:** Should we migrate the current `data.json` prototype into SQLite automatically on first run of the new database version?
2. **SQLAlchemy version:** Should we pin a specific SQLAlchemy major/minor version for V1, or allow the current compatible release?
3. **Database location:** Confirm `data/divineflipper.db` as the final user-data location on every platform, using an OS-appropriate application-data directory if required by packaging conventions?
4. **Backup format:** Should backups be raw SQLite database copies, SQL dumps, or both?
5. **Restore:** Should V1 include a user-facing Restore Backup button, or only automatic/manual backup creation?
6. **Schema migrations:** Should V1 use Alembic for database migrations?
7. **Delete behavior:** When a transaction is deleted, should all dependent/recalculable data be rebuilt from the remaining source transactions rather than stored snapshots being edited directly?

### League / Trading Day

8. **League selection:** Should the app ask the user to choose the PoE league on first setup, then keep the active league until changed in Settings?
9. **League switching:** Should switching league change the visible trading history/inventory immediately while preserving all other leagues?
10. **Trading Day timestamp:** Confirm that a new Trading Day defaults to the current date/time but allows a custom start date/time.
11. **Closing a Trading Day:** Should the user explicitly close/end a Trading Day, or should starting another day implicitly close the previous one?
12. **Continue behavior:** If there is no open Trading Day, should startup always force creation of a new one?
13. **Carry-over inventory:** When a new Trading Day starts, should all unsold inventory remain available and count as carry-over inventory?
14. **Today's Profit:** Should Today's Profit include only realized profit from sales made during the current Trading Day, including sales of older/carry-over inventory?

### Trade model / accounting

15. **Trade identity:** Should every BUY transaction create exactly one Trade by default, with later SELL transactions linked to that Trade?
16. **Multiple BUYs:** If the same item is bought again while an earlier Trade is open, should that create a separate Trade rather than merge into the existing one?
17. **Partial sales:** Should a partial SELL always remain linked to the original Trade that owns the inventory being sold?
18. **Cross-trade FIFO:** If multiple open Trades contain the same item, should global FIFO determine which Trade's inventory is consumed, or should each Trade have isolated inventory?
19. **Target sell price:** Is the target/current sell price a user-entered field on an open Trade, or should it be automatically populated from market data?
20. **Target price updates:** If market data changes, should an open Trade's displayed target price update automatically without changing its accounting history?
21. **SELL currency:** Should SELL transactions support both Chaos and Divine exactly like BUY transactions?
22. **Gold on SELL:** Is Gold on SELL a value received, spent, or simply a separate transaction-level measurement chosen by the user?
23. **Zero-profit sales:** Should a SELL with exactly zero realized profit use neutral styling/audio rather than positive or negative feedback?
24. **Negative-profit sales:** Should losses be displayed as negative profit and trigger the warning effect/TINK alternative?

### Rates / APIs

25. **poe.ninja rate source:** Confirm `poe.ninja` as the V1 automatic reference provider for Divine/Chaos market data.
26. **Manual override:** Should the user be able to override the automatically fetched Divine rate before confirming the startup rate?
27. **Rate refresh:** Should the app refresh the reference rate automatically on startup, manually through Settings, or both?
28. **Rate failure:** If poe.ninja is unavailable, should the app use the last cached rate and allow the user to continue offline?
29. **Rate caching:** Should fetched market rates be cached locally with timestamp and league information?
30. **Other market prices:** For unrealized inventory value, should we use poe.ninja item prices in V1, or leave market valuation manual until a provider is explicitly locked?
31. **API limits:** Should the app implement rate limiting/backoff and never request the economy API more frequently than necessary?
32. **API attribution:** Should the UI include a small source/attribution indicator for market data providers?

### Asset catalog / images

33. **Catalog provider:** Confirm the asset catalog should use a provider abstraction with poe.ninja as the preferred V1 source where possible.
34. **Catalog refresh:** Should the catalog refresh automatically at startup when internet is available, or only through Settings/manual refresh?
35. **New assets:** Should newly discovered assets become selectable immediately after a successful catalog refresh?
36. **Image source:** Confirm the actual item icon should be retrieved from the official PoE CDN URL supplied/referenced by the catalog data rather than from poe.ninja itself.
37. **Image cache location:** Should cached images live under an OS-appropriate application cache directory rather than inside the user database directory?
38. **Cache invalidation:** Should image URLs/content be refreshed when the provider reports a changed asset version/hash?
39. **Placeholder:** Confirm one generic placeholder style for missing/unavailable item icons in V1.
40. **Licensing:** Before distribution, should we explicitly verify and document PoE/CDN asset usage and redistribution permissions?

### UI / visual design

41. **Sidebar collapse:** The conversation contained a recommendation for a collapsible right sidebar (full labels normally, icons-only when collapsed). Should this be part of V1, or remain a later polish feature?
42. **Sidebar icons:** Should each sidebar entry have a custom icon in addition to its text label?
43. **Overlay title bars:** Should overlays have a dedicated PoE/cosmic title bar with a close button, or use a cleaner frameless panel style?
44. **Hideout HUD layout:** Which HUD blocks are permanently visible on the Hideout, and which of Profit/ROI/Gold/Trading Stash/Recent Activity/Open Trades should be prioritized if space is limited?
45. **Hideout background:** Confirm the V1 background is the Celestial Nebula/Galaxy Hideout style discussed in the conversation, with continuous animation.
46. **No dimming:** Confirm overlays should not darken/dim the Hideout behind them.
47. **Responsive sizing:** Should the application support a defined minimum window size and adapt the HUD/sidebar/overlay layout below the preferred 1400×850 prototype size?
48. **Typography:** Should we select and bundle a dedicated fantasy/PoE-inspired display font for headings while keeping body text in a highly readable system/UI font?
49. **Sound settings:** Which exact sound controls belong in Settings for V1: master volume, enable/disable TINK, enable/disable warnings, and separate effect categories?
50. **Final interaction polish:** Should we lock exact button labels, colors, hover/active states, animations, chart types, sound thresholds and overlay layouts only after the structural UI is fully implemented and visually tested, or decide them now before coding those areas?

---

# 45. Decision Policy

For each open question above:

- Do not silently choose an answer.
- Record the user's answer in this document.
- If a later decision contradicts an earlier directive, the later explicit decision wins.
- Mark each resolved question as **LOCKED** and preserve the decision in the relevant technical/UI section.
- Keep genuinely implementation-dependent details marked **OPEN** until implementation/design testing resolves them.

The objective is for this document to contain approximately 95% of the project's durable V1 directives, including architecture, database, APIs, assets, images, caching, accounting, UI, navigation, buttons, styling, sound, startup behavior, data integrity, testing and packaging.


1 data from Jason is irrelevant we should start from zero, clean slate 
2 chose latest stable and compatible version and keep it 
3 yes, using convention is always best :)
4 both
5  backup should be automatic made and user in setting should be able to backup if needed , you should have 1 back up per day, and hold them for 15 days
6 Yes
7 yes
8 always of start up and able to switch in setting yes
9 yes
10 no when you start a trading day just fetch the time that we selected that option and go
11 user input should change the day never auto
12 yes
13 yes
14 only realized, if I buy 10 mists today and sell tomorrow that profit is tomorrow profit
15 yes
16 yes
17 yes
18 isolated inv, a card should be linked with something like a trade id and If I sell my item there that counts for that trade with makes FIFO a bit obsolete for now I think, I can be wrong ahah
19 target price should not be a thing 
20 target price should not be a thing 
21 yes
22 GOLD is just a stat to measure how much trading we did, should be automatically calculated, stored and stored separetly
23 yeeees
24 yees, sounds can be elected further down the line but I want like a poe dead sound 
25 yes
26 yes
27 startup
28 yes, and ask for a div rate mandatory to answer
29 yes
30 items should be valued at the cost price 
31 yes
32 yes
33 yes
34 at start up
35 yes
36 yes
37 yes
38yes
39 yes
40 yes pls pls 
41 part of v1
42 yes
43yes
44 always visible: 
- Daily profit 
- Current div rate at smaller like bottom corner just the image and a number like    x 214
- Current activity 
- Latest 6 open trades
- Also leaving space for further additions 
45 yes celestial nebula style 
46 confirmed
47 not under that no but should support being enlarged
48 yes sir but leave all styling for later lets build a function Ning app and then polish 
49 yes
50 after the app is working as intended we will style it 
