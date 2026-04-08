# MT5 Trade Monitoring & Analytics Dashboard - AI Agent Prompt

## Objective
Build a **multi-account MT5 Trade Monitoring and Analytics Dashboard** with an automated data pipeline that extracts trading data from MetaTrader 5, processes it through a structured ETL pipeline, stores it in a centralized database, and visualizes key trading, financial, and risk metrics in an interactive dashboard with alerting capabilities.

---

## Project Context

### Client
- **Company:** Rey Capital
- **Broker:** CFI (financial broker)
- **Use Case:** Institutional money manager overseeing multiple client accounts
- **MT5 Access:** Standard MT5 terminal (no Manager API access currently - request pending with CFI)

### Core Requirements (from SOW)
- Automate extraction of trading and account data from MT5
- Create structured data pipeline to store and process trade information
- Develop dashboard to visualize key performance and risk indicators
- Provide real-time and historical analysis of trading activity
- Enable monitoring of account balances, open positions, and exposure
- Deliver a scalable reporting framework

---

## System Architecture

### High-Level Flow

```
MT5 Terminal(s)
    |
    |-- Phase 1: MQL5 EA per account (exports CSV/JSON every 5 min)
    |-- Phase 2: Manager API (single connection, all accounts - pending CFI approval)
    |
    v
Python ETL Pipeline (APScheduler, runs every 5 min)
    |
    |-- Extract: Read exported files or pull from API
    |-- Transform: Calculate derived metrics, normalize currencies, validate data
    |-- Load: Upsert into database
    |
    v
PostgreSQL / Supabase (structured tables + materialized views)
    |
    |-- Dashboard: Grafana (operational) OR Next.js custom app (polished)
    |-- Alerts: Telegram bot + Email (SMTP)
    |-- Reports: Auto-generated PDF/Excel exports (daily/weekly/monthly)
```

---

## Phase 1: MQL5 Data Exporter EA

### Overview
Build a lightweight EA that runs on each MT5 terminal instance and exports account/trade data to local files on a timer.

### Data Export Frequency
- **Default interval:** Every 5 minutes (configurable via input parameter)
- **Export format:** CSV files (one file per data category)
- **Export location:** Configurable path, default `C:/MT5Data/{AccountNumber}/`

### Data to Extract

#### 1. Account Snapshot (`account_snapshot.csv`)
| Field | MQL5 Function | Description |
|-------|---------------|-------------|
| account_number | `AccountInfoInteger(ACCOUNT_LOGIN)` | Account login ID |
| account_name | `AccountInfoString(ACCOUNT_NAME)` | Client name |
| currency | `AccountInfoString(ACCOUNT_CURRENCY)` | Base currency |
| balance | `AccountInfoDouble(ACCOUNT_BALANCE)` | Current balance |
| equity | `AccountInfoDouble(ACCOUNT_EQUITY)` | Current equity |
| margin | `AccountInfoDouble(ACCOUNT_MARGIN)` | Used margin |
| free_margin | `AccountInfoDouble(ACCOUNT_MARGIN_FREE)` | Free margin |
| margin_level | `AccountInfoDouble(ACCOUNT_MARGIN_LEVEL)` | Margin level % |
| leverage | `AccountInfoInteger(ACCOUNT_LEVERAGE)` | Account leverage |
| profit | `AccountInfoDouble(ACCOUNT_PROFIT)` | Floating P&L |
| timestamp | `TimeCurrent()` | Server time of snapshot |

