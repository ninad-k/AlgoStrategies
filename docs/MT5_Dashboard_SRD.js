const fs = require("C:/Users/Ninad/AppData/Roaming/npm/node_modules/docx");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, LevelFormat,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TableOfContents, ExternalHyperlink, ImageRun
} = fs;

// ── Color Palette ──
const COLORS = {
  primary: "1B3A5C",    // Dark navy
  secondary: "2E75B6",  // Blue
  accent: "4CAF50",     // Green
  warning: "FF9800",    // Orange
  danger: "E53935",     // Red
  lightBg: "E8F0FE",   // Light blue bg
  lightGray: "F5F5F5",
  medGray: "D0D0D0",
  darkText: "1A1A1A",
  white: "FFFFFF",
  headerBg: "1B3A5C",
  rowAlt: "F0F6FF",
};

// ── Reusable Components ──
const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.medGray };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorders = {
  top: { style: BorderStyle.NONE, size: 0 },
  bottom: { style: BorderStyle.NONE, size: 0 },
  left: { style: BorderStyle.NONE, size: 0 },
  right: { style: BorderStyle.NONE, size: 0 },
};
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };
const PAGE_WIDTH = 9360; // US Letter with 1" margins

function headerCell(text, width, alignment = AlignmentType.LEFT) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: COLORS.headerBg, type: ShadingType.CLEAR },
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({
      alignment,
      children: [new TextRun({ text, bold: true, color: COLORS.white, font: "Calibri", size: 19 })]
    })]
  });
}

function dataCell(text, width, opts = {}) {
  const { bold = false, color = COLORS.darkText, fill = null, alignment = AlignmentType.LEFT, fontSize = 19 } = opts;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({
      alignment,
      children: [new TextRun({ text, bold, color, font: "Calibri", size: fontSize })]
    })]
  });
}

function makeTable(headers, rows, colWidths) {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => headerCell(h, colWidths[i])) }),
      ...rows.map((row, ri) =>
        new TableRow({
          children: row.map((cell, ci) => {
            if (typeof cell === "object" && cell._isTc) return cell;
            return dataCell(String(cell), colWidths[ci], { fill: ri % 2 === 1 ? COLORS.rowAlt : null });
          })
        })
      )
    ]
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, bold: true, font: "Calibri", size: 32, color: COLORS.primary })]
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 160 },
    children: [new TextRun({ text, bold: true, font: "Calibri", size: 26, color: COLORS.secondary })]
  });
}

function heading3(text) {
  return new Paragraph({
    spacing: { before: 200, after: 120 },
    children: [new TextRun({ text, bold: true, font: "Calibri", size: 22, color: COLORS.primary })]
  });
}

function para(text, opts = {}) {
  const { bold = false, spacing = { after: 120 }, alignment = AlignmentType.LEFT, italic = false } = opts;
  return new Paragraph({
    alignment,
    spacing,
    children: [new TextRun({ text, font: "Calibri", size: 20, bold, italic, color: COLORS.darkText })]
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Calibri", size: 20, color: COLORS.darkText })]
  });
}

function numberedItem(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Calibri", size: 20, color: COLORS.darkText })]
  });
}

function boldBullet(label, desc) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [
      new TextRun({ text: label + ": ", font: "Calibri", size: 20, bold: true, color: COLORS.darkText }),
      new TextRun({ text: desc, font: "Calibri", size: 20, color: COLORS.darkText }),
    ]
  });
}

function infoBox(title, text) {
  return new Table({
    width: { size: PAGE_WIDTH, type: WidthType.DXA },
    columnWidths: [PAGE_WIDTH],
    rows: [new TableRow({
      children: [new TableCell({
        borders: {
          top: { style: BorderStyle.SINGLE, size: 1, color: COLORS.secondary },
          bottom: { style: BorderStyle.SINGLE, size: 1, color: COLORS.secondary },
          left: { style: BorderStyle.SINGLE, size: 12, color: COLORS.secondary },
          right: { style: BorderStyle.SINGLE, size: 1, color: COLORS.secondary },
        },
        width: { size: PAGE_WIDTH, type: WidthType.DXA },
        shading: { fill: COLORS.lightBg, type: ShadingType.CLEAR },
        margins: { top: 100, bottom: 100, left: 150, right: 150 },
        children: [
          new Paragraph({ children: [new TextRun({ text: title, bold: true, font: "Calibri", size: 20, color: COLORS.secondary })] }),
          new Paragraph({ spacing: { before: 60 }, children: [new TextRun({ text, font: "Calibri", size: 19, color: COLORS.darkText })] }),
        ]
      })]
    })]
  });
}

function diagramBox(lines, caption) {
  const children = lines.map(line =>
    new Paragraph({
      spacing: { after: 0, before: 0, line: 276 },
      children: [new TextRun({ text: line, font: "Consolas", size: 17, color: COLORS.primary })]
    })
  );
  children.push(new Paragraph({
    spacing: { before: 80 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: caption, font: "Calibri", size: 18, italic: true, color: COLORS.secondary })]
  }));

  return new Table({
    width: { size: PAGE_WIDTH, type: WidthType.DXA },
    columnWidths: [PAGE_WIDTH],
    rows: [new TableRow({
      children: [new TableCell({
        borders: {
          top: { style: BorderStyle.SINGLE, size: 2, color: COLORS.secondary },
          bottom: { style: BorderStyle.SINGLE, size: 2, color: COLORS.secondary },
          left: { style: BorderStyle.SINGLE, size: 2, color: COLORS.secondary },
          right: { style: BorderStyle.SINGLE, size: 2, color: COLORS.secondary },
        },
        width: { size: PAGE_WIDTH, type: WidthType.DXA },
        shading: { fill: "FAFBFD", type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 120, left: 200, right: 200 },
        children
      })]
    })]
  });
}

function spacer(pts = 100) {
  return new Paragraph({ spacing: { before: pts, after: 0 }, children: [] });
}

