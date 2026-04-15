# Vesto - MVP Phase Breakdown (Solo Developer)

## Overview

This document breaks the full Vesto enterprise system into incremental MVPs,
with MVP1 designed for a **solo developer** managing their **own portfolio** across
**India (NSE/BSE)** and **CFD (MT5)** markets.

Each "Day" = one Claude session consuming your daily token budget.
Each day produces a **working, testable increment**.

---

## MVP1: Personal Portfolio Manager (Days 1-22)

### Scope (What's IN)
- Simple JWT login (username + password, no roles, no MFA)
- 2 trading accounts (1 India, 1 CFD)
- Portfolio dashboard with holdings, P&L, allocation charts
- Advanced portfolio analytics (Sharpe, Sortino, Drawdown, Benchmark comparison)
- Risk management module (risk metrics, alerts, no compliance)
- Simplified rebalancing (create plan with lot size/shares, edit/cancel/execute)
- Reports module (PDF performance reports, email-able)
- Email notifications (configurable per account)
- Broker adapters: Zerodha, Dhan (India), MT5 (CFD) - data import only
- Auto audit logging for all events
- Dark/Light theme (extend existing)
- No: AI engine, roles, compliance, mobile, MFA, real-time sync

### Scope (What's DEFERRED to later MVPs)
- AI recommendation engine → MVP2
- Role-based access control (6 roles) → MVP2
- Multi-tenant architecture → MVP3
- Compliance (SEBI, SEC/FINRA) → MVP3
- Mobile app (React Native) → MVP4
- Self-learning AI → MVP5
- Real-time broker sync → MVP2
- MFA, OAuth2, SSO → MVP3
- Tax management → MVP2
- Approval workflow (multi-role) → MVP3

---

## MVP1: Daily Execution Phases

### Day 1: Project Scaffolding & Database Schema Design
**Goal:** New `vesto/` app structure alongside existing trading-dashboard, complete DB schema

**Tasks:**
1. Create `vesto/` directory structure:
   ```
   vesto/
   ├── backend/
   │   ├── app/
   │   │   ├── __init__.py
   │   │   ├── main.py          # FastAPI app
   │   │   ├── config.py        # Settings
   │   │   ├── database.py      # DB engine
   │   │   ├── models/          # SQLAlchemy models
   │   │   ├── schemas/         # Pydantic schemas
   │   │   ├── routers/         # API routes
   │   │   ├── services/        # Business logic
   │   │   ├── integrations/    # Broker adapters
   │   │   └── utils/           # Helpers
   │   ├── alembic/             # Migrations
   │   ├── requirements.txt
   │   └── alembic.ini
   └── frontend/
       ├── src/
       │   ├── pages/
       │   ├── components/
       │   ├── api/
       │   ├── store/
       │   ├── hooks/
       │   └── utils/
       ├── package.json
       ├── vite.config.js
       └── tailwind.config.js
   ```
2. Design complete database schema (all tables for MVP1)
3. Create SQLAlchemy models:
   - `users` (id, email, hashed_password, display_name, is_active, created_at)
   - `accounts` (id, user_id, name, broker_type, broker_account_id, market, currency, is_active, config_json, created_at)
   - `positions` (id, account_id, symbol, quantity, avg_cost, current_price, market_value, unrealized_pnl, sector, instrument_type, updated_at)
   - `trades` (id, account_id, symbol, trade_type, quantity, price, fees, net_amount, trade_date, settled, notes)
   - `portfolio_snapshots` (id, account_id, date, total_value, cash, invested, daily_return, cumulative_return)
   - `rebalance_plans` (id, account_id, name, status, target_allocation_json, created_at, executed_at)
   - `rebalance_items` (id, plan_id, symbol, action, quantity, lot_size, estimated_price, status)
   - `audit_logs` (id, user_id, action, entity_type, entity_id, metadata_json, ip_address, created_at)
   - `notification_configs` (id, account_id, email, events_json, is_active)
   - `risk_alerts` (id, account_id, alert_type, message, severity, is_read, created_at)
4. Create Alembic migration
5. Set up .env template and config.py

**Deliverable:** Project structure + DB models + migration ready to run

---

### Day 2: Authentication & Core Backend Setup
**Goal:** Working JWT auth, user creation, FastAPI app running