#### 2. Open Positions (`positions.csv`)
| Field | MQL5 Function | Description |
|-------|---------------|-------------|
| position_id | `PositionGetInteger(POSITION_IDENTIFIER)` | Unique position ID |
| symbol | `PositionGetString(POSITION_SYMBOL)` | Trading symbol |
| type | `PositionGetInteger(POSITION_TYPE)` | Buy (0) or Sell (1) |
| volume | `PositionGetDouble(POSITION_VOLUME)` | Lot size |
| open_price | `PositionGetDouble(POSITION_PRICE_OPEN)` | Entry price |
| current_price | `PositionGetDouble(POSITION_PRICE_CURRENT)` | Current market price |
| sl | `PositionGetDouble(POSITION_SL)` | Stop loss |
| tp | `PositionGetDouble(POSITION_TP)` | Take profit |
| swap | `PositionGetDouble(POSITION_SWAP)` | Accumulated swap |
| profit | `PositionGetDouble(POSITION_PROFIT)` | Floating P&L |
| open_time | `PositionGetInteger(POSITION_TIME)` | Position open time |
| magic | `PositionGetInteger(POSITION_MAGIC)` | EA magic number |
| comment | `PositionGetString(POSITION_COMMENT)` | Trade comment |

#### 3. Deal History (`deals.csv`) - Incremental
| Field | MQL5 Function | Description |
|-------|---------------|-------------|
| deal_id | `HistoryDealGetInteger(ticket, DEAL_TICKET)` | Deal ticket |
| order_id | `HistoryDealGetInteger(ticket, DEAL_ORDER)` | Related order |
| position_id | `HistoryDealGetInteger(ticket, DEAL_POSITION_ID)` | Related position |
| symbol | `HistoryDealGetString(ticket, DEAL_SYMBOL)` | Symbol |
| type | `HistoryDealGetInteger(ticket, DEAL_TYPE)` | Buy/Sell/Balance |
| entry | `HistoryDealGetInteger(ticket, DEAL_ENTRY)` | In/Out/InOut |
| volume | `HistoryDealGetDouble(ticket, DEAL_VOLUME)` | Volume |
| price | `HistoryDealGetDouble(ticket, DEAL_PRICE)` | Execution price |
| commission | `HistoryDealGetDouble(ticket, DEAL_COMMISSION)` | Commission |
| swap | `HistoryDealGetDouble(ticket, DEAL_SWAP)` | Swap |
| profit | `HistoryDealGetDouble(ticket, DEAL_PROFIT)` | Realized P&L |
| time | `HistoryDealGetInteger(ticket, DEAL_TIME)` | Execution time |
| magic | `HistoryDealGetInteger(ticket, DEAL_MAGIC)` | Magic number |
| comment | `HistoryDealGetString(ticket, DEAL_COMMENT)` | Comment |

#### 4. Pending Orders (`orders.csv`)
| Field | MQL5 Function | Description |
|-------|---------------|-------------|
| ticket | `OrderGetInteger(ORDER_TICKET)` | Order ticket |
| symbol | `OrderGetString(ORDER_SYMBOL)` | Symbol |
| type | `OrderGetInteger(ORDER_TYPE)` | Order type |
| volume | `OrderGetDouble(ORDER_VOLUME_CURRENT)` | Current volume |
| price_open | `OrderGetDouble(ORDER_PRICE_OPEN)` | Requested price |
| sl | `OrderGetDouble(ORDER_SL)` | Stop loss |
| tp | `OrderGetDouble(ORDER_TP)` | Take profit |
| time_setup | `OrderGetInteger(ORDER_TIME_SETUP)` | Order creation time |
| magic | `OrderGetInteger(ORDER_MAGIC)` | Magic number |
| comment | `OrderGetString(ORDER_COMMENT)` | Comment |

#### 5. Symbol Info (`symbols.csv`) - Export once daily
| Field | MQL5 Function | Description |
|-------|---------------|-------------|
| symbol | `SymbolInfoString(sym, SYMBOL_DESCRIPTION)` | Symbol name |
| asset_class | `SymbolInfoString(sym, SYMBOL_PATH)` | Category path |
| contract_size | `SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE)` | Contract size |
| tick_size | `SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE)` | Tick size |
| tick_value | `SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE)` | Tick value |
| spread | `SymbolInfoInteger(sym, SYMBOL_SPREAD)` | Current spread |
| digits | `SymbolInfoInteger(sym, SYMBOL_DIGITS)` | Price digits |

