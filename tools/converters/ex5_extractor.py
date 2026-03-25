#!/usr/bin/env python3
"""
EX5 Extractor - Extract recoverable information from compiled MQL5 .ex5 files.

Helps reconstruct lost source code by extracting strings, metadata, input parameters,
API function usage, DLL imports, and generating a .mq5 skeleton template.

Usage:
    python ex5_extractor.py input.ex5 [--output-dir ./output] [--format all|text|json|mq5]
"""

import argparse
import json
import os
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# =============================================================================
# Known MQL5 API Functions Database
# =============================================================================

KNOWN_MQL5_FUNCTIONS: Dict[str, List[str]] = {
    "Event Handlers": [
        "OnInit", "OnDeinit", "OnTick", "OnTimer", "OnTrade",
        "OnTradeTransaction", "OnBookEvent", "OnChartEvent",
        "OnCalculate", "OnStart", "OnTester", "OnTesterInit",
        "OnTesterDeinit", "OnTesterPass",
    ],
    "Trading": [
        "OrderSend", "OrderCalcMargin", "OrderCalcProfit", "OrderCheck",
        "OrderGetDouble", "OrderGetInteger", "OrderGetString",
        "OrderGetTicket", "OrderSelect", "OrdersTotal",
        "PositionSelect", "PositionSelectByTicket", "PositionGetDouble",
        "PositionGetInteger", "PositionGetString", "PositionGetSymbol",
        "PositionGetTicket", "PositionsTotal",
        "HistorySelect", "HistorySelectByPosition", "HistoryOrderSelect",
        "HistoryOrderGetDouble", "HistoryOrderGetInteger",
        "HistoryOrderGetString", "HistoryOrderGetTicket", "HistoryOrdersTotal",
        "HistoryDealSelect", "HistoryDealGetDouble", "HistoryDealGetInteger",
        "HistoryDealGetString", "HistoryDealGetTicket", "HistoryDealsTotal",
    ],
    "Account Info": [
        "AccountInfoDouble", "AccountInfoInteger", "AccountInfoString",
    ],
    "Market Info": [
        "SymbolInfoDouble", "SymbolInfoInteger", "SymbolInfoString",
        "SymbolInfoTick", "SymbolInfoSessionQuote", "SymbolInfoSessionTrade",
        "SymbolInfoMarginRate", "SymbolName", "SymbolsTotal", "SymbolSelect",
        "SymbolIsSynchronized", "MarketBookAdd", "MarketBookGet",
        "MarketBookRelease",
    ],
    "Price Data": [
        "CopyRates", "CopyTime", "CopyOpen", "CopyHigh", "CopyLow",
        "CopyClose", "CopyTickVolume", "CopyRealVolume", "CopySpread",
        "CopyTicks", "CopyTicksRange", "SeriesInfoInteger", "Bars",
        "BarsCalculated", "iBars", "iBarShift", "iClose", "iHigh",
        "iHighest", "iLow", "iLowest", "iOpen", "iTime", "iTickVolume",
        "iVolume", "iSpread",
    ],
    "Technical Indicators": [
        "iAC", "iAD", "iADX", "iADXWilder", "iAlligator", "iAMA", "iAO",
        "iATR", "iBands", "iBearsPower", "iBullsPower", "iBWMFI", "iCCI",
        "iChaikin", "iCustom", "iDEMA", "iDeMarker", "iEnvelopes",
        "iForce", "iFractals", "iFrAMA", "iGator", "iHeikenAshi",
        "iIchimoku", "iMA", "iMACD", "iMFI", "iMomentum", "iOBV",
        "iOsMA", "iRSI", "iRVI", "iSAR", "iStdDev", "iStochastic",
        "iTEMA", "iTriX", "iVIDyA", "iVolumes", "iWPR",
        "IndicatorCreate", "IndicatorParameters", "IndicatorRelease",
        "CopyBuffer",
    ],
    "Chart Operations": [
        "ChartApplyTemplate", "ChartClose", "ChartFirst", "ChartGetDouble",
        "ChartGetInteger", "ChartGetString", "ChartID", "ChartIndicatorAdd",
        "ChartIndicatorDelete", "ChartIndicatorGet", "ChartIndicatorName",
        "ChartIndicatorsTotal", "ChartNavigate", "ChartNext", "ChartOpen",
        "ChartPeriod", "ChartRedraw", "ChartSaveTemplate",
        "ChartScreenShot", "ChartSetDouble", "ChartSetInteger",
        "ChartSetString", "ChartSetSymbolPeriod", "ChartSymbol",
        "ChartTimePriceToXY", "ChartWindowFind", "ChartWindowOnDropped",
        "ChartXYToTimePrice", "Period", "Symbol", "WindowExpertName",
    ],
    "Object Operations": [
        "ObjectCreate", "ObjectDelete", "ObjectFind", "ObjectGetDouble",
        "ObjectGetInteger", "ObjectGetString", "ObjectGetTimeByValue",
        "ObjectGetValueByTime", "ObjectMove", "ObjectName",
        "ObjectSetDouble", "ObjectSetInteger", "ObjectSetString",
        "ObjectsDeleteAll", "ObjectsTotal",
    ],
    "String Functions": [
        "StringAdd", "StringBufferLen", "StringCompare", "StringConcatenate",
        "StringFill", "StringFind", "StringFormat", "StringGetCharacter",
        "StringInit", "StringLen", "StringReplace", "StringSetCharacter",
        "StringSplit", "StringSubstr", "StringToLower", "StringToUpper",
        "StringTrimLeft", "StringTrimRight",
    ],
    "Conversion": [
        "CharToString", "ColorToString", "DoubleToString",
        "EnumToString", "IntegerToString", "ShortToString",
        "StringToColor", "StringToDouble", "StringToInteger",
        "StringToShortArray", "StringToTime", "TimeToString",
        "TimeToStruct", "NormalizeDouble",
    ],
    "Math Functions": [
        "MathAbs", "MathArccos", "MathArcsin", "MathArctan", "MathCeil",
        "MathCos", "MathExp", "MathFloor", "MathLog", "MathLog10",
        "MathMax", "MathMin", "MathMod", "MathPow", "MathRand",
        "MathRound", "MathSin", "MathSqrt", "MathSrand", "MathTan",
        "MathIsValidNumber", "MathExpm1", "MathLog1p", "MathSwap",
    ],
    "Array Functions": [
        "ArrayBsearch", "ArrayCopy", "ArrayCompare", "ArrayFill",
        "ArrayFree", "ArrayGetAsSeries", "ArrayInitialize", "ArrayIsDynamic",
        "ArrayIsSeries", "ArrayMaximum", "ArrayMinimum", "ArrayPrint",
        "ArrayRange", "ArrayResize", "ArrayReverse", "ArraySetAsSeries",
        "ArraySize", "ArraySort", "ArraySwap",
    ],
    "File Operations": [
        "FileClose", "FileCopy", "FileDelete", "FileFindClose",
        "FileFindFirst", "FileFindNext", "FileFlush", "FileGetInteger",
        "FileIsEnding", "FileIsExist", "FileIsLineEnding", "FileMove",
        "FileOpen", "FileReadArray", "FileReadBool", "FileReadDatetime",
        "FileReadDouble", "FileReadFloat", "FileReadInteger",
        "FileReadLong", "FileReadNumber", "FileReadString",
        "FileReadStruct", "FileSeek", "FileSize", "FileTell",
        "FileWrite", "FileWriteArray", "FileWriteDouble", "FileWriteFloat",
        "FileWriteInteger", "FileWriteLong", "FileWriteString",
        "FileWriteStruct", "FolderClean", "FolderCreate", "FolderDelete",
    ],
    "Time Functions": [
        "TimeCurrent", "TimeLocal", "TimeGMT", "TimeDaylightSavings",
        "TimeGMTOffset", "TimeTradeServer", "TimeToStruct", "StructToTime",
    ],
    "Print & Alert": [
        "Alert", "Comment", "Print", "PrintFormat", "printf",
        "SendFTP", "SendMail", "SendNotification", "PlaySound",
        "MessageBox", "DebugBreak",
    ],
    "Global Variables": [
        "GlobalVariableCheck", "GlobalVariableDel", "GlobalVariableGet",
        "GlobalVariableName", "GlobalVariableSet", "GlobalVariableSetOnCondition",
        "GlobalVariableTemp", "GlobalVariableTime", "GlobalVariablesDeleteAll",
        "GlobalVariablesFlush", "GlobalVariablesTotal",
    ],
    "Common Functions": [
        "CLBufferCreate", "CLBufferFree", "CLBufferRead", "CLBufferWrite",
        "CLContextCreate", "CLContextFree", "CLExecute", "CLGetDeviceInfo",
        "CLGetInfoInteger", "CLHandleType", "CLKernelCreate", "CLKernelFree",
        "CLProgramCreate", "CLProgramFree", "CryptDecode", "CryptEncode",
        "EventChartCustom", "EventKillTimer", "EventSetMillisecondTimer",
        "EventSetTimer", "ExpertRemove", "GetLastError", "GetPointer",
        "GetTickCount", "GetTickCount64", "IsStopped", "MQLInfoInteger",
        "MQLInfoString", "ResetLastError", "ResourceCreate", "ResourceFree",
        "ResourceReadImage", "ResourceSave", "Sleep", "TerminalClose",
        "TerminalInfoDouble", "TerminalInfoInteger", "TerminalInfoString",
        "TesterStatistics", "ZeroMemory", "CheckPointer",
    ],
    "CTrade Class Methods": [
        "Buy", "Sell", "BuyLimit", "SellLimit", "BuyStop", "SellStop",
        "PositionOpen", "PositionClose", "PositionCloseBy",
        "PositionModify", "OrderOpen", "OrderModify", "OrderDelete",
        "SetExpertMagicNumber", "SetDeviationInPoints", "SetTypeFilling",
        "SetTypeFillingBySymbol", "SetMarginMode", "Request", "Result",
        "RequestAction", "RequestMagic", "RequestOrder", "RequestSymbol",
        "ResultOrder", "ResultDeal", "ResultRetcode", "ResultComment",
    ],
}

