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
const WHITE = "FFFFFF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

// Helper: create a table cell
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

// Helper: heading paragraph
function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: 300, after: 200 },
    children: [new TextRun({ text, bold: true, font: "Arial" })]
  });
}

// Helper: body paragraph
function para(text, opts = {}) {
  const { bold, italic, spacing, alignment } = opts;
  return new Paragraph({
    spacing: { after: spacing || 120 },
    alignment: alignment || AlignmentType.LEFT,
    children: [new TextRun({ text, bold, italics: italic, font: "Arial", size: 22 })]
  });
}

// Helper: multi-run paragraph
function multiPara(runs, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.spacing || 120 },
    alignment: opts.alignment || AlignmentType.LEFT,
    children: runs.map(r => new TextRun({ text: r.text, bold: r.bold, italics: r.italic, font: "Arial", size: r.size || 22, color: r.color }))
  });
}

// Numbering config
const numbering = {
  config: [
    {
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
    {
      reference: "bullets2",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1080, hanging: 360 } } }
      }]
    },
    {
      reference: "steps",
      levels: [{
        level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
    {
      reference: "steps2",
      levels: [{
        level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
    {
      reference: "steps3",
      levels: [{
        level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
    {
      reference: "steps4",
      levels: [{
        level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
    {
      reference: "steps5",
      levels: [{
        level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } }
      }]
    },
  ]
};

// Helper: bullet item
function bullet(text, ref) {
  return new Paragraph({
    numbering: { reference: ref || "bullets", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}

// Helper: numbered step
function step(text, ref) {
  return new Paragraph({
    numbering: { reference: ref || "steps", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}

// Helper: code block style paragraph
function codePara(text) {
  return new Paragraph({
    spacing: { after: 60 },
    indent: { left: 360 },
    shading: { fill: GRAY_BG, type: ShadingType.CLEAR },
    children: [new TextRun({ text, font: "Consolas", size: 18 })]
  });
}

// =====================================================================
// BUILD DOCUMENT
// =====================================================================

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 280, after: 180 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering,
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "IFVG EA Strategy Guide", font: "Arial", size: 18, italics: true, color: "888888" })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", font: "Arial", size: 18, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "888888" }),
          ]
        })]
      })
    },
    children: [
      // ===== TITLE PAGE =====
      new Paragraph({ spacing: { before: 3000 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: "IFVG EA Strategy Guide", bold: true, font: "Arial", size: 56, color: BLUE })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: "Inverted Fair Value Gap Expert Advisor", font: "Arial", size: 28, color: "555555" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: "MQL5 for MetaTrader 5", font: "Arial", size: 24, color: "777777" })]
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
        children: [new TextRun({ text: "Version 1.01", font: "Arial", size: 22, color: "888888" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Copyright 2026", font: "Arial", size: 22, color: "888888" })]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== TABLE OF CONTENTS PLACEHOLDER =====
      heading("Table of Contents", HeadingLevel.HEADING_1),
      para("1. Strategy Overview"),
      para("2. Core Concept: What is a Fair Value Gap (FVG)?"),
      para("3. The 4-Stage FVG Lifecycle"),
      para("4. Buy Signal Logic (Bullish IFVG)"),
      para("5. Sell Signal Logic (Bearish IFVG)"),
      para("6. Chart Visualization & Color Coding"),
      para("7. Trade Execution Details"),
      para("8. Dynamic Lot Sizing"),
      para("9. Trailing Stop Logic"),
      para("10. Input Parameters Reference"),
      para("11. Step-by-Step Walkthrough Examples"),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 1. STRATEGY OVERVIEW =====
      heading("1. Strategy Overview", HeadingLevel.HEADING_1),
      para("The IFVG EA (Inverted Fair Value Gap Expert Advisor) is an automated trading strategy for MetaTrader 5 that identifies Fair Value Gaps in price action, tracks their lifecycle through mitigation and retracement, and trades the inversion signal when the FVG flips from a support/resistance zone into a breakout confirmation zone."),
      para(""),
      para("Key characteristics:", { bold: true }),
      bullet("Identifies 3-candle Fair Value Gaps (price imbalances) automatically"),
      bullet("Tracks each FVG through 4 states: Normal, Mitigated, Retraced, and Inverted"),
      bullet("Only trades on the Inversion signal (the highest-probability setup)"),
      bullet("Plots colored rectangles on the chart showing each FVG and its current state"),
      bullet("Supports dynamic lot sizing based on account risk percentage"),
      bullet("Includes trailing stop for profit protection"),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 2. WHAT IS AN FVG =====
      heading("2. Core Concept: What is a Fair Value Gap (FVG)?", HeadingLevel.HEADING_1),
      para("A Fair Value Gap (FVG) is a price imbalance created when a strong move leaves a gap between three consecutive candles. The gap represents an area where price moved so quickly that no trading occurred on one side, leaving unfinished business for the market to potentially revisit."),
      para(""),
      heading("Bullish FVG (Gap Up)", HeadingLevel.HEADING_2),
      para("A Bullish FVG forms when price surges upward, leaving a gap between three candles:"),
      para(""),

      // Bullish FVG detection table
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 3510, 3510],
        rows: [
          new TableRow({ children: [
            cell("Candle", { bold: true, width: 2340, shading: LIGHT_BLUE }),
            cell("Price Used", { bold: true, width: 3510, shading: LIGHT_BLUE }),
            cell("Role", { bold: true, width: 3510, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i+2]", { width: 2340 }),
            cell("High of bar [i+2]", { width: 3510 }),
            cell("Bottom edge of the gap", { width: 3510 }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i+1]", { width: 2340, shading: GREEN_BG }),
            cell("(The big move candle)", { width: 3510, shading: GREEN_BG }),
            cell("The candle that created the gap", { width: 3510, shading: GREEN_BG }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i]", { width: 2340 }),
            cell("Low of bar [i]", { width: 3510 }),
            cell("Top edge of the gap", { width: 3510 }),
          ]}),
        ]
      }),
      para(""),
      multiPara([
        { text: "Detection condition: ", bold: true },
        { text: "Low[i] > High[i+2]", italic: true },
        { text: " AND the gap size in points > ", },
        { text: "minPts", italic: true },
        { text: " (default 100)" },
      ]),
      para("The FVG zone is the rectangle between High[i+2] (bottom) and Low[i] (top)."),
      para(""),

      heading("Bearish FVG (Gap Down)", HeadingLevel.HEADING_2),
      para("A Bearish FVG forms when price drops sharply, leaving a gap between three candles:"),
      para(""),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 3510, 3510],
        rows: [
          new TableRow({ children: [
            cell("Candle", { bold: true, width: 2340, shading: LIGHT_BLUE }),
            cell("Price Used", { bold: true, width: 3510, shading: LIGHT_BLUE }),
            cell("Role", { bold: true, width: 3510, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i+2]", { width: 2340 }),
            cell("Low of bar [i+2]", { width: 3510 }),
            cell("Top edge of the gap", { width: 3510 }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i+1]", { width: 2340, shading: RED_BG }),
            cell("(The big move candle)", { width: 3510, shading: RED_BG }),
            cell("The candle that created the gap", { width: 3510, shading: RED_BG }),
          ]}),
          new TableRow({ children: [
            cell("Bar [i]", { width: 2340 }),
            cell("High of bar [i]", { width: 3510 }),
            cell("Bottom edge of the gap", { width: 3510 }),
          ]}),
        ]
      }),
      para(""),
      multiPara([
        { text: "Detection condition: ", bold: true },
        { text: "Low[i+2] > High[i]", italic: true },
        { text: " AND the gap size in points > ", },
        { text: "minPts", italic: true },
        { text: " (default 100)" },
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 3. FVG LIFECYCLE =====
      heading("3. The 4-Stage FVG Lifecycle", HeadingLevel.HEADING_1),
      para("Every FVG goes through a specific lifecycle. The EA tracks each stage and only generates trade signals at the final Inversion stage. This ensures high-probability entries."),
      para(""),

      // Lifecycle stages table
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1400, 1200, 2380, 2380, 2000],
        rows: [
          new TableRow({ children: [
            cell("Stage", { bold: true, width: 1400, shading: LIGHT_BLUE }),
            cell("State", { bold: true, width: 1200, shading: LIGHT_BLUE }),
            cell("What Happens", { bold: true, width: 2380, shading: LIGHT_BLUE }),
            cell("Condition", { bold: true, width: 2380, shading: LIGHT_BLUE }),
            cell("Chart Color", { bold: true, width: 2000, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("1. Detection", { width: 1400, bold: true }),
            cell("Normal", { width: 1200 }),
            cell("3-candle gap found, zone plotted", { width: 2380 }),
            cell("Gap > minPts between bar[i] and bar[i+2]", { width: 2380 }),
            cell(["Bullish: Green", "Bearish: Red"], { width: 2000 }),
          ]}),
          new TableRow({ children: [
            cell("2. Mitigation", { width: 1400, bold: true }),
            cell("Mitigated", { width: 1200 }),
            cell("Price breaks through the far side of the FVG zone", { width: 2380 }),
            cell(["Bullish FVG: bar Low < FVG Low", "Bearish FVG: bar High > FVG High"], { width: 2380 }),
            cell(["Bullish: Purple", "Bearish: Orange"], { width: 2000 }),
          ]}),
          new TableRow({ children: [
            cell("3. Retracement", { width: 1400, bold: true }),
            cell("(still Mitigated)", { width: 1200 }),
            cell("Price returns back inside the FVG zone", { width: 2380 }),
            cell("bar High > FVG Low AND bar Low < FVG High", { width: 2380 }),
            cell("No color change", { width: 2000 }),
          ]}),
          new TableRow({ children: [
            cell("4. Inversion", { width: 1400, bold: true }),
            cell("Inverted", { width: 1200 }),
            cell(["Price breaks out the other side.", "THIS IS THE TRADE SIGNAL"], { width: 2380 }),
            cell(["Previous bar Close inside FVG zone AND Current bar Close exits opposite side"], { width: 2380 }),
            cell(["Bullish IFVG: Green", "Bearish IFVG: Red"], { width: 2000 }),
          ]}),
        ]
      }),

      para(""),
      para("Important: The signal requires TWO consecutive bars:", { bold: true }),
      bullet("Bar [2] (two bars ago): Close must be INSIDE the FVG zone"),
      bullet("Bar [1] (previous bar): Close must be OUTSIDE the FVG zone on the opposite side from mitigation"),
      para("This two-bar confirmation prevents false signals from single-bar spikes."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 4. BUY SIGNAL LOGIC =====
      heading("4. Buy Signal Logic (Bullish IFVG)", HeadingLevel.HEADING_1),
      para("A Buy trade is generated from an originally Bearish FVG that gets inverted. The logic is counter-intuitive: a Bearish FVG (gap down) becomes a Bullish IFVG (buy signal) when price proves the bears wrong."),
      para(""),
      heading("Step-by-Step Buy Signal Formation", HeadingLevel.HEADING_2),
      para(""),

      step("A Bearish FVG forms (gap down detected, Red rectangle plotted)", "steps"),
      step("Price rallies and breaks ABOVE the FVG High (Mitigation: rectangle turns Orange)", "steps"),
      step("Price pulls back and re-enters the FVG zone (Retracement: no color change)", "steps"),
      step("Bar [2] closes INSIDE the FVG zone (confirming price is testing the zone)", "steps"),
      step("Bar [1] closes ABOVE the FVG High (Inversion: rectangle turns Green = Bullish IFVG)", "steps"),
      para(""),
      para("TRADE EXECUTION:", { bold: true }),
      para(""),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          new TableRow({ children: [
            cell("Parameter", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("Value", { bold: true, width: 6240, shading: GREEN_BG }),
          ]}),
          new TableRow({ children: [
            cell("Direction", { width: 3120 }),
            cell("BUY", { width: 6240, bold: true }),
          ]}),
          new TableRow({ children: [
            cell("Entry Price", { width: 3120 }),
            cell("Current Ask price at signal bar open", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Stop Loss", { width: 3120 }),
            cell("FVG Low - sl_pts (default 500 points below FVG bottom)", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Take Profit", { width: 3120 }),
            cell("Ask + tp_pts (default 10000 points above entry)", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Comment", { width: 3120 }),
            cell("\"IFVG Buy\"", { width: 6240 }),
          ]}),
        ]
      }),

      para(""),
      para("Why it works:", { bold: true, italic: true }),
      para("The Bearish FVG was where sellers dominated. When price breaks above it (mitigation), the sellers are proven wrong. When price pulls back into the zone (retracement), it tests whether buyers can hold. When price closes back above (inversion), it confirms the zone has flipped from resistance to support. This is a high-probability long entry."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 5. SELL SIGNAL LOGIC =====
      heading("5. Sell Signal Logic (Bearish IFVG)", HeadingLevel.HEADING_1),
      para("A Sell trade is generated from an originally Bullish FVG that gets inverted. A Bullish FVG (gap up) becomes a Bearish IFVG (sell signal) when price proves the bulls wrong."),
      para(""),
      heading("Step-by-Step Sell Signal Formation", HeadingLevel.HEADING_2),
      para(""),

      step("A Bullish FVG forms (gap up detected, Green rectangle plotted)", "steps2"),
      step("Price drops and breaks BELOW the FVG Low (Mitigation: rectangle turns Purple)", "steps2"),
      step("Price bounces and re-enters the FVG zone (Retracement: no color change)", "steps2"),
      step("Bar [2] closes INSIDE the FVG zone (confirming price is testing the zone)", "steps2"),
      step("Bar [1] closes BELOW the FVG Low (Inversion: rectangle turns Red = Bearish IFVG)", "steps2"),
      para(""),
      para("TRADE EXECUTION:", { bold: true }),
      para(""),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          new TableRow({ children: [
            cell("Parameter", { bold: true, width: 3120, shading: RED_BG }),
            cell("Value", { bold: true, width: 6240, shading: RED_BG }),
          ]}),
          new TableRow({ children: [
            cell("Direction", { width: 3120 }),
            cell("SELL", { width: 6240, bold: true }),
          ]}),
          new TableRow({ children: [
            cell("Entry Price", { width: 3120 }),
            cell("Current Bid price at signal bar open", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Stop Loss", { width: 3120 }),
            cell("FVG High + sl_pts (default 500 points above FVG top)", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Take Profit", { width: 3120 }),
            cell("Bid - tp_pts (default 10000 points below entry)", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Comment", { width: 3120 }),
            cell("\"IFVG Sell\"", { width: 6240 }),
          ]}),
        ]
      }),

      para(""),
      para("Why it works:", { bold: true, italic: true }),
      para("The Bullish FVG was where buyers dominated. When price breaks below it (mitigation), the buyers are proven wrong. When price retraces back into the zone, it tests whether sellers can maintain control. When price closes back below (inversion), it confirms the zone has flipped from support to resistance. This is a high-probability short entry."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 6. CHART VISUALIZATION =====
      heading("6. Chart Visualization & Color Coding", HeadingLevel.HEADING_1),
      para("The EA plots several visual elements on the chart to help you understand the current state of each FVG at a glance."),
      para(""),

      heading("Rectangle Color Guide", HeadingLevel.HEADING_2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 1560, 2730, 2730],
        rows: [
          new TableRow({ children: [
            cell("State", { bold: true, width: 2340, shading: LIGHT_BLUE }),
            cell("Color", { bold: true, width: 1560, shading: LIGHT_BLUE }),
            cell("Meaning", { bold: true, width: 2730, shading: LIGHT_BLUE }),
            cell("Action", { bold: true, width: 2730, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("Bullish FVG (Normal)", { width: 2340 }),
            cell("Green", { width: 1560, shading: "C6EFCE" }),
            cell("Fresh gap up detected", { width: 2730 }),
            cell("Wait for mitigation", { width: 2730 }),
          ]}),
          new TableRow({ children: [
            cell("Bearish FVG (Normal)", { width: 2340 }),
            cell("Red", { width: 1560, shading: "FFC7CE" }),
            cell("Fresh gap down detected", { width: 2730 }),
            cell("Wait for mitigation", { width: 2730 }),
          ]}),
          new TableRow({ children: [
            cell("Mitigated Bullish", { width: 2340 }),
            cell("Purple", { width: 1560, shading: "E1BEE7" }),
            cell("Bullish FVG broken below", { width: 2730 }),
            cell("Watch for retracement", { width: 2730 }),
          ]}),
          new TableRow({ children: [
            cell("Mitigated Bearish", { width: 2340 }),
            cell("Orange", { width: 1560, shading: "FFE0B2" }),
            cell("Bearish FVG broken above", { width: 2730 }),
            cell("Watch for retracement", { width: 2730 }),
          ]}),
          new TableRow({ children: [
            cell("Bullish IFVG (Inverted)", { width: 2340 }),
            cell("Green", { width: 1560, shading: "C6EFCE" }),
            cell("Bearish FVG inverted = BUY", { width: 2730 }),
            cell("Buy signal fired", { width: 2730 }),
          ]}),
          new TableRow({ children: [
            cell("Bearish IFVG (Inverted)", { width: 2340 }),
            cell("Red", { width: 1560, shading: "FFC7CE" }),
            cell("Bullish FVG inverted = SELL", { width: 2730 }),
            cell("Sell signal fired", { width: 2730 }),
          ]}),
        ]
      }),

      para(""),
      heading("Other Chart Objects", HeadingLevel.HEADING_2),
      bullet("Rectangle: Filled rectangle spanning the FVG zone, extended 30 bars (configurable) from the middle candle"),
      bullet("Label: Text label centered on the rectangle showing the FVG type and trade count (e.g., \"Bullish IFVG (Traded 1x)\")"),
      bullet("Mitigation Icon: Blue arrow (code 251) placed at the bar where mitigation occurred, at the far edge of the FVG"),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 7. TRADE EXECUTION =====
      heading("7. Trade Execution Details", HeadingLevel.HEADING_1),
      para(""),

      heading("When Trades Are Checked", HeadingLevel.HEADING_2),
      para("The EA only checks for new signals on new bar open. It does NOT trade intra-bar. The sequence on each new bar:"),
      step("DetectFVGs() - scan last 3 bars for new FVG formations", "steps3"),
      step("UpdateFVGs() - check all tracked FVGs for mitigation, retracement, and inversion", "steps3"),
      step("TradeOnFVGs() - execute trades for any FVGs with new inversion signals", "steps3"),
      para(""),

      heading("Trade Mode", HeadingLevel.HEADING_2),
      para("The tradeMode parameter controls how many trades each FVG can generate:"),
      para(""),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 7020],
        rows: [
          new TableRow({ children: [
            cell("Mode", { bold: true, width: 2340, shading: LIGHT_BLUE }),
            cell("Behavior", { bold: true, width: 7020, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("TradeOnce", { width: 2340 }),
            cell("Each FVG fires exactly 1 trade, then is done forever", { width: 7020 }),
          ]}),
          new TableRow({ children: [
            cell("LimitedTrades", { width: 2340 }),
            cell("Each FVG fires up to maxTradesPerFVG trades (default 1). After each trade, the ret flag resets so the FVG can re-qualify if price retraces back in and breaks out again.", { width: 7020 }),
          ]}),
          new TableRow({ children: [
            cell("UnlimitedTrades", { width: 2340 }),
            cell("No limit on trades per FVG. The ret flag resets after each trade allowing repeated re-entry.", { width: 7020 }),
          ]}),
        ]
      }),
      para(""),
      para("Default: LimitedTrades with maxTradesPerFVG = 1 (effectively same as TradeOnce, but allows increasing via input).", { italic: true }),

      heading("Overlap Filtering", HeadingLevel.HEADING_2),
      para("When ignoreOverlaps = true (default), any new FVG that overlaps with an existing FVG zone is discarded. This prevents cluttering the chart with redundant zones in the same price area."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 8. DYNAMIC LOT SIZING =====
      heading("8. Dynamic Lot Sizing", HeadingLevel.HEADING_1),
      para("The EA supports two lot sizing modes:"),
      para(""),

      heading("Fixed Lot", HeadingLevel.HEADING_2),
      para("Uses the fixedLot input directly (default 1.0 lot). Simple and predictable."),
      para(""),

      heading("Dynamic Lot (Risk %)", HeadingLevel.HEADING_2),
      para("Calculates lot size so that if the stop loss is hit, you lose exactly riskPercent% of your account balance. Default is 1.0% risk."),
      para(""),
      para("Formula:", { bold: true }),
      codePara("riskMoney = Balance * riskPercent / 100"),
      codePara("slMoney   = (slDistance * Point / TickSize) * TickValue"),
      codePara("lot       = riskMoney / slMoney"),
      para(""),
      para("Important: The SL distance is calculated as the ACTUAL distance from entry to SL, not just sl_pts. For a Buy trade:", { bold: true }),
      codePara("slDistance = (Ask - fvgLow) / Point + sl_pts"),
      para("This accounts for the distance from entry to the FVG bottom edge PLUS the sl_pts buffer below it. This ensures your 1% risk is accurate regardless of where price is relative to the FVG zone."),
      para(""),
      para("The calculated lot is clamped to the broker's min/max volume and rounded down to the nearest volume step."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 9. TRAILING STOP =====
      heading("9. Trailing Stop Logic", HeadingLevel.HEADING_1),
      para("When TrailingType = By Points (default), the trailing stop runs on EVERY tick (not just new bars) for maximum protection."),
      para(""),

      heading("For Buy Positions", HeadingLevel.HEADING_2),
      step("Calculate new SL = Current Bid - Trailing_Stop_Pips * Point", "steps4"),
      step("Only move SL if: new SL > current SL (never moves SL down)", "steps4"),
      step("Only start trailing if: Bid - OpenPrice > Min_Profit_To_Trail_Pips * Point", "steps4"),
      para(""),

      heading("For Sell Positions", HeadingLevel.HEADING_2),
      step("Calculate new SL = Current Ask + Trailing_Stop_Pips * Point", "steps5"),
      step("Only move SL if: new SL < current SL (never moves SL up)", "steps5"),
      step("Only start trailing if: OpenPrice - Ask > Min_Profit_To_Trail_Pips * Point", "steps5"),
      para(""),

      para("Default settings: Trailing begins once profit reaches 10 points (Min_Profit_To_Trail_Pips), then keeps SL 30 points (Trailing_Stop_Pips) behind the current price. The trailing stop only moves in the profitable direction and never widens."),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 10. INPUT PARAMETERS =====
      heading("10. Input Parameters Reference", HeadingLevel.HEADING_1),
      para(""),

      heading("Lot Settings", HeadingLevel.HEADING_2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 1400, 5160],
        rows: [
          new TableRow({ children: [
            cell("Parameter", { bold: true, width: 2800, shading: LIGHT_BLUE }),
            cell("Default", { bold: true, width: 1400, shading: LIGHT_BLUE }),
            cell("Description", { bold: true, width: 5160, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("lotMode", { width: 2800 }),
            cell("DynamicLot", { width: 1400 }),
            cell("Fixed Lot or Dynamic (Risk %)", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("fixedLot", { width: 2800 }),
            cell("1.0", { width: 1400 }),
            cell("Lot size when using Fixed mode", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("riskPercent", { width: 2800 }),
            cell("1.0", { width: 1400 }),
            cell("Percentage of account balance risked per trade in Dynamic mode", { width: 5160 }),
          ]}),
        ]
      }),

      para(""),
      heading("Strategy Settings", HeadingLevel.HEADING_2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 1400, 5160],
        rows: [
          new TableRow({ children: [
            cell("Parameter", { bold: true, width: 2800, shading: LIGHT_BLUE }),
            cell("Default", { bold: true, width: 1400, shading: LIGHT_BLUE }),
            cell("Description", { bold: true, width: 5160, shading: LIGHT_BLUE }),
          ]}),
          new TableRow({ children: [
            cell("sl_pts", { width: 2800 }),
            cell("500", { width: 1400 }),
            cell("Stop loss buffer in points beyond FVG edge", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("tp_pts", { width: 2800 }),
            cell("10000", { width: 1400 }),
            cell("Take profit distance in points from entry price", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("minPts", { width: 2800 }),
            cell("100", { width: 1400 }),
            cell("Minimum FVG gap size in points to qualify", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("FVG_Rec_Ext_Bars", { width: 2800 }),
            cell("30", { width: 1400 }),
            cell("Number of bars to extend the FVG rectangle forward", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("magic_number", { width: 2800 }),
            cell("123456789", { width: 1400 }),
            cell("Unique ID to identify this EA's trades", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("ignoreOverlaps", { width: 2800 }),
            cell("true", { width: 1400 }),
            cell("Skip new FVGs that overlap existing ones", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("tradeMode", { width: 2800 }),
            cell("LimitedTrades", { width: 1400 }),
            cell("TradeOnce / LimitedTrades / UnlimitedTrades", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("maxTradesPerFVG", { width: 2800 }),
            cell("1", { width: 1400 }),
            cell("Max trades per FVG in LimitedTrades mode", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("maxFVGs", { width: 2800 }),
            cell("50", { width: 1400 }),
            cell("Maximum FVG zones tracked in memory", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("TrailingType", { width: 2800 }),
            cell("By Points", { width: 1400 }),
            cell("None or By Points trailing stop", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("Trailing_Stop_Pips", { width: 2800 }),
            cell("30.0", { width: 1400 }),
            cell("Trailing stop distance in points behind price", { width: 5160 }),
          ]}),
          new TableRow({ children: [
            cell("Min_Profit_To_Trail_Pips", { width: 2800 }),
            cell("10.0", { width: 1400 }),
            cell("Minimum profit in points before trailing starts", { width: 5160 }),
          ]}),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 11. WALKTHROUGH EXAMPLES =====
      heading("11. Step-by-Step Walkthrough Examples", HeadingLevel.HEADING_1),
      para(""),

      heading("Example 1: Bullish IFVG Buy Trade (from a Bearish FVG)", HeadingLevel.HEADING_2),
      para("Scenario: XAUUSD (Gold) on M15 timeframe"),
      para(""),

      para("Stage 1 - Detection:", { bold: true }),
      para("Three consecutive candles form a bearish gap. Bar[i+2] Low = 2350.00, Bar[i] High = 2347.50. The gap of 250 points (2350.00 - 2347.50 = 2.50 = 250 pts) exceeds minPts (100). A Red rectangle is drawn from 2347.50 to 2350.00."),
      para(""),

      para("Stage 2 - Mitigation:", { bold: true }),
      para("Several bars later, a candle's High reaches 2351.00, which is above the FVG High (2350.00). This breaks through the far side. The rectangle turns Orange. A blue arrow icon is placed at this bar."),
      para(""),

      para("Stage 3 - Retracement:", { bold: true }),
      para("Price pulls back. A candle's range (Low: 2348.00, High: 2349.50) overlaps with the FVG zone (2347.50 - 2350.00). The bar is \"inside\" the zone. Retracement is confirmed."),
      para(""),

      para("Stage 4 - Inversion (TRADE SIGNAL):", { bold: true }),
      para("Bar[2] closes at 2349.00 (inside the zone: between 2347.50 and 2350.00). Bar[1] closes at 2350.80 (above FVG High 2350.00). Both conditions met. The rectangle turns Green (Bullish IFVG)."),
      para(""),

      para("Trade Execution:", { bold: true }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          new TableRow({ children: [
            cell("Entry", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("Buy at Ask = 2351.00", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Stop Loss", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("FVG Low (2347.50) - 500 pts (5.00) = 2342.50", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Take Profit", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("Ask (2351.00) + 10000 pts (100.00) = 2451.00", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Risk (SL distance)", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("2351.00 - 2342.50 = 850 points", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Dynamic Lot (1% of $10,000)", { bold: true, width: 3120, shading: GREEN_BG }),
            cell("$100 risk / (850 pts * tick_value) = calculated lot", { width: 6240 }),
          ]}),
        ]
      }),

      para(""),
      para("After entry: Trailing stop activates once profit reaches 10 points above entry. It then keeps the SL 30 points behind the current Bid price, ratcheting up as price climbs."),

      para(""),
      heading("Example 2: Bearish IFVG Sell Trade (from a Bullish FVG)", HeadingLevel.HEADING_2),
      para("Scenario: EURUSD on H1 timeframe"),
      para(""),

      para("Stage 1 - Detection:", { bold: true }),
      para("Three consecutive candles form a bullish gap. Bar[i+2] High = 1.08500, Bar[i] Low = 1.08650. The gap of 150 points exceeds minPts (100). A Green rectangle is drawn from 1.08500 to 1.08650."),
      para(""),

      para("Stage 2 - Mitigation:", { bold: true }),
      para("Price drops and a candle's Low reaches 1.08420, below the FVG Low (1.08500). The rectangle turns Purple. A blue arrow icon is placed at this bar."),
      para(""),

      para("Stage 3 - Retracement:", { bold: true }),
      para("Price bounces. A candle's range enters the FVG zone (1.08500 - 1.08650). Retracement confirmed."),
      para(""),

      para("Stage 4 - Inversion (TRADE SIGNAL):", { bold: true }),
      para("Bar[2] closes at 1.08580 (inside the zone). Bar[1] closes at 1.08470 (below FVG Low 1.08500). Both conditions met. The rectangle turns Red (Bearish IFVG)."),
      para(""),

      para("Trade Execution:", { bold: true }),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          new TableRow({ children: [
            cell("Entry", { bold: true, width: 3120, shading: RED_BG }),
            cell("Sell at Bid = 1.08460", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Stop Loss", { bold: true, width: 3120, shading: RED_BG }),
            cell("FVG High (1.08650) + 500 pts (0.00500) = 1.09150", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Take Profit", { bold: true, width: 3120, shading: RED_BG }),
            cell("Bid (1.08460) - 10000 pts (0.10000) = 0.98460", { width: 6240 }),
          ]}),
          new TableRow({ children: [
            cell("Risk (SL distance)", { bold: true, width: 3120, shading: RED_BG }),
            cell("1.09150 - 1.08460 = 690 points", { width: 6240 }),
          ]}),
        ]
      }),

      para(""),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== QUICK REFERENCE =====
      heading("Quick Reference: Signal Cheat Sheet", HeadingLevel.HEADING_1),
      para(""),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({ children: [
            cell("BUY Signal (Bullish IFVG)", { bold: true, width: 4680, shading: GREEN_BG, alignment: AlignmentType.CENTER }),
            cell("SELL Signal (Bearish IFVG)", { bold: true, width: 4680, shading: RED_BG, alignment: AlignmentType.CENTER }),
          ]}),
          new TableRow({ children: [
            cell("Starts as: Bearish FVG (Red)", { width: 4680 }),
            cell("Starts as: Bullish FVG (Green)", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("Mitigation: Price breaks ABOVE FVG High", { width: 4680 }),
            cell("Mitigation: Price breaks BELOW FVG Low", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("Retracement: Price returns inside FVG zone", { width: 4680 }),
            cell("Retracement: Price returns inside FVG zone", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("Signal: Bar[2] close inside, Bar[1] close ABOVE", { width: 4680 }),
            cell("Signal: Bar[2] close inside, Bar[1] close BELOW", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("SL = FVG Low - sl_pts", { width: 4680 }),
            cell("SL = FVG High + sl_pts", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("TP = Ask + tp_pts", { width: 4680 }),
            cell("TP = Bid - tp_pts", { width: 4680 }),
          ]}),
          new TableRow({ children: [
            cell("Color: Red > Orange > Green", { width: 4680 }),
            cell("Color: Green > Purple > Red", { width: 4680 }),
          ]}),
        ]
      }),

      para(""),
      para(""),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 1 } },
        spacing: { before: 400 },
        children: [new TextRun({ text: "End of Document", font: "Arial", size: 20, color: "888888", italics: true })]
      }),
    ]
  }]
});

// Generate
const outPath = process.argv[2] || "IFVG_EA_Guide.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("Created: " + outPath);
});