### EA Input Parameters
```
input int      ExportIntervalMinutes = 5;       // Export frequency
input string   ExportPath = "C:/MT5Data/";       // Base export path
input int      HistoryDaysBackfill = 365;         // Initial backfill days
input bool     ExportAccountSnapshot = true;
input bool     ExportPositions = true;
input bool     ExportDeals = true;
input bool     ExportOrders = true;
input bool     ExportSymbols = true;
input string   LastDealTicket = "";               // Track incremental exports
```

### EA Logic
1. On `OnInit()`: Create export directory, do initial historical backfill of deals
2. On `OnTimer()` (every ExportIntervalMinutes):
   - Export account snapshot (full overwrite)
   - Export all current open positions (full overwrite)
   - Export new deals since last export (append mode, track last deal ticket)
   - Export pending orders (full overwrite)
   - Export symbol info (once per day only)
   - Write a `heartbeat.txt` with timestamp so pipeline can detect if EA is stale
3. Handle errors gracefully - log to `export_errors.log`

---

## Phase 2: Manager API Integration (Future - Pending CFI Approval)

### How to Request from CFI
Send a formal request to CFI account manager / institutional desk emphasizing:
- **Read-only access** only (no trade execution needed)
- **Purpose:** Risk oversight and operational monitoring of managed accounts
- **Compliance angle:** Aligns with regulatory best practices for fund monitoring

### What to Ask CFI Specifically
1. Do you provide MT5 Manager API access for institutional clients / money managers?
2. Can we get read-only Manager API credentials?
3. If not Manager API, do you offer:
   - MT5 Web API / Gateway API?
   - Database replica or read-only SQL access?
   - Reporting API or bulk data export for all managed accounts?
   - MAM/PAMM reporting APIs?
4. What documentation or agreements are required?
5. Technical specs: API version, server address, port?
6. Rate limits or query frequency restrictions?

### Manager API Integration Architecture (When Available)
```
Manager API (.dll via C# service or Python ctypes)
    |
    |-- UserRequest()           -> All client accounts
    |-- DealRequest()           -> All deals across accounts
    |-- PositionGetByLogins()   -> All open positions
    |-- OrderRequest()          -> All pending orders
    |
    v
Same Python pipeline (swap extraction layer only)
```

### Alternative: MAM/PAMM Terminal Approach
If CFI provides MAM software, run the EA on the MAM terminal which can see all sub-accounts. This is a self-service option requiring no broker API cooperation.

---

## Data Pipeline (Python ETL)

### Technology Stack
- **Language:** Python 3.11+
- **Scheduler:** APScheduler (lightweight, no infrastructure overhead)
- **Data Processing:** pandas
- **Database Driver:** psycopg2 (PostgreSQL) or supabase-py (Supabase)
- **Logging:** Python logging module with file rotation

### Pipeline Steps

#### Step 1: Extract
```python
# Watch export directory for new/updated files
# For each account folder in C:/MT5Data/{AccountNumber}/:
#   - Read account_snapshot.csv
#   - Read positions.csv
#   - Read deals.csv (new rows only, track last processed deal_id)
#   - Read orders.csv
#   - Read symbols.csv
#   - Check heartbeat.txt staleness (alert if > 10 min old)
```

#### Step 2: Transform & Validate
- Validate data types and required fields
- Normalize all monetary values to a base currency (USD) using current exchange rates
- Calculate derived metrics (see Dashboard Metrics section)
- Detect anomalies (sudden equity drops, unusual volume spikes)
- Deduplicate deals (use deal_id as unique key)

#### Step 3: Load
- Upsert account snapshots (insert new, update existing)
- Upsert positions (full refresh per account per cycle)
- Append new deals (incremental, never overwrite)
- Upsert pending orders
- Update symbol info (daily refresh)
- Refresh materialized views for dashboard queries

#### Step 4: Post-Load
- Evaluate alert conditions (margin thresholds, drawdown limits)
- Send alerts if triggered (Telegram, email)
- Log pipeline execution status, row counts, errors
- Write pipeline health metrics for monitoring