KNOWN_MQL5_ENUMS = [
    "ENUM_ORDER_TYPE", "ENUM_POSITION_TYPE", "ENUM_DEAL_TYPE",
    "ENUM_TRADE_REQUEST_ACTIONS", "ENUM_ORDER_TYPE_FILLING",
    "ENUM_ORDER_TYPE_TIME", "ENUM_TIMEFRAMES", "ENUM_MA_METHOD",
    "ENUM_APPLIED_PRICE", "ENUM_APPLIED_VOLUME", "ENUM_CHART_PROPERTY",
    "ENUM_SYMBOL_INFO_DOUBLE", "ENUM_SYMBOL_INFO_INTEGER",
    "ENUM_SYMBOL_INFO_STRING", "ENUM_ACCOUNT_INFO_DOUBLE",
    "ENUM_ACCOUNT_INFO_INTEGER", "ENUM_ACCOUNT_INFO_STRING",
    "ENUM_INDICATOR", "ENUM_OBJECT_TYPE",
]

KNOWN_MQL5_CONSTANTS = [
    "ORDER_TYPE_BUY", "ORDER_TYPE_SELL", "ORDER_TYPE_BUY_LIMIT",
    "ORDER_TYPE_SELL_LIMIT", "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP",
    "POSITION_TYPE_BUY", "POSITION_TYPE_SELL",
    "TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING", "TRADE_ACTION_SLTP",
    "TRADE_ACTION_MODIFY", "TRADE_ACTION_REMOVE", "TRADE_ACTION_CLOSE_BY",
    "SYMBOL_BID", "SYMBOL_ASK", "SYMBOL_POINT", "SYMBOL_DIGITS",
    "SYMBOL_VOLUME_MIN", "SYMBOL_VOLUME_MAX", "SYMBOL_VOLUME_STEP",
    "SYMBOL_TRADE_TICK_SIZE", "SYMBOL_TRADE_TICK_VALUE",
    "ACCOUNT_BALANCE", "ACCOUNT_EQUITY", "ACCOUNT_MARGIN",
    "ACCOUNT_MARGIN_FREE", "ACCOUNT_PROFIT", "ACCOUNT_LEVERAGE",
    "PERIOD_M1", "PERIOD_M5", "PERIOD_M15", "PERIOD_M30",
    "PERIOD_H1", "PERIOD_H4", "PERIOD_D1", "PERIOD_W1", "PERIOD_MN1",
    "MODE_SMA", "MODE_EMA", "MODE_SMMA", "MODE_LWMA",
    "PRICE_CLOSE", "PRICE_OPEN", "PRICE_HIGH", "PRICE_LOW",
    "PRICE_MEDIAN", "PRICE_TYPICAL", "PRICE_WEIGHTED",
    "INIT_SUCCEEDED", "INIT_FAILED", "INIT_PARAMETERS_INCORRECT",
    "TRADE_RETCODE_DONE", "TRADE_RETCODE_PLACED",
    "ORDER_FILLING_FOK", "ORDER_FILLING_IOC", "ORDER_FILLING_RETURN",
    "WRONG_VALUE", "EMPTY_VALUE", "CLR_NONE", "clrNONE",
    "OBJ_HLINE", "OBJ_VLINE", "OBJ_TREND", "OBJ_RECTANGLE",
    "OBJ_LABEL", "OBJ_TEXT", "OBJ_ARROW",
    "CHART_WINDOW_MAIN", "OBJPROP_COLOR", "OBJPROP_WIDTH",
    "FILE_READ", "FILE_WRITE", "FILE_CSV", "FILE_TXT", "FILE_BIN",
    "FILE_COMMON", "FILE_ANSI", "FILE_UNICODE",
]