// ── Architecture Diagram (ASCII) ──
const archDiagram = [
  "+===========================================================================+",
  "|                    MT5 TRADE MONITORING SYSTEM ARCHITECTURE                |",
  "+===========================================================================+",
  "",
  "  +------------------+   +------------------+   +------------------+",
  "  |  MT5 Terminal 1   |   |  MT5 Terminal 2   |   |  MT5 Terminal N   |",
  "  |  (Account A)      |   |  (Account B)      |   |  (Account N)      |",
  "  |  [Data Export EA] |   |  [Data Export EA] |   |  [Data Export EA] |",
  "  +--------+---------+   +--------+---------+   +--------+---------+",
  "           |                       |                       |",
  "           |   CSV/JSON Files      |                       |",
  "           +----------+------------+-----------+-----------+",
  "                      |                        |",
  "                      v                        v",
  "           +----------+----------+  +----------+----------+",
  "           |  Local File System  |  | MT5 Manager API     |",
  "           |  C:/MT5Data/        |  | (Future - Phase 2)  |",
  "           +----------+----------+  +----------+----------+",
  "                      |                        |",
  "                      +----------+-------------+",
  "                                 |",
  "                                 v",
  "              +------------------+------------------+",
  "              |        PYTHON ETL PIPELINE          |",
  "              |  +------------+ +------------+      |",
  "              |  |  EXTRACT   | | TRANSFORM  |      |",
  "              |  | File Watch | | Validation |      |",
  "              |  | API Pull   | | Metrics    |      |",
  "              |  +------+-----+ | Currency   |      |",
  "              |         |       | Normalize  |      |",
  "              |         v       +------+-----+      |",
  "              |  +------+-----+        |            |",
  "              |  |    LOAD    |<-------+            |",
  "              |  |  Upsert   |  +------------+     |",
  "              |  |  Append   |  | SCHEDULER  |     |",
  "              |  +------+----+  | APScheduler|     |",
  "              |         |       | Cron Jobs  |     |",
  "              +---------+-------+------+-----+-----+",
  "                        |              |",
  "                        v              v",
  "              +---------+--------+  +--+-------------+",
  "              |   PostgreSQL /   |  | ALERTING       |",
  "              |   Supabase DB   |  | ENGINE         |",
  "              |                  |  |                |",
  "              | - account_snap  |  | +------------+ |",
  "              | - positions     |  | | Telegram   | |",
  "              | - deals         |  | | Bot API    | |",
  "              | - orders        |  | +------------+ |",
  "              | - symbols       |  | +------------+ |",
  "              | - daily_pnl     |  | | Email      | |",
  "              | - alerts        |  | | SMTP       | |",
  "              | - pipeline_runs |  | +------------+ |",
  "              +--------+--------+  +----------------+",
  "                       |",
  "          +------------+-------------+",
  "          |                          |",
  "          v                          v",
  "+--------+--------+    +------------+-----------+",
  "|   DASHBOARD      |    |   REPORT GENERATOR    |",
  "|                   |    |                       |",
  "| Option A: Grafana |    | - Daily PDF Summary  |",
  "| Option B: Next.js |    | - Weekly Excel       |",
  "|                   |    | - Monthly Client PDF |",
  "| - Exec Summary    |    |                       |",
  "| - Trade Activity  |    | ReportLab + openpyxl |",
  "| - Positions       |    +-----------------------+",
  "| - P&L Analysis    |",
  "| - Risk Monitor    |",
  "| - Client Perf     |",
  "| - Exposure        |",
  "+-------------------+",
];

// ── Network Diagram ──
const networkDiagram = [
  "+===========================================================================+",
  "|                       NETWORK & DEPLOYMENT TOPOLOGY                        |",
  "+===========================================================================+",
  "",
  "  TRADING FLOOR / OFFICE NETWORK              CLOUD / VPS",
  "  ================================             ==========================",
  "",
  "  +------------------+                         +----------------------+",
  "  | Windows Server / |     Firewall            |  VPS / Cloud Server  |",
  "  | Trading Machine  |     (Outbound           |  (Hetzner / DO /     |",
  "  |                  |      Only)              |   AWS Lightsail)     |",
  "  | +------+------+  |        |                |                      |",
  "  | | MT5  | MT5  |  | Port   |                | +------------------+ |",
  "  | | T-1  | T-2  |  | 443    |                | | Python ETL       | |",
  "  | +--+---+--+---+  +--------+--------------->| | Pipeline Service | |",
  "  |    |      |       |  HTTPS/TLS             | +--------+---------+ |",
  "  | +--+------+----+  |                        |          |           |",
  "  | | Data Export  |  |                        | +--------+---------+ |",
  "  | | EA (MQL5)    |  |                        | | PostgreSQL /     | |",
  "  | +------+-------+  |                        | | Supabase DB      | |",
  "  |        |          |                        | | Port 5432        | |",
  "  |        v          |                        | +--------+---------+ |",
  "  | +------+-------+  |                        |          |           |",
  "  | | Shared Drive |  |                        | +--------+---------+ |",
  "  | | C:/MT5Data/  |  |                        | | Grafana / Web    | |",
  "  | | (CSV/JSON)   |  |                        | | Dashboard        | |",
  "  | +------+-------+  |                        | | Port 443 (HTTPS) | |",
  "  |        |          |                        | +--------+---------+ |",
  "  +--------+----------+                        +----------+-----------+",
  "           |                                              |",
  "           |  Option A: File Sync                         |",
  "           |  (rsync/SCP/SFTP every 5 min)                |",
  "           +--------------------------------------------->|",
  "           |                                              |",
  "           |  Option B: Same Machine                      |",
  "           |  (Pipeline reads files locally)              |",
  "           +------+                                       |",
  "                                                          |",
  "                                                          |",
  "  EXTERNAL SERVICES                                       |",
  "  ==================                                      |",
  "                                                          |",
  "  +-------------------+    API Calls                      |",
  "  | Telegram Bot API  |<----------------------------------+",
  "  | api.telegram.org  |    (Alert Notifications)          |",
  "  +-------------------+                                   |",
  "                                                          |",
  "  +-------------------+    SMTP                           |",
  "  | Email Server      |<----------------------------------+",
  "  | (Gmail/SendGrid)  |    (Reports & Alerts)             |",
  "  +-------------------+                                   |",
  "                                                          |",
  "  +-------------------+    HTTPS                          |",
  "  | Exchange Rate API |<----------------------------------+",
  "  | (Fixer.io/ECB)    |    (Currency Conversion)          |",
  "  +-------------------+                                   |",
  "                                                          v",
  "  END USERS                                    +----------+---------+",
  "  ==========                                   | HTTPS / Port 443   |",
  "                                               +----------+---------+",
  "  +------------------+                                    |",
  "  | Desktop Browser  |<------ HTTPS (TLS 1.3) -----------+",
  "  +------------------+                                    |",
  "  +------------------+                                    |",
  "  | Mobile Browser   |<------ HTTPS (TLS 1.3) -----------+",
  "  +------------------+                                    |",
  "  +------------------+                                    |",
  "  | Telegram Mobile  |<------ Push Notifications ---------+",
  "  +------------------+",
];

// ── Data Flow Diagram ──
const dataFlowDiagram = [
  "+===========================================================================+",
  "|                         DATA FLOW DIAGRAM (DFD)                           |",
  "+===========================================================================+",
  "",
  "  1. DATA EXTRACTION (Every 5 Minutes)",
  "  =====================================",
  "  MT5 Terminal -----> EA Timer Event -----> MQL5 Functions",
  "                                            |",
  "                         +------------------+------------------+",
  "                         |                  |                  |",
  "                         v                  v                  v",
  "                   AccountInfo()      PositionsTotal()   HistorySelect()",
  "                   Balance,Equity     Open Positions     Deals History",
  "                   Margin,Leverage    Symbol,Volume      P&L,Commission",
  "                         |                  |                  |",
  "                         v                  v                  v",
  "                   account.csv         positions.csv      deals.csv",
  "",
  "  2. DATA PIPELINE (ETL Process)",
  "  ===============================",
  "  Raw CSV Files",
  "       |",
  "       v",
  "  [EXTRACT] ---> Read files, parse CSV, detect new records",
  "       |",
  "       v",
  "  [VALIDATE] --> Check data types, required fields, duplicates",
  "       |",
  "       v",
  "  [TRANSFORM] -> Calculate derived metrics:",
  "       |         - Win Rate = Wins / Total Trades",
  "       |         - Profit Factor = Gross Profit / Gross Loss",
  "       |         - Drawdown = (Peak - Current) / Peak",
  "       |         - Sharpe = Avg Return / StdDev(Returns)",
  "       |         - VaR 95% = Historical simulation",
  "       |         - Normalize currencies to USD",
  "       v",
  "  [LOAD] ------> Upsert to PostgreSQL (accounts, positions)",
  "       |         Append to PostgreSQL (deals - incremental)",
  "       |         Refresh materialized views",
  "       v",
  "  [EVALUATE] --> Check alert conditions against thresholds",
  "       |",
  "       +---> [ALERT] ---> Telegram / Email if triggered",
  "       |",
  "       +---> [LOG] -----> Pipeline execution metrics",
  "",
  "  3. DATA CONSUMPTION",
  "  ====================",
  "  PostgreSQL -----> Materialized Views -----> Dashboard Queries",
  "       |                                           |",
  "       |                              +------------+------------+",
  "       |                              |            |            |",
  "       v                              v            v            v",
  "  Report Generator            Executive    Trade       Risk",
  "  (Daily/Weekly/Monthly)      Summary      Activity    Monitor",
];