### Pipeline Schedule
```python
# Primary schedule: every 5 minutes during trading hours
# Daily jobs: symbol refresh, daily P&L snapshot, report generation
# Weekly jobs: weekly performance summary report
# Monthly jobs: monthly client performance report
```

### Error Handling
- Retry failed file reads up to 3 times with backoff
- Alert if an account's heartbeat is stale (EA stopped)
- Alert if pipeline itself fails (email/Telegram)
- Log all errors with full context to `pipeline.log`
- Never crash - skip failed accounts and continue with others

---

## Database Schema

### Technology
- **Primary:** PostgreSQL 15+ (or Supabase for hosted + instant REST API + auth)
- **Consider:** TimescaleDB extension for time-series optimization at scale

### Core Tables

```sql
-- Account snapshots (time-series)
CREATE TABLE account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_number BIGINT NOT NULL,
    account_name VARCHAR(255),
    currency VARCHAR(10),
    balance DECIMAL(18,2),
    equity DECIMAL(18,2),
    margin_used DECIMAL(18,2),
    free_margin DECIMAL(18,2),
    margin_level DECIMAL(10,2),
    leverage INT,
    floating_pnl DECIMAL(18,2),
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(account_number, snapshot_time)
);

-- Open positions (current state)
CREATE TABLE positions (
    position_id BIGINT NOT NULL,
    account_number BIGINT NOT NULL,
    symbol VARCHAR(50),
    direction VARCHAR(4),  -- BUY/SELL
    volume DECIMAL(10,4),
    open_price DECIMAL(18,6),
    current_price DECIMAL(18,6),
    sl DECIMAL(18,6),
    tp DECIMAL(18,6),
    swap DECIMAL(18,2),
    floating_pnl DECIMAL(18,2),
    open_time TIMESTAMP,
    magic_number INT,
    comment VARCHAR(255),
    last_updated TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY(position_id, account_number)
);

-- Deal history (append-only)
CREATE TABLE deals (
    deal_id BIGINT PRIMARY KEY,
    order_id BIGINT,
    position_id BIGINT,
    account_number BIGINT NOT NULL,
    symbol VARCHAR(50),
    deal_type VARCHAR(20),
    entry_type VARCHAR(10),  -- IN/OUT/INOUT
    volume DECIMAL(10,4),
    price DECIMAL(18,6),
    commission DECIMAL(18,2),
    swap DECIMAL(18,2),
    profit DECIMAL(18,2),
    executed_at TIMESTAMP NOT NULL,
    magic_number INT,
    comment VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pending orders (current state)
CREATE TABLE pending_orders (
    ticket BIGINT PRIMARY KEY,
    account_number BIGINT NOT NULL,
    symbol VARCHAR(50),
    order_type VARCHAR(30),
    volume DECIMAL(10,4),
    price DECIMAL(18,6),
    sl DECIMAL(18,6),
    tp DECIMAL(18,6),
    setup_time TIMESTAMP,
    magic_number INT,
    comment VARCHAR(255),
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Symbol metadata (reference table)
CREATE TABLE symbols (
    symbol VARCHAR(50) PRIMARY KEY,
    asset_class VARCHAR(100),
    contract_size DECIMAL(18,4),
    tick_size DECIMAL(18,8),
    tick_value DECIMAL(18,6),
    spread INT,
    digits INT,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Daily P&L snapshots (aggregated)
CREATE TABLE daily_pnl (
    id BIGSERIAL PRIMARY KEY,
    account_number BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    starting_balance DECIMAL(18,2),
    ending_balance DECIMAL(18,2),
    realized_pnl DECIMAL(18,2),
    commissions DECIMAL(18,2),
    swaps DECIMAL(18,2),
    deposits DECIMAL(18,2),
    withdrawals DECIMAL(18,2),
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    UNIQUE(account_number, trade_date)
);

-- Alert history
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    account_number BIGINT,
    alert_type VARCHAR(50),
    severity VARCHAR(10),  -- INFO/WARNING/CRITICAL
    message TEXT,
    metric_value DECIMAL(18,4),
    threshold_value DECIMAL(18,4),
    triggered_at TIMESTAMP DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Pipeline execution log
CREATE TABLE pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20),  -- SUCCESS/PARTIAL/FAILED
    accounts_processed INT,
    deals_inserted INT,
    errors TEXT,
    duration_seconds DECIMAL(8,2)
);
```