# Common input parameter name patterns
INPUT_PARAM_PATTERNS = [
    r"(?i)^inp[_]?\w+",       # inp_ or Inp prefix
    r"(?i)^(take|tp)\s*profit",
    r"(?i)^(stop|sl)\s*loss",
    r"(?i)^lot\s*size",
    r"(?i)^magic\s*number",
    r"(?i)^(period|ma_period|rsi_period)",
    r"(?i)^(slippage|deviation)",
    r"(?i)^max\s*(lot|spread|drawdown|loss|risk)",
    r"(?i)^(trailing|trail)\s*(stop|start|step)",
    r"(?i)^(break|be)\s*even",
    r"(?i)^(start|end)\s*(hour|time|day)",
    r"(?i)^(enable|use|allow|show|display)\s*\w+",
    r"(?i)^(risk)\s*(percent|pct|ratio)",
]

# MQL5 data types
MQL5_TYPES = [
    "int", "uint", "long", "ulong", "short", "ushort",
    "double", "float", "string", "bool", "char", "uchar",
    "color", "datetime", "void",
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExtractedString:
    """A string extracted from the binary with metadata."""
    value: str
    offset: int
    encoding: str  # "utf-8" or "utf-16le"
    length: int

    def __hash__(self):
        return hash((self.value, self.offset))


@dataclass
class InputParameter:
    """A probable input parameter extracted from the binary."""
    name: str
    type_hint: str
    default_value: str
    confidence: str  # "high", "medium", "low"
    offset: int


@dataclass
class HeaderInfo:
    """Parsed .ex5 header information."""
    magic_bytes: str
    file_size: int
    raw_header_hex: str
    version_hint: str


@dataclass
class AnalysisResult:
    """Complete analysis result from an .ex5 file."""
    file_path: str
    file_size: int
    header: dict
    program_type: str  # "Expert Advisor", "Indicator", "Script", "Library", "Unknown"
    metadata: dict
    input_parameters: list
    api_functions: dict  # category -> list of function names
    event_handlers: list
    dll_imports: dict  # dll_name -> list of function names
    mql5_constants: list
    mql5_enums: list
    user_strings: list  # probable user-defined identifiers
    string_literals: list  # human-readable text strings
    all_strings_count: int


# =============================================================================
# String Extractor
# =============================================================================

class StringExtractor:
    """Extract readable strings from binary data."""

    def __init__(self, min_length: int = 4):
        self.min_length = min_length
        # Printable ASCII range plus common extended chars
        self._printable = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}

    def extract_utf8(self, data: bytes) -> List[ExtractedString]:
        """Extract UTF-8 / ASCII strings from binary data."""
        results = []
        current = bytearray()
        start_offset = 0

        for i, byte in enumerate(data):
            if byte in self._printable:
                if not current:
                    start_offset = i
                current.append(byte)
            else:
                if len(current) >= self.min_length:
                    try:
                        value = current.decode("utf-8", errors="ignore").strip()
                        if value and len(value) >= self.min_length:
                            results.append(ExtractedString(
                                value=value,
                                offset=start_offset,
                                encoding="utf-8",
                                length=len(current),
                            ))
                    except Exception:
                        pass
                current = bytearray()

        # Handle tail
        if len(current) >= self.min_length:
            try:
                value = current.decode("utf-8", errors="ignore").strip()
                if value and len(value) >= self.min_length:
                    results.append(ExtractedString(
                        value=value,
                        offset=start_offset,
                        encoding="utf-8",
                        length=len(current),
                    ))
            except Exception:
                pass

        return results

    def extract_utf16le(self, data: bytes) -> List[ExtractedString]:
        """Extract UTF-16LE strings (common in MQL5 compiled binaries)."""
        results = []
        current = bytearray()
        start_offset = 0

        i = 0
        while i < len(data) - 1:
            low, high = data[i], data[i + 1]
            # ASCII-range UTF-16LE: low byte is printable, high byte is 0x00
            if low in self._printable and high == 0x00:
                if not current:
                    start_offset = i
                current.extend([low, high])
                i += 2
            else:
                if len(current) >= self.min_length * 2:
                    try:
                        value = current.decode("utf-16-le", errors="ignore").strip()
                        if value and len(value) >= self.min_length:
                            results.append(ExtractedString(
                                value=value,
                                offset=start_offset,
                                encoding="utf-16le",
                                length=len(current),
                            ))
                    except Exception:
                        pass
                current = bytearray()
                i += 2 if i + 1 < len(data) else 1

        # Handle tail
        if len(current) >= self.min_length * 2:
            try:
                value = current.decode("utf-16-le", errors="ignore").strip()
                if value and len(value) >= self.min_length:
                    results.append(ExtractedString(
                        value=value,
                        offset=start_offset,
                        encoding="utf-16le",
                        length=len(current),
                    ))
            except Exception:
                pass

        return results

    def extract_all(self, data: bytes) -> List[ExtractedString]:
        """Extract and deduplicate strings from both encodings."""
        utf8_strings = self.extract_utf8(data)
        utf16_strings = self.extract_utf16le(data)

        # Build a map of UTF-16LE offset ranges for deduplication
        utf16_ranges = []
        for s in utf16_strings:
            utf16_ranges.append((s.offset, s.offset + s.length))

        # Filter UTF-8 strings that overlap with UTF-16LE matches
        filtered_utf8 = []
        for s in utf8_strings:
            overlaps = False
            for start, end in utf16_ranges:
                if start <= s.offset < end or start < s.offset + s.length <= end:
                    overlaps = True
                    break
            if not overlaps:
                filtered_utf8.append(s)

        combined = filtered_utf8 + utf16_strings

        # Remove duplicates by value (keep first occurrence)
        seen = set()
        unique = []
        for s in sorted(combined, key=lambda x: x.offset):
            if s.value not in seen:
                seen.add(s.value)
                unique.append(s)

        # Filter garbage strings (all same char, random binary artifacts)
        return [s for s in unique if not self._is_garbage(s.value)]

    def _is_garbage(self, value: str) -> bool:
        """Check if a string is likely garbage/binary artifact."""
        if len(set(value)) <= 1:
            return True
        # Mostly non-alphanumeric
        alnum_count = sum(1 for c in value if c.isalnum())
        if len(value) > 4 and alnum_count / len(value) < 0.3:
            return True
        return False


