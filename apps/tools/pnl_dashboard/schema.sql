-- MT5 P&L Dashboard - SQLite Schema
-- Used by Python merge scripts and .NET EF Core

-- ============================================================
-- ACCOUNTS (max 20, enforced in application layer)
-- ============================================================
CREATE TABLE IF NOT EXISTS Accounts (
    Id                TEXT PRIMARY KEY,
    Mt5Login          INTEGER NOT NULL UNIQUE,
    Server            TEXT NOT NULL,
    PrimaryTraderName TEXT NOT NULL,
    AccountType       INTEGER NOT NULL,          -- 0=Demo, 1=Real
    Status            INTEGER NOT NULL DEFAULT 0,
    StrategiesCsv     TEXT,
    Balance           REAL NOT NULL DEFAULT 0,
    Equity            REAL NOT NULL DEFAULT 0,
    Currency          TEXT DEFAULT 'USD',
    CreatedAt         TEXT NOT NULL,
    LastSyncAt        TEXT
);

-- ============================================================
-- TRADERS
-- ============================================================
CREATE TABLE IF NOT EXISTS Traders (
    Id              TEXT PRIMARY KEY,
    Name            TEXT NOT NULL UNIQUE,
    DisplayName     TEXT,
    Email           TEXT,
    IsActive        INTEGER NOT NULL DEFAULT 1,
    CreatedAt       TEXT NOT NULL,
    UpdatedAt       TEXT
);

-- ============================================================
-- ACCOUNT <-> TRADER (many-to-many)
-- ============================================================
CREATE TABLE IF NOT EXISTS AccountTraderAssignments (
    Id              TEXT PRIMARY KEY,
    AccountId       TEXT NOT NULL,
    TraderId        TEXT NOT NULL,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id),
    FOREIGN KEY (TraderId)  REFERENCES Traders(Id),
    UNIQUE(AccountId, TraderId)
);

-- ============================================================
-- STRATEGIES
-- ============================================================
CREATE TABLE IF NOT EXISTS Strategies (
    Id              TEXT PRIMARY KEY,
    Name            TEXT NOT NULL UNIQUE,
    Description     TEXT,
    MagicNumbers    TEXT,                       -- JSON array: [12345, 67890]
    SymbolFilter    TEXT,
    LotSizeMin      REAL,
    LotSizeMax      REAL,
    CommentPattern  TEXT,
    Color           TEXT NOT NULL DEFAULT '#2196F3',
    IsAutoDetected  INTEGER NOT NULL DEFAULT 0,
    CreatedAt       TEXT NOT NULL,
    UpdatedAt       TEXT
);

-- ============================================================
-- TRADES (extended with categorization fields)
-- ============================================================
CREATE TABLE IF NOT EXISTS Trades (
    Id                    TEXT PRIMARY KEY,
    AccountId             TEXT NOT NULL,
    Ticket                INTEGER NOT NULL,
    DealEntryTicket       INTEGER,
    DealExitTicket        INTEGER,
    Symbol                TEXT NOT NULL,
    Direction             INTEGER NOT NULL,
    MagicNumber           INTEGER NOT NULL DEFAULT 0,
    TradeOrigin           INTEGER NOT NULL DEFAULT -1, -- -1=Unclassified, 0=Manual, 1=Automated, 2=SemiManual
    StrategyName          TEXT,
    TraderId              TEXT,
    CategorizationStatus  INTEGER NOT NULL DEFAULT 0,  -- 0=Uncategorized, 1=RuleMatched, 2=Manual
    OrderComment          TEXT,
    EntryTime             TEXT NOT NULL,
    ExitTime              TEXT,
    EntryPrice            REAL NOT NULL,
    ExitPrice             REAL,
    Volume                REAL NOT NULL,
    ProfitLoss            REAL,
    Commission            REAL DEFAULT 0,
    Swap                  REAL DEFAULT 0,
    StopLoss              REAL,
    TakeProfit            REAL,
    Status                INTEGER NOT NULL DEFAULT 0,  -- 0=Open, 1=Closed
    IsOpen                INTEGER NOT NULL DEFAULT 1,
    Mfe                   REAL,
    Mae                   REAL,
    HoldingTimeMinutes    REAL,
    AccountLogin          INTEGER,
    AccountServer         TEXT,
    AccountName           TEXT,
    AccountCurrency       TEXT,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id),
    FOREIGN KEY (TraderId)  REFERENCES Traders(Id)
);