### Materialized Views (for Dashboard Performance)

```sql
-- Account overview (refreshed every pipeline run)
CREATE MATERIALIZED VIEW mv_account_overview AS
SELECT
    a.account_number,
    a.account_name,
    a.currency,
    a.balance,
    a.equity,
    a.margin_level,
    a.floating_pnl,
    a.leverage,
    COUNT(p.position_id) AS open_positions,
    SUM(CASE WHEN p.floating_pnl > 0 THEN 1 ELSE 0 END) AS winning_positions,
    SUM(CASE WHEN p.floating_pnl < 0 THEN 1 ELSE 0 END) AS losing_positions,
    SUM(p.floating_pnl) AS total_floating_pnl,
    a.snapshot_time AS last_update
FROM account_snapshots a
LEFT JOIN positions p ON a.account_number = p.account_number
WHERE a.snapshot_time = (
    SELECT MAX(snapshot_time) FROM account_snapshots WHERE account_number = a.account_number
)
GROUP BY a.account_number, a.account_name, a.currency, a.balance, a.equity,
         a.margin_level, a.floating_pnl, a.leverage, a.snapshot_time;

-- Symbol exposure across all accounts
CREATE MATERIALIZED VIEW mv_symbol_exposure AS
SELECT
    symbol,
    SUM(CASE WHEN direction = 'BUY' THEN volume ELSE 0 END) AS long_volume,
    SUM(CASE WHEN direction = 'SELL' THEN volume ELSE 0 END) AS short_volume,
    SUM(CASE WHEN direction = 'BUY' THEN volume ELSE -volume END) AS net_volume,
    SUM(floating_pnl) AS total_floating_pnl,
    COUNT(DISTINCT account_number) AS accounts_exposed
FROM positions
GROUP BY symbol;

-- Trading performance metrics (per account, rolling 30 days)
CREATE MATERIALIZED VIEW mv_trading_performance AS
SELECT
    account_number,
    COUNT(*) FILTER (WHERE entry_type = 'OUT') AS total_closed_trades,
    COUNT(*) FILTER (WHERE entry_type = 'OUT' AND profit > 0) AS winning_trades,
    COUNT(*) FILTER (WHERE entry_type = 'OUT' AND profit < 0) AS losing_trades,
    ROUND(
        COUNT(*) FILTER (WHERE entry_type = 'OUT' AND profit > 0)::DECIMAL /
        NULLIF(COUNT(*) FILTER (WHERE entry_type = 'OUT'), 0) * 100, 2
    ) AS win_rate,
    SUM(profit) FILTER (WHERE entry_type = 'OUT') AS net_profit,
    AVG(profit) FILTER (WHERE entry_type = 'OUT') AS avg_trade_profit,
    SUM(commission) AS total_commissions,
    SUM(swap) AS total_swaps,
    ROUND(
        ABS(SUM(profit) FILTER (WHERE entry_type = 'OUT' AND profit > 0)) /
        NULLIF(ABS(SUM(profit) FILTER (WHERE entry_type = 'OUT' AND profit < 0)), 0), 2
    ) AS profit_factor
FROM deals
WHERE executed_at >= NOW() - INTERVAL '30 days'
GROUP BY account_number;
```

---

## Dashboard Modules

### Technology Options
- **Option A: Grafana** - Best for real-time monitoring, built-in alerts, free, connects to PostgreSQL directly
- **Option B: Custom Next.js + Supabase** - Full control, branded, polished UI, uses Recharts or Lightweight Charts