# =============================================================================
# Header Parser
# =============================================================================

class HeaderParser:
    """Parse .ex5 file header for basic metadata."""

    def parse(self, data: bytes) -> HeaderInfo:
        file_size = len(data)
        magic_hex = data[:16].hex() if len(data) >= 16 else data.hex()

        # Try to identify version hints from header
        version_hint = "unknown"
        if len(data) >= 8:
            try:
                val = struct.unpack_from("<I", data, 4)[0]
                if 400 <= val <= 2000:
                    version_hint = f"build ~{val}"
            except struct.error:
                pass

        return HeaderInfo(
            magic_bytes=magic_hex,
            file_size=file_size,
            raw_header_hex=data[:64].hex() if len(data) >= 64 else data.hex(),
            version_hint=version_hint,
        )


# =============================================================================
# Metadata Extractor
# =============================================================================

class MetadataExtractor:
    """Extract EA/indicator metadata (#property values) from strings."""

    def extract(self, strings: List[ExtractedString], filename: str) -> dict:
        metadata = {
            "name": Path(filename).stem,
            "copyright": "",
            "link": "",
            "version": "",
            "description": "",
        }

        for s in strings:
            val = s.value

            # Copyright detection
            if not metadata["copyright"]:
                if re.search(r"(?i)copyright|©|\(c\)", val):
                    metadata["copyright"] = val

            # URL/link detection
            if not metadata["link"]:
                if re.search(r"https?://|www\.", val):
                    metadata["link"] = val

            # Version detection (e.g., "1.00", "2.5")
            if not metadata["version"]:
                if re.match(r"^\d+\.\d+$", val.strip()):
                    metadata["version"] = val.strip()

            # Description (longer text strings near start of file)
            if not metadata["description"] and s.offset < 2048:
                if len(val) > 20 and " " in val and not metadata["copyright"] == val:
                    if not re.search(r"https?://|copyright|©", val, re.IGNORECASE):
                        metadata["description"] = val

        return metadata


# =============================================================================
# Import Extractor
# =============================================================================

class ImportExtractor:
    """Extract DLL imports from the binary."""

    def extract(self, strings: List[ExtractedString], data: bytes) -> dict:
        imports = defaultdict(list)
        dll_strings = []

        # Find DLL name strings
        for s in strings:
            if re.search(r"\.dll$", s.value, re.IGNORECASE):
                dll_strings.append(s)

        # For each DLL, find nearby strings that look like function names
        for dll in dll_strings:
            nearby = [
                s for s in strings
                if s.offset > dll.offset
                and s.offset < dll.offset + 1024
                and re.match(r"^[A-Za-z_]\w+$", s.value)
                and s.value != dll.value
            ]
            for func in nearby:
                if func.value not in imports[dll.value]:
                    imports[dll.value].append(func.value)

        return dict(imports)