-- ============================================================
-- CATEGORIZATION RULES
-- ============================================================
CREATE TABLE IF NOT EXISTS CategorizationRules (
    Id                  TEXT PRIMARY KEY,
    Name                TEXT NOT NULL,
    Priority            INTEGER NOT NULL DEFAULT 0,
    StrategyId          TEXT,
    TraderId            TEXT,
    RuleType            INTEGER NOT NULL,
    MagicNumberStart    INTEGER,
    MagicNumberEnd      INTEGER,
    LotSizeMin          REAL,
    LotSizeMax          REAL,
    CommentPattern      TEXT,
    SymbolPattern       TEXT,
    TimeOfDayStartUtc   TEXT,
    TimeOfDayEndUtc     TEXT,
    IsActive            INTEGER NOT NULL DEFAULT 1,
    CreatedAt           TEXT NOT NULL,
    UpdatedAt           TEXT,
    FOREIGN KEY (StrategyId) REFERENCES Strategies(Id),
    FOREIGN KEY (TraderId)   REFERENCES Traders(Id)
);

-- ============================================================
-- TRADE DISTRIBUTION RULES
-- ============================================================
CREATE TABLE IF NOT EXISTS TradeDistributionRules (
    Id                  TEXT PRIMARY KEY,
    AccountId           TEXT NOT NULL,
    TraderId            TEXT NOT NULL,
    Priority            INTEGER NOT NULL DEFAULT 0,
    RuleType            INTEGER NOT NULL,
    MagicNumberStart    INTEGER,
    MagicNumberEnd      INTEGER,
    LotSizePattern      TEXT,
    CommentPattern      TEXT,
    SymbolPattern       TEXT,
    TimeOfDayStartUtc   TEXT,
    TimeOfDayEndUtc     TEXT,
    IsActive            INTEGER NOT NULL DEFAULT 1,
    CreatedAt           TEXT NOT NULL,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id),
    FOREIGN KEY (TraderId)  REFERENCES Traders(Id)
);

-- ============================================================
-- DAILY EQUITY SNAPSHOTS
-- ============================================================
CREATE TABLE IF NOT EXISTS EquitySnapshots (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountId         TEXT NOT NULL,
    SnapshotDate      TEXT NOT NULL,
    Balance           REAL NOT NULL,
    Equity            REAL NOT NULL,
    FreeMargin        REAL,
    MarginLevel       REAL,
    OpenTradeCount    INTEGER DEFAULT 0,
    ClosedTradeCount  INTEGER DEFAULT 0,
    DailyPnl          REAL DEFAULT 0,
    DrawdownAbsolute  REAL DEFAULT 0,
    DrawdownPercent   REAL DEFAULT 0,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id),
    UNIQUE(AccountId, SnapshotDate)
);

-- ============================================================
-- STRATEGY DAILY STATS
-- ============================================================
CREATE TABLE IF NOT EXISTS StrategyDailyStats (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountId         TEXT NOT NULL,
    StrategyName      TEXT NOT NULL,
    StatDate          TEXT NOT NULL,
    TradeCount        INTEGER DEFAULT 0,
    WinningTrades     INTEGER DEFAULT 0,
    LosingTrades      INTEGER DEFAULT 0,
    TotalPnl          REAL DEFAULT 0,
    WinRate           REAL,
    ProfitFactor      REAL,
    AverageWin        REAL,
    AverageLoss       REAL,
    LargestWin        REAL,
    LargestLoss       REAL,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id),
    UNIQUE(AccountId, StrategyName, StatDate)
);

-- ============================================================
-- PERIOD SUMMARIES
-- ============================================================
CREATE TABLE IF NOT EXISTS PeriodSummaries (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountId         TEXT NOT NULL,
    PeriodType        INTEGER NOT NULL,
    PeriodStart       TEXT NOT NULL,
    PeriodEnd         TEXT NOT NULL,
    TotalPnl          REAL,
    TradeCount        INTEGER,
    WinRate           REAL,
    ProfitFactor      REAL,
    MaxDrawdownPct    REAL,
    SharpeRatio       REAL,
    SortinoRatio      REAL,
    CalmarRatio       REAL,
    RecoveryFactor    REAL,
    Expectancy        REAL,
    FOREIGN KEY (AccountId) REFERENCES Accounts(Id)
);