### Module 1: Executive Summary
- Total AUM (Assets Under Management) across all accounts
- Total number of active accounts
- Aggregate floating P&L
- Aggregate realized P&L (today / this week / this month)
- Total open positions count
- System health indicator (pipeline status, data freshness)

### Module 2: Account Overview Table
- Sortable/filterable table of all accounts
- Columns: Account #, Name, Balance, Equity, Floating P&L, Margin Level, Open Positions, Last Updated
- Color coding: Red for margin level < 200%, Yellow < 500%
- Click-through to individual account detail view

### Module 3: Trade Activity Monitoring
- Trade count timeline (bar chart, daily/hourly)
- Recent trades table (last 50 trades across all accounts)
- Volume by symbol (pie/bar chart)
- Buy vs Sell distribution

### Module 4: Open Positions Monitoring
- All open positions across all accounts in one table
- Group by symbol to see net exposure
- Heatmap: positions by account x symbol
- Largest positions highlighted

### Module 5: Profit & Loss Analysis
- Equity curve (line chart, daily snapshots)
- Daily P&L bar chart (green/red)
- Cumulative P&L over time
- P&L breakdown: gross profit, commissions, swaps, net profit
- P&L by symbol (which instruments are profitable?)

### Module 6: Client Account Performance
- Per-account performance cards
- Win rate, profit factor, avg trade, Sharpe ratio per account
- Account comparison view (benchmark accounts against each other)
- Deposit/withdrawal timeline per account

### Module 7: Symbol Exposure Analysis
- Net exposure by symbol (long vs short volume)
- Exposure by asset class (Forex, Metals, Indices, Crypto, etc.)
- Correlation risk indicator (correlated positions warning)
- Concentration risk (% of total volume in single symbol)

### Module 8: Risk Monitoring & Alerts
- Real-time margin level gauges per account
- Drawdown tracking (current vs max historical)
- Alert configuration panel (set thresholds)
- Alert history log
- VaR (Value at Risk) estimate at 95%/99% confidence

---

## Dashboard Metrics (Derived Calculations)

### Performance Metrics
| Metric | Formula | Purpose |
|--------|---------|---------|
| Win Rate | Winning Trades / Total Trades * 100 | Basic success rate |
| Profit Factor | Gross Profit / Gross Loss | Risk-adjusted profitability |
| Expectancy | (Win% x Avg Win) - (Loss% x Avg Loss) | Expected return per trade |
| Sharpe Ratio | (Avg Return - Risk Free Rate) / StdDev(Returns) | Risk-adjusted return |
| Sortino Ratio | (Avg Return - Risk Free Rate) / StdDev(Negative Returns) | Downside risk focus |
| Max Drawdown | (Peak Equity - Trough Equity) / Peak Equity * 100 | Worst loss from peak |
| Max Drawdown Duration | Days from peak to recovery | Recovery time |
| Calmar Ratio | Annual Return / Max Drawdown | Return per unit of drawdown |
| R-Multiple | Trade P&L / Initial Risk (SL distance) | Normalized trade quality |
| Average Trade Duration | Avg(close_time - open_time) | Holding period analysis |

### Risk Metrics
| Metric | Formula | Purpose |
|--------|---------|---------|
| Margin Level | (Equity / Used Margin) * 100 | Margin safety indicator |
| VaR (95%) | Historical simulation of daily returns | Potential daily loss |
| Exposure Ratio | Total Position Value / Equity | Leverage utilization |
| Concentration Risk | Max Single Symbol Volume / Total Volume * 100 | Diversification check |
| Correlation Score | Pearson correlation between position returns | Hidden risk detection |
| Net Exposure | Sum of directional volumes per symbol | Hedge effectiveness |

### Behavioral / Operational Metrics
| Metric | Calculation | Purpose |
|--------|-------------|---------|
| Trade Frequency | Trades per day/hour | Activity pattern |
| Time-of-Day P&L | P&L grouped by hour of execution | Best/worst trading hours |
| Day-of-Week P&L | P&L grouped by weekday | Best/worst trading days |
| Slippage | Execution price - Order price | Execution quality |
| Commission Impact | Total Commission / Total Volume | Cost analysis |
| Swap Impact | Total Swaps / Net Profit * 100 | Overnight cost impact |
| Consecutive Wins/Losses | Streak analysis | Tilt detection |