# =============================================================================
# Input Parameter Extractor
# =============================================================================

class InputParameterExtractor:
    """Attempt to identify input parameters from string patterns."""

    def extract(self, strings: List[ExtractedString]) -> List[InputParameter]:
        params = []
        string_values = {s.value: s for s in strings}

        for s in strings:
            val = s.value.strip()

            # Skip known API functions and constants
            if self._is_known_api(val):
                continue

            confidence = "low"
            type_hint = "double"

            # High confidence: matches common input parameter patterns
            for pattern in INPUT_PARAM_PATTERNS:
                if re.match(pattern, val):
                    confidence = "high"
                    break

            # Medium confidence: CamelCase identifiers that look like params
            if confidence == "low":
                if re.match(r"^[A-Z][a-z]+[A-Z]\w*$", val) and len(val) <= 30:
                    # CamelCase, reasonable length
                    lower = val.lower()
                    param_keywords = [
                        "period", "lot", "stop", "take", "profit", "loss",
                        "magic", "slip", "trail", "risk", "max", "min",
                        "level", "distance", "step", "size", "count",
                        "enable", "use", "show", "start", "end", "hour",
                        "multiplier", "factor", "ratio", "threshold",
                    ]
                    if any(kw in lower for kw in param_keywords):
                        confidence = "medium"

            if confidence == "low":
                continue

            # Try to infer type
            lower = val.lower()
            if any(kw in lower for kw in ["period", "magic", "count", "bar", "shift", "hour", "minute"]):
                type_hint = "int"
            elif any(kw in lower for kw in ["enable", "use", "show", "allow", "display", "is_"]):
                type_hint = "bool"
            elif any(kw in lower for kw in ["name", "symbol", "comment", "prefix", "suffix"]):
                type_hint = "string"
            elif any(kw in lower for kw in ["color", "clr"]):
                type_hint = "color"
            elif any(kw in lower for kw in ["time", "date", "expir"]):
                type_hint = "datetime"

            params.append(InputParameter(
                name=val,
                type_hint=type_hint,
                default_value="0" if type_hint in ("int", "double") else '""' if type_hint == "string" else "true" if type_hint == "bool" else "clrNone" if type_hint == "color" else "0",
                confidence=confidence,
                offset=s.offset,
            ))

        # Deduplicate by name
        seen = set()
        unique = []
        for p in params:
            if p.name not in seen:
                seen.add(p.name)
                unique.append(p)

        # Sort by confidence (high first) then offset
        priority = {"high": 0, "medium": 1, "low": 2}
        unique.sort(key=lambda p: (priority.get(p.confidence, 3), p.offset))

        return unique

    def _is_known_api(self, name: str) -> bool:
        """Check if a string is a known MQL5 API function or constant."""
        for funcs in KNOWN_MQL5_FUNCTIONS.values():
            if name in funcs:
                return True
        if name in KNOWN_MQL5_CONSTANTS or name in KNOWN_MQL5_ENUMS:
            return True
        if name in MQL5_TYPES:
            return True
        return False


# =============================================================================
# Function Matcher
# =============================================================================

class FunctionMatcher:
    """Match extracted strings against known MQL5 API functions."""

    def __init__(self):
        # Build a flat lookup for speed
        self._func_to_category: Dict[str, str] = {}
        for category, funcs in KNOWN_MQL5_FUNCTIONS.items():
            for func in funcs:
                self._func_to_category[func] = category

    def match(self, strings: List[ExtractedString]) -> Tuple[
        Dict[str, List[str]], List[str], List[str], List[str], List[str]
    ]:
        """
        Returns:
            api_functions: category -> list of matched function names
            event_handlers: list of detected event handlers
            constants_found: list of MQL5 constants found
            enums_found: list of MQL5 enums found
            user_strings: strings that look like user identifiers
        """
        api_functions = defaultdict(list)
        event_handlers = []
        constants_found = []
        enums_found = []
        user_strings = []

        string_values = {s.value for s in strings}

        for val in string_values:
            if val in self._func_to_category:
                cat = self._func_to_category[val]
                if cat == "Event Handlers":
                    event_handlers.append(val)
                api_functions[cat].append(val)
            elif val in KNOWN_MQL5_CONSTANTS:
                constants_found.append(val)
            elif val in KNOWN_MQL5_ENUMS:
                enums_found.append(val)
            elif re.match(r"^[A-Za-z_]\w{2,40}$", val) and val not in MQL5_TYPES:
                # Looks like an identifier but not a known API
                user_strings.append(val)

        # Sort everything
        for cat in api_functions:
            api_functions[cat].sort()
        event_handlers.sort()
        constants_found.sort()
        enums_found.sort()
        user_strings.sort()

        return dict(api_functions), event_handlers, constants_found, enums_found, user_strings


# =============================================================================
# EX5 Analyzer (Orchestrator)
# =============================================================================

