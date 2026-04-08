const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TabStopType, TabStopPosition
} = require("docx");

// Colors
const BLUE = "1F4E79";
const LIGHT_BLUE = "D5E8F0";
const GREEN_BG = "E2EFDA";
const RED_BG = "FCE4EC";
const ORANGE_BG = "FFF3E0";
const PURPLE_BG = "F3E5F5";
const GRAY_BG = "F5F5F5";
const YELLOW_BG = "FFF9C4";
const WHITE = "FFFFFF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

// Page dimensions
const PAGE_W = 12240;
const PAGE_H = 15840;
const MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9360

// Helpers
function cell(text, opts = {}) {
  const { bold, width, shading, font, size, alignment, colSpan } = opts;
  const children = [];
  if (Array.isArray(text)) {
    text.forEach(t => {
      children.push(new Paragraph({
        spacing: { after: 60 },
        alignment: alignment || AlignmentType.LEFT,
        children: [new TextRun({ text: t, bold: bold || false, font: font || "Arial", size: size || 20 })]
      }));
    });
  } else {
    children.push(new Paragraph({
      alignment: alignment || AlignmentType.LEFT,
      children: [new TextRun({ text: text, bold: bold || false, font: font || "Arial", size: size || 20 })]
    }));
  }
  const cellOpts = {
    borders,
    margins: cellMargins,
    children,
    width: width ? { size: width, type: WidthType.DXA } : undefined,
  };
  if (shading) cellOpts.shading = { fill: shading, type: ShadingType.CLEAR };
  if (colSpan) cellOpts.columnSpan = colSpan;
  return new TableCell(cellOpts);
}

function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: 300, after: 200 },
    children: [new TextRun({ text, bold: true, font: "Arial" })]
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after || 120 },
    alignment: opts.alignment || AlignmentType.LEFT,
    children: [new TextRun({
      text,
      font: opts.font || "Arial",
      size: opts.size || 22,
      bold: opts.bold || false,
      italics: opts.italics || false,
      color: opts.color || "000000"
    })]
  });
}

function bulletList(items, ref) {
  return items.map(item => new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text: item, font: "Arial", size: 22 })]
  }));
}

function numberList(items, ref) {
  return items.map(item => new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text: item, font: "Arial", size: 22 })]
  }));
}

function tipBox(title, text, bgColor) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders,
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            shading: { fill: bgColor, type: ShadingType.CLEAR },
            width: { size: CONTENT_W, type: WidthType.DXA },
            children: [
              new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: title, bold: true, font: "Arial", size: 22 })] }),
              new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20 })] }),
            ]
          })
        ]
      })
    ]
  });
}

// Column widths for settings tables
const COL_SETTING = 3200;
const COL_DEFAULT = 1600;
const COL_DESC = CONTENT_W - COL_SETTING - COL_DEFAULT; // 4560

function settingsRow(setting, defVal, desc, bg) {
  return new TableRow({
    children: [
      cell(setting, { width: COL_SETTING, bold: true, shading: bg }),
      cell(defVal, { width: COL_DEFAULT, alignment: AlignmentType.CENTER, shading: bg }),
      cell(desc, { width: COL_DESC, shading: bg }),
    ]
  });
}

function settingsHeader() {
  return new TableRow({
    children: [
      cell("Setting", { width: COL_SETTING, bold: true, shading: BLUE, font: "Arial", size: 20 }),
      cell("Default", { width: COL_DEFAULT, bold: true, shading: BLUE, alignment: AlignmentType.CENTER, font: "Arial", size: 20 }),
      cell("Description", { width: COL_DESC, bold: true, shading: BLUE, font: "Arial", size: 20 }),
    ]
  });
}

// Make header cells white text
function headerCell(text, width) {
  return new TableCell({
    borders,
    margins: cellMargins,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: BLUE, type: ShadingType.CLEAR },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, font: "Arial", size: 20, color: "FFFFFF" })]
    })]
  });
}

function settingsHeaderRow() {
  return new TableRow({
    children: [
      headerCell("Setting", COL_SETTING),
      headerCell("Default", COL_DEFAULT),
      headerCell("Description", COL_DESC),
    ]
  });
}