### Client / Business Metrics
| Metric | Calculation | Purpose |
|--------|-------------|---------|
| Total AUM | Sum of all account balances | Business size |
| Deposit/Withdrawal Ratio | Total Deposits / Total Withdrawals | Client retention signal |
| Dormant Accounts | Accounts with no trades in X days | Client engagement |
| Revenue (Commissions) | Sum of commissions paid | Brokerage revenue |
| Active Account % | Accounts with trades this week / Total accounts | Engagement rate |

---

## Alerting System

### Alert Channels
1. **Telegram Bot** - Instant mobile notifications for critical alerts
2. **Email (SMTP)** - Daily digest summaries + critical alerts
3. **Dashboard Banner** - In-app alert notifications

### Alert Rules (Configurable Thresholds)

| Alert | Default Threshold | Severity | Description |
|-------|-------------------|----------|-------------|
| Low Margin Level | < 200% | CRITICAL | Account approaching margin call |
| Margin Warning | < 500% | WARNING | Margin getting tight |
| Equity Drawdown | > 10% from peak | WARNING | Significant drawdown |
| Severe Drawdown | > 20% from peak | CRITICAL | Major drawdown event |
| Large Position | > 5% of equity | WARNING | Concentrated position risk |
| EA Heartbeat Stale | > 10 min no update | WARNING | Data exporter may have stopped |
| Pipeline Failure | Consecutive failures > 3 | CRITICAL | Data pipeline is down |
| Unusual Volume | > 3x average daily volume | INFO | Abnormal trading activity |
| High Swap Accumulation | > $X per position | INFO | Expensive overnight holds |
| Account Dormant | No trades in 7 days | INFO | Inactive account detection |

### Alert Message Format (Telegram)
```
[CRITICAL] Low Margin Level
Account: 12345 (Client Name)
Margin Level: 185.4%
Threshold: 200%
Equity: $4,520.00
Used Margin: $2,438.00
Time: 2026-03-31 14:35 UTC
```

---

## Report Generation

### Automated Reports
1. **Daily Summary** (PDF/Excel, emailed at market close)
   - Account balances and equity changes
   - Today's trades and P&L
   - Open positions summary
   - Alerts triggered today

2. **Weekly Performance** (PDF, emailed every Friday)
   - Week-over-week performance comparison
   - Win rate, profit factor, Sharpe ratio
   - Top/bottom performing accounts
   - Symbol exposure analysis

3. **Monthly Client Report** (PDF, emailed 1st of month)
   - Full month performance summary per account
   - Equity curve chart
   - Detailed trade log
   - Risk metrics summary
   - Comparison vs. previous month

---

## Suggested Enhancements (Beyond SOW)

### High Value Additions
1. **Comparison View** - Compare performance across time periods (this month vs last, this strategy vs that)
2. **Strategy Tagging** - Use magic numbers or comments to tag trades by strategy, then analyze per-strategy performance
3. **Audit Trail** - Log every pipeline run, data anomaly, and alert for compliance
4. **Mobile-Responsive Dashboard** - Stakeholders will want to check on their phone
5. **Data Anomaly Detection** - Flag suspicious patterns (spike in volume, unusual trade times, duplicate deals)
6. **Account Grouping** - Group accounts by strategy, manager, or client tier for aggregate views
7. **Benchmark Comparison** - Compare account performance against a market benchmark (e.g., S&P 500, Gold)

### Future Roadmap
- Predictive analytics (ML-based drawdown prediction)
- Copy trading performance analysis
- Client onboarding/offboarding tracking
- Regulatory reporting export (MiFID, ASIC format)
- Multi-broker support (beyond CFI)

---

## Risks & Limitations