class EX5Analyzer:
    """Main analyzer that orchestrates all extraction components."""

    def __init__(self, min_string_length: int = 4, verbose: bool = False):
        self.min_string_length = min_string_length
        self.verbose = verbose

    def analyze(self, file_path: str) -> AnalysisResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.suffix.lower() == ".ex5":
            print(f"Warning: File does not have .ex5 extension: {path.name}")

        with open(path, "rb") as f:
            data = f.read()

        if self.verbose:
            print(f"Read {len(data)} bytes from {path.name}")

        # 1. Parse header
        header_parser = HeaderParser()
        header = header_parser.parse(data)
        if self.verbose:
            print(f"Header: magic={header.magic_bytes[:16]}...")

        # 2. Extract strings
        extractor = StringExtractor(min_length=self.min_string_length)
        all_strings = extractor.extract_all(data)
        if self.verbose:
            print(f"Extracted {len(all_strings)} unique strings")

        # 3. Extract metadata
        meta_extractor = MetadataExtractor()
        metadata = meta_extractor.extract(all_strings, file_path)
        if self.verbose:
            print(f"Metadata: {metadata}")

        # 4. Match functions
        matcher = FunctionMatcher()
        api_functions, event_handlers, constants, enums, user_strings = matcher.match(all_strings)
        if self.verbose:
            total_api = sum(len(v) for v in api_functions.values())
            print(f"Matched {total_api} API functions, {len(event_handlers)} event handlers")

        # 5. Extract imports
        import_extractor = ImportExtractor()
        dll_imports = import_extractor.extract(all_strings, data)
        if self.verbose:
            print(f"Found {len(dll_imports)} DLL imports")

        # 6. Extract input parameters
        input_extractor = InputParameterExtractor()
        inputs = input_extractor.extract(all_strings)
        if self.verbose:
            print(f"Found {len(inputs)} probable input parameters")

        # 7. Detect program type
        program_type = self._detect_program_type(event_handlers)

        # 8. Separate string literals from identifiers
        string_literals = [
            s.value for s in all_strings
            if " " in s.value or len(s.value) > 50
            or re.search(r"[!?,.:;\"']", s.value)
        ]

        return AnalysisResult(
            file_path=str(path),
            file_size=len(data),
            header={
                "magic_bytes": header.magic_bytes,
                "raw_header_hex": header.raw_header_hex,
                "version_hint": header.version_hint,
            },
            program_type=program_type,
            metadata=metadata,
            input_parameters=[
                {
                    "name": p.name,
                    "type": p.type_hint,
                    "default": p.default_value,
                    "confidence": p.confidence,
                }
                for p in inputs
            ],
            api_functions=api_functions,
            event_handlers=event_handlers,
            dll_imports=dll_imports,
            mql5_constants=constants,
            mql5_enums=enums,
            user_strings=user_strings,
            string_literals=string_literals,
            all_strings_count=len(all_strings),
        )

    def _detect_program_type(self, event_handlers: List[str]) -> str:
        handlers_set = set(event_handlers)
        if "OnTick" in handlers_set:
            return "Expert Advisor"
        elif "OnCalculate" in handlers_set:
            return "Indicator"
        elif "OnStart" in handlers_set:
            return "Script"
        elif not handlers_set:
            return "Library / Unknown"
        else:
            return "Unknown"


# =============================================================================
# Output Generators
# =============================================================================

class TextReportGenerator:
    """Generate human-readable text report."""

    def generate(self, result: AnalysisResult) -> str:
        lines = []
        sep = "=" * 70

        lines.append(sep)
        lines.append("  EX5 ANALYSIS REPORT")
        lines.append(sep)
        lines.append(f"  File:         {result.file_path}")
        lines.append(f"  Size:         {result.file_size:,} bytes")
        lines.append(f"  Program Type: {result.program_type}")
        lines.append(f"  Strings Found:{result.all_strings_count}")
        lines.append(sep)

        # Metadata
        lines.append("\n--- METADATA ---")
        for key, val in result.metadata.items():
            lines.append(f"  {key:15s}: {val if val else '(not detected)'}")

        # Header info
        lines.append("\n--- HEADER ---")
        lines.append(f"  Magic bytes:   {result.header['magic_bytes'][:32]}...")
        lines.append(f"  Version hint:  {result.header['version_hint']}")

        # Event handlers
        lines.append("\n--- EVENT HANDLERS ---")
        if result.event_handlers:
            for h in result.event_handlers:
                lines.append(f"  {h}()")
        else:
            lines.append("  (none detected)")

        # Input parameters
        lines.append("\n--- INPUT PARAMETERS (probable) ---")
        if result.input_parameters:
            for p in result.input_parameters:
                conf = p["confidence"].upper()
                lines.append(f"  [{conf:6s}]  input {p['type']:10s} {p['name']} = {p['default']};")
        else:
            lines.append("  (none detected)")

        # API functions
        lines.append("\n--- MQL5 API FUNCTIONS USED ---")
        if result.api_functions:
            for cat, funcs in sorted(result.api_functions.items()):
                if cat == "Event Handlers":
                    continue
                lines.append(f"\n  [{cat}]")
                for func in funcs:
                    lines.append(f"    {func}()")
        else:
            lines.append("  (none detected)")

        # Constants
        if result.mql5_constants:
            lines.append("\n--- MQL5 CONSTANTS FOUND ---")
            for c in result.mql5_constants:
                lines.append(f"  {c}")

        # Enums
        if result.mql5_enums:
            lines.append("\n--- MQL5 ENUMS FOUND ---")
            for e in result.mql5_enums:
                lines.append(f"  {e}")

        # DLL imports
        lines.append("\n--- DLL IMPORTS ---")
        if result.dll_imports:
            for dll, funcs in result.dll_imports.items():
                lines.append(f"\n  #import \"{dll}\"")
                for func in funcs:
                    lines.append(f"    {func}()")
        else:
            lines.append("  (none detected)")

        # String literals
        lines.append("\n--- STRING LITERALS ---")
        if result.string_literals:
            for s in result.string_literals[:50]:  # Limit output
                display = s[:100] + "..." if len(s) > 100 else s
                lines.append(f"  \"{display}\"")
            if len(result.string_literals) > 50:
                lines.append(f"  ... and {len(result.string_literals) - 50} more")
        else:
            lines.append("  (none detected)")

        # User identifiers
        lines.append("\n--- USER-DEFINED IDENTIFIERS ---")
        if result.user_strings:
            for s in result.user_strings[:80]:
                lines.append(f"  {s}")
            if len(result.user_strings) > 80:
                lines.append(f"  ... and {len(result.user_strings) - 80} more")
        else:
            lines.append("  (none detected)")

        lines.append(f"\n{sep}")
        lines.append("  End of report")
        lines.append(sep)

        return "\n".join(lines)