-- ============================================================
-- ALERT HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS AlertHistory (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    AlertType         TEXT NOT NULL,
    Severity          INTEGER NOT NULL,
    Message           TEXT NOT NULL,
    AccountId         TEXT,
    StrategyName      TEXT,
    TriggeredAt       TEXT NOT NULL,
    AcknowledgedAt    TEXT,
    EmailSent         INTEGER DEFAULT 0
);

-- ============================================================
-- GENERATED REPORTS
-- ============================================================
CREATE TABLE IF NOT EXISTS GeneratedReports (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ReportType        TEXT NOT NULL,
    AccountType       INTEGER NOT NULL,
    PeriodStart       TEXT NOT NULL,
    PeriodEnd         TEXT NOT NULL,
    FilePath          TEXT NOT NULL,
    GeneratedAt       TEXT NOT NULL,
    FileSize          INTEGER
);

-- ============================================================
-- TRADE NOTES
-- ============================================================
CREATE TABLE IF NOT EXISTS TradeNotes (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    TradeId           TEXT NOT NULL,
    Note              TEXT NOT NULL,
    CreatedAt         TEXT NOT NULL,
    UpdatedAt         TEXT,
    FOREIGN KEY (TradeId) REFERENCES Trades(Id)
);

-- ============================================================
-- AUDIT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS AuditLog (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    Action            TEXT NOT NULL,
    Details           TEXT,
    Timestamp         TEXT NOT NULL
);

-- ============================================================
-- SYNC LOG (tracks per-account sync history)
-- ============================================================
CREATE TABLE IF NOT EXISTS SyncLog (
    Id                INTEGER PRIMARY KEY AUTOINCREMENT,
    AccountLogin      INTEGER NOT NULL,
    SyncStartedAt     TEXT NOT NULL,
    SyncCompletedAt   TEXT,
    NewTrades         INTEGER DEFAULT 0,
    UpdatedTrades     INTEGER DEFAULT 0,
    SkippedTrades     INTEGER DEFAULT 0,
    ErrorMessage      TEXT,
    Source            TEXT                       -- 'csv' or 'api'
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS IX_Trades_AccountId ON Trades(AccountId);
CREATE INDEX IF NOT EXISTS IX_Trades_ExitTime ON Trades(ExitTime);
CREATE INDEX IF NOT EXISTS IX_Trades_MagicNumber ON Trades(MagicNumber);
CREATE INDEX IF NOT EXISTS IX_Trades_StrategyName ON Trades(StrategyName);
CREATE INDEX IF NOT EXISTS IX_Trades_TraderId ON Trades(TraderId);
CREATE INDEX IF NOT EXISTS IX_Trades_Symbol ON Trades(Symbol);
CREATE INDEX IF NOT EXISTS IX_Trades_CategorizationStatus ON Trades(CategorizationStatus);
CREATE INDEX IF NOT EXISTS IX_Trades_TradeOrigin ON Trades(TradeOrigin);
CREATE INDEX IF NOT EXISTS IX_Trades_CompositeKey ON Trades(AccountLogin, Ticket, DealExitTicket);
CREATE INDEX IF NOT EXISTS IX_EquitySnapshots_AccountDate ON EquitySnapshots(AccountId, SnapshotDate);
CREATE INDEX IF NOT EXISTS IX_StrategyDailyStats_Date ON StrategyDailyStats(StatDate, AccountId);
CREATE INDEX IF NOT EXISTS IX_PeriodSummaries_Type ON PeriodSummaries(PeriodType, AccountId);
CREATE INDEX IF NOT EXISTS IX_CategorizationRules_Priority ON CategorizationRules(Priority, IsActive);
CREATE INDEX IF NOT EXISTS IX_TradeDistributionRules_Account ON TradeDistributionRules(AccountId, Priority);
CREATE INDEX IF NOT EXISTS IX_Strategies_Name ON Strategies(Name);
CREATE INDEX IF NOT EXISTS IX_Traders_Name ON Traders(Name);