| Risk | Impact | Mitigation |
|------|--------|------------|
| No Manager API access | Cannot see all accounts from single connection | Use EA per terminal (Phase 1), escalate request to CFI |
| MT5 terminal crashes | Data export stops | Heartbeat monitoring + alert when stale |
| Multi-currency accounts | P&L comparison becomes inaccurate | Normalize all values to USD using live exchange rates |
| Data volume at scale | Slow queries, large storage | PostgreSQL partitioning, materialized views, data retention policy |
| Network/file system issues | Pipeline fails to read exports | Retry logic, error logging, failure alerts |
| MetaQuotes restrictions | Potential licensing concerns with data extraction | EA approach is within standard terminal capabilities |
| Historical data limits | MT5 may not have full history | Backfill on first run, document data start date per account |
| Security of trade data | Sensitive financial data exposure | Encrypted DB connections, role-based dashboard access, no public endpoints |
| Single point of failure | If pipeline machine goes down | Deploy on reliable VPS, add health monitoring |
| Stale data during market volatility | 5-min delay may miss rapid margin changes | MT5 built-in alerts for immediate margin calls, dashboard for oversight |

---

## Project Timeline (6 Weeks)

| Week | Activity | Deliverables |
|------|----------|--------------|
| Week 1 | Requirements, system design, DB schema | ERD diagram, architecture doc, confirmed tech stack |
| Week 2 | MQL5 EA development, MT5 data integration setup | Working EA exporting all data categories |
| Week 3 | Python ETL pipeline, database setup, automation | Pipeline running on schedule, data flowing to DB |
| Week 4 | Dashboard design and visualization development | Working dashboard with all 8 modules |
| Week 5 | Alerting system, report generation, testing | Telegram/email alerts, PDF reports, end-to-end testing |
| Week 6 | Deployment, documentation, handover | Production deployment, user guide, training |

---

## Technology Summary

| Component | Technology | Why |
|-----------|-----------|-----|
| Data Extraction | MQL5 EA (Phase 1) / Manager API (Phase 2) | EA works immediately, API pending broker approval |
| Data Pipeline | Python 3.11 + APScheduler + pandas | Simple, no infrastructure overhead, maintainable |
| Database | PostgreSQL / Supabase | Reliable, analytics-friendly, free/low-cost |
| Dashboard | Grafana (ops) or Next.js + Recharts (custom) | Grafana for speed, Next.js for polish |
| Alerts | Telegram Bot API + SMTP email | Instant mobile + email coverage |
| Reports | Python + ReportLab (PDF) / openpyxl (Excel) | Automated generation, no manual work |
| Hosting | VPS (Hetzner/DigitalOcean) or Supabase Cloud | Cost-effective, reliable |
| Version Control | Git (this repo) | Already in place |

---

## File Structure (Proposed)

```
AlgoStrategies/
├── mql5/
│   └── experts/
│       └── MT5_DataExporter_EA.mq5          # Data exporter EA
├── dashboard/
│   ├── pipeline/
│   │   ├── extract.py                        # Data extraction module
│   │   ├── transform.py                      # Data transformation & metrics
│   │   ├── load.py                           # Database loading
│   │   ├── scheduler.py                      # APScheduler orchestration
│   │   ├── alerts.py                         # Alert evaluation & sending
│   │   └── reports.py                        # PDF/Excel report generation
│   ├── database/
│   │   ├── schema.sql                        # Full database schema
│   │   ├── views.sql                         # Materialized views
│   │   └── migrations/                       # Schema migrations
│   ├── web/                                   # Next.js dashboard (if custom)
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   ├── grafana/                               # Grafana dashboard configs (if Grafana)
│   │   └── dashboards/
│   ├── config/
│   │   ├── settings.yaml                      # Pipeline configuration
│   │   └── alerts.yaml                        # Alert thresholds
│   ├── requirements.txt
│   └── README.md
└── docs/
    └── prompts/
        └── MT5_Trade_Dashboard_Prompt.md      # This file
```
