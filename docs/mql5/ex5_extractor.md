# EX5 Extractor - MQL5 Binary Analysis Tool

## Overview

A Python CLI utility that extracts recoverable information from compiled MQL5 `.ex5` files to help reconstruct lost source code. It does **not** decompile — it performs intelligent binary analysis to extract strings, metadata, API usage, and generates a ready-to-edit `.mq5` skeleton.

**Location**: `tools/converters/ex5_extractor.py`

## What It Extracts

| Data | Method | Reliability |
|------|--------|-------------|
| EA/Indicator name, copyright, version, link | String pattern matching | High |
| Event handlers (OnTick, OnInit, OnCalculate...) | Exact match vs known list | High |
| MQL5 API functions used | Exact match vs 300+ known functions | High |
| MQL5 constants & enums | Exact match vs known constants | High |
| DLL imports | .dll string detection + nearby functions | High |
| Input parameter names | Pattern matching (inp_, TakeProfit, etc.) | Medium |
| Input parameter types | Keyword heuristic inference | Low-Medium |
| String literals (error messages, comments) | UTF-8 + UTF-16LE extraction | High |
| User-defined identifiers | Identifier pattern, not in API list | Medium |

## What It Cannot Recover

- Internal code logic, conditions, loops
- Variable values and calculations
- Custom function implementations
- Comments and documentation
- Algorithm/formula details

## Installation

No external dependencies required — uses only Python standard library.

```bash
# Requires Python 3.7+
python --version
```

## Usage

### Basic (generates all outputs)
```bash
python tools/converters/ex5_extractor.py path/to/MyEA.ex5
```

### Specify output format
```bash
# Only .mq5 skeleton
python tools/converters/ex5_extractor.py MyEA.ex5 --format mq5

# Only JSON report
python tools/converters/ex5_extractor.py MyEA.ex5 --format json

# Only text report
python tools/converters/ex5_extractor.py MyEA.ex5 --format text
```

### Custom output directory
```bash
python tools/converters/ex5_extractor.py MyEA.ex5 --output-dir ./recovered
```

### Adjust string extraction sensitivity
```bash
# Capture shorter strings (may include more noise)
python tools/converters/ex5_extractor.py MyEA.ex5 --min-string-length 3

# Only longer strings (less noise, may miss parameter names)
python tools/converters/ex5_extractor.py MyEA.ex5 --min-string-length 6
```

### Verbose mode
```bash
python tools/converters/ex5_extractor.py MyEA.ex5 --verbose
```

## Output Files

When using `--format all` (default), three files are generated:

### 1. `<name>_report.txt` — Human-readable report
Contains all findings organized by section: metadata, event handlers, input parameters, API functions by category, DLL imports, string literals, and user identifiers.

### 2. `<name>_report.json` — Structured JSON report
Machine-readable format for further processing or integration with other tools.

### 3. `<name>_skeleton.mq5` — Ready-to-edit MQL5 source template
A `.mq5` file pre-filled with:
- Correct `#property` directives from metadata
- `#import` blocks for detected DLL imports
- `input` variable declarations for detected parameters
- Correct event handler signatures based on program type (EA/Indicator/Script)
- Comments listing detected API calls in each handler
- All string literals and user identifiers as comments for reference

## Example Output

### Skeleton for an Expert Advisor:
```mql5
//+------------------------------------------------------------------+
//| MyEA.mq5                                                          |
//| Copyright 2024, MyCompany                                         |
//| https://www.mysite.com                                            |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, MyCompany"
#property link      "https://www.mysite.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

// --- Input Parameters ---
input double   TakeProfit                     = 0;   // [HIGH]
input double   StopLoss                       = 0;   // [HIGH]
input int      MagicNumber                    = 0;   // [HIGH]
input double   LotSize                        = 0;   // [HIGH]
input int      RSI_Period                     = 0;   // [MEDIUM]

void OnTick()
{
   // Detected [Trading]: OrderSend, PositionSelect, PositionClose
   // Detected [Technical Indicators]: iMA, iRSI
   // Detected [Market Info]: SymbolInfoDouble, SymbolInfoTick
   // TODO: Reconstruct trading logic
}
```

## Reconstruction Workflow

1. **Run the extractor** on your `.ex5` file
2. **Review the text report** to understand what the EA does (API calls reveal the pattern)
3. **Open the skeleton .mq5** in MetaEditor
4. **Cross-reference string literals** — error messages often reveal the logic flow
5. **Use API function categories** to reconstruct:
   - Which indicators were used (Technical Indicators section)
   - How trades were managed (Trading section)
   - What account/symbol info was checked (Account/Market Info sections)
6. **Fill in the logic** based on your memory + the clues extracted
7. **Compile and test** against the original .ex5 behavior

## Limitations

- Newer MetaQuotes compiler versions apply stronger obfuscation
- Some strings may be encrypted at runtime and won't appear in binary
- Input parameter default values cannot be reliably extracted
- Type inference for parameters is heuristic-based and may be incorrect
- Protected/encrypted .ex5 files will yield fewer results

## API Function Database

The tool matches against **300+ known MQL5 functions** across 15 categories:
- Event Handlers, Trading, Account Info, Market Info
- Price Data, Technical Indicators (40+ indicators)
- Chart/Object Operations, String/Conversion Functions
- Math, Array, File Operations, Time Functions
- Print & Alert, Global Variables, Common Functions
- CTrade Class Methods