// ── Security Architecture ──
const securityDiagram = [
  "+===========================================================================+",
  "|                      SECURITY ARCHITECTURE                                 |",
  "+===========================================================================+",
  "",
  "  +------------------+     +-------------------+     +------------------+",
  "  |   END USERS      |     |   AUTH LAYER      |     |   APPLICATION    |",
  "  |                  |     |                   |     |                  |",
  "  | Browser / Mobile | --> | TLS 1.3 (HTTPS)   | --> | Dashboard App   |",
  "  |                  |     | JWT Auth Tokens    |     |                  |",
  "  |                  |     | Role-Based Access  |     | Role: Admin     |",
  "  |                  |     |   - Admin          |     |   Full access   |",
  "  |                  |     |   - Manager        |     | Role: Manager   |",
  "  |                  |     |   - Viewer         |     |   Own accounts  |",
  "  +------------------+     +-------------------+     | Role: Viewer    |",
  "                                                     |   Read-only     |",
  "                                                     +--------+--------+",
  "                                                              |",
  "  +----------------------------------------------------------+",
  "  |",
  "  v",
  "  +-------------------+     +-------------------+",
  "  | DATABASE SECURITY |     | DATA PROTECTION   |",
  "  |                   |     |                   |",
  "  | - SSL connections |     | - No PII in logs  |",
  "  | - IP whitelisting |     | - Encrypted at    |",
  "  | - Strong passwords|     |   rest (AES-256)  |",
  "  | - Read-only user  |     | - API keys in     |",
  "  |   for dashboard   |     |   env variables   |",
  "  | - Backup daily    |     | - Audit trail     |",
  "  +-------------------+     +-------------------+",
];