// ============================================================================
// DOCUMENT CONTENT
// ============================================================================

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 280, after: 180 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "333333" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "bullets2",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "bullets3",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "bullets4",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers1",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers2",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers3",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "200 EMA Squeeze Strategy - Manual Trading Guide", font: "Arial", size: 16, color: "999999", italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "AlgoStrategies | Page ", font: "Arial", size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "999999" }),
          ]
        })]
      })
    },
    children: [

      // ====== TITLE PAGE ======
      new Paragraph({ spacing: { before: 3000 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: "200 EMA Squeeze Strategy", font: "Arial", size: 56, bold: true, color: BLUE })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: "Manual Trading Guide", font: "Arial", size: 32, color: "666666" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 1 } },
        children: []
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: "A simple trend-following strategy using a single EMA", font: "Arial", size: 24, italics: true, color: "555555" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: "with partial profit booking and EMA touch entries", font: "Arial", size: 24, italics: true, color: "555555" })]
      }),
      new Paragraph({ spacing: { before: 1200 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "April 2026", font: "Arial", size: 22, color: "888888" })]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 1: STRATEGY OVERVIEW ======
      heading("1. Strategy Overview", HeadingLevel.HEADING_1),
      para("The 200 EMA Squeeze is a trend-following strategy that uses a single Exponential Moving Average (EMA) to determine trade direction. Trades are only opened when price touches or crosses the EMA \u2014 not when price is away from it. After an exit, the strategy stays flat until price returns to touch the EMA again."),

      heading("Core Concept", HeadingLevel.HEADING_2),
      ...bulletList([
        "Price TOUCHES the EMA and closes ABOVE = LONG entry",
        "Price TOUCHES the EMA and closes BELOW = SHORT entry",
        "When price returns to EMA, close ALL lots and go FLAT",
        "Next trade only opens when price touches the EMA again",
        "Book partial profits at fixed point intervals while the trend runs",
        "Remaining position carries forward until the EMA exit",
      ], "bullets"),

      tipBox("Key Principle", "This strategy only trades at the EMA. No entries are taken when price is far from the EMA. After every exit, you wait patiently for the next EMA touch to re-enter.", GREEN_BG),

      new Paragraph({ spacing: { after: 200 } }),

      // ====== SECTION 2: ENTRY RULES ======
      heading("2. Entry Rules", HeadingLevel.HEADING_1),

      heading("Long Entry", HeadingLevel.HEADING_2),
      para("Open a BUY position when:", { bold: true }),
      ...numberList([
        "The candle TOUCHES the 200 EMA (the candle's low is at or below the EMA AND the high is at or above the EMA)",
        "The candle CLOSES above the 200 EMA",
        "You are currently FLAT (no open position)",
      ], "numbers1"),

      heading("Short Entry", HeadingLevel.HEADING_2),
      para("Open a SELL position when:", { bold: true }),
      ...numberList([
        "The candle TOUCHES the 200 EMA (the candle's high is at or above the EMA AND the low is at or below the EMA)",
        "The candle CLOSES below the 200 EMA",
        "You are currently FLAT (no open position)",
      ], "numbers2"),

      tipBox("Important", "Entry requires the candle to TOUCH the EMA. If price is far away from the EMA (both high and low on the same side), do NOT enter. Wait for price to come back and touch the EMA before opening a new trade.", ORANGE_BG),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 3: EXIT RULES ======
      heading("3. Exit Rules", HeadingLevel.HEADING_1),
      para("There are six exit modes. Choose one from the dropdown based on your preference:"),

      heading("Option A: Candle Close (Conservative)", HeadingLevel.HEADING_2),
      ...bulletList([
        "LONG exit: Candle CLOSES below the EMA",
        "SHORT exit: Candle CLOSES above the EMA",
        "More reliable signal, fewer whipsaws",
      ], "bullets2"),

      heading("Option B: Candle Touch (Aggressive)", HeadingLevel.HEADING_2),
      ...bulletList([
        "LONG exit: Candle LOW touches or goes below the EMA (wick touch counts)",
        "SHORT exit: Candle HIGH touches or goes above the EMA (wick touch counts)",
        "Faster exit, preserves more profit",
      ], "bullets3"),

      heading("Option C: SuperTrend Flip", HeadingLevel.HEADING_2),
      ...bulletList([
        "LONG exit: SuperTrend flips to bearish (price drops below SuperTrend line)",
        "SHORT exit: SuperTrend flips to bullish (price rises above SuperTrend line)",
        "Trend-based exit, may hold trades longer in strong trends",
      ], "bullets2"),

      heading("Option D: ADX Below Threshold", HeadingLevel.HEADING_2),
      ...bulletList([
        "Exit when ADX drops below the minimum threshold (default 25)",
        "Signals that the trend is weakening and it is time to close the position",
        "Works for both Long and Short positions",
      ], "bullets3"),

      heading("Option E: EMA + SuperTrend", HeadingLevel.HEADING_2),
      ...bulletList([
        "Exit when EITHER the EMA close-cross OR the SuperTrend flip triggers",
        "Whichever signal comes first closes the trade",
        "Combines EMA precision with SuperTrend trend confirmation",
      ], "bullets2"),

      heading("Option F: EMA + ADX", HeadingLevel.HEADING_2),
      ...bulletList([
        "Exit when EITHER the EMA close-cross OR ADX drops below threshold",
        "Whichever signal comes first closes the trade",
        "Protects against holding trades in weakening trends",
      ], "bullets3"),

      tipBox("After Every Exit: GO FLAT", "When you exit a trade, you go FLAT. Do NOT immediately open the opposite position. Wait for the next candle that touches the EMA and closes on the other side to enter a new trade.", RED_BG),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 4: PARTIAL PROFIT BOOKING ======
      heading("4. Partial Profit Booking", HeadingLevel.HEADING_1),
      para("The strategy books partial profits at 3 fixed-point levels from entry. Each level is optional and can be enabled or disabled independently."),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [1500, 2200, 1800, 3860],
        rows: [
          new TableRow({ children: [
            headerCell("Level", 1500),
            headerCell("Points from Entry", 2200),
            headerCell("Qty to Close", 1800),
            headerCell("Remaining Position", 3860),
          ]}),
          new TableRow({ children: [
            cell("TP1", { width: 1500, bold: true, shading: GREEN_BG }),
            cell("+30 points", { width: 2200, alignment: AlignmentType.CENTER, shading: GREEN_BG }),
            cell("20%", { width: 1800, alignment: AlignmentType.CENTER, shading: GREEN_BG }),
            cell("80% still open", { width: 3860, shading: GREEN_BG }),
          ]}),
          new TableRow({ children: [
            cell("TP2", { width: 1500, bold: true, shading: LIGHT_BLUE }),
            cell("+60 points", { width: 2200, alignment: AlignmentType.CENTER, shading: LIGHT_BLUE }),
            cell("20%", { width: 1800, alignment: AlignmentType.CENTER, shading: LIGHT_BLUE }),
            cell("60% still open", { width: 3860, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("TP3", { width: 1500, bold: true, shading: PURPLE_BG }),
            cell("+90 points", { width: 2200, alignment: AlignmentType.CENTER, shading: PURPLE_BG }),
            cell("20%", { width: 1800, alignment: AlignmentType.CENTER, shading: PURPLE_BG }),
            cell("40% still open (carry forward)", { width: 3860, shading: PURPLE_BG }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),

      heading("Example: Long Trade at 2000", HeadingLevel.HEADING_2),
      para("Entry: BUY 1.0 lot at price 2000", { bold: true }),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [1200, 2000, 2000, 1800, 2360],
        rows: [
          new TableRow({ children: [
            headerCell("Event", 1200),
            headerCell("Price Level", 2000),
            headerCell("Action", 2000),
            headerCell("Lots Closed", 1800),
            headerCell("Remaining", 2360),
          ]}),
          new TableRow({ children: [
            cell("Entry", { width: 1200, bold: true }),
            cell("2000", { width: 2000, alignment: AlignmentType.CENTER }),
            cell("BUY 1.0 lot", { width: 2000 }),
            cell("-", { width: 1800, alignment: AlignmentType.CENTER }),
            cell("1.0 lot", { width: 2360, alignment: AlignmentType.CENTER }),
          ]}),
          new TableRow({ children: [
            cell("TP1", { width: 1200, bold: true, shading: GREEN_BG }),
            cell("2030", { width: 2000, alignment: AlignmentType.CENTER, shading: GREEN_BG }),
            cell("Close 20%", { width: 2000, shading: GREEN_BG }),
            cell("0.20 lot", { width: 1800, alignment: AlignmentType.CENTER, shading: GREEN_BG }),
            cell("0.80 lot", { width: 2360, alignment: AlignmentType.CENTER, shading: GREEN_BG }),
          ]}),
          new TableRow({ children: [
            cell("TP2", { width: 1200, bold: true, shading: LIGHT_BLUE }),
            cell("2060", { width: 2000, alignment: AlignmentType.CENTER, shading: LIGHT_BLUE }),
            cell("Close 20%", { width: 2000, shading: LIGHT_BLUE }),
            cell("0.20 lot", { width: 1800, alignment: AlignmentType.CENTER, shading: LIGHT_BLUE }),
            cell("0.60 lot", { width: 2360, alignment: AlignmentType.CENTER, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("TP3", { width: 1200, bold: true, shading: PURPLE_BG }),
            cell("2090", { width: 2000, alignment: AlignmentType.CENTER, shading: PURPLE_BG }),
            cell("Close 20%", { width: 2000, shading: PURPLE_BG }),
            cell("0.20 lot", { width: 1800, alignment: AlignmentType.CENTER, shading: PURPLE_BG }),
            cell("0.40 lot", { width: 2360, alignment: AlignmentType.CENTER, shading: PURPLE_BG }),
          ]}),
          new TableRow({ children: [
            cell("EMA Exit", { width: 1200, bold: true, shading: RED_BG }),
            cell("EMA touch", { width: 2000, alignment: AlignmentType.CENTER, shading: RED_BG }),
            cell("Close ALL + SELL", { width: 2000, shading: RED_BG }),
            cell("0.40 lot", { width: 1800, alignment: AlignmentType.CENTER, shading: RED_BG }),
            cell("0 (then open Short)", { width: 2360, alignment: AlignmentType.CENTER, shading: RED_BG }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),

      heading("Early EMA Exit (Before All TPs Hit)", HeadingLevel.HEADING_2),
      para("If price touches the EMA before hitting all TP levels, the strategy does NOT wait for remaining TPs. It immediately:"),
      ...numberList([
        "Closes ALL remaining lots (whatever is left)",
        "Opens the OPPOSITE direction trade with full fresh lot size",
        "Resets all TP levels for the new trade",
      ], "numbers3"),

      tipBox("Example: Early Exit", "You entered Long at 2000 and TP1 hit at 2030 (closed 0.20 lot). Price then reverses and touches the EMA at 1990 before TP2. Action: Close all remaining 0.80 lots at 1990 and go FLAT. Wait for the next candle that touches the EMA to determine the next trade direction.", YELLOW_BG),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 5: SUPERTREND & ADX FILTERS ======
      heading("5. SuperTrend & ADX Filters (Optional)", HeadingLevel.HEADING_1),
      para("These optional filters help avoid false signals by confirming trend direction or strength before entering a trade."),

      heading("SuperTrend Filter", HeadingLevel.HEADING_2),
      para("SuperTrend is an ATR-based trend indicator that draws a line above or below price:"),
      ...bulletList([
        "When price is above SuperTrend line = Bullish (green line below price)",
        "When price is below SuperTrend line = Bearish (red line above price)",
        "When enabled as entry filter: Long trades only allowed when SuperTrend is bullish, Short trades only when bearish",
        "Can also be used as an exit mode (SuperTrend Flip) or combined with EMA exit",
      ], "bullets2"),

      new Paragraph({ spacing: { after: 200 } }),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable SuperTrend", "No", "Toggle SuperTrend entry filter on/off", WHITE),
          settingsRow("ATR Period", "10", "ATR lookback period for band calculation", GRAY_BG),
          settingsRow("Multiplier", "3.0", "Band distance multiplier (higher = wider bands, fewer flips)", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 300 } }),

      heading("ADX Filter", HeadingLevel.HEADING_2),
      para("ADX (Average Directional Index) measures trend strength from 0 to 100:"),
      ...bulletList([
        "ADX above threshold (default 25) = Strong trend, trades allowed",
        "ADX below threshold = Weak/ranging market, trades blocked",
        "ADX does NOT indicate direction, only strength. It works with both Long and Short trades",
        "Can also be used as an exit mode (ADX Below Threshold) to close trades when trends weaken",
      ], "bullets3"),

      new Paragraph({ spacing: { after: 200 } }),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable ADX", "No", "Toggle ADX entry filter on/off", WHITE),
          settingsRow("ADX Period", "14", "Lookback period for ADX calculation", GRAY_BG),
          settingsRow("Min Threshold", "25", "Minimum ADX value to allow new trades", WHITE),
        ]
      }),

      tipBox("Combining Filters", "You can enable BOTH SuperTrend and ADX filters together. Both conditions must be met for a trade to be taken: SuperTrend must agree with direction AND ADX must be above threshold. This gives the highest quality signals but fewer trades.", GREEN_BG),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 6: TRAILING STOP LOSS ======
      heading("6. Trailing Stop Loss (Optional)", HeadingLevel.HEADING_1),
      para("An optional trailing stop loss can be enabled for additional protection. This is independent of the EMA exit."),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable TSL", "Off", "Toggle trailing stop on/off", WHITE),
          settingsRow("Trigger Profit %", "1.5%", "TSL activates only after price moves this % in your favor", GRAY_BG),
          settingsRow("Trail Offset %", "0.5%", "Once active, stop trails this % behind the highest/lowest price", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      para("How it works:"),
      ...bulletList([
        "TSL only activates after price has moved the Trigger % in profit",
        "Once active, the stop follows the price at the Offset % distance",
        "For Long: stop moves UP as price rises, never moves down",
        "For Short: stop moves DOWN as price falls, never moves up",
        "If TSL is hit, all remaining lots are closed",
      ], "bullets4"),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 7: ML PROBABILITY FILTER ======
      heading("7. ML Probability Filter (Optional)", HeadingLevel.HEADING_1),
      para("An optional Machine Learning model can be used to filter trades. The ML model analyzes 24 technical features and outputs the probability of a successful buy or sell. Only trades with probability above the threshold (default 0.6) are taken."),

      heading("How It Works", HeadingLevel.HEADING_2),
      ...numberList([
        "A LightGBM classifier is trained on historical 1H data from Yahoo Finance (Gold, EUR/USD, GBP/USD, SPY, QQQ, AAPL)",
        "The model learns patterns from 24 technical features: EMA distance, RSI, ADX, SuperTrend, MACD, Bollinger Bands, volume, price changes, etc.",
        "The trained model is exported to ONNX format and loaded by the MQL5 EA",
        "On each EMA touch signal, the EA computes all 24 features and runs them through the model",
        "If the model's buy probability >= 0.6, the buy is taken. If sell probability >= 0.6, the sell is taken. Otherwise, the signal is skipped",
      ], "numbers1"),

      heading("Training the Model", HeadingLevel.HEADING_2),
      para("Run from the project root:"),
      para("python models/training/train_model.py", { bold: true, font: "Consolas", size: 20 }),
      para("This downloads 2 years of 1H data, trains the model, and saves to models/saved_models/"),

      new Paragraph({ spacing: { after: 200 } }),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable ML Filter", "No", "Toggle ML probability filter on/off", WHITE),
          settingsRow("ONNX File", "ema200_squeeze_model.onnx", "Model file name (must be in MQL5/Files/)", GRAY_BG),
          settingsRow("Min Probability", "0.6", "Minimum ML probability (0.0 to 1.0) to allow entry", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),

      tipBox("MQL5 Only", "The ML/ONNX filter is available in the MQL5 Expert Advisor only. PineScript does not support loading ONNX models. For PineScript, use the Python inference script (models/inference/predict.py) to check probabilities manually.", ORANGE_BG),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 8: COMPLETE TRADE FLOW ======
      heading("8. Complete Trade Flow", HeadingLevel.HEADING_1),
      para("Follow this step-by-step checklist for every trade:"),

      // Step-by-step flow as a visual table
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [800, 8560],
        rows: [
          new TableRow({ children: [
            cell("Step 1", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: LIGHT_BLUE, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "CHECK EMA POSITION", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "Is the candle touching the 200 EMA? (Low <= EMA <= High)", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
          new TableRow({ children: [
            cell("Step 2", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: GREEN_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "ENTER TRADE", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "EMA touched + Close above = BUY | EMA touched + Close below = SELL", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
          new TableRow({ children: [
            cell("Step 3", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: ORANGE_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "SET TP LEVELS", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "Mark TP1 (+30 pts), TP2 (+60 pts), TP3 (+90 pts) from entry", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
          new TableRow({ children: [
            cell("Step 4", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: PURPLE_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "BOOK PARTIAL PROFITS", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "As each TP level is hit, close 20% of original position", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
          new TableRow({ children: [
            cell("Step 5", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: RED_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "EMA EXIT \u2192 GO FLAT", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "When price returns to EMA: Close ALL remaining lots and go FLAT", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
          new TableRow({ children: [
            cell("Step 6", { width: 800, bold: true, shading: BLUE }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 8560, type: WidthType.DXA },
              shading: { fill: YELLOW_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ children: [
                  new TextRun({ text: "WAIT FOR NEXT EMA TOUCH", bold: true, font: "Arial", size: 22 }),
                ]}),
                new Paragraph({ spacing: { before: 40 }, children: [
                  new TextRun({ text: "Stay flat. When price touches EMA again, go back to Step 1.", font: "Arial", size: 20 }),
                ]}),
              ]
            }),
          ]}),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 9: SETTINGS REFERENCE ======
      heading("9. Settings Reference", HeadingLevel.HEADING_1),

      heading("EMA Settings", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("EMA Length", "200", "Period for the Exponential Moving Average", WHITE),
          settingsRow("Exit Mode", "Candle Close", "Candle Close, Candle Touch, SuperTrend, ADX, EMA+SuperTrend, EMA+ADX", GRAY_BG),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      heading("Partial Profit Booking", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable TP1", "Yes", "Toggle first partial profit on/off", WHITE),
          settingsRow("TP1 Points", "30", "Points from entry for first partial close", GRAY_BG),
          settingsRow("TP1 Qty %", "20%", "Percentage of original lot to close at TP1", WHITE),
          settingsRow("Enable TP2", "Yes", "Toggle second partial profit on/off", GRAY_BG),
          settingsRow("TP2 Points", "60", "Points from entry for second partial close", WHITE),
          settingsRow("TP2 Qty %", "20%", "Percentage of original lot to close at TP2", GRAY_BG),
          settingsRow("Enable TP3", "Yes", "Toggle third partial profit on/off", WHITE),
          settingsRow("TP3 Points", "90", "Points from entry for third partial close", GRAY_BG),
          settingsRow("TP3 Qty %", "20%", "Percentage of original lot to close at TP3", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      heading("SuperTrend Filter", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable SuperTrend", "No", "Toggle SuperTrend entry filter on/off", WHITE),
          settingsRow("ATR Period", "10", "ATR lookback for SuperTrend band calculation", GRAY_BG),
          settingsRow("Multiplier", "3.0", "Band distance multiplier", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      heading("ADX Filter", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable ADX", "No", "Toggle ADX entry filter on/off", WHITE),
          settingsRow("ADX Period", "14", "ADX calculation lookback period", GRAY_BG),
          settingsRow("Min Threshold", "25", "Minimum ADX value to allow trades", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      heading("ML / ONNX Filter", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable ML Filter", "No", "Toggle ML probability filter on/off", WHITE),
          settingsRow("ONNX File", "ema200_squeeze_model.onnx", "ONNX model filename in MQL5/Files/", GRAY_BG),
          settingsRow("Min Probability", "0.6", "Minimum probability threshold to allow entry", WHITE),
        ]
      }),

      new Paragraph({ spacing: { after: 200 } }),
      heading("Trailing Stop Loss", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [COL_SETTING, COL_DEFAULT, COL_DESC],
        rows: [
          settingsHeaderRow(),
          settingsRow("Enable TSL", "No", "Toggle trailing stop loss on/off", WHITE),
          settingsRow("TSL Trigger %", "1.5%", "Profit % required before TSL activates", GRAY_BG),
          settingsRow("TSL Offset %", "0.5%", "Trail distance behind highest/lowest price", WHITE),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 10: DO'S AND DON'TS ======
      heading("10. Rules to Follow", HeadingLevel.HEADING_1),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({ children: [
            headerCell("DO", 4680),
            headerCell("DON'T", 4680),
          ]}),
          new TableRow({ children: [
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 4680, type: WidthType.DXA },
              shading: { fill: GREEN_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Only enter when price TOUCHES the EMA", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Go flat after EMA exit, wait for next touch", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Book partial profits at each TP level", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Let remaining 40% ride the trend", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Use consistent lot sizing", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Track your stats (win rate, P&L)", font: "Arial", size: 20 })] }),
              ]
            }),
            new TableCell({
              borders, margins: cellMargins,
              width: { size: 4680, type: WidthType.DXA },
              shading: { fill: RED_BG, type: ShadingType.CLEAR },
              children: [
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Enter when price is far from the EMA", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Enter immediately after exit without EMA touch", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Move TP levels or skip them", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Close the carry-forward early out of fear", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Change lot size mid-trade", font: "Arial", size: 20 })] }),
                new Paragraph({ numbering: { reference: "bullets2", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: "Override signals with personal bias", font: "Arial", size: 20 })] }),
              ]
            }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { after: 300 } }),

      // ====== SECTION 11: QUICK REFERENCE CARD ======
      heading("11. Quick Reference Card", HeadingLevel.HEADING_1),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [3000, 6360],
        rows: [
          new TableRow({ children: [
            headerCell("Item", 3000),
            headerCell("Rule", 6360),
          ]}),
          new TableRow({ children: [
            cell("Indicator", { width: 3000, bold: true, shading: GRAY_BG }),
            cell("200 EMA (single line)", { width: 6360, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            cell("Long Entry", { width: 3000, bold: true }),
            cell("Candle touches EMA + closes above", { width: 6360 }),
          ]}),
          new TableRow({ children: [
            cell("Short Entry", { width: 3000, bold: true, shading: GRAY_BG }),
            cell("Candle touches EMA + closes below", { width: 6360, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            cell("Entry Filters", { width: 3000, bold: true }),
            cell("SuperTrend + ADX + ML probability (all optional)", { width: 6360 }),
          ]}),
          new TableRow({ children: [
            cell("Exit", { width: 3000, bold: true, shading: GRAY_BG }),
            cell("EMA, SuperTrend, ADX, or combined (6 modes)", { width: 6360, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            cell("After Exit", { width: 3000, bold: true }),
            cell("Go FLAT, wait for next EMA touch to re-enter", { width: 6360 }),
          ]}),
          new TableRow({ children: [
            cell("TP1", { width: 3000, bold: true }),
            cell("+30 points = close 20%", { width: 6360 }),
          ]}),
          new TableRow({ children: [
            cell("TP2", { width: 3000, bold: true, shading: GRAY_BG }),
            cell("+60 points = close 20%", { width: 6360, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            cell("TP3", { width: 3000, bold: true }),
            cell("+90 points = close 20%", { width: 6360 }),
          ]}),
          new TableRow({ children: [
            cell("Carry Forward", { width: 3000, bold: true, shading: GRAY_BG }),
            cell("Remaining 40% rides until EMA exit", { width: 6360, shading: GRAY_BG }),
          ]}),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ====== SECTION 12: CHART COLOR REFERENCE ======
      heading("12. Chart Color Reference", HeadingLevel.HEADING_1),
      para("All lines and markers on the chart use distinct colors so you can identify them at a glance."),

      new Paragraph({ spacing: { after: 200 } }),
      heading("Lines & Levels", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [800, 2200, 1800, 4560],
        rows: [
          new TableRow({ children: [
            headerCell("", 800),
            headerCell("Element", 2200),
            headerCell("Color", 1800),
            headerCell("Style", 4560),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "FFD700", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("EMA 200", { width: 2200, bold: true }),
            cell("Yellow", { width: 1800 }),
            cell("Solid line, width 2 \u2014 the main indicator curve on chart", { width: 4560 }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "32CD32", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("TP1 Level", { width: 2200, bold: true, shading: GRAY_BG }),
            cell("Lime", { width: 1800, shading: GRAY_BG }),
            cell("Dashed line \u2014 +30 points from entry (first partial profit)", { width: 4560, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "1E90FF", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("TP2 Level", { width: 2200, bold: true }),
            cell("Dodger Blue", { width: 1800 }),
            cell("Dashed line \u2014 +60 points from entry (second partial profit)", { width: 4560 }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "00FFFF", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("TP3 Level", { width: 2200, bold: true, shading: GRAY_BG }),
            cell("Aqua", { width: 1800, shading: GRAY_BG }),
            cell("Dashed line \u2014 +90 points from entry (third partial profit)", { width: 4560, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "32CD32", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("SuperTrend (Bull)", { width: 2200, bold: true }),
            cell("Green", { width: 1800 }),
            cell("Dot markers below price \u2014 bullish SuperTrend (only when ST active)", { width: 4560 }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "DD0000", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("SuperTrend (Bear)", { width: 2200, bold: true, shading: GRAY_BG }),
            cell("Red", { width: 1800, shading: GRAY_BG }),
            cell("Dot markers above price \u2014 bearish SuperTrend (only when ST active)", { width: 4560, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "FF00FF", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("Trailing SL", { width: 2200, bold: true }),
            cell("Magenta", { width: 1800 }),
            cell("Dash-dot line \u2014 trailing stop level (only when TSL is active)", { width: 4560 }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { after: 300 } }),
      heading("Trade Signals (Arrows)", HeadingLevel.HEADING_2),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [800, 2200, 1800, 4560],
        rows: [
          new TableRow({ children: [
            headerCell("", 800),
            headerCell("Signal", 2200),
            headerCell("Color", 1800),
            headerCell("Description", 4560),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "00AA00", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("BUY", { width: 2200, bold: true }),
            cell("Green", { width: 1800 }),
            cell("Up arrow below bar \u2014 Long entry signal", { width: 4560 }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "DD0000", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("SELL", { width: 2200, bold: true, shading: GRAY_BG }),
            cell("Red", { width: 1800, shading: GRAY_BG }),
            cell("Down arrow above bar \u2014 Short entry signal", { width: 4560, shading: GRAY_BG }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "DD0000", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("EXIT Long", { width: 2200, bold: true }),
            cell("Red", { width: 1800 }),
            cell("Down arrow above bar \u2014 Long position closed at EMA", { width: 4560 }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: cellMargins, width: { size: 800, type: WidthType.DXA },
              shading: { fill: "00AA00", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [] })] }),
            cell("EXIT Short", { width: 2200, bold: true, shading: GRAY_BG }),
            cell("Green", { width: 1800, shading: GRAY_BG }),
            cell("Up arrow below bar \u2014 Short position closed at EMA", { width: 4560, shading: GRAY_BG }),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { after: 300 } }),

      tipBox("Reading the Chart", "The yellow EMA line is your primary guide. Green/red dot markers show the SuperTrend direction when active. The colored dashed lines show your TP targets. As each TP is hit, its line disappears. The remaining position rides until the selected exit condition triggers.", LIGHT_BLUE),

    ]
  }]
});

// Generate
Packer.toBuffer(doc).then(buffer => {
  const outPath = "EMA200Squeeze_Guide.docx";
  try {
    fs.writeFileSync(outPath, buffer);
    console.log("Created " + outPath);
  } catch(e) {
    // File locked - write to temp, then user can rename
    const tmp = "EMA200Squeeze_Guide_new.docx";
    fs.writeFileSync(tmp, buffer);
    console.log("Original locked. Created " + tmp + " - close the original and rename.");
  }
});