**Tasks:**
1. Implement `auth/jwt.py` - JWT token creation, password hashing (reuse pattern from trading-dashboard)
2. Implement `auth/dependencies.py` - Simple auth dependency (no role checks, just authenticated user)
3. Create `routers/auth.py`:
   - `POST /api/v1/auth/register` (one-time setup, creates first user)
   - `POST /api/v1/auth/login` (returns JWT + sets refresh cookie)
   - `POST /api/v1/auth/refresh` (silent refresh)
   - `POST /api/v1/auth/logout` (revoke refresh token)
4. Create `routers/users.py`:
   - `GET /api/v1/users/me` (get current user profile)
   - `PUT /api/v1/users/me` (update profile)
5. Set up CORS middleware, exception handlers
6. Create `main.py` with all router registrations
7. Create seed script to create initial user
8. Test all auth endpoints with curl/httpie

**Deliverable:** Backend running on port 8000, JWT auth working

---

### Day 3: Account Management Backend + Frontend Shell
**Goal:** CRUD for accounts, frontend app shell with login

**Tasks:**
1. Create `routers/accounts.py`:
   - `GET /api/v1/accounts` (list user's accounts)
   - `POST /api/v1/accounts` (create account, max 2 for MVP1)
   - `GET /api/v1/accounts/{id}` (account details)
   - `PUT /api/v1/accounts/{id}` (update account settings)
   - `DELETE /api/v1/accounts/{id}` (soft delete)
2. Set up frontend with Vite + React + Tailwind + shadcn/ui
3. Implement frontend auth:
   - Login page
   - AuthContext (reuse pattern from trading-dashboard)
   - API client with interceptors (reuse from trading-dashboard)
   - Protected route wrapper
4. Create AppShell layout:
   - Sidebar with navigation
   - TopBar with account switcher + theme toggle
   - Dark/Light theme using CSS variables + Tailwind dark mode
5. Create Account setup page (add Zerodha/Dhan/MT5 account)
6. Rey Capital logo integration

**Deliverable:** Login working, account creation, dark/light theme toggle

---

### Day 4: Portfolio Dashboard Backend
**Goal:** Core portfolio data APIs

**Tasks:**
1. Create `services/portfolio_service.py`:
   - `get_portfolio_summary(account_id)` - Total value, cash, invested, P&L
   - `get_holdings(account_id)` - All current positions with market values
   - `get_asset_allocation(account_id)` - By sector, instrument type
   - `get_portfolio_history(account_id, period)` - Daily snapshots for charts
2. Create `routers/portfolio.py`:
   - `GET /api/v1/portfolio/{account_id}/summary`
   - `GET /api/v1/portfolio/{account_id}/holdings`
   - `GET /api/v1/portfolio/{account_id}/allocation`
   - `GET /api/v1/portfolio/{account_id}/history?period=1M`
   - `GET /api/v1/portfolio/consolidated/summary` (both accounts combined)
3. Create `services/market_data.py`:
   - Helper to fetch current prices (mock for now, real later)
   - Symbol info lookup
4. Create position management endpoints:
   - `POST /api/v1/portfolio/{account_id}/positions` (add position manually)
   - `PUT /api/v1/portfolio/{account_id}/positions/{id}` (update)
   - `DELETE /api/v1/portfolio/{account_id}/positions/{id}` (remove)

**Deliverable:** All portfolio APIs working and tested

---

### Day 5: Portfolio Dashboard Frontend
**Goal:** Main dashboard UI with charts and holdings table

**Tasks:**
1. Create Dashboard page with:
   - Account switcher dropdown (or tabs for 2 accounts + consolidated)
   - Summary KPI cards (Total Value, Day Change, Total P&L, Cash Available)
   - Holdings table (TanStack Table with sorting, filtering)
     - Columns: Symbol, Qty, Avg Cost, Current Price, Market Value, Unrealized P&L, % Change, % Allocation
   - P&L colors: green for profit, red for loss
2. Create charts:
   - Asset Allocation pie chart (Recharts)
   - Portfolio performance line chart (1D/1W/1M/3M/6M/YTD/1Y selector)
   - Sector allocation bar chart
3. Create Holdings detail modal (click on holding → full details)
4. Add position manually dialog (quick add from dashboard)
5. Responsive layout (works on tablet too)

**Deliverable:** Full working dashboard with real data from API

---

### Day 6: Trade Management & Import
**Goal:** Trade logging and CSV/Excel import

**Tasks:**
1. Create `routers/trades.py`:
   - `GET /api/v1/trades/{account_id}` (list trades, paginated, filterable)
   - `POST /api/v1/trades/{account_id}` (log single trade)
   - `POST /api/v1/trades/{account_id}/import` (CSV/Excel upload)
   - `GET /api/v1/trades/{account_id}/export` (export CSV)
2. Create `services/trade_service.py`:
   - CSV/Excel parser (reuse pattern from trading-dashboard)
   - Auto-update positions on trade entry
   - Cost basis calculation (average cost method)
   - P&L calculation on close trades
3. Create Trades page in frontend:
   - Trade history table (filterable by date, symbol, type)
   - Add trade dialog (buy/sell form)
   - CSV upload with drag-and-drop
   - Trade detail view
4. Update positions automatically when trades are logged

**Deliverable:** Complete trade management with import/export

---

### Day 7: Advanced Portfolio Analytics Backend
**Goal:** All performance and risk metric calculations

**Tasks:**
1. Create `services/analytics_service.py`:
   - **Period returns**: Daily, weekly, monthly, YTD, 1Y, since inception
   - **Risk-adjusted returns**: Sharpe Ratio, Sortino Ratio, Calmar Ratio
   - **Drawdown analysis**: Max drawdown, current drawdown, drawdown duration
   - **Benchmark comparison**: Track NIFTY50 (India) or S&P500 (US) as benchmark
     - Excess return, tracking error, information ratio
   - **Attribution analysis**: Return by sector, by instrument
   - **Contribution analysis**: Top/bottom contributors to P&L
2. Create `routers/analytics.py`:
   - `GET /api/v1/analytics/{account_id}/performance?period=YTD`
   - `GET /api/v1/analytics/{account_id}/risk-metrics`
   - `GET /api/v1/analytics/{account_id}/drawdown`
   - `GET /api/v1/analytics/{account_id}/benchmark?benchmark=NIFTY50`
   - `GET /api/v1/analytics/{account_id}/attribution`
   - `GET /api/v1/analytics/{account_id}/contribution`
   - `GET /api/v1/analytics/consolidated/performance` (both accounts)
3. Implement portfolio snapshot scheduler (daily snapshot creation)

**Deliverable:** All analytics endpoints with real calculations

---

### Day 8: Advanced Portfolio Analytics Frontend
**Goal:** Analytics dashboard with professional charts

**Tasks:**
1. Create Performance page:
   - Period return cards (1D, 1W, 1M, 3M, 6M, YTD, 1Y, All)
   - Risk metrics cards (Sharpe, Sortino, Calmar, Max Drawdown)
   - Performance vs benchmark chart (dual line chart)
   - Drawdown chart (area chart showing drawdown periods)
   - Rolling returns chart (12M rolling returns)
2. Create Attribution page:
   - Sector contribution bar chart (horizontal)
   - Top 5 contributors / bottom 5 detractors
   - Holdings heat map (size = allocation, color = return)
3. Account comparison view:
   - Side-by-side metrics for both accounts
   - Combined vs individual performance
4. Date range selector for all analytics

**Deliverable:** Professional analytics dashboard

---

### Day 9: Risk Management Module
**Goal:** Risk metrics, alerts, and monitoring

**Tasks:**
1. Create `services/risk_service.py`:
   - **Portfolio Beta**: vs benchmark (NIFTY50 / S&P500)
   - **Concentration risk**: % in top 5/10 holdings, single stock exposure
   - **Volatility**: Portfolio volatility (30D, 90D), individual stock vol
   - **Value at Risk (VaR)**: 95% confidence, 1-day VaR
   - **Correlation matrix**: Between holdings
   - **Stop-loss monitoring**: Track holdings below cost basis by X%
   - **Sector exposure limits**: Alert if any sector > threshold
2. Create `routers/risk.py`:
   - `GET /api/v1/risk/{account_id}/metrics` (all risk metrics)
   - `GET /api/v1/risk/{account_id}/concentration`
   - `GET /api/v1/risk/{account_id}/var`
   - `GET /api/v1/risk/{account_id}/correlation`
   - `GET /api/v1/risk/{account_id}/alerts` (active risk alerts)
   - `PUT /api/v1/risk/{account_id}/alerts/{id}/read` (mark alert read)
   - `POST /api/v1/risk/{account_id}/thresholds` (set alert thresholds)
3. Create risk alert generation service (runs on position updates)
4. Create Risk Dashboard frontend page:
   - Risk metrics cards
   - Concentration pie chart
   - Correlation heat map
   - VaR visualization
   - Alert list with severity indicators
   - Threshold configuration modal

**Deliverable:** Complete risk management with alerts

---

### Day 10: Rebalancing Workflow
**Goal:** Create, edit, and execute rebalancing plans

**Tasks:**
1. Create `services/rebalance_service.py`:
   - `create_plan(account_id, name, target_allocation)` - Create new plan
   - `calculate_trades(plan_id)` - Compute trades needed to reach target
   - `update_item(item_id, quantity, lot_size)` - Edit individual item
   - `execute_plan(plan_id)` - Generate trade orders
   - `cancel_plan(plan_id)` - Cancel plan
   - Target allocation: Can be % based or specific share/lot count
   - Estimate cost, fees, and impact
2. Create `routers/rebalance.py`:
   - `GET /api/v1/rebalance/{account_id}/plans` (list plans)
   - `POST /api/v1/rebalance/{account_id}/plans` (create plan)
   - `GET /api/v1/rebalance/{account_id}/plans/{id}` (plan details)
   - `PUT /api/v1/rebalance/{account_id}/plans/{id}` (update plan)
   - `DELETE /api/v1/rebalance/{account_id}/plans/{id}` (cancel)
   - `POST /api/v1/rebalance/{account_id}/plans/{id}/execute` (execute)
   - `PUT /api/v1/rebalance/{account_id}/plans/{id}/items/{item_id}` (edit item)
3. Create Rebalancing page in frontend:
   - Plan list (status: Draft, Ready, Executed, Cancelled)
   - Create plan wizard:
     - Step 1: Name plan, select target allocation method (% or shares)
     - Step 2: Set target for each holding (new or existing)
     - Step 3: Review computed trades (buy X, sell Y)
     - Step 4: Confirm and execute OR save as draft
   - Plan detail view with editable items
   - Execute button with confirmation modal
   - Cancel button with confirmation

**Deliverable:** Working rebalancing from plan creation to execution

---

### Day 11: Broker Adapter - Zerodha (India)
**Goal:** Import portfolio and trade data from Zerodha

**Tasks:**
1. Create `integrations/broker_adapter.py` (abstract base class):
   ```python
   class BrokerAdapter(ABC):
       def authenticate(self, credentials) -> bool
       def get_holdings(self) -> List[Position]
       def get_positions(self) -> List[Position]  # open positions
       def get_trades(self, from_date, to_date) -> List[Trade]
       def get_account_info(self) -> AccountInfo
       def import_portfolio(self, account_id) -> ImportResult
   ```
2. Create `integrations/zerodha_adapter.py`:
   - Implement using Kite Connect API (kiteconnect Python package)
   - Holdings import
   - Trade history import
   - Position mapping to internal format
   - Symbol normalization (NSE:RELIANCE → RELIANCE)
3. Create `routers/broker.py`:
   - `POST /api/v1/broker/{account_id}/connect` (save API key/secret)
   - `POST /api/v1/broker/{account_id}/import/holdings` (pull current holdings)
   - `POST /api/v1/broker/{account_id}/import/trades` (pull trade history)
   - `GET /api/v1/broker/{account_id}/status` (connection status)
4. Create broker settings UI in account page:
   - API key/secret input
   - Import buttons
   - Last sync timestamp

**Deliverable:** Zerodha data import working

---

### Day 12: Broker Adapter - Dhan + MT5
**Goal:** Dhan (India) and MT5 (CFD) import adapters

**Tasks:**
1. Create `integrations/dhan_adapter.py`:
   - Implement using Dhan HQ API (dhanhq Python package)
   - Holdings import
   - Trade history import
   - Symbol normalization
2. Create `integrations/mt5_adapter.py`:
   - Implement using MetaTrader5 Python package
   - Pull account info
   - Import open positions
   - Import trade history (closed deals)
   - Symbol mapping for CFD instruments
3. Update broker router to support all 3 brokers
4. Update frontend account setup to support broker selection:
   - Zerodha: API key + secret + request token flow
   - Dhan: Client ID + Access token
   - MT5: Server + Login + Password
5. Test all 3 broker imports end-to-end

**Deliverable:** All 3 brokers importing data

---

### Day 13: Reports Module
**Goal:** PDF report generation and report management

**Tasks:**
1. Create `services/report_service.py`:
   - **Monthly Report**: Summary, holdings snapshot, trades, performance metrics
   - **Account Statement**: All trades with running balance
   - **Risk Report**: Risk metrics snapshot, concentration, alerts
   - **Custom Report**: User-selected date range and metrics
   - PDF generation using ReportLab or WeasyPrint
   - Report stored in filesystem with metadata in DB
2. Create `routers/reports.py`:
   - `GET /api/v1/reports/{account_id}` (list generated reports)
   - `POST /api/v1/reports/{account_id}/generate` (generate new report)
   - `GET /api/v1/reports/{account_id}/{id}/download` (download PDF)
   - `DELETE /api/v1/reports/{account_id}/{id}` (delete report)
3. Add `report_history` table (id, account_id, report_type, period_start, period_end, file_path, created_at)
4. Create Reports page in frontend:
   - Report type selector (Monthly, Statement, Risk, Custom)
   - Date range picker
   - Generate button
   - Report list with download links
   - Preview modal (embedded PDF viewer)

**Deliverable:** PDF reports generated and downloadable

---

### Day 14: Email Notifications Module
**Goal:** Configurable email alerts per account

**Tasks:**
1. Create `services/notification_service.py`:
   - Email sending via SMTP (smtp.gmail.com or configurable)
   - Templated emails (HTML templates with Jinja2)
   - Event types:
     - Daily portfolio summary
     - Risk alert triggered
     - Rebalance plan executed
     - Large position change (> X%)
     - Weekly performance digest
2. Create `routers/notifications.py`:
   - `GET /api/v1/notifications/{account_id}/config` (get notification settings)
   - `PUT /api/v1/notifications/{account_id}/config` (update settings)
   - `POST /api/v1/notifications/test` (send test email)
   - `GET /api/v1/notifications/history` (sent notifications log)
3. Create notification config UI per account:
   - Email address input
   - Toggle for each event type
   - Frequency settings (immediate, daily digest, weekly)
   - Test email button
4. Background task for scheduled notifications (daily/weekly)
5. Hook into risk alerts and rebalancing execution

**Deliverable:** Email notifications working for all event types

---

### Day 15: Audit Logging & Activity Feed
**Goal:** Complete audit trail + activity dashboard

**Tasks:**
1. Create `services/audit_service.py`:
   - Auto-log middleware (log every API call)
   - Action types: LOGIN, LOGOUT, CREATE, UPDATE, DELETE, IMPORT, EXPORT, EXECUTE, VIEW
   - Entity types: ACCOUNT, POSITION, TRADE, REBALANCE_PLAN, REPORT, NOTIFICATION, SETTINGS
   - Capture: user_id, action, entity, metadata (before/after values), IP, timestamp
2. Create `routers/audit.py`:
   - `GET /api/v1/audit/logs` (paginated, filterable by action, entity, date)
   - `GET /api/v1/audit/activity` (recent activity feed)
   - `GET /api/v1/audit/stats` (login count, actions by type, etc.)
3. Create Activity page in frontend:
   - Activity timeline (chronological feed)
   - Filters (by action type, entity type, date range)
   - Search within logs
   - Export logs as CSV
4. Add audit logging decorators/middleware to all existing routers
5. Dashboard widget showing recent activity

**Deliverable:** Complete audit trail + activity UI

---

### Day 16: Dashboard Polish & Consolidated View
**Goal:** Polish dashboard, add consolidated portfolio view, watchlist

**Tasks:**
1. Consolidated portfolio view (both accounts combined):
   - Merged holdings with per-account breakdown
   - Combined performance chart
   - Combined risk metrics
   - Currency conversion for cross-market (INR ↔ USD)
2. Watchlist feature:
   - `POST /api/v1/watchlist` (add symbol)
   - `DELETE /api/v1/watchlist/{id}` (remove)
   - `GET /api/v1/watchlist` (list with current prices)
   - Watchlist widget on dashboard
3. Market data integration (basic):
   - India: NSE EOD data via yfinance or nsepy
   - CFD: MT5 price feed or free API
   - Price cache with 15-min refresh
4. Dashboard improvements:
   - Quick stats bar at top
   - Mini portfolio breakdown cards
   - Recent trades widget
   - Pending rebalance plans widget
   - Risk alerts badge

**Deliverable:** Polished, production-quality dashboard

---

### Day 17: UI/UX Polish & Theme Finalization
**Goal:** Professional UI, Rey Capital branding, responsive design

**Tasks:**
1. Design system finalization:
   - Color palette: Dark (#0F0F0F, #1A1A2E) + Light (white, light gray)
   - Gold accent (#C9A227) for buttons, highlights
   - Green (#22C55E) for profit, Red (#EF4444) for loss
   - shadcn/ui component customization
2. Rey Capital branding:
   - Logo in sidebar header
   - Branded login page
   - Favicon
3. Responsive design check:
   - All pages work on 1024px+ screens
   - Tables scroll horizontally on smaller screens
   - Charts resize properly
4. Accessibility check:
   - Keyboard navigation
   - Color contrast (WCAG AA)
   - Focus indicators
5. Loading states, error states, empty states for all pages
6. Toast notifications for actions (success/error)
7. Settings page:
   - User profile edit
   - Theme preference
   - Default account selection
   - Data export (full portfolio export)

**Deliverable:** Polished, branded, production-ready UI

---

### Day 18: Integration Testing & Bug Fixes
**Goal:** End-to-end testing, fix all bugs

**Tasks:**
1. Test complete workflows:
   - Register → Login → Create Account → Import from Broker → View Dashboard
   - Add trades → View analytics → Generate report → Download PDF
   - Create rebalance plan → Edit items → Execute → Verify positions updated
   - Set notification config → Trigger event → Verify email received
2. Test edge cases:
   - Empty portfolio (no positions)
   - Single position portfolio
   - Large portfolio (50+ positions)
   - Invalid CSV upload
   - Broker connection failure
   - Expired JWT token
3. Fix all bugs found
4. Performance optimization:
   - Add database indexes
   - Optimize slow queries
   - Add Redis caching if needed
5. Security review:
   - Input validation on all endpoints
   - SQL injection prevention (parameterized queries)
   - XSS prevention (output encoding)
   - CORS configuration

**Deliverable:** Stable, tested MVP1

---

### Day 19: Nice-to-Have Features (Suggested Additions)
**Goal:** Features that make MVP1 stand out

**Tasks (pick based on remaining tokens):**
1. **Portfolio comparison**: Compare your 2 accounts side-by-side
2. **Sector rotation view**: Show sector performance over time
3. **Holdings aging**: Show how long each position has been held
4. **Dividend tracker**: Track dividends received per holding
5. **Goal tracking**: Set portfolio value goal, show progress
6. **Export to Excel**: Export all data as .xlsx workbook with multiple sheets
7. **Dashboard customization**: Drag-and-drop widget layout
8. **Price alerts**: Set price targets for watchlist symbols
9. **Notes on holdings**: Add personal notes/thesis to each holding

**Deliverable:** Enhanced MVP1 with differentiating features

---

### Day 20: Deployment & Documentation
**Goal:** Deploy and document the application

**Tasks:**
1. Docker setup:
   - Dockerfile for backend
   - Dockerfile for frontend
   - docker-compose.yml (backend + frontend + postgres + redis)
2. Environment configuration:
   - Production .env template
   - Database initialization script
3. Basic documentation:
   - API documentation (auto-generated by FastAPI/Swagger)
   - User guide (how to set up accounts, import data)
   - Deployment guide
4. Backup script (database backup to file)
5. Health check endpoint

**Deliverable:** Deployable application with documentation

---

## MVP2: Analytics & Automation (Days 21-35)

### Scope
- AI recommendation engine (basic: portfolio optimization, rebalancing suggestions)
- Tax management (India: STT/Capital Gains, US: wash sale tracking)
- Real-time broker sync (periodic polling, not streaming)
- Advanced reporting (custom templates, scheduled reports)
- Market data enrichment (news, sector data, fundamentals)
- Role system (add viewer role for sharing with advisor)
- Advanced rebalancing (scenario comparison, tax-aware rebalancing)
- Performance benchmarking against multiple indices
- Corporate actions tracking (dividends, splits, bonus)

### Phases
- Day 21: AI portfolio optimizer (MPT, efficient frontier)
- Day 22: AI rebalancing suggestions with confidence scores
- Day 23: Tax management module (India)
- Day 24: Tax management module (CFD/US)
- Day 25: Periodic broker sync (background job)
- Day 26: Advanced reports (custom templates)
- Day 27: Market data integration (news, fundamentals)
- Day 28: Viewer role + sharing
- Day 29: Tax-aware rebalancing
- Day 30: Corporate actions tracker
- Day 31: Advanced benchmarking
- Day 32: Scenario comparison for rebalancing
- Day 33: Scheduled reports (email weekly/monthly)
- Day 34: Integration testing
- Day 35: Polish + deployment

---

## MVP3: Enterprise Features (Days 36-55)

### Scope
- Multi-tenant architecture (support multiple users/RIAs)
- Full role-based access control (6 roles)
- Multi-step approval workflow for rebalancing
- Compliance module (SEBI + SEC/FINRA)
- MFA + OAuth2 + SSO
- Advanced audit & regulatory reporting
- Multi-currency with live forex rates
- Password policy enforcement
- IP whitelisting
- Support for 5+ accounts per user

### Phases
- Day 36-38: Multi-tenant database architecture
- Day 39-40: Role-based access control (6 roles)
- Day 41-43: Approval workflow (Strategy Maker → PM → Director)
- Day 44-45: India compliance (SEBI)
- Day 46-47: US compliance (SEC/FINRA)
- Day 48: MFA implementation
- Day 49: OAuth2 + SSO
- Day 50-51: Regulatory reporting
- Day 52: Multi-currency
- Day 53: Security hardening
- Day 54-55: Testing + deployment

---

## MVP4: Mobile & Scale (Days 56-75)

### Scope
- React Native mobile app (iOS + Android)
- Real-time WebSocket updates
- Push notifications
- Offline mode
- Additional broker integrations
- Advanced charting (TradingView-style)
- White-label capability
- Client onboarding flow

### Phases
- Day 56-58: React Native project setup + auth
- Day 59-60: Mobile dashboard
- Day 61-62: Mobile holdings + analytics
- Day 63: Mobile rebalancing approval
- Day 64-65: Push notifications
- Day 66: Offline mode
- Day 67-68: WebSocket real-time updates
- Day 69-70: Additional broker integrations
- Day 71-72: Advanced charting
- Day 73: White-label setup
- Day 74-75: Testing + deployment

---

## MVP5: AI Self-Learning (Days 76-90)

### Scope
- Self-learning AI that improves with experience
- Market regime detection
- Anomaly detection
- Predictive analytics (sector rotation, volatility forecasting)
- A/B testing framework for strategies
- Backtesting engine
- LLM integration for natural language portfolio queries

### Phases
- Day 76-78: Market regime detector (HMM/clustering)
- Day 79-80: Predictive analytics models
- Day 81-82: Self-learning mechanism (track recommendations vs outcomes)
- Day 83-84: Anomaly detection
- Day 85-86: Backtesting engine
- Day 87-88: LLM integration (chat with your portfolio)
- Day 89-90: A/B testing + deployment

---

## Summary Table

| MVP | Focus | Days | Key Deliverables |
|-----|-------|------|-----------------|
| **MVP1** | Personal Portfolio Manager | 1-20 | Dashboard, Analytics, Risk, Rebalancing, Reports, 3 Brokers |
| **MVP2** | Analytics & Automation | 21-35 | AI Optimizer, Tax, Auto-sync, Advanced Reports |
| **MVP3** | Enterprise Features | 36-55 | Multi-tenant, Roles, Compliance, Approvals, Security |
| **MVP4** | Mobile & Scale | 56-75 | Mobile App, Real-time, Push Notifications, White-label |
| **MVP5** | AI Self-Learning | 76-90 | Self-evolving AI, Regime Detection, Backtesting, LLM |

---

## Nice-to-Have for MVP1 (Recommended)

These features add significant value with minimal effort:

1. **Dividend Tracker** - Track dividends per holding (India stocks pay good dividends)
2. **Holdings Aging** - Show days held, highlight short-term vs long-term for tax planning
3. **Quick Trade Entry** - One-click buy/sell from dashboard
4. **Portfolio Comparison** - Side-by-side India vs CFD performance
5. **Export to Excel** - Full data export with multiple sheets
6. **Price Alerts** - Email when holding crosses threshold
7. **Market Overview Widget** - NIFTY50, SENSEX, S&P500 mini charts on dashboard
8. **Position Sizing Calculator** - Calculate lot size based on risk percentage