// ── BUILD DOCUMENT ──
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 20, color: COLORS.darkText } }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: COLORS.primary },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: COLORS.secondary },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Calibri", color: COLORS.primary },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 }
      },
    ]
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ]
      },
      {
        reference: "numbers",
        levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.DECIMAL, text: "%1.%2.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ]
      },
    ]
  },
  sections: [
    // ═══════════════════════════════════════
    // TITLE PAGE
    // ═══════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: [
        spacer(2400),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "REY CAPITAL", font: "Calibri", size: 52, bold: true, color: COLORS.primary })]
        }),
        spacer(200),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.secondary, space: 1 } },
          children: []
        }),
        spacer(200),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Software Requirements Document", font: "Calibri", size: 40, color: COLORS.secondary })]
        }),
        spacer(100),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "MT5 Trade Monitoring & Analytics Dashboard", font: "Calibri", size: 28, color: COLORS.primary })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "with Automated Data Pipeline", font: "Calibri", size: 28, color: COLORS.primary })]
        }),
        spacer(600),
        // Document Info Table
        new Table({
          width: { size: 5000, type: WidthType.DXA },
          columnWidths: [2000, 3000],
          rows: [
            ["Document ID", "RC-SRD-WS3-001"],
            ["Version", "1.0"],
            ["Date", "April 1, 2026"],
            ["Status", "Draft"],
            ["Classification", "Confidential"],
            ["Workstream", "Workstream 3"],
          ].map(([k, v]) => new TableRow({
            children: [
              new TableCell({
                borders: noBorders, width: { size: 2000, type: WidthType.DXA }, margins: { top: 40, bottom: 40, left: 60, right: 60 },
                children: [new Paragraph({ children: [new TextRun({ text: k, bold: true, font: "Calibri", size: 20, color: COLORS.secondary })] })]
              }),
              new TableCell({
                borders: noBorders, width: { size: 3000, type: WidthType.DXA }, margins: { top: 40, bottom: 40, left: 60, right: 60 },
                children: [new Paragraph({ children: [new TextRun({ text: v, font: "Calibri", size: 20, color: COLORS.darkText })] })]
              }),
            ]
          }))
        }),
      ]
    },

    // ═══════════════════════════════════════
    // REVISION HISTORY + TOC
    // ═══════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: COLORS.secondary, space: 1 } },
            children: [
              new TextRun({ text: "Rey Capital  |  SRD - MT5 Trade Dashboard  |  RC-SRD-WS3-001", font: "Calibri", size: 16, color: COLORS.secondary })
            ]
          })]
        })
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            border: { top: { style: BorderStyle.SINGLE, size: 2, color: COLORS.medGray, space: 1 } },
            children: [
              new TextRun({ text: "Confidential  |  Page ", font: "Calibri", size: 16, color: COLORS.medGray }),
              new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 16, color: COLORS.medGray }),
            ]
          })]
        })
      },
      children: [
        heading1("Revision History"),
        makeTable(
          ["Version", "Date", "Author", "Description"],
          [
            ["1.0", "April 1, 2026", "Rey Capital / AI Team", "Initial SRD creation"],
            ["", "", "", "Pending review and sign-off"],
          ],
          [1200, 2000, 2600, 3560]
        ),
        spacer(300),
        heading1("Table of Contents"),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),

        // ═══════════════════════════════════════
        // 1. INTRODUCTION
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("1. Introduction"),

        heading2("1.1 Purpose"),
        para("This Software Requirements Document (SRD) defines the functional and non-functional requirements for the MT5 Trade Monitoring and Analytics Dashboard with Automated Data Pipeline. It serves as the primary reference for design, development, testing, and acceptance of the system."),

        heading2("1.2 Scope"),
        para("The system will provide Rey Capital with a centralized platform to monitor trading activity, client account performance, open positions, profit and loss metrics, and risk exposure across multiple MetaTrader 5 (MT5) trading accounts managed through CFI broker."),
        para("The solution consists of four integrated components:"),
        numberedItem("MQL5 Data Exporter EA - Automated data extraction from MT5 terminals"),
        numberedItem("Python ETL Pipeline - Data processing, transformation, and loading"),
        numberedItem("PostgreSQL Database - Centralized data storage with analytics views"),
        numberedItem("Interactive Dashboard - Real-time visualization with alerting"),

        heading2("1.3 Intended Audience"),
        bullet("Development team (system architects, developers, QA)"),
        bullet("Project managers and stakeholders at Rey Capital"),
        bullet("Operations and risk management personnel"),
        bullet("System administrators responsible for deployment"),

        heading2("1.4 Definitions and Acronyms"),
        makeTable(
          ["Term", "Definition"],
          [
            ["MT5", "MetaTrader 5 - Trading platform by MetaQuotes"],
            ["EA", "Expert Advisor - Automated script running in MT5"],
            ["ETL", "Extract, Transform, Load - Data pipeline process"],
            ["API", "Application Programming Interface"],
            ["SRD", "Software Requirements Document"],
            ["AUM", "Assets Under Management"],
            ["P&L", "Profit and Loss"],
            ["VaR", "Value at Risk - Statistical risk measure"],
            ["MAM", "Multi-Account Manager"],
            ["PAMM", "Percentage Allocation Management Module"],
            ["SL/TP", "Stop Loss / Take Profit"],
            ["CFI", "CFI Financial Group - Broker"],
          ],
          [2500, 6860]
        ),

        // ═══════════════════════════════════════
        // 2. SYSTEM OVERVIEW
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("2. System Overview"),

        heading2("2.1 System Context"),
        para("Rey Capital manages multiple client trading accounts through the CFI broker on the MetaTrader 5 platform. Currently, monitoring of these accounts requires manual checking of individual MT5 terminals, which is time-consuming and provides no consolidated view of risk or performance."),
        para("This system automates the entire data collection and visualization pipeline, providing stakeholders with a single dashboard to monitor all accounts in near real-time with a maximum data delay of 5 minutes."),

        heading2("2.2 System Architecture Diagram"),
        diagramBox(archDiagram, "Figure 1: High-Level System Architecture"),

        heading2("2.3 Key Design Decisions"),
        makeTable(
          ["Decision", "Choice", "Rationale"],
          [
            ["Data Extraction", "MQL5 EA (Phase 1)", "No Manager API access; EA works within standard terminal capabilities"],
            ["Pipeline Technology", "Python + APScheduler", "Lightweight, no infrastructure overhead vs. Airflow; team expertise in Python"],
            ["Database", "PostgreSQL / Supabase", "Proven for analytics; Supabase adds instant REST API and auth layer"],
            ["Dashboard", "Grafana or Next.js", "Grafana for rapid deployment; Next.js for full customization"],
            ["Export Format", "CSV files", "Universal, easy to parse, no binary dependencies"],
            ["Refresh Interval", "5 minutes", "Balances data freshness with system performance"],
            ["Alert Channel", "Telegram + Email", "Instant mobile reach + formal audit trail"],
          ],
          [2000, 2400, 4960]
        ),

        // ═══════════════════════════════════════
        // 3. FUNCTIONAL REQUIREMENTS
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("3. Functional Requirements"),

        heading2("3.1 Data Extraction (FR-100)"),
        heading3("FR-101: Account Data Export"),
        para("The MQL5 EA shall export account snapshot data including balance, equity, margin, free margin, margin level, leverage, and floating P&L at configurable intervals (default: 5 minutes)."),
        heading3("FR-102: Open Positions Export"),
        para("The EA shall export all current open positions including position ID, symbol, direction, volume, entry price, current price, SL, TP, swap, floating P&L, open time, magic number, and comment."),
        heading3("FR-103: Deal History Export (Incremental)"),
        para("The EA shall export new deal history records since the last export. On first run, it shall backfill all available history (configurable, default: 365 days). Each deal includes deal ID, order ID, position ID, symbol, type, entry type, volume, price, commission, swap, profit, timestamp, magic, and comment."),
        heading3("FR-104: Pending Orders Export"),
        para("The EA shall export all current pending orders including ticket, symbol, type, volume, price, SL, TP, setup time, magic number, and comment."),
        heading3("FR-105: Symbol Information Export"),
        para("The EA shall export symbol metadata including name, asset class, contract size, tick size, tick value, spread, and digits. This export runs once daily."),
        heading3("FR-106: Heartbeat Mechanism"),
        para("The EA shall write a heartbeat file with the current timestamp after each successful export cycle. The pipeline shall use this to detect stale or stopped EAs."),
        heading3("FR-107: Multi-Account Support"),
        para("Each MT5 terminal instance shall run one EA instance. Data shall be exported to account-specific subdirectories: C:/MT5Data/{AccountNumber}/."),

        heading2("3.2 Data Pipeline (FR-200)"),
        heading3("FR-201: Automated File Ingestion"),
        para("The pipeline shall monitor the export directory and ingest new/updated files from all account subdirectories every pipeline cycle (default: 5 minutes)."),
        heading3("FR-202: Data Validation"),
        para("The pipeline shall validate all ingested data for:"),
        bullet("Required fields are present and non-null"),
        bullet("Data types match expected formats (numeric, timestamp, string)"),
        bullet("Deal IDs are unique (no duplicate ingestion)"),
        bullet("Timestamps are within reasonable range"),
        bullet("Account numbers match known/registered accounts"),
        heading3("FR-203: Data Transformation"),
        para("The pipeline shall compute the following derived metrics:"),
        makeTable(
          ["Metric", "Formula", "Category"],
          [
            ["Win Rate (%)", "Winning Trades / Total Closed Trades * 100", "Performance"],
            ["Profit Factor", "Sum(Positive P&L) / |Sum(Negative P&L)|", "Performance"],
            ["Expectancy", "(Win% * Avg Win) - (Loss% * Avg Loss)", "Performance"],
            ["Sharpe Ratio", "(Avg Daily Return - Rf) / StdDev(Daily Returns)", "Risk-Adjusted"],
            ["Sortino Ratio", "(Avg Daily Return - Rf) / StdDev(Negative Daily Returns)", "Risk-Adjusted"],
            ["Max Drawdown (%)", "(Peak Equity - Trough Equity) / Peak Equity * 100", "Risk"],
            ["Calmar Ratio", "Annualized Return / Max Drawdown", "Risk-Adjusted"],
            ["VaR 95%", "5th percentile of daily return distribution", "Risk"],
            ["Margin Level", "(Equity / Used Margin) * 100", "Risk"],
            ["Concentration Risk", "Max Symbol Volume / Total Volume * 100", "Exposure"],
            ["Net Exposure", "Sum(Long Volume) - Sum(Short Volume) per symbol", "Exposure"],
          ],
          [2400, 4560, 2400]
        ),
        heading3("FR-204: Currency Normalization"),
        para("All monetary values shall be normalized to a base currency (USD) using exchange rates fetched from a reliable API (e.g., ECB, Fixer.io). Exchange rates shall be cached and refreshed every 4 hours."),
        heading3("FR-205: Incremental Processing"),
        para("The pipeline shall track the last processed deal ID per account to ensure only new deals are ingested on each cycle, preventing duplicate records and reducing processing time."),
        heading3("FR-206: Daily Aggregation"),
        para("The pipeline shall compute and store daily P&L snapshots per account at end of trading day, including: starting balance, ending balance, realized P&L, commissions, swaps, deposits, withdrawals, and trade counts."),

        heading2("3.3 Database (FR-300)"),
        heading3("FR-301: Core Tables"),
        para("The database shall implement the following core tables:"),
        makeTable(
          ["Table", "Type", "Key", "Description"],
          [
            ["account_snapshots", "Time-series", "account_number + snapshot_time", "Periodic account state captures"],
            ["positions", "Current state", "position_id + account_number", "All currently open positions"],
            ["deals", "Append-only", "deal_id", "Complete trade execution history"],
            ["pending_orders", "Current state", "ticket", "Active pending orders"],
            ["symbols", "Reference", "symbol", "Trading instrument metadata"],
            ["daily_pnl", "Aggregated", "account_number + trade_date", "Daily performance snapshots"],
            ["alerts", "Event log", "id (serial)", "Alert history with acknowledgment"],
            ["pipeline_runs", "Audit log", "id (serial)", "Pipeline execution history"],
          ],
          [2200, 1600, 2800, 2760]
        ),
        heading3("FR-302: Materialized Views"),
        para("The database shall maintain the following materialized views, refreshed after each pipeline cycle:"),
        bullet("mv_account_overview - Latest account state with position counts and P&L"),
        bullet("mv_symbol_exposure - Net long/short exposure per symbol across all accounts"),
        bullet("mv_trading_performance - Rolling 30-day performance metrics per account"),
        heading3("FR-303: Data Retention"),
        para("Account snapshots shall be retained for 90 days (configurable). Deal history shall be retained indefinitely. Daily P&L aggregations shall be retained indefinitely. Positions and orders tables reflect current state only."),

        heading2("3.4 Dashboard (FR-400)"),
        heading3("FR-401: Executive Summary Module"),
        para("Shall display: Total AUM, active account count, aggregate floating P&L, aggregate realized P&L (today/week/month), total open positions, and system health status (pipeline status, data freshness)."),
        heading3("FR-402: Account Overview Module"),
        para("Shall display a sortable, filterable table of all accounts with columns: Account #, Name, Balance, Equity, Floating P&L, Margin Level, Open Positions, Last Updated. Color coding: Red for margin < 200%, Yellow for < 500%."),
        heading3("FR-403: Trade Activity Module"),
        para("Shall display: Trade count timeline (bar chart), recent trades table (last 50), volume by symbol (pie chart), buy vs sell distribution, and time-of-day heatmap."),
        heading3("FR-404: Open Positions Module"),
        para("Shall display: All open positions across all accounts, grouped/filterable by symbol, heatmap by account x symbol, and largest positions highlighted."),
        heading3("FR-405: Profit & Loss Module"),
        para("Shall display: Equity curve (line chart), daily P&L bar chart (green/red), cumulative P&L, P&L breakdown (gross, commissions, swaps, net), and P&L by symbol."),
        heading3("FR-406: Client Performance Module"),
        para("Shall display: Per-account performance cards, win rate, profit factor, Sharpe ratio, account comparison view, and deposit/withdrawal timeline per account."),
        heading3("FR-407: Symbol Exposure Module"),
        para("Shall display: Net exposure by symbol (long vs short), exposure by asset class, correlation risk indicator, and concentration risk percentage."),
        heading3("FR-408: Risk Monitoring Module"),
        para("Shall display: Margin level gauges per account, drawdown tracking (current vs max historical), alert configuration panel, alert history log, and VaR estimate at 95%/99%."),
        heading3("FR-409: Filtering and Drill-Down"),
        para("All dashboard modules shall support: Date range filtering, account selection (single/multi/all), symbol filtering, and strategy filtering (by magic number or comment tag)."),

        heading2("3.5 Alerting System (FR-500)"),
        heading3("FR-501: Alert Channels"),
        para("The system shall support alert delivery via:"),
        bullet("Telegram Bot - Instant mobile push notifications"),
        bullet("Email (SMTP) - Formatted HTML emails"),
        bullet("Dashboard Banner - In-app notification bar"),
        heading3("FR-502: Configurable Alert Rules"),
        makeTable(
          ["Alert ID", "Alert Name", "Default Threshold", "Severity"],
          [
            ["ALT-001", "Critical Margin Level", "Margin Level < 200%", "CRITICAL"],
            ["ALT-002", "Margin Warning", "Margin Level < 500%", "WARNING"],
            ["ALT-003", "Severe Drawdown", "Equity Drawdown > 20% from peak", "CRITICAL"],
            ["ALT-004", "Moderate Drawdown", "Equity Drawdown > 10% from peak", "WARNING"],
            ["ALT-005", "Large Position", "Single position > 5% of equity", "WARNING"],
            ["ALT-006", "EA Heartbeat Stale", "No update > 10 minutes", "WARNING"],
            ["ALT-007", "Pipeline Failure", "3+ consecutive pipeline failures", "CRITICAL"],
            ["ALT-008", "Unusual Volume", "Volume > 3x daily average", "INFO"],
            ["ALT-009", "High Swap Cost", "Swap > configured threshold per position", "INFO"],
            ["ALT-010", "Dormant Account", "No trades in 7+ days", "INFO"],
          ],
          [1200, 2200, 3560, 2400]
        ),
        heading3("FR-503: Alert Deduplication"),
        para("The system shall not send duplicate alerts for the same condition within a configurable cooldown period (default: 30 minutes). Once acknowledged, the alert shall not re-trigger until the condition resolves and recurs."),

        heading2("3.6 Report Generation (FR-600)"),
        heading3("FR-601: Daily Summary Report"),
        para("Auto-generated PDF emailed at market close. Contains: account balances, equity changes, P&L summary, open positions count, and alerts triggered."),
        heading3("FR-602: Weekly Performance Report"),
        para("Auto-generated PDF emailed every Friday. Contains: week-over-week comparison, win rate, profit factor, Sharpe ratio, top/bottom accounts, and symbol exposure."),
        heading3("FR-603: Monthly Client Report"),
        para("Auto-generated PDF emailed 1st of each month. Contains: full month performance, equity curve chart, trade log, risk metrics, and comparison vs previous month."),

        // ═══════════════════════════════════════
        // 4. NON-FUNCTIONAL REQUIREMENTS
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("4. Non-Functional Requirements"),

        heading2("4.1 Performance (NFR-100)"),
        makeTable(
          ["Requirement ID", "Description", "Target"],
          [
            ["NFR-101", "Pipeline cycle completion time", "< 60 seconds for 50 accounts"],
            ["NFR-102", "Dashboard page load time", "< 3 seconds"],
            ["NFR-103", "Dashboard data refresh", "< 5 minutes from MT5 to dashboard"],
            ["NFR-104", "Database query response (materialized views)", "< 500 milliseconds"],
            ["NFR-105", "Report generation time", "< 30 seconds per report"],
            ["NFR-106", "Alert delivery latency", "< 30 seconds from detection to notification"],
            ["NFR-107", "Concurrent dashboard users", "Up to 10 simultaneous users"],
          ],
          [1800, 5160, 2400]
        ),

        heading2("4.2 Reliability & Availability (NFR-200)"),
        makeTable(
          ["Requirement ID", "Description", "Target"],
          [
            ["NFR-201", "System uptime during trading hours", "99.5%"],
            ["NFR-202", "Pipeline failure recovery (auto-retry)", "3 retries with exponential backoff"],
            ["NFR-203", "Data loss tolerance", "Zero data loss for deal history"],
            ["NFR-204", "Database backup frequency", "Daily automated backups"],
            ["NFR-205", "Maximum acceptable data gap", "15 minutes (3 missed cycles before alert)"],
          ],
          [1800, 5160, 2400]
        ),

        heading2("4.3 Security (NFR-300)"),
        diagramBox(securityDiagram, "Figure 2: Security Architecture"),
        spacer(100),
        makeTable(
          ["Requirement ID", "Description", "Implementation"],
          [
            ["NFR-301", "Authentication", "JWT-based auth or Supabase Auth; mandatory login for all users"],
            ["NFR-302", "Authorization", "Role-based access: Admin (full), Manager (own accounts), Viewer (read-only)"],
            ["NFR-303", "Data encryption in transit", "TLS 1.3 for all HTTP and database connections"],
            ["NFR-304", "Data encryption at rest", "AES-256 encryption for database storage"],
            ["NFR-305", "Secrets management", "API keys and credentials stored in environment variables, never in code"],
            ["NFR-306", "Audit logging", "All user actions and data access logged with timestamp and user ID"],
            ["NFR-307", "IP whitelisting", "Database access restricted to pipeline and dashboard server IPs only"],
          ],
          [1800, 3160, 4400]
        ),

        heading2("4.4 Scalability (NFR-400)"),
        bullet("System shall support up to 100 trading accounts without architectural changes"),
        bullet("Database shall support up to 10 million deal records with acceptable query performance"),
        bullet("Pipeline shall scale horizontally by adding parallel extraction workers if needed"),
        bullet("Dashboard shall support additional modules without requiring full rebuild"),

        heading2("4.5 Maintainability (NFR-500)"),
        bullet("Code shall follow PEP 8 (Python) and ESLint standards (JavaScript/TypeScript)"),
        bullet("All pipeline modules shall have unit test coverage of at least 80%"),
        bullet("Configuration shall be externalized via YAML/env files (no hardcoded values)"),
        bullet("Database schema changes shall be managed via versioned migration scripts"),
        bullet("All components shall produce structured logs (JSON format) for monitoring"),

        // ═══════════════════════════════════════
        // 5. NETWORK & DEPLOYMENT
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("5. Network & Deployment Architecture"),

        heading2("5.1 Network Topology"),
        diagramBox(networkDiagram, "Figure 3: Network & Deployment Topology"),

        heading2("5.2 Deployment Options"),
        makeTable(
          ["Component", "Option A (Same Machine)", "Option B (Cloud/VPS)"],
          [
            ["MT5 Terminals", "Windows Server (Trading Machine)", "Windows Server (Trading Machine)"],
            ["Data Export EA", "Runs inside MT5", "Runs inside MT5"],
            ["File Transfer", "Local filesystem (direct access)", "rsync/SFTP to cloud every 5 min"],
            ["Python Pipeline", "Same Windows Server", "Linux VPS (Hetzner/DigitalOcean)"],
            ["PostgreSQL DB", "Same server or local network", "Supabase Cloud or VPS PostgreSQL"],
            ["Dashboard", "Localhost access only", "Cloud VPS with HTTPS (public/VPN)"],
            ["Cost Estimate", "~$0/month (existing infra)", "~$20-50/month for VPS"],
          ],
          [2200, 3580, 3580]
        ),

        heading2("5.3 Recommended Deployment (Hybrid)"),
        para("The recommended deployment uses a hybrid approach:"),
        numberedItem("MT5 terminals and EAs run on the existing Windows trading server"),
        numberedItem("Python pipeline runs on the same Windows server (reads files locally)"),
        numberedItem("Database hosted on Supabase (free tier supports up to 500MB, then $25/month)"),
        numberedItem("Dashboard hosted on Supabase or a $6/month VPS with HTTPS"),
        numberedItem("Alerts sent via Telegram Bot API and email (no cost)"),

        infoBox("Cost Advantage", "By keeping the pipeline on the existing trading server and using Supabase for DB + dashboard hosting, the total monthly infrastructure cost can be as low as $0-25/month for the initial deployment."),

        heading2("5.4 Data Flow Diagram"),
        diagramBox(dataFlowDiagram, "Figure 4: Data Flow Diagram - Extract, Transform, Load"),

        // ═══════════════════════════════════════
        // 6. DATA DICTIONARY
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("6. Data Dictionary"),

        heading2("6.1 Account Snapshots Table"),
        makeTable(
          ["Column", "Data Type", "Nullable", "Description"],
          [
            ["id", "BIGSERIAL", "No", "Auto-increment primary key"],
            ["account_number", "BIGINT", "No", "MT5 account login number"],
            ["account_name", "VARCHAR(255)", "Yes", "Client display name"],
            ["currency", "VARCHAR(10)", "No", "Account base currency (e.g., USD)"],
            ["balance", "DECIMAL(18,2)", "No", "Current account balance"],
            ["equity", "DECIMAL(18,2)", "No", "Current equity (balance + floating P&L)"],
            ["margin_used", "DECIMAL(18,2)", "No", "Margin currently in use"],
            ["free_margin", "DECIMAL(18,2)", "No", "Available margin"],
            ["margin_level", "DECIMAL(10,2)", "Yes", "Margin level percentage"],
            ["leverage", "INT", "No", "Account leverage ratio"],
            ["floating_pnl", "DECIMAL(18,2)", "No", "Unrealized profit/loss"],
            ["snapshot_time", "TIMESTAMP", "No", "Time of data capture"],
          ],
          [2200, 1800, 1200, 4160]
        ),

        heading2("6.2 Deals Table"),
        makeTable(
          ["Column", "Data Type", "Nullable", "Description"],
          [
            ["deal_id", "BIGINT (PK)", "No", "Unique deal ticket from MT5"],
            ["order_id", "BIGINT", "Yes", "Related order ticket"],
            ["position_id", "BIGINT", "Yes", "Related position identifier"],
            ["account_number", "BIGINT", "No", "Account that executed the deal"],
            ["symbol", "VARCHAR(50)", "No", "Trading instrument"],
            ["deal_type", "VARCHAR(20)", "No", "BUY, SELL, BALANCE, CREDIT, etc."],
            ["entry_type", "VARCHAR(10)", "No", "IN (open), OUT (close), INOUT (reverse)"],
            ["volume", "DECIMAL(10,4)", "No", "Trade volume in lots"],
            ["price", "DECIMAL(18,6)", "No", "Execution price"],
            ["commission", "DECIMAL(18,2)", "No", "Commission charged"],
            ["swap", "DECIMAL(18,2)", "No", "Swap/rollover cost"],
            ["profit", "DECIMAL(18,2)", "No", "Realized profit or loss"],
            ["executed_at", "TIMESTAMP", "No", "Execution timestamp"],
            ["magic_number", "INT", "Yes", "EA identifier (strategy tagging)"],
            ["comment", "VARCHAR(255)", "Yes", "Trade comment (strategy tagging)"],
          ],
          [2200, 1800, 1200, 4160]
        ),

        heading2("6.3 Positions Table"),
        makeTable(
          ["Column", "Data Type", "Nullable", "Description"],
          [
            ["position_id", "BIGINT", "No", "MT5 position identifier"],
            ["account_number", "BIGINT", "No", "Account holding the position"],
            ["symbol", "VARCHAR(50)", "No", "Trading instrument"],
            ["direction", "VARCHAR(4)", "No", "BUY or SELL"],
            ["volume", "DECIMAL(10,4)", "No", "Position size in lots"],
            ["open_price", "DECIMAL(18,6)", "No", "Entry price"],
            ["current_price", "DECIMAL(18,6)", "No", "Last known market price"],
            ["sl", "DECIMAL(18,6)", "Yes", "Stop loss level"],
            ["tp", "DECIMAL(18,6)", "Yes", "Take profit level"],
            ["swap", "DECIMAL(18,2)", "No", "Accumulated swap charges"],
            ["floating_pnl", "DECIMAL(18,2)", "No", "Unrealized P&L"],
            ["open_time", "TIMESTAMP", "No", "Position open timestamp"],
            ["magic_number", "INT", "Yes", "EA/strategy identifier"],
            ["comment", "VARCHAR(255)", "Yes", "Trade comment"],
          ],
          [2200, 1800, 1200, 4160]
        ),

        // ═══════════════════════════════════════
        // 7. INTERFACE SPECIFICATIONS
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("7. Interface Specifications"),

        heading2("7.1 MT5 EA to Pipeline Interface"),
        makeTable(
          ["Attribute", "Specification"],
          [
            ["Protocol", "File-based (CSV) - local filesystem"],
            ["File Encoding", "UTF-8"],
            ["Delimiter", "Comma (,)"],
            ["Date Format", "ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)"],
            ["Decimal Separator", "Period (.)"],
            ["Header Row", "Required (first row)"],
            ["File Naming", "{data_type}.csv (e.g., positions.csv)"],
            ["Directory Structure", "C:/MT5Data/{AccountNumber}/{filename}.csv"],
            ["Heartbeat", "C:/MT5Data/{AccountNumber}/heartbeat.txt"],
          ],
          [2800, 6560]
        ),

        heading2("7.2 Pipeline to Database Interface"),
        makeTable(
          ["Attribute", "Specification"],
          [
            ["Protocol", "PostgreSQL wire protocol (TCP)"],
            ["Port", "5432 (default) or Supabase port"],
            ["Connection", "SSL/TLS required"],
            ["Connection Pooling", "psycopg2 connection pool (min: 2, max: 10)"],
            ["Write Pattern", "UPSERT for snapshots/positions, INSERT for deals"],
            ["Transaction", "Each account processed in single transaction"],
          ],
          [2800, 6560]
        ),

        heading2("7.3 External API Interfaces"),
        makeTable(
          ["Service", "API", "Purpose", "Auth Method"],
          [
            ["Telegram", "api.telegram.org/bot{token}", "Alert notifications", "Bot Token"],
            ["Email", "SMTP (Gmail/SendGrid)", "Reports and alerts", "App Password / API Key"],
            ["Exchange Rates", "api.exchangeratesapi.io or ECB", "Currency normalization", "API Key (free tier)"],
          ],
          [1800, 2800, 2560, 2200]
        ),

        heading2("7.4 Future: MT5 Manager API Interface"),
        infoBox("Pending CFI Approval", "Manager API access has been requested from CFI broker. When granted, the extraction layer will be replaced with a direct API integration. The Manager API connects via TCP to the MT5 server using manager credentials and provides read access to all accounts, positions, deals, and orders from a single connection point. No changes to the database, pipeline processing, or dashboard layers will be required."),

        // ═══════════════════════════════════════
        // 8. TECHNOLOGY STACK
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("8. Technology Stack"),

        makeTable(
          ["Layer", "Technology", "Version", "License", "Purpose"],
          [
            ["Data Extraction", "MQL5 (Expert Advisor)", "MT5 Build 4000+", "Free (MetaQuotes)", "Extract data from MT5 terminal"],
            ["Data Pipeline", "Python", "3.11+", "Open Source", "ETL orchestration"],
            ["Scheduling", "APScheduler", "3.x", "MIT", "Task scheduling"],
            ["Data Processing", "pandas", "2.x", "BSD-3", "Data transformation"],
            ["Database", "PostgreSQL", "15+", "PostgreSQL License", "Data storage and analytics"],
            ["DB Hosting (Alt)", "Supabase", "Cloud", "Free / $25 mo", "Hosted PostgreSQL + REST API + Auth"],
            ["Dashboard (Opt A)", "Grafana", "10+", "AGPLv3 (Free)", "Real-time monitoring dashboards"],
            ["Dashboard (Opt B)", "Next.js + React", "14+", "MIT", "Custom web dashboard"],
            ["Charts", "Recharts / Lightweight Charts", "Latest", "MIT", "Data visualization"],
            ["Alerts", "python-telegram-bot", "20+", "LGPL-3", "Telegram notifications"],
            ["Email", "smtplib (built-in)", "Python stdlib", "PSF", "Email delivery"],
            ["Reports (PDF)", "ReportLab", "4.x", "BSD", "PDF report generation"],
            ["Reports (Excel)", "openpyxl", "3.x", "MIT", "Excel report generation"],
            ["Version Control", "Git", "2.x+", "GPLv2", "Source code management"],
          ],
          [1700, 2200, 1500, 1760, 2200]
        ),

        // ═══════════════════════════════════════
        // 9. RISK ANALYSIS
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("9. Risk Analysis"),

        heading2("9.1 Technical Risks"),
        makeTable(
          ["Risk ID", "Risk Description", "Probability", "Impact", "Mitigation"],
          [
            ["R-001", "Manager API not granted by CFI", "High", "Medium", "EA-per-terminal approach works as fallback; MAM terminal as alternative"],
            ["R-002", "MT5 terminal crash stops data export", "Medium", "High", "Heartbeat monitoring with alerts; auto-restart scripts for MT5"],
            ["R-003", "Multi-currency P&L normalization errors", "Medium", "Medium", "Use reliable exchange rate API; validate conversion results; audit trail"],
            ["R-004", "Data volume exceeds DB capacity", "Low", "High", "PostgreSQL partitioning by date; data retention policies; TimescaleDB if needed"],
            ["R-005", "Pipeline server downtime", "Low", "High", "Deploy on reliable VPS; health monitoring; manual re-run capability"],
            ["R-006", "MetaQuotes restricts data export", "Low", "High", "EA file export is standard terminal functionality; no API TOS violation"],
            ["R-007", "Network failure between MT5 and DB", "Medium", "Medium", "Local queue for failed writes; retry on reconnection; data integrity checks"],
            ["R-008", "Stale data shown on dashboard", "Medium", "Medium", "Data freshness indicator on every dashboard page; stale data warning"],
          ],
          [900, 2500, 1200, 1000, 3760]
        ),

        heading2("9.2 Business Risks"),
        makeTable(
          ["Risk ID", "Risk Description", "Probability", "Impact", "Mitigation"],
          [
            ["R-009", "Stakeholders expect true real-time", "Medium", "Medium", "Set clear expectation: 5-min delay; MT5 built-in alerts for immediate needs"],
            ["R-010", "Scope creep (additional features)", "High", "Medium", "Strict change control; enhancements tracked in backlog for future phases"],
            ["R-011", "Single point of knowledge", "Medium", "High", "Comprehensive documentation; code comments; deployment guide; training session"],
          ],
          [900, 2500, 1200, 1000, 3760]
        ),

        // ═══════════════════════════════════════
        // 10. CONSTRAINTS & ASSUMPTIONS
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("10. Constraints and Assumptions"),

        heading2("10.1 Constraints"),
        bullet("No MT5 Manager API access available at project start; system must work with standard terminal EAs"),
        bullet("Each MT5 terminal can only see its own account data (not other accounts on the same server)"),
        bullet("MT5 WebRequest() function has limitations (URL whitelisting, basic HTTP only)"),
        bullet("Dashboard must be accessible via standard web browser (no desktop client)"),
        bullet("Budget constraint for hosting infrastructure (prefer free/low-cost solutions)"),
        bullet("6-week delivery timeline as per SOW"),

        heading2("10.2 Assumptions"),
        bullet("Rey Capital will provide a Windows machine with MT5 terminals running for all managed accounts"),
        bullet("MT5 terminals will remain logged in and connected during trading hours"),
        bullet("CFI broker does not restrict EA execution or file export operations"),
        bullet("Historical deal data is available within MT5 terminal (at least 1 year back)"),
        bullet("Stakeholders have internet access to view the dashboard (browser-based)"),
        bullet("Telegram is an acceptable alert channel for all stakeholders"),
        bullet("Maximum number of managed accounts will not exceed 100 in the initial phase"),

        heading2("10.3 Dependencies"),
        makeTable(
          ["Dependency", "Owner", "Status", "Impact if Delayed"],
          [
            ["MT5 terminal access for all accounts", "Rey Capital", "Required", "Cannot extract data from missing accounts"],
            ["Manager API credentials from CFI", "CFI Broker", "Requested", "Phase 2 delayed; Phase 1 EA approach continues"],
            ["VPS/hosting provisioning", "Rey Capital / Dev Team", "Pending", "Can develop locally; deploy later"],
            ["Telegram Bot token", "Dev Team", "Not started", "Alerts cannot be sent via Telegram"],
            ["SMTP credentials (email)", "Rey Capital", "Not started", "Reports cannot be emailed"],
            ["Database provisioning (Supabase)", "Dev Team", "Not started", "Can use local PostgreSQL for development"],
          ],
          [2800, 1800, 1400, 3360]
        ),

        // ═══════════════════════════════════════
        // 11. PROJECT TIMELINE
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("11. Project Timeline"),

        makeTable(
          ["Week", "Phase", "Activities", "Deliverables"],
          [
            ["Week 1", "Requirements & Design", "Finalize requirements; database schema design; architecture review; environment setup", "Signed-off SRD; ERD diagram; dev environment ready"],
            ["Week 2", "Data Extraction", "MQL5 EA development; file export testing; multi-account setup; heartbeat mechanism", "Working EA on all accounts; data files flowing"],
            ["Week 3", "Pipeline & Database", "ETL pipeline development; database setup; materialized views; validation rules", "Pipeline running on schedule; data in database"],
            ["Week 4", "Dashboard Development", "Dashboard UI development (all 8 modules); chart implementation; filtering/drill-down", "Working dashboard with live data"],
            ["Week 5", "Alerts, Reports & Testing", "Alert engine; Telegram/email integration; PDF/Excel reports; end-to-end testing; bug fixes", "Alerting system live; automated reports; test results"],
            ["Week 6", "Deployment & Handover", "Production deployment; performance tuning; documentation; training session; handover", "Production system; user guide; training completed"],
          ],
          [1000, 1800, 3560, 3000]
        ),

        // ═══════════════════════════════════════
        // 12. ACCEPTANCE CRITERIA
        // ═══════════════════════════════════════
        heading1("12. Acceptance Criteria"),

        makeTable(
          ["AC ID", "Criteria", "Verification Method"],
          [
            ["AC-01", "Dashboard displays accurate account balances matching MT5 terminal values", "Manual comparison with MT5 terminal"],
            ["AC-02", "Data refreshes within 5 minutes of MT5 changes", "Timestamp comparison test"],
            ["AC-03", "All 8 dashboard modules are functional and display correct data", "Module-by-module walkthrough"],
            ["AC-04", "Alert notifications delivered to Telegram within 30 seconds of trigger", "Simulate alert condition and measure"],
            ["AC-05", "Deal history matches MT5 history with zero discrepancies", "Export comparison audit"],
            ["AC-06", "Pipeline recovers gracefully from errors without data loss", "Fault injection testing"],
            ["AC-07", "Daily/weekly/monthly reports generated and delivered on schedule", "Monitor over 1 week of operation"],
            ["AC-08", "System supports all current managed accounts simultaneously", "Load test with all accounts"],
            ["AC-09", "Dashboard accessible via web browser with proper authentication", "Access test from multiple devices"],
            ["AC-10", "Technical documentation and deployment guide provided", "Documentation review"],
          ],
          [1000, 5560, 2800]
        ),

        // ═══════════════════════════════════════
        // 13. APPENDIX
        // ═══════════════════════════════════════
        new Paragraph({ children: [new PageBreak()] }),
        heading1("13. Appendix"),

        heading2("13.1 Proposed Directory Structure"),
        diagramBox([
          "AlgoStrategies/",
          "+-- mql5/",
          "|   +-- experts/",
          "|       +-- MT5_DataExporter_EA.mq5",
          "+-- dashboard/",
          "|   +-- pipeline/",
          "|   |   +-- extract.py",
          "|   |   +-- transform.py",
          "|   |   +-- load.py",
          "|   |   +-- scheduler.py",
          "|   |   +-- alerts.py",
          "|   |   +-- reports.py",
          "|   +-- database/",
          "|   |   +-- schema.sql",
          "|   |   +-- views.sql",
          "|   |   +-- migrations/",
          "|   +-- web/                    (Next.js dashboard)",
          "|   |   +-- app/",
          "|   |   +-- components/",
          "|   |   +-- lib/",
          "|   +-- grafana/                (Grafana configs)",
          "|   |   +-- dashboards/",
          "|   +-- config/",
          "|   |   +-- settings.yaml",
          "|   |   +-- alerts.yaml",
          "|   +-- requirements.txt",
          "+-- docs/",
          "    +-- prompts/",
          "    |   +-- MT5_Trade_Dashboard_Prompt.md",
          "    +-- MT5_Dashboard_SRD.docx",
        ], "Figure 5: Proposed Project Directory Structure"),

        heading2("13.2 Related Documents"),
        bullet("MT5_Trade_Dashboard_Prompt.md - Development prompt and technical brief"),
        bullet("Rey_Capital_Final_SOW_Final_Combined_All_3.docx - Original Statement of Work"),
        bullet("CFI Manager API Request (pending) - Broker API access request"),

        spacer(200),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: COLORS.secondary, space: 1 } },
          spacing: { before: 200 },
          children: [new TextRun({ text: "--- End of Document ---", font: "Calibri", size: 20, italic: true, color: COLORS.secondary })]
        }),
      ]
    },
  ]
});

// ── Generate file ──
const outputPath = "D:/Projects/AlgoStrategies/AlgoStrategies/docs/MT5_Dashboard_SRD.docx";
Packer.toBuffer(doc).then(buffer => {
  require("fs").writeFileSync(outputPath, buffer);
  console.log("SRD document created:", outputPath);
  console.log("Size:", (buffer.length / 1024).toFixed(1), "KB");
});