class JsonReportGenerator:
    """Generate structured JSON report."""

    def generate(self, result: AnalysisResult) -> str:
        data = {
            "file": result.file_path,
            "file_size": result.file_size,
            "program_type": result.program_type,
            "strings_extracted": result.all_strings_count,
            "header": result.header,
            "metadata": result.metadata,
            "event_handlers": result.event_handlers,
            "input_parameters": result.input_parameters,
            "api_functions": result.api_functions,
            "mql5_constants": result.mql5_constants,
            "mql5_enums": result.mql5_enums,
            "dll_imports": result.dll_imports,
            "string_literals": result.string_literals,
            "user_identifiers": result.user_strings,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


class MQ5SkeletonGenerator:
    """Generate a .mq5 skeleton file from extracted data."""

    def generate(self, result: AnalysisResult) -> str:
        lines = []
        name = result.metadata.get("name", "Recovered_EA")
        copyright_val = result.metadata.get("copyright", "")
        link = result.metadata.get("link", "")
        version = result.metadata.get("version", "1.00")
        description = result.metadata.get("description", "")

        # Header comment
        lines.append("//+------------------------------------------------------------------+")
        lines.append(f"//| {name + '.mq5':<65s}|")
        lines.append(f"//| {copyright_val:<65s}|")
        lines.append(f"//| {link:<65s}|")
        lines.append("//+------------------------------------------------------------------+")

        # Properties
        if copyright_val:
            lines.append(f'#property copyright "{copyright_val}"')
        if link:
            lines.append(f'#property link      "{link}"')
        lines.append(f'#property version   "{version}"')
        if description:
            lines.append(f'#property description "{description}"')
        lines.append('#property strict')

        # Indicator-specific properties
        if result.program_type == "Indicator":
            lines.append('#property indicator_chart_window')
            lines.append('#property indicator_buffers 1')
            lines.append('#property indicator_plots   1')

        lines.append("")

        # Includes (detect CTrade usage)
        api_all = []
        for funcs in result.api_functions.values():
            api_all.extend(funcs)
        ctrade_methods = set(KNOWN_MQL5_FUNCTIONS.get("CTrade Class Methods", []))
        if any(f in ctrade_methods for f in api_all):
            lines.append('#include <Trade\\Trade.mqh>')
            lines.append('CTrade trade;')
            lines.append("")

        # DLL imports
        if result.dll_imports:
            for dll, funcs in result.dll_imports.items():
                lines.append(f'#import "{dll}"')
                for func in funcs:
                    lines.append(f"   // {func}() - reconstruct signature")
                lines.append("#import")
            lines.append("")

        # Input parameters
        if result.input_parameters:
            lines.append("// --- Input Parameters ---")
            lines.append("// Confidence: HIGH = name pattern matched, MEDIUM = keyword matched, LOW = guess")
            for p in result.input_parameters:
                conf = p["confidence"]
                lines.append(f'input {p["type"]:<10s} {p["name"]:<30s} = {p["default"]};   // [{conf}]')
            lines.append("")

        # Global variables placeholder
        lines.append("// --- Global Variables ---")
        lines.append("// TODO: Add global variables as needed")
        lines.append("")

        # Event handlers
        if result.program_type == "Expert Advisor":
            self._gen_ea_skeleton(lines, result)
        elif result.program_type == "Indicator":
            self._gen_indicator_skeleton(lines, result)
        elif result.program_type == "Script":
            self._gen_script_skeleton(lines, result)
        else:
            self._gen_ea_skeleton(lines, result)  # Default to EA

        # Detected string literals as comments
        if result.string_literals:
            lines.append("")
            lines.append("//+------------------------------------------------------------------+")
            lines.append("//| String literals found in binary (clues for logic reconstruction) |")
            lines.append("//+------------------------------------------------------------------+")
            for s in result.string_literals[:30]:
                safe = s.replace("*/", "* /")[:90]
                lines.append(f'// "{safe}"')
            if len(result.string_literals) > 30:
                lines.append(f"// ... and {len(result.string_literals) - 30} more (see full report)")

        # User identifiers as comments
        if result.user_strings:
            lines.append("")
            lines.append("//+------------------------------------------------------------------+")
            lines.append("//| User-defined identifiers (possible function/variable names)      |")
            lines.append("//+------------------------------------------------------------------+")
            for s in result.user_strings[:40]:
                lines.append(f"// {s}")
            if len(result.user_strings) > 40:
                lines.append(f"// ... and {len(result.user_strings) - 40} more (see full report)")

        return "\n".join(lines)

    def _gen_ea_skeleton(self, lines: list, result: AnalysisResult):
        # OnInit
        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Expert initialization function                                    |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("int OnInit()")
        lines.append("{")
        self._add_api_comments(lines, result, ["Common Functions", "Chart Operations"])
        lines.append("   // TODO: Reconstruct initialization logic")
        lines.append("   return(INIT_SUCCEEDED);")
        lines.append("}")
        lines.append("")

        # OnDeinit
        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Expert deinitialization function                                  |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("void OnDeinit(const int reason)")
        lines.append("{")
        lines.append("   // TODO: Cleanup logic")
        lines.append("}")
        lines.append("")

        # OnTick
        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Expert tick function                                              |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("void OnTick()")
        lines.append("{")
        self._add_api_comments(lines, result, [
            "Trading", "Market Info", "Price Data",
            "Technical Indicators", "Account Info",
        ])
        lines.append("   // TODO: Reconstruct trading logic")
        lines.append("}")
        lines.append("")

        # OnTimer if detected
        if "OnTimer" in result.event_handlers:
            lines.append("//+------------------------------------------------------------------+")
            lines.append("//| Timer function                                                    |")
            lines.append("//+------------------------------------------------------------------+")
            lines.append("void OnTimer()")
            lines.append("{")
            lines.append("   // TODO: Reconstruct timer logic")
            lines.append("}")
            lines.append("")

        # OnTrade if detected
        if "OnTrade" in result.event_handlers:
            lines.append("//+------------------------------------------------------------------+")
            lines.append("//| Trade event handler                                              |")
            lines.append("//+------------------------------------------------------------------+")
            lines.append("void OnTrade()")
            lines.append("{")
            lines.append("   // TODO: Reconstruct trade event logic")
            lines.append("}")
            lines.append("")

        # OnChartEvent if detected
        if "OnChartEvent" in result.event_handlers:
            lines.append("//+------------------------------------------------------------------+")
            lines.append("//| Chart event handler                                              |")
            lines.append("//+------------------------------------------------------------------+")
            lines.append("void OnChartEvent(const int id, const long &lparam,")
            lines.append("                  const double &dparam, const string &sparam)")
            lines.append("{")
            lines.append("   // TODO: Reconstruct chart event logic")
            lines.append("}")
            lines.append("")

    def _gen_indicator_skeleton(self, lines: list, result: AnalysisResult):
        lines.append("// --- Indicator Buffers ---")
        lines.append("double Buffer1[];")
        lines.append("")

        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Custom indicator initialization function                          |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("int OnInit()")
        lines.append("{")
        lines.append("   SetIndexBuffer(0, Buffer1);")
        self._add_api_comments(lines, result, ["Chart Operations"])
        lines.append("   // TODO: Reconstruct indicator setup")
        lines.append("   return(INIT_SUCCEEDED);")
        lines.append("}")
        lines.append("")

        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Custom indicator iteration function                               |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("int OnCalculate(const int rates_total,")
        lines.append("                const int prev_calculated,")
        lines.append("                const datetime &time[],")
        lines.append("                const double &open[],")
        lines.append("                const double &high[],")
        lines.append("                const double &low[],")
        lines.append("                const double &close[],")
        lines.append("                const long &tick_volume[],")
        lines.append("                const long &volume[],")
        lines.append("                const int &spread[])")
        lines.append("{")
        self._add_api_comments(lines, result, [
            "Technical Indicators", "Price Data", "Math Functions",
        ])
        lines.append("   // TODO: Reconstruct indicator calculation logic")
        lines.append("   return(rates_total);")
        lines.append("}")
        lines.append("")

    def _gen_script_skeleton(self, lines: list, result: AnalysisResult):
        lines.append("//+------------------------------------------------------------------+")
        lines.append("//| Script program start function                                     |")
        lines.append("//+------------------------------------------------------------------+")
        lines.append("void OnStart()")
        lines.append("{")
        self._add_api_comments(lines, result, list(result.api_functions.keys()))
        lines.append("   // TODO: Reconstruct script logic")
        lines.append("}")
        lines.append("")

    def _add_api_comments(self, lines: list, result: AnalysisResult, categories: list):
        """Add comments listing detected API calls for given categories."""
        for cat in categories:
            funcs = result.api_functions.get(cat, [])
            if funcs:
                func_list = ", ".join(funcs)
                lines.append(f"   // Detected [{cat}]: {func_list}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="EX5 Extractor - Extract information from compiled MQL5 .ex5 files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ex5_extractor.py MyEA.ex5
  python ex5_extractor.py MyEA.ex5 --format mq5 --output-dir ./recovered
  python ex5_extractor.py MyEA.ex5 --format all --min-string-length 3 --verbose
        """,
    )
    parser.add_argument("input", help="Path to .ex5 file")
    parser.add_argument(
        "--output-dir", "-o",
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "mq5", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--min-string-length", "-m",
        type=int,
        default=4,
        help="Minimum string length to extract (default: 4)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed extraction progress",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress stdout, only write files",
    )

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run analysis
    analyzer = EX5Analyzer(
        min_string_length=args.min_string_length,
        verbose=args.verbose,
    )

    try:
        result = analyzer.analyze(str(input_path))
    except Exception as e:
        print(f"Error analyzing file: {e}", file=sys.stderr)
        sys.exit(1)

    base_name = input_path.stem
    formats = ["text", "json", "mq5"] if args.format == "all" else [args.format]
    written_files = []

    for fmt in formats:
        if fmt == "text":
            generator = TextReportGenerator()
            content = generator.generate(result)
            out_path = output_dir / f"{base_name}_report.txt"
            out_path.write_text(content, encoding="utf-8")
            written_files.append(str(out_path))

        elif fmt == "json":
            generator = JsonReportGenerator()
            content = generator.generate(result)
            out_path = output_dir / f"{base_name}_report.json"
            out_path.write_text(content, encoding="utf-8")
            written_files.append(str(out_path))

        elif fmt == "mq5":
            generator = MQ5SkeletonGenerator()
            content = generator.generate(result)
            out_path = output_dir / f"{base_name}_skeleton.mq5"
            out_path.write_text(content, encoding="utf-8")
            written_files.append(str(out_path))

    if not args.quiet:
        print(f"\nAnalysis complete for: {input_path.name}")
        print(f"Program type: {result.program_type}")
        print(f"Strings extracted: {result.all_strings_count}")
        print(f"API functions found: {sum(len(v) for v in result.api_functions.values())}")
        print(f"Event handlers: {', '.join(result.event_handlers) or 'none'}")
        print(f"Input parameters (probable): {len(result.input_parameters)}")
        print(f"DLL imports: {sum(len(v) for v in result.dll_imports.values())}")
        print(f"String literals: {len(result.string_literals)}")
        print(f"\nOutput files:")
        for f in written_files:
            print(f"  {f}")


if __name__ == "__main__":
    main()
