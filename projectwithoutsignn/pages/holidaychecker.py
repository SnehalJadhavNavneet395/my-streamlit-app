
import io
import re
import difflib
import calendar
import html as html_module
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
import fitz  # PyMuPDF
import base64
import requests
from PIL import Image
import json
import pandas as pd
import streamlit as st
from dateutil.easter import easter as western_easter

# ──────────────────────────────────────────────────────────────────────
# LangChain / LangGraph imports
# ──────────────────────────────────────────────────────────────────────
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.documents import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        from langchain.chat_models import ChatOpenAI
        from langchain.schema import HumanMessage, SystemMessage
        from langchain.prompts import ChatPromptTemplate
        LANGCHAIN_AVAILABLE = True
        Document = None
    except ImportError:
        LANGCHAIN_AVAILABLE = False
        ChatOpenAI = None

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

try:
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import HuggingFaceEmbeddings
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────
# Optional libraries
# ──────────────────────────────────────────────────────────────────────
try:
    from dateutil.easter import easter as orthodox_easter_raw
    EASTER_ORTHODOX_METHOD = 2
except Exception:
    orthodox_easter_raw = None
    EASTER_ORTHODOX_METHOD = None

try:
    from hijridate import Hijri, Gregorian
    HIJRI_AVAILABLE = True
except Exception:
    HIJRI_AVAILABLE = False
    Hijri = None
    Gregorian = None

try:
    from convertdate import hebrew
    HEBREW_AVAILABLE = True
except Exception:
    HEBREW_AVAILABLE = False
    hebrew = None


# ======================================================
# CONFIG
# ======================================================
APP_TITLE = "Holiday Calendar Report Generator"
APP_ICON = "📅"

REQUIRED_COLUMNS = ["year", "Holiday", "day", "datetext", "date"]

HOLIDAY_NAMES = [
    "New Year's Day",
    "Martin Luther King, Jr. Day (US)",
    "Lunar New Year",
    "First of Ramadan begins at sundown",
    "First of Ramadan",
    "Groundhog Day",
    "Lincoln's Birthday (US)",
    "Valentine's Day",
    "Presidents' Day (US)",
    "Washington's Birthday (US)",
    "Eid al Fitr begins at sundown",
    "Eid al Fitr",
    "Eastern Orthodox Lent begins",
    "Ash Wednesday",
    "Daylight Saving Time begins",
    "St. Patrick's Day",
    "Spring begins",
    "Palm Sunday",
    "Passover begins at sundown",
    "Passover",
    "Good Friday",
    "Easter",
    "Eastern Orthodox Easter",
    "Easter Monday (C)",
    "Earth Day",
    "Holocaust Remembrance Day",
    "Administrative Professionals Day",
    "National Teacher Day",
    "National Nurses Day",
    "Mother's Day",
    "Armed Forces Day (US)",
    "Victoria Day (C)",
    "Memorial Day (US)",
    "Flag Day (US)",
    "Father's Day",
    "Juneteenth",
    "Summer begins",
    "Canada Day (C)",
    "Independence Day (US)",
    "Civic Holiday (C)",
    "Labor Day",
    "National Grandparents Day (US)",
    "Patriot Day (US)",
    "Constitution Day (US)",
    "Rosh Hashanah begins at sundown",
    "Rosh Hashanah",
    "Fall begins",
    "Yom Kippur begins at sundown",
    "Yom Kippur",
    "Columbus Day (US)",
    "Thanksgiving Day (C)",
    "National Bosses Day (US)",
    "United Nations Day (US)",
    "Halloween",
    "Daylight Saving Time ends",
    "Election Day (US)",
    "Remembrance Day (C)",
    "Veterans Day (US)",
    "Thanksgiving Day (US)",
    "Pearl Harbor Remembrance Day (US)",
    "Hanukkah begins at sundown",
    "Hanukkah",
    "Winter begins",
    "Christmas Day",
    "Boxing Day (C)",
    "Kwanzaa begins",
]

import os
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "openai/gpt-4o-mini"
ZOOM_FACTOR = 3.0

BOLD_FONT_KEYWORDS = ["bold", "extrabold", "heavy", "black", "demi", "semibold"]

MONTH_MAP = {m.lower(): i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"], 1)}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

FLEXIBLE_DATE_HOLIDAYS = {
    "Spring begins", "Summer begins", "Fall begins", "Winter begins",
    "First of Ramadan begins at sundown", "First of Ramadan",
    "Eid al Fitr begins at sundown", "Eid al Fitr",
    "Passover begins at sundown", "Passover",
    "Rosh Hashanah begins at sundown", "Rosh Hashanah",
    "Yom Kippur begins at sundown", "Yom Kippur",
    "Hanukkah begins at sundown", "Hanukkah",
    "Holocaust Remembrance Day", "Eastern Orthodox Easter",
    "Eastern Orthodox Lent begins", "Lunar New Year",
}

OBSERVED_SHIFT_HOLIDAYS = {
    "National Bosses Day (US)", "Juneteenth", "Veterans Day (US)",
    "Remembrance Day (C)", "Canada Day (C)", "Christmas Day",
    "New Year's Day", "Independence Day (US)",
}

FLEXIBLE_TOLERANCE = 4
OBSERVED_TOLERANCE = 2

# ======================================================
# ── NEW: DESIGN FAMILY LIBRARY (all calendar design patterns)
# ======================================================
DESIGN_FAMILY_DEFAULTS = {
    "deskpad": {
        "design_type": "deskpad",
        "week_start": "Sunday",
        "num_columns": 7,
        "num_rows": 5,
        "date_rendering_mode": "slash",
        "holiday_label_anchor": "top-left",
        "date_number_anchor": "top-left",
        "grid_style": "lined",
        "has_mini_calendar": False,
        "has_notes_area": False,
    },
    "wall_single": {
        "design_type": "wall_single",
        "week_start": "Sunday",
        "num_columns": 7,
        "num_rows": 6,
        "date_rendering_mode": "single",
        "holiday_label_anchor": "top-left",
        "date_number_anchor": "top-right",
        "grid_style": "bordered",
        "has_mini_calendar": True,
        "has_notes_area": False,
    },
    "wall_three_month": {
        "design_type": "wall_three_month",
        "week_start": "Sunday",
        "num_columns": 7,
        "num_rows": 6,
        "month_count": 3,
        "date_rendering_mode": "single",
        "holiday_label_anchor": "top-left",
        "date_number_anchor": "top-left",
        "grid_style": "minimal",
        "has_mini_calendar": False,
        "has_notes_area": True,
    },
}

# ── Design-type display metadata ──────────────────────────────────────
DESIGN_TYPE_META = {
    "deskpad":           ("📋", "#6f42c1", "Desk Pad"),
    "wall_single":       ("🖼️",  "#0d6efd", "Wall Calendar (Single Month)"),
    "wall_three_month":  ("📅", "#20c997", "Wall Calendar (Three-Month View)"),
    "wall_large_format": ("🗺️",  "#fd7e14", "Wall Calendar (Large Format)"),
    "mini_wall":         ("🗒️",  "#6c757d", "Mini Wall Calendar"),
    "digital":           ("💻", "#17a2b8", "Digital Calendar"),
    "unknown":           ("❓", "#adb5bd", "Unknown Design"),
}
# ──────────────────────────────────────────────────────────────────────
# DESIGN-SPECIFIC EXTRACTION CONFIG
# Controls extraction behaviour per calendar design type.
# ──────────────────────────────────────────────────────────────────────
DESIGN_EXTRACTION_CONFIG: Dict[str, Dict] = {
    "deskpad": {
        "use_bold_rule": True,
        "x_tolerance": 95,
        "row_padding": 18,
        "merge_y_gap": 80,
        "label_size_min": 4,
        "label_size_max": 13,
        "spelling_threshold": 0.75,
    },
    "wall_single": {
        "use_bold_rule": False,
        "x_tolerance": 60,
        "row_padding": 10,
        "merge_y_gap": 45,
        "label_size_min": 5,
        "label_size_max": 11,
        "spelling_threshold": 0.75,
    },
    "wall_three_month": {
        "use_bold_rule": False,
        "x_tolerance": 50,
        "row_padding": 8,
        "merge_y_gap": 35,
        "label_size_min": 5,
        "label_size_max": 10,
        "spelling_threshold": 0.75,
    },
    "unknown": {
        "use_bold_rule": True,
        "x_tolerance": 80,
        "row_padding": 12,
        "merge_y_gap": 65,
        "label_size_min": 4,
        "label_size_max": 14,
        "spelling_threshold": 0.75,
    },
}

def get_design_extraction_config(design_type: str) -> Dict:
    """Return the extraction config for a design type, falling back to 'unknown'."""
    return DESIGN_EXTRACTION_CONFIG.get(design_type, DESIGN_EXTRACTION_CONFIG["unknown"])




# ======================================================
# HELPERS
# ======================================================
def fmt_date(dt: date) -> str:
    return dt.isoformat()

def fmt_datetext(dt: date) -> str:
    return f"{dt.strftime('%a')} {dt.strftime('%b')} {dt.day}"

def day_name(dt: date) -> str:
    return dt.strftime("%a")

def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    count = 0
    for d in range(1, calendar.monthrange(year, month)[1] + 1):
        x = date(year, month, d)
        if x.weekday() == weekday:
            count += 1
            if count == n:
                return x
    raise ValueError("No nth weekday found")

def last_weekday(year: int, month: int, weekday: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    for d in range(last_day, 0, -1):
        x = date(year, month, d)
        if x.weekday() == weekday:
            return x
    raise ValueError("No last weekday found")

def first_weekday_on_or_after(year: int, month: int, day: int, weekday: int) -> date:
    x = date(year, month, day)
    while x.weekday() != weekday:
        x += timedelta(days=1)
    return x

def nearest_weekday_before(year: int, month: int, day: int, weekday: int) -> date:
    x = date(year, month, day)
    while x.weekday() != weekday:
        x -= timedelta(days=1)
    return x

def nearest_observed_weekday(fixed_date: date) -> date:
    dow = fixed_date.weekday()
    if dow == 5:
        return fixed_date - timedelta(days=1)
    elif dow == 6:
        return fixed_date + timedelta(days=1)
    return fixed_date

def add_row(rows: List[Dict], holiday_name: str, dt: date):
    rows.append({
        "year": dt.year,
        "Holiday": holiday_name,
        "day": day_name(dt),
        "datetext": fmt_datetext(dt),
        "date": fmt_date(dt),
        "date_obj": pd.Timestamp(dt),
    })

def period_range(base_year: int, mode: str) -> Tuple[date, date]:
    if mode == "Fiscal":
        return date(base_year, 1, 1), date(base_year, 12, 31)
    elif mode == "Academic":
        return date(base_year, 7, 1), date(base_year + 1, 6, 30)
    raise ValueError("Mode must be Fiscal or Academic")

def years_needed(start_dt: date, end_dt: date) -> List[int]:
    return list(range(start_dt.year, end_dt.year + 1))

def validate_required_libraries():
    missing = []
    if any(h in HOLIDAY_NAMES for h in [
        "First of Ramadan begins at sundown", "First of Ramadan",
        "Eid al Fitr begins at sundown", "Eid al Fitr",
    ]) and not HIJRI_AVAILABLE:
        missing.append("hijridate")
    if any(h in HOLIDAY_NAMES for h in [
        "Passover begins at sundown", "Passover", "Holocaust Remembrance Day",
        "Rosh Hashanah begins at sundown", "Rosh Hashanah",
        "Yom Kippur begins at sundown", "Yom Kippur",
        "Hanukkah begins at sundown", "Hanukkah",
    ]) and not HEBREW_AVAILABLE:
        missing.append("convertdate")
    return missing


# ======================================================
# NORMALIZE UPLOADED EXCEL/CSV → STANDARD FORMAT
# ======================================================
def normalize_uploaded_df(df: pd.DataFrame, fallback_year: int) -> Tuple[pd.DataFrame, bool]:
    try:
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        holiday_col = None
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("holiday", "holiday name", "name", "event", "holiday_name", "holidayname"):
                holiday_col = col
                break
        if holiday_col is None:
            str_cols = [c for c in df.columns if df[c].dtype == object]
            if str_cols:
                holiday_col = max(str_cols, key=lambda c: df[c].astype(str).str.len().mean())
        if holiday_col is None:
            return pd.DataFrame(), False

        date_col = None
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("date", "holiday date", "event date", "date_value", "datevalue", "datetext", "full_date"):
                date_col = col
                break
        if date_col is None:
            for col in df.columns:
                if col == holiday_col:
                    continue
                try:
                    parsed = pd.to_datetime(df[col], errors="coerce")
                    if parsed.notna().sum() > len(df) * 0.5:
                        date_col = col
                        break
                except Exception:
                    pass
        if date_col is None:
            return pd.DataFrame(), False

        df["_date_parsed"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["_date_parsed"]).copy()
        if df.empty:
            return pd.DataFrame(), False

        if (df["_date_parsed"].dt.year == 1900).all() or (df["_date_parsed"].dt.year < 2000).all():
            df["_date_parsed"] = df["_date_parsed"].apply(
                lambda d: d.replace(year=fallback_year) if d.year < 2000 else d
            )

        result = pd.DataFrame()
        result["Holiday"] = df[holiday_col].astype(str).str.strip()
        result["date"] = df["_date_parsed"].dt.strftime("%Y-%m-%d")
        result["year"] = df["_date_parsed"].dt.year
        result["day"] = df["_date_parsed"].dt.strftime("%a")
        result["datetext"] = df["_date_parsed"].apply(
            lambda d: f"{d.strftime('%a')} {d.strftime('%b')} {d.day}"
        )
        result = result[result["Holiday"].str.len() > 0].reset_index(drop=True)
        return result, True

    except Exception:
        return pd.DataFrame(), False


# ======================================================
# SEASONS
# ======================================================
def spring_begins(year: int) -> date: return date(year, 3, 20)
def summer_begins(year: int) -> date: return date(year, 6, 21)
def fall_begins(year: int) -> date:   return date(year, 9, 22)
def winter_begins(year: int) -> date: return date(year, 12, 21)


# ======================================================
# RELIGIOUS CALCULATIONS
# ======================================================
def western_easter_date(year: int) -> date:
    return western_easter(year)

def orthodox_easter_date(year: int) -> Optional[date]:
    if orthodox_easter_raw is None or EASTER_ORTHODOX_METHOD is None:
        return None
    return orthodox_easter_raw(year, method=EASTER_ORTHODOX_METHOD)

def find_hijri_date_in_gregorian_year(gregorian_year: int, hijri_month: int, hijri_day: int) -> Optional[date]:
    if not HIJRI_AVAILABLE:
        return None
    current = date(gregorian_year, 1, 1)
    end = date(gregorian_year, 12, 31)
    while current <= end:
        try:
            h = Gregorian(current.year, current.month, current.day).to_hijri()
            if h.month == hijri_month and h.day == hijri_day:
                return current
        except Exception:
            pass
        current += timedelta(days=1)
    return None

def find_hebrew_date_in_gregorian_year(gregorian_year: int, hebrew_month: int, hebrew_day: int) -> Optional[date]:
    if not HEBREW_AVAILABLE:
        return None
    current = date(gregorian_year, 1, 1)
    end = date(gregorian_year, 12, 31)
    while current <= end:
        try:
            hy, hm, hd = hebrew.from_gregorian(current.year, current.month, current.day)
            if hm == hebrew_month and hd == hebrew_day:
                return current
        except Exception:
            pass
        current += timedelta(days=1)
    return None


# ======================================================
# LUNAR NEW YEAR
# ======================================================
def lunar_new_year_fallback(year: int) -> date:
    known = {
        2020: date(2020, 1, 25), 2021: date(2021, 2, 12), 2022: date(2022, 2, 1),
        2023: date(2023, 1, 22), 2024: date(2024, 2, 10), 2025: date(2025, 1, 29),
        2026: date(2026, 2, 17), 2027: date(2027, 2, 6),  2028: date(2028, 1, 26),
        2029: date(2029, 2, 13), 2030: date(2030, 2, 3),  2031: date(2031, 1, 23),
        2032: date(2032, 2, 11), 2033: date(2033, 1, 31), 2034: date(2034, 2, 19),
        2035: date(2035, 2, 8),  2036: date(2036, 1, 28), 2037: date(2037, 2, 15),
        2038: date(2038, 2, 4),  2039: date(2039, 1, 24), 2040: date(2040, 2, 12),
    }
    return known.get(year, date(year, 2, 1))


# ======================================================
# HOLIDAY ENGINE
# ======================================================
def build_exact_holidays_for_year(year: int) -> pd.DataFrame:
    rows: List[Dict] = []

    add_row(rows, "New Year's Day", date(year, 1, 1))
    add_row(rows, "Groundhog Day", date(year, 2, 2))
    add_row(rows, "Lincoln's Birthday (US)", date(year, 2, 12))
    add_row(rows, "Valentine's Day", date(year, 2, 14))
    add_row(rows, "St. Patrick's Day", date(year, 3, 17))
    add_row(rows, "Earth Day", date(year, 4, 22))
    add_row(rows, "National Nurses Day", date(year, 5, 6))
    add_row(rows, "Flag Day (US)", date(year, 6, 14))
    add_row(rows, "Juneteenth", date(year, 6, 19))
    add_row(rows, "Canada Day (C)", date(year, 7, 1))
    add_row(rows, "Independence Day (US)", date(year, 7, 4))
    add_row(rows, "Patriot Day (US)", date(year, 9, 11))
    add_row(rows, "Constitution Day (US)", date(year, 9, 17))

    bosses_raw = date(year, 10, 16)
    bosses_observed = nearest_observed_weekday(bosses_raw)
    add_row(rows, "National Bosses Day (US)", bosses_observed)

    add_row(rows, "United Nations Day (US)", date(year, 10, 24))
    add_row(rows, "Halloween", date(year, 10, 31))
    add_row(rows, "Remembrance Day (C)", date(year, 11, 11))
    add_row(rows, "Veterans Day (US)", date(year, 11, 11))
    add_row(rows, "Pearl Harbor Remembrance Day (US)", date(year, 12, 7))
    add_row(rows, "Christmas Day", date(year, 12, 25))
    add_row(rows, "Boxing Day (C)", date(year, 12, 26))
    add_row(rows, "Kwanzaa begins", date(year, 12, 26))

    add_row(rows, "Martin Luther King, Jr. Day (US)", nth_weekday(year, 1, 0, 3))
    add_row(rows, "Presidents' Day (US)", nth_weekday(year, 2, 0, 3))
    add_row(rows, "Washington's Birthday (US)", date(year, 2, 22))
    add_row(rows, "Mother's Day", nth_weekday(year, 5, 6, 2))
    add_row(rows, "Armed Forces Day (US)", nth_weekday(year, 5, 5, 3))
    add_row(rows, "Memorial Day (US)", last_weekday(year, 5, 0))
    add_row(rows, "Father's Day", nth_weekday(year, 6, 6, 3))
    add_row(rows, "Labor Day", nth_weekday(year, 9, 0, 1))
    add_row(rows, "National Grandparents Day (US)", first_weekday_on_or_after(year, 9, 7, 6))
    add_row(rows, "Columbus Day (US)", nth_weekday(year, 10, 0, 2))
    add_row(rows, "Election Day (US)", first_weekday_on_or_after(year, 11, 2, 1))
    add_row(rows, "Thanksgiving Day (US)", nth_weekday(year, 11, 3, 4))

    add_row(rows, "Victoria Day (C)", nearest_weekday_before(year, 5, 24, 0))
    add_row(rows, "Civic Holiday (C)", nth_weekday(year, 8, 0, 1))
    add_row(rows, "Thanksgiving Day (C)", nth_weekday(year, 10, 0, 2))
    add_row(rows, "Easter Monday (C)", western_easter_date(year) + timedelta(days=1))

    add_row(rows, "Daylight Saving Time begins", nth_weekday(year, 3, 6, 2))
    add_row(rows, "Daylight Saving Time ends", nth_weekday(year, 11, 6, 1))

    easter_dt = western_easter_date(year)
    add_row(rows, "Ash Wednesday", easter_dt - timedelta(days=46))
    add_row(rows, "Palm Sunday", easter_dt - timedelta(days=7))
    add_row(rows, "Good Friday", easter_dt - timedelta(days=2))
    add_row(rows, "Easter", easter_dt)

    orthodox_dt = orthodox_easter_date(year)
    if orthodox_dt:
        add_row(rows, "Eastern Orthodox Easter", orthodox_dt)
        add_row(rows, "Eastern Orthodox Lent begins", orthodox_dt - timedelta(days=48))

    add_row(rows, "Spring begins", spring_begins(year))
    add_row(rows, "Summer begins", summer_begins(year))
    add_row(rows, "Fall begins", fall_begins(year))
    add_row(rows, "Winter begins", winter_begins(year))

    ramadan_start = find_hijri_date_in_gregorian_year(year, 9, 1)
    if ramadan_start:
        add_row(rows, "First of Ramadan", ramadan_start)
        add_row(rows, "First of Ramadan begins at sundown", ramadan_start - timedelta(days=1))

    eid_al_fitr = find_hijri_date_in_gregorian_year(year, 10, 1)
    if eid_al_fitr:
        add_row(rows, "Eid al Fitr", eid_al_fitr)
        add_row(rows, "Eid al Fitr begins at sundown", eid_al_fitr - timedelta(days=1))

    passover = find_hebrew_date_in_gregorian_year(year, 1, 15)
    if passover:
        add_row(rows, "Passover", passover)
        add_row(rows, "Passover begins at sundown", passover - timedelta(days=1))

    rosh_hashanah = find_hebrew_date_in_gregorian_year(year, 7, 1)
    if rosh_hashanah:
        add_row(rows, "Rosh Hashanah", rosh_hashanah)
        add_row(rows, "Rosh Hashanah begins at sundown", rosh_hashanah - timedelta(days=1))

    yom_kippur = find_hebrew_date_in_gregorian_year(year, 7, 10)
    if yom_kippur:
        add_row(rows, "Yom Kippur", yom_kippur)
        add_row(rows, "Yom Kippur begins at sundown", yom_kippur - timedelta(days=1))

    hanukkah = find_hebrew_date_in_gregorian_year(year, 9, 25)
    if hanukkah:
        add_row(rows, "Hanukkah", hanukkah)
        add_row(rows, "Hanukkah begins at sundown", hanukkah - timedelta(days=1))

    yom_hashoah = find_hebrew_date_in_gregorian_year(year, 1, 27)
    if yom_hashoah:
        add_row(rows, "Holocaust Remembrance Day", yom_hashoah)

    add_row(rows, "Administrative Professionals Day", nth_weekday(year, 4, 2, 4))
    add_row(rows, "National Teacher Day", nth_weekday(year, 5, 1, 1))
    add_row(rows, "Lunar New Year", lunar_new_year_fallback(year))

    df = pd.DataFrame(rows)
    order_map = {name: i for i, name in enumerate(HOLIDAY_NAMES)}
    df = df[df["Holiday"].isin(HOLIDAY_NAMES)].copy()
    df["order_key"] = df["Holiday"].map(order_map)
    df = df.sort_values(["date_obj", "order_key"]).drop_duplicates(subset=["Holiday", "date"], keep="first")
    return df.sort_values(["date_obj", "order_key"]).reset_index(drop=True)


def build_report(base_year: int, mode: str) -> pd.DataFrame:
    start_dt, end_dt = period_range(base_year, mode)
    yrs = years_needed(start_dt, end_dt)
    frames = [build_exact_holidays_for_year(y) for y in yrs]
    df = pd.concat(frames, ignore_index=True)
    df = df[(df["date_obj"].dt.date >= start_dt) & (df["date_obj"].dt.date <= end_dt)].copy()
    order_map = {name: i for i, name in enumerate(HOLIDAY_NAMES)}
    df["order_key"] = df["Holiday"].map(order_map)
    df = df.sort_values(["date_obj", "order_key"]).reset_index(drop=True)
    return df[REQUIRED_COLUMNS].copy()


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Holiday Report")
        ws = writer.book["Holiday Report"]
        ws.freeze_panes = "A2"
        for col in ws.columns:
            col_letter = col[0].column_letter
            max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
            ws.column_dimensions[col_letter].width = min(max_len + 2, 30)
    return bio.getvalue()


# =========================================
# AI NOTE GENERATOR FOR WRONG DATES
# =========================================

def _rule_based_wrong_date_note(holiday_name, expected_date, found_day, found_label):
    expected_ts = pd.Timestamp(expected_date)
    expected_day = expected_ts.day
    diff = found_day - expected_day
    h_lower = holiday_name.lower()
    if "bosses" in h_lower:
        raw = date(expected_ts.year, 10, 16)
        obs = nearest_observed_weekday(raw)
        if obs.day != expected_day:
            return f"Oct 16 falls on {raw.strftime('%A')}; observed on {obs.strftime('%A %b')} {obs.day}. PDF shows day {found_day} — needs review."
        return f"National Bosses Day should be {expected_day} (observed). PDF shows {found_day} — needs review."
    if any(k in h_lower for k in ["ramadan", "eid", "passover", "rosh", "yom", "hanukkah", "lunar"]):
        return f"Lunar/religious calendar variation: expected day {expected_day}, PDF shows day {found_day} (diff {diff:+d}). Manual verification recommended."
    if any(k in h_lower for k in ["spring", "summer", "fall", "winter"]):
        return f"Astronomical season date varies ±1–2 days by year. Expected day {expected_day}, PDF shows {found_day}. Verify against almanac."
    if abs(diff) == 1:
        return f"Off by 1 day — possible weekend observation shift or timezone boundary. Expected {expected_day}, found {found_day}. Needs review."
    return f"Date mismatch: expected day {expected_day}, PDF shows day {found_day} (diff {diff:+d}). Possible calendar design or data entry error. Needs review."


def get_ai_notes_batch(wrong_date_items: List[Dict]) -> Dict[int, str]:
    if not wrong_date_items:
        return {}
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        return {i: _rule_based_wrong_date_note(item["holiday_name"], item["expected_date"], item["found_day"], item["found_label"]) for i, item in enumerate(wrong_date_items)}
    lines = []
    for i, item in enumerate(wrong_date_items):
        expected_ts = pd.Timestamp(item["expected_date"])
        lines.append(f'{i}. Holiday="{item["holiday_name"]}", ExpectedDate={expected_ts.strftime("%A %B %d %Y")}, PDFLabel="{item["found_label"]}", PDFDay={item["found_day"]}')
    prompt = (
        "You are a calendar accuracy expert.\n"
        "For each numbered holiday below, write ONE concise sentence (max 25 words) explaining the most likely reason the date in the PDF differs from the expected date.\n"
        "Consider: weekend observation rules (Sat→Fri, Sun→Mon), leap years, astronomical/lunar/Hebrew calendar variation, or design errors.\n"
        "Reply ONLY as a JSON object: {\"0\": \"...\", \"1\": \"...\", ...}\n\n"
        + "\n".join(lines)
    )
    try:
        payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 60 * len(wrong_date_items) + 50}
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=60)
        data = response.json()
        if response.status_code == 200:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = " ".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
            content = str(content).strip()
            start = content.find("{"); end = content.rfind("}") + 1
            if start != -1 and end > start:
                parsed = json.loads(content[start:end])
                return {int(k): str(v).strip() for k, v in parsed.items()}
    except Exception:
        pass
    return {i: _rule_based_wrong_date_note(item["holiday_name"], item["expected_date"], item["found_day"], item["found_label"]) for i, item in enumerate(wrong_date_items)}


def get_ai_unexpected_notes_batch(unexpected_items: List[Dict]) -> Dict[int, str]:
    if not unexpected_items:
        return {}
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        return {i: f"Not in expected list. PDF label: \"{item['found_label']}\" on day {item['day']}. Manually verify if this is a legitimate holiday." for i, item in enumerate(unexpected_items)}
    lines = [f'{i}. Label="{item["found_label"]}", Day={item["day"]}' for i, item in enumerate(unexpected_items)]
    prompt = (
        "You are a calendar accuracy expert reviewing holiday labels found in a printed calendar PDF that were NOT in the expected holiday list.\n\n"
        "For each numbered label below, answer in ONE sentence (max 30 words):\n"
        "  - Is this a real, recognized holiday? (Yes/No)\n"
        "  - If yes: name it and briefly explain why it may have been missed from the list.\n"
        "  - If no: state it is likely a false positive, misread text, or design element.\n\n"
        "Reply ONLY as a JSON object: {\"0\": \"...\", \"1\": \"...\", ...}\n\n"
        + "\n".join(lines)
    )
    try:
        payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 70 * len(unexpected_items) + 60}
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=60)
        data = response.json()
        if response.status_code == 200:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = " ".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
            content = str(content).strip()
            start = content.find("{"); end = content.rfind("}") + 1
            if start != -1 and end > start:
                parsed = json.loads(content[start:end])
                return {int(k): str(v).strip() for k, v in parsed.items()}
    except Exception:
        pass
    return {i: f"Not in expected list. PDF label: \"{item['found_label']}\" on day {item['day']}. Manually verify if this is a legitimate holiday." for i, item in enumerate(unexpected_items)}


# =========================================
# AI PDF PROCESSING - NATIVE EXTRACTION
# =========================================

def is_bold_span(span: Dict) -> bool:
    flags = span.get("flags", 0)
    font = span.get("font", "").lower()
    return bool(flags & 16) or any(kw in font for kw in BOLD_FONT_KEYWORDS)


def split_holidays(text: str) -> List[str]:
    """
    Split a text string that may contain multiple holiday labels.
    Works regardless of PDF design/layout pattern.
    KEY RULES:
    - Does NOT split on spaces or uppercase transitions (preserves multi-word names).
    - Splits on commas, slashes, pipes, bullets, newlines, semicolons, tabs, and
      double-spaces (common in PDF extractions where layout gaps become spaces).
    - Tries to re-join adjacent comma-parts that together form a known canonical
      holiday name (e.g. "Martin Luther King, Jr. Day (US)" stays intact).
    - Returns each discovered holiday label as a separate string.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # Normalise common PDF encoding artefacts
    text = text.replace("\u00a0", " ").replace("\u2022", "\u2022").replace("\uf0b7", "\u2022")

    _pre_norm = normalize_holiday(text)
    for _name in HOLIDAY_NAMES:
        if normalize_holiday(_name) == _pre_norm:
            return [re.sub(r"\s+", " ", text).strip()]

    text = re.sub(r"\t+", "\n", text)
    text = re.sub(r"  +", "\n", text)

    norm_text = normalize_holiday(text)
    for name in HOLIDAY_NAMES:
        if normalize_holiday(name) == norm_text:
            return [re.sub(r"\s+", " ", text).strip()]

    raw_parts = re.split(r"\s*(?:,|/|\||\u2022|\n|;)\s*", text)
    raw_parts = [p.strip() for p in raw_parts if p.strip()]

    if len(raw_parts) == 1:
        for name in HOLIDAY_NAMES:
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            if pattern.search(raw_parts[0]) and normalize_holiday(name) != normalize_holiday(raw_parts[0]):
                remainder = pattern.sub("\n", raw_parts[0]).strip()
                parts2 = [name] + [p.strip() for p in remainder.split("\n") if p.strip() and len(p.strip()) >= 3]
                if len(parts2) > 1:
                    return parts2
        return [re.sub(r'\s+', ' ', text).strip()] if len(text) >= 3 else []

    merged: List[str] = []
    i = 0
    while i < len(raw_parts):
        if not raw_parts[i]:
            i += 1
            continue
        best_j = None
        for j in range(len(raw_parts), i, -1):
            candidate = ", ".join(raw_parts[i:j])
            if any(normalize_holiday(candidate) == normalize_holiday(name) for name in HOLIDAY_NAMES):
                best_j = j
                break
        if best_j is not None:
            merged.append(", ".join(raw_parts[i:best_j]))
            i = best_j
        else:
            if len(raw_parts[i]) >= 3:
                merged.append(raw_parts[i])
            i += 1

    return merged if merged else [text]


def detect_font_size_ranges(page) -> Tuple[float, float, float, float]:
    all_sizes = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text and len(text) <= 40:
                    all_sizes.append(span["size"])
    if not all_sizes:
        return 14.0, 5.0, 14.0, 4.0
    all_sizes.sort()
    max_sz = max(all_sizes)
    date_min = max(12.0, max_sz * 0.55)
    label_max = date_min - 0.5
    label_min = max(4.0, min(all_sizes) + 0.5) if len(all_sizes) > 5 else 4.0
    return date_min, label_min, label_max, 4.0


def extract_calendar_grid(page) -> Tuple[List[Dict], List[Dict]]:
    """
    Extracts date numbers and holiday labels from a calendar page.
    IMPORTANT: date numbers that are NOT bold are prev/next month spillover dates —
    they and any associated holiday labels should be IGNORED in all analysis.
    Returns (large_dates, holiday_labels) where each large_date has a 'bold' flag.
    """
    SKIP_WORDS = {
        'S', 'M', 'T', 'W', 'F',
        'Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa',
        'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat',
        'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December',
        'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
        'Holiday', 'Holidays', 'Notes', 'Important', 'Events',
        'Calendar', 'Month', 'Year',
    }
    date_min_sz, label_min_sz, label_max_sz, _ = detect_font_size_ranges(page)
    large_dates: List[Dict] = []
    holiday_labels: List[Dict] = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                raw = span["text"]
                text = raw.strip()
                if not text:
                    continue
                sz = span["size"]
                bold = is_bold_span(span)
                bbox = span["bbox"]
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                is_date_sized = sz >= date_min_sz
                is_bold_date = bold and sz >= 8.0
                if (is_date_sized or is_bold_date) and re.match(r'^\d{1,2}$', text):
                    day = int(text)
                    if 1 <= day <= 31:
                        large_dates.append({
                            "day": day,
                            "x": cx,
                            "y": cy,
                            "y0": bbox[1],
                            "y1": bbox[3],
                            "bbox": bbox,
                            "size": sz,
                            "bold": bold,
                        })
                    continue
                in_adaptive_range = label_min_sz <= sz <= label_max_sz
                in_fallback_range = 4.0 <= sz <= 14.0
                if not (in_adaptive_range or in_fallback_range):
                    continue
                if re.match(r'^[\d/\s\t]+$', text):
                    continue
                if text in SKIP_WORDS:
                    continue
                if len(text) < 3:
                    continue
                _FRAG_SKIP = {
                    'day', 'days', 'day us', 'day c', 'jr', 'jr day us',
                    'at', 'starts', 'end', 'ends',
                    'observed',
                    'us', 'c', 'am', 'pm',
                }
                _norm_for_frag = re.sub(r"[^a-z0-9 ]", " ", text.lower().strip())
                _norm_for_frag = re.sub(r"\s+", " ", _norm_for_frag).strip()
                if _norm_for_frag in _FRAG_SKIP:
                    continue
                if re.match(r'^\d+\.?\d*\s*(in|cm|mm|pt)\b', text, re.IGNORECASE):
                    continue
                clean = re.sub(r'[\d\s/\t]', '', text)
                if len(clean) < 3:
                    continue
                sub_parts = split_holidays(text)
                for part in sub_parts:
                    holiday_labels.append({"text": part, "x": cx, "y": cy, "y0": bbox[1], "y1": bbox[3], "bbox": bbox})
    if large_dates:
        deduped = {}
        for d in large_dates:
            key = (d["day"], round(d["x"] / 10), round(d["y0"] / 10))
            if key not in deduped or d["bold"]:
                deduped[key] = d
        large_dates = list(deduped.values())
    return large_dates, holiday_labels


def detect_page_month(page, large_dates: List[Dict]) -> Optional[int]:
    """Legacy wrapper — returns only month. Use detect_page_month_year_strict for new code."""
    month, _ = detect_page_month_year_strict(page, large_dates)
    return month


def detect_page_month_year_strict(page, large_dates: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
    """
    Detect the main month/year of the page using only large header text
    above the main date grid. Ignores small reference calendars and
    any text that sits at or below the grid.
    Returns (month_number, year_int) — either may be None.
    """
    if not large_dates:
        return None, None

    grid_top = min(d["y0"] for d in large_dates)
    candidates = []

    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            line_text = " ".join(span["text"].strip() for span in line["spans"]).strip()
            if not line_text:
                continue

            ys = [span["bbox"][1] for span in line["spans"]]
            y = min(ys)
            max_size = max(span["size"] for span in line["spans"])

            if y > grid_top - 10:
                continue
            if max_size < 12:
                continue

            low = line_text.lower()
            found_month = None
            for mname, mnum in MONTH_MAP.items():
                if re.search(rf"\b{re.escape(mname)}\b", low):
                    found_month = mnum
                    break

            if found_month:
                year_match = re.search(r"\b(20\d{2})\b", line_text)
                found_year = int(year_match.group(1)) if year_match else None
                score = max_size * 10 - abs(grid_top - y)
                candidates.append((score, found_month, found_year, line_text))

    if not candidates:
        return None, None

    candidates.sort(reverse=True)
    _, month, year, _ = candidates[0]
    return month, year


def detect_page_year(page) -> Optional[int]:
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                m = re.search(r'\b(20\d{2})\b', span["text"])
                if m:
                    return int(m.group(1))
    return None


def repair_page_month_sequence(page_meta: List[Dict]) -> List[Dict]:
    """
    Given a list of page metadata dicts (each with 'page', 'month', 'year'),
    fill missing months by interpolating from neighbours and fix obvious
    sequence jumps so every page gets a correct month assignment.
    """
    if not page_meta:
        return page_meta

    for i in range(len(page_meta)):
        if page_meta[i]["month"] is None:
            prev_month = page_meta[i - 1]["month"] if i > 0 else None
            next_month = None
            for j in range(i + 1, len(page_meta)):
                if page_meta[j]["month"] is not None:
                    next_month = page_meta[j]["month"]
                    break

            if prev_month:
                expected = 1 if prev_month == 12 else prev_month + 1
                page_meta[i]["month"] = expected
            elif next_month:
                page_meta[i]["month"] = next_month

    for i in range(1, len(page_meta)):
        pm = page_meta[i - 1]["month"]
        cm = page_meta[i]["month"]
        if pm is None or cm is None:
            continue
        expected = 1 if pm == 12 else pm + 1
        if cm != expected and abs(cm - expected) > 1:
            page_meta[i]["month"] = expected

    for i in range(1, len(page_meta)):
        prev = page_meta[i - 1]
        curr = page_meta[i]
        if prev["month"] == 12 and curr["month"] == 1:
            if prev["year"] is not None:
                curr["year"] = prev["year"] + 1
        elif curr["year"] is None and prev["year"] is not None:
            curr["year"] = prev["year"]

    return page_meta


def match_holidays_to_dates(
    holiday_labels: List[Dict],
    large_dates: List[Dict],
    x_tolerance: float = 80.0,
) -> List[Dict]:
    """
    Match holiday labels to date numbers.
    CRITICAL: Only matches labels to BOLD dates (current month).
    Unbold dates are prev/next month spillover dates — ignored completely.
    """
    if not large_dates or not holiday_labels:
        return []

    bold_dates = [d for d in large_dates if d.get("bold", True)]
    if not bold_dates:
        bold_dates = large_dates

    col_map: Dict[float, List[Dict]] = {}
    for d in bold_dates:
        placed = False
        for cx in list(col_map.keys()):
            if abs(d["x"] - cx) <= x_tolerance:
                col_map[cx].append(d)
                placed = True
                break
        if not placed:
            col_map[d["x"]] = [d]

    for cx in col_map:
        col_map[cx].sort(key=lambda d: d["y0"])

    results = []
    for hl in holiday_labels:
        best_cx = None
        best_dist = float("inf")
        for cx in col_map:
            dist = abs(hl["x"] - cx)
            if dist < best_dist:
                best_dist = dist
                best_cx = cx
        if best_cx is None or best_dist > x_tolerance * 1.5:
            continue
        col_dates = col_map[best_cx]
        matched_day = None
        MARGIN = 10
        for i, d in enumerate(col_dates):
            row_top = d["y0"] - MARGIN
            row_bot = col_dates[i + 1]["y0"] if i + 1 < len(col_dates) else d["y0"] + 120
            if row_top <= hl["y"] <= row_bot:
                matched_day = d["day"]
                break
        if matched_day is None:
            closest = min(col_dates, key=lambda d: abs(hl["y"] - d["y"]))
            if abs(hl["y"] - closest["y"]) < 400:
                matched_day = closest["day"]
        if matched_day is not None:
            results.append({"holiday": hl["text"], "day": matched_day})
    return results


def match_holidays_to_dates_strict(
    holiday_labels: List[Dict],
    large_dates: List[Dict],
    x_tolerance: float = 70.0,
    row_padding: float = 12.0,
) -> List[Dict]:
    """
    Strict version: matches holiday labels only to BOLD current-month date cells,
    using column clustering and precise row-band containment.
    """
    bold_dates = [d for d in large_dates if d.get("bold", False)]
    if not bold_dates:
        bold_dates = large_dates

    bold_dates = sorted(bold_dates, key=lambda d: (round(d["x"] / 20), d["y0"]))

    columns: List[Dict] = []
    for d in bold_dates:
        placed = False
        for col in columns:
            if abs(col["x"] - d["x"]) <= x_tolerance:
                col["dates"].append(d)
                col["x"] = sum(x["x"] for x in col["dates"]) / len(col["dates"])
                placed = True
                break
        if not placed:
            columns.append({"x": d["x"], "dates": [d]})

    for col in columns:
        col["dates"].sort(key=lambda z: z["y0"])

    out = []
    for hl in holiday_labels:
        if not columns:
            break
        best_col = min(columns, key=lambda c: abs(c["x"] - hl["x"]))
        if abs(best_col["x"] - hl["x"]) > x_tolerance * 1.5:
            continue

        dates = best_col["dates"]
        for i, d in enumerate(dates):
            row_top = d["y0"] - row_padding
            row_bottom = (
                dates[i + 1]["y0"] - row_padding
                if i + 1 < len(dates)
                else d["y1"] + 110
            )
            if row_top <= hl["y"] <= row_bottom:
                out.append({"holiday": hl["text"], "day": d["day"]})
                break
    return out


def merge_split_holiday_labels(
    holiday_labels: List[Dict],
    x_tolerance: float = 85.0,
    max_y_gap: float = 65.0,
) -> List[Dict]:
    """
    Merge adjacent text fragments from the same PDF cell column that together
    form a single canonical holiday name split across two (or more) visual lines.

    For example, a PDF may print:
        Line 1: "Martin Luther King,"
        Line 2: "Jr. Day (US)"
    or
        Line 1: "Lincoln's"
        Line 2: "Birthday (US)"

    Without this merge step the fragments are matched individually and flagged
    as Wording/Spelling Mistakes.  This function detects those cases and replaces
    the fragments with the full canonical name so they match correctly.
    """
    if not holiday_labels:
        return holiday_labels

    # Sort by column x then y
    labels = sorted(holiday_labels, key=lambda l: (round(l["x"] / 15), l["y"]))

    # Group into columns
    columns: List[List[Dict]] = []
    for lbl in labels:
        placed = False
        for col in columns:
            if abs(col[0]["x"] - lbl["x"]) <= x_tolerance:
                col.append(lbl)
                placed = True
                break
        if not placed:
            columns.append([lbl])

    merged_labels: List[Dict] = []
    for col in columns:
        col_sorted = sorted(col, key=lambda l: l["y"])
        used = [False] * len(col_sorted)

        for i in range(len(col_sorted)):
            if used[i]:
                continue

            best_merge_name: Optional[str] = None
            best_j = i

            # Try merging with the next 1-3 labels in the same column/cell
            for j in range(i + 1, min(i + 4, len(col_sorted))):
                if used[j]:
                    break
                # Only merge if they are vertically close (within the same cell)
                if col_sorted[j]["y"] - col_sorted[i]["y"] > max_y_gap:
                    break

                parts = [col_sorted[k]["text"] for k in range(i, j + 1)]

                # Try several joining strategies
                join_candidates = [
                    " ".join(parts),
                    ", ".join(parts),
                ]
                # Also try removing trailing comma from all-but-last part then joining
                stripped = [p.rstrip(",").rstrip() for p in parts[:-1]] + [parts[-1]]
                join_candidates.append(", ".join(stripped))
                join_candidates.append(" ".join(stripped))

                for candidate in join_candidates:
                    norm_cand = normalize_holiday(candidate)
                    for name in HOLIDAY_NAMES:
                        if normalize_holiday(name) == norm_cand:
                            best_merge_name = name
                            best_j = j
                            break
                    if best_merge_name:
                        break
                if best_merge_name:
                    break

            if best_merge_name:
                merged_labels.append({
                    "text": best_merge_name,
                    "x": col_sorted[i]["x"],
                    "y": col_sorted[i]["y"],
                    "y0": col_sorted[i]["y0"],
                    "y1": col_sorted[best_j]["y1"],
                    "bbox": col_sorted[i]["bbox"],
                })
                for k in range(i, best_j + 1):
                    used[k] = True
            else:
                merged_labels.append(col_sorted[i])
                used[i] = True

    return merged_labels


def extract_holidays_from_page_native(
    pdf_bytes: bytes,
    page_num: int,
    fallback_year: Optional[int] = None,
    page_meta: Optional[Dict] = None,
) -> List[Dict]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    large_dates, holiday_labels = extract_calendar_grid(page)
    if not large_dates or not holiday_labels:
        return []
    # Merge multi-line holiday name fragments (e.g. "Martin Luther King," / "Jr. Day (US)")
    holiday_labels = merge_split_holiday_labels(holiday_labels)

    if page_meta is not None:
        page_month = page_meta.get("month")
        page_year = page_meta.get("year") or fallback_year
    else:
        page_month, page_year = detect_page_month_year_strict(page, large_dates)
        page_year = page_year or fallback_year

    matched_strict = match_holidays_to_dates_strict(holiday_labels, large_dates)
    matched_regular = match_holidays_to_dates(holiday_labels, large_dates)

    seen_match_keys: set = set()
    matched: List[Dict] = []
    for m in matched_strict + matched_regular:
        mk = (m["holiday"].strip().lower(), m["day"])
        if mk not in seen_match_keys:
            seen_match_keys.add(mk)
            matched.append(m)

    return [
        {
            "holiday": m["holiday"],
            "date": m["day"],
            "month": page_month,
            "year": page_year,
            "page": page_num + 1,
            "source": "native",
        }
        for m in matched
    ]


# =========================================
# AI PDF PROCESSING - LLM VISION
# =========================================

def render_pdf_page(pdf_bytes, page_number):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number]
    mat = fitz.Matrix(ZOOM_FACTOR, ZOOM_FACTOR)
    pix = page.get_pixmap(matrix=mat)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def image_to_base64(img):
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def extract_json_array(text: str):
    if not text:
        return []
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("["); end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return []

def extract_json_object(text: str) -> Optional[Dict]:
    """Extract a JSON object from raw LLM text."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{"); end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            pass
    return None

def ask_ai(image_base64: str) -> str:
    prompt = """You are a calendar QA validator inspecting a printed desk-pad or wall calendar page.
TASK: Extract every HOLIDAY NAME that is printed as a text label inside a date cell of the MAIN (current) month only.
RULES:
- A holiday label is small descriptive text (like "New Year's Day", "Valentine's Day") inside a date cell.
- Do NOT extract the large bold date numbers (1, 2, 3 … 31).
- Do NOT extract day-of-week headers (Sunday, Monday, etc.).
- Do NOT extract reference-calendar grids (small month grids at top/side).
- IMPORTANT: Do NOT extract holidays from date cells that are GREYED OUT, lighter in color, or smaller — those are previous/next month dates and must be ignored.
- Only extract holidays for the BOLD, full-size date cells belonging to the main displayed month.
- Use the EXACT full text printed on the page for the holiday name (preserve original casing and spelling — even if misspelled).
- For "date" field: use the day number of the date cell containing the holiday.
- For "month": use the full month name of the main large calendar shown.
- For "year": use the 4-digit year shown (or null if not visible).
- If multiple holidays appear in the same date cell, return each as a SEPARATE JSON object.

OUTPUT ONLY valid JSON array, no commentary:
[
  {"holiday": "New Year's Day", "date": 1, "month": "January", "year": 2026},
  {"holiday": "Groundhog Day",  "date": 2, "month": "February", "year": 2026}
]"""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
        ]}],
        "temperature": 0, "max_tokens": 1500,
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=120
    )
    try:
        data = response.json()
    except Exception:
        raise RuntimeError(f"OpenRouter returned non-JSON response: {response.text[:500]}")
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter API error ({response.status_code}): {data.get('error', data)}")
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"OpenRouter response missing 'choices': {data}")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        content = "\n".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected response content format: {content}")
    return content


def extract_holidays_from_page_llm(pdf_bytes: bytes, page_num: int) -> List[Dict]:
    img = render_pdf_page(pdf_bytes, page_num)
    b64 = image_to_base64(img)
    result = ask_ai(b64)
    raw = extract_json_array(result)
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        holiday = str(item.get("holiday", "")).strip()
        day = item.get("date")
        month_raw = item.get("month")
        year_raw = item.get("year")
        if not holiday or not day:
            continue
        month_num = None
        if isinstance(month_raw, str):
            month_num = MONTH_MAP.get(month_raw.strip().lower())
        elif isinstance(month_raw, int):
            month_num = month_raw
        year_int = None
        if isinstance(year_raw, int):
            year_int = year_raw
        elif isinstance(year_raw, str):
            m = re.search(r'(20\d{2})', year_raw)
            if m:
                year_int = int(m.group(1))
        for part in split_holidays(holiday):
            out.append({
                "holiday": part,
                "date": int(day),
                "month": month_num,
                "year": year_int,
                "page": page_num + 1,
                "source": "llm",
            })
    return out


# =========================================
# FUZZY HOLIDAY NAME MATCHING
# =========================================

def normalize_holiday(name: str) -> str:
    s = name.lower()
    s = re.sub(r"['''\u2018\u2019]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_exact_name_match(raw: str, canonical: str) -> bool:
    return normalize_holiday(raw) == normalize_holiday(canonical)


def make_spelling_diff(wrong: str, correct: str) -> str:
    import difflib as _dl
    matcher = _dl.SequenceMatcher(None, wrong, correct)
    missing_chars, extra_chars = [], []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "delete":
            extra_chars.append(wrong[i1:i2])
        elif op == "insert":
            missing_chars.append(correct[j1:j2])
        elif op == "replace":
            extra_chars.append(wrong[i1:i2])
            missing_chars.append(correct[j1:j2])
    parts = []
    if missing_chars:
        parts.append(f"missing: '{' '.join(missing_chars)}'")
    if extra_chars:
        parts.append(f"extra: '{' '.join(extra_chars)}'")
    diff_note = f"  [{', '.join(parts)}]" if parts else ""
    return f"PDF: '{wrong}' → Correct: '{correct}'{diff_note}"


def fuzzy_match_holiday(raw_name: str, known_names: List[str], threshold: float = 0.40) -> Optional[str]:
    norm_raw = normalize_holiday(raw_name)

    if len(norm_raw) < 5:
        return None
    _NEVER_MATCH_FRAGMENTS = {
        'day', 'days', 'day us', 'day c', 'begins', 'sundown', 'at',
        'ends', 'end', 'starts', 'observed', 'begins at', 'at sundown',
        'begins at sundown', 'jr', 'jr day us', 'us', 'c',
    }
    if norm_raw in _NEVER_MATCH_FRAGMENTS:
        return None

    _MONTH_NAMES_EXACT = {
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    }
    if norm_raw in _MONTH_NAMES_EXACT:
        return None

    best_name = None
    best_ratio = 0.0
    for known in known_names:
        norm_known = normalize_holiday(known)
        ratio = difflib.SequenceMatcher(None, norm_raw, norm_known).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_name = known
    if best_ratio >= threshold:
        return best_name
    for known in known_names:
        norm_known = normalize_holiday(known)
        if norm_raw in norm_known or norm_known in norm_raw:
            return known
    raw_tokens = set(norm_raw.split())
    best_overlap_name = None
    best_overlap = 0.0
    for known in known_names:
        known_tokens = set(normalize_holiday(known).split())
        overlap = len(raw_tokens & known_tokens)
        total = len(raw_tokens | known_tokens)
        if total > 0 and overlap / total > best_overlap and overlap >= 2:
            best_overlap = overlap / total
            best_overlap_name = known
    if best_overlap_name:
        return best_overlap_name
    return None


# =========================================
# LangChain LLM Initialization
# =========================================

@st.cache_resource(show_spinner=False)
def get_langchain_llm():
    if not LANGCHAIN_AVAILABLE or not OPENROUTER_API_KEY:
        return None
    try:
        llm = ChatOpenAI(
            model=MODEL,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=0,
            max_tokens=2000,
        )
        return llm
    except Exception:
        return None


# =========================================
# RAG: Holiday Knowledge Base
# =========================================

def build_holiday_rag_context() -> str:
    lines = ["CANONICAL HOLIDAY NAME KNOWLEDGE BASE (use as ground truth for spelling/naming):"]
    for i, name in enumerate(HOLIDAY_NAMES, 1):
        lines.append(f"  {i:02d}. {name}")
    return "\n".join(lines)

HOLIDAY_RAG_CONTEXT = build_holiday_rag_context()


# =========================================
# Excel AI Analyzer (LangChain)
# =========================================

def analyze_excel_with_langchain(df: pd.DataFrame, llm) -> Dict[str, Any]:
    fallback = {
        "detected_year": None,
        "calendar_type": "Unknown",
        "design_pattern": "Unknown",
        "year_range": "Unknown",
        "confidence": "Low",
        "notes": "LLM analysis unavailable.",
        "filtered_df": df,
    }

    if llm is None or df.empty:
        return fallback

    try:
        columns_str = ", ".join(str(c) for c in df.columns)
        sample_rows = df.head(30).to_string(index=False, max_cols=10)

        year_hints = []
        for col in df.columns:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                years = parsed.dt.year.dropna().unique().tolist()
                if years:
                    year_hints.extend([int(y) for y in years if 2000 <= y <= 2100])
            except Exception:
                pass
            try:
                nums = pd.to_numeric(df[col], errors="coerce").dropna()
                year_like = [int(n) for n in nums if 2000 <= n <= 2100]
                year_hints.extend(year_like)
            except Exception:
                pass

        year_hint_str = f"Possible years found in data: {sorted(set(year_hints))}" if year_hints else "No year columns detected automatically."

        system_msg = (
            "You are an expert calendar data analyst. "
            "You analyze spreadsheet data to understand what type of calendar it represents."
        )
        user_msg = f"""Analyze this uploaded holiday calendar spreadsheet and return a JSON response.

COLUMNS: {columns_str}

SAMPLE DATA (first 30 rows):
{sample_rows}

{year_hint_str}

{HOLIDAY_RAG_CONTEXT}

Based on the data above, determine:
1. detected_year: The primary calendar year (integer). If Academic, use the START year (e.g., 2025 for AY 2025-2026).
2. calendar_type: "Fiscal" (Jan-Dec), "Academic" (Jul-Jun or Sep-Aug), or "Custom"
3. design_pattern: The physical/digital calendar format. Options: "Desk-Pad", "Wall Calendar", "Planner", "Digital Spreadsheet", "Unknown"
4. year_range: Human-readable range string e.g. "Jan 2026 – Dec 2026" or "Jul 2025 – Jun 2026"
5. confidence: "High", "Medium", or "Low"
6. notes: One sentence explaining your reasoning.
7. filter_year: The specific year to filter holidays for (integer). For Academic, this is the start year.
8. filter_mode: "Fiscal" or "Academic" (choose which period_range mode to apply)

Reply ONLY with valid JSON, no extra text:
{{
  "detected_year": 2026,
  "calendar_type": "Fiscal",
  "design_pattern": "Desk-Pad",
  "year_range": "Jan 2026 – Dec 2026",
  "confidence": "High",
  "notes": "Data contains dated holidays across all 12 months of 2026.",
  "filter_year": 2026,
  "filter_mode": "Fiscal"
}}"""

        messages = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]
        response = llm.invoke(messages)
        raw_content = response.content if hasattr(response, "content") else str(response)

        start = raw_content.find("{")
        end = raw_content.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(raw_content[start:end])
        else:
            return fallback

        filter_year = int(parsed.get("filter_year") or parsed.get("detected_year") or datetime.now().year)
        filter_mode = str(parsed.get("filter_mode", "Fiscal"))
        if filter_mode not in ("Fiscal", "Academic"):
            filter_mode = "Fiscal"

        try:
            filtered_df = build_report(filter_year, filter_mode)
        except Exception:
            filtered_df = df

        return {
            "detected_year": parsed.get("detected_year"),
            "calendar_type": parsed.get("calendar_type", "Unknown"),
            "design_pattern": parsed.get("design_pattern", "Unknown"),
            "year_range": parsed.get("year_range", "Unknown"),
            "confidence": parsed.get("confidence", "Low"),
            "notes": parsed.get("notes", ""),
            "filter_year": filter_year,
            "filter_mode": filter_mode,
            "filtered_df": filtered_df,
        }

    except Exception as e:
        fallback["notes"] = f"LLM analysis error: {e}"
        return fallback


# =========================================
# LangGraph PDF Quality Workflow (backend only)
# =========================================

class PDFQualityState(TypedDict):
    extractions: List[Dict]
    expected_names: List[str]
    rag_context: str
    duplicates: List[Dict]
    missing_holidays: List[str]
    spelling_issues: List[Dict]
    llm_summary: str
    pdf_year: Optional[int]


def _node_detect_duplicates(state: PDFQualityState) -> PDFQualityState:
    """
    Duplicate detection rules:
    - A holiday is a DUPLICATE only when the EXACT same full holiday name
      (case-insensitive) appears MORE THAN ONCE in the PDF.
    - Spelling variants are DIFFERENT names — NOT duplicates.
    - ONLY considers current-month (bold) extractions.
    """
    extractions = state["extractions"]
    duplicates = []

    name_to_entries: Dict[str, List[Dict]] = {}
    for ext in extractions:
        raw_name = ext.get("holiday", "").strip()
        if not raw_name:
            continue
        key = raw_name.lower()
        name_to_entries.setdefault(key, [])
        name_to_entries[key].append(ext)

    for exact_lower_name, entries in name_to_entries.items():
        if len(entries) <= 1:
            continue

        display_name = entries[0].get("holiday", exact_lower_name)
        all_pages = sorted({e.get("page") for e in entries if e.get("page") is not None})

        duplicates.append({
            "type": "Duplicate",
            "holiday": display_name,
            "count": len(entries),
            "pages": all_pages,
            "details": (
                f"'{display_name}' — same full holiday name appears {len(entries)}× in PDF"
                + (f" (pages: {all_pages})" if all_pages else ".")
            ),
        })

    state["duplicates"] = duplicates
    return state


def _node_detect_missing(state: PDFQualityState) -> PDFQualityState:
    extractions = state["extractions"]
    expected_names = state["expected_names"]
    found_normalized = set()
    for ext in extractions:
        norm = normalize_holiday(ext.get("holiday", ""))
        if norm:
            found_normalized.add(norm)
    missing = []
    for expected in expected_names:
        norm_exp = normalize_holiday(expected)
        if norm_exp in found_normalized:
            continue
        matched = any(
            difflib.SequenceMatcher(None, norm_exp, fn).ratio() >= 0.70
            for fn in found_normalized
        )
        if not matched:
            missing.append(expected)
    state["missing_holidays"] = missing
    return state


def _node_detect_spelling(state: PDFQualityState, llm) -> PDFQualityState:
    """
    Detect spelling mistakes in PDF holiday labels using LangChain LLM + RAG.
    """
    extractions = state["extractions"]
    rag_context = state["rag_context"]
    spelling_issues = []

    if llm is None or not extractions:
        state["spelling_issues"] = spelling_issues
        return state

    unique_extracted = list({ext.get("holiday", "").strip() for ext in extractions if ext.get("holiday", "").strip()})
    if not unique_extracted:
        state["spelling_issues"] = spelling_issues
        return state

    candidates = []
    for raw_name in unique_extracted:
        best_match = fuzzy_match_holiday(raw_name, HOLIDAY_NAMES, threshold=0.75)
        if best_match:
            similarity = difflib.SequenceMatcher(
                None, normalize_holiday(raw_name), normalize_holiday(best_match)
            ).ratio()
            if similarity < 0.95 and not is_exact_name_match(raw_name, best_match):
                candidates.append({
                    "extracted": raw_name,
                    "closest_match": best_match,
                    "similarity": round(similarity, 3),
                })

    if not candidates:
        state["spelling_issues"] = spelling_issues
        return state

    lines = [
        f'{i}. PDF="{c["extracted"]}" → Closest="{c["closest_match"]}" (similarity={c["similarity"]})'
        for i, c in enumerate(candidates)
    ]
    prompt = f"""You are a calendar proofreader using the following authoritative holiday name database.

{rag_context}

Below are holiday labels extracted from a PDF calendar, each paired with the closest canonical name from the database.
For each entry, determine:
- Is the PDF label a SPELLING/WORDING MISTAKE of the canonical name? (Yes/No)
- If Yes: what is the correct canonical name and what exactly is wrong (typo, missing letter, missing word, wrong abbreviation, etc.)?
- If No: it may be an alternate accepted name or abbreviation — mark as OK.
- NOTE: If the PDF label is EXACTLY the same as the canonical name (ignoring case), mark as OK.

Reply ONLY as a JSON array:
[
  {{"index": 0, "is_mistake": true, "correct_name": "Valentine's Day", "issue": "Missing apostrophe: 'Valentines Day'"}},
  {{"index": 1, "is_mistake": false, "correct_name": null, "issue": "OK"}}
]

Entries to review:
{chr(10).join(lines)}"""

    try:
        messages = [HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        raw = extract_json_array(content)
        for item in raw:
            if not isinstance(item, dict):
                continue
            idx = item.get("index", -1)
            if item.get("is_mistake") and 0 <= idx < len(candidates):
                candidate = candidates[idx]
                spelling_issues.append({
                    "extracted_label": candidate["extracted"],
                    "correct_name": item.get("correct_name", candidate["closest_match"]),
                    "issue": item.get("issue", "Possible spelling/wording mistake"),
                    "similarity": candidate["similarity"],
                })
    except Exception:
        for c in candidates:
            if c["similarity"] < 0.85:
                spelling_issues.append({
                    "extracted_label": c["extracted"],
                    "correct_name": c["closest_match"],
                    "issue": f"Low similarity ({c['similarity']:.0%}) to canonical name — possible spelling/wording mistake.",
                    "similarity": c["similarity"],
                })

    state["spelling_issues"] = spelling_issues
    return state


def _node_compile_summary(state: PDFQualityState, llm) -> PDFQualityState:
    duplicates = state["duplicates"]
    missing = state["missing_holidays"]
    spelling = state["spelling_issues"]
    total_issues = len(duplicates) + len(missing) + len(spelling)
    if total_issues == 0:
        state["llm_summary"] = "✅ PDF calendar passed all quality checks — no duplicates, missing holidays, or wording/spelling mistakes detected."
    else:
        parts = []
        if duplicates:
            parts.append(f"🔁 {len(duplicates)} duplicate name(s)")
        if missing:
            parts.append(f"❌ {len(missing)} missing holiday(s)")
        if spelling:
            parts.append(f"✏️ {len(spelling)} wording/spelling mistake(s)")
        state["llm_summary"] = "Issues found: " + ", ".join(parts) + ". Review the unified validation table below."
    return state


def build_pdf_quality_graph(llm):
    if not LANGGRAPH_AVAILABLE:
        return None
    workflow = StateGraph(PDFQualityState)
    workflow.add_node("detect_duplicates", _node_detect_duplicates)
    workflow.add_node("detect_missing", _node_detect_missing)
    workflow.add_node("detect_spelling", lambda s: _node_detect_spelling(s, llm))
    workflow.add_node("compile_summary", lambda s: _node_compile_summary(s, llm))
    workflow.set_entry_point("detect_duplicates")
    workflow.add_edge("detect_duplicates", "detect_missing")
    workflow.add_edge("detect_missing", "detect_spelling")
    workflow.add_edge("detect_spelling", "compile_summary")
    workflow.add_edge("compile_summary", END)
    return workflow.compile()


def run_pdf_quality_langgraph(
    all_extractions: List[Dict],
    expected_df: pd.DataFrame,
    llm,
    pdf_year: Optional[int] = None,
) -> Dict[str, Any]:
    fallback = {
        "duplicates": [],
        "missing_holidays": [],
        "spelling_issues": [],
        "llm_summary": "",
    }

    if not LANGGRAPH_AVAILABLE or not all_extractions:
        return fallback

    expected_names = list(expected_df["Holiday"].dropna().unique()) if not expected_df.empty else []

    initial_state: PDFQualityState = {
        "extractions": all_extractions,
        "expected_names": expected_names,
        "rag_context": HOLIDAY_RAG_CONTEXT,
        "duplicates": [],
        "missing_holidays": [],
        "spelling_issues": [],
        "llm_summary": "",
        "pdf_year": pdf_year,
    }

    try:
        graph = build_pdf_quality_graph(llm)
        if graph is None:
            return fallback
        final_state = graph.invoke(initial_state)
        return {
            "duplicates": final_state.get("duplicates", []),
            "missing_holidays": final_state.get("missing_holidays", []),
            "spelling_issues": final_state.get("spelling_issues", []),
            "llm_summary": final_state.get("llm_summary", ""),
        }
    except Exception as e:
        fallback["llm_summary"] = f"Quality check error: {e}"
        return fallback


# ======================================================
# ── NEW: AI DESIGN TEMPLATE INFERENCE (all design patterns)
# ======================================================


def infer_design_type(pdf_bytes: bytes, page_num: int = 0) -> Dict:
    """
    Classify the PDF calendar into a known design family using page geometry
    heuristics. Returns a design_profile dict compatible with DESIGN_FAMILY_DEFAULTS.

    Strategy:
      - Cluster large bold date numbers into x-columns and y-rows.
      - 18+ x-columns or very wide landscape  →  wall_three_month
      - Landscape + ≤5 row clusters           →  deskpad
      - Otherwise                              →  wall_single
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num]
        rect = page.rect
        width, height = rect.width, rect.height

        large_dates, _ = extract_calendar_grid(page)
        bold_dates = [d for d in large_dates if d.get("bold", True)]

        if not bold_dates:
            profile = dict(DESIGN_FAMILY_DEFAULTS["wall_single"])
            profile["confidence"] = 0.0
            profile["layout_notes"] = "No bold dates detected; defaulting to wall_single."
            return profile

        col_clusters: List[List[float]] = []
        for d in bold_dates:
            placed = False
            for cl in col_clusters:
                if abs(cl[0] - d["x"]) <= 40:
                    cl.append(d["x"])
                    placed = True
                    break
            if not placed:
                col_clusters.append([d["x"]])
        num_cols = len(col_clusters)

        row_clusters: List[List[float]] = []
        for d in bold_dates:
            placed = False
            for rl in row_clusters:
                if abs(rl[0] - d["y0"]) <= 25:
                    rl.append(d["y0"])
                    placed = True
                    break
            if not placed:
                row_clusters.append([d["y0"]])
        num_rows = len(row_clusters)

        is_landscape = width > height
        confidence = 0.85

        if num_cols >= 18 or (num_cols >= 7 and width > height * 1.5):
            profile = dict(DESIGN_FAMILY_DEFAULTS["wall_three_month"])
            profile["num_rows"] = num_rows
            profile["confidence"] = confidence
            profile["layout_notes"] = (
                f"Detected {num_cols} date columns on wide landscape page "
                f"({width:.0f}x{height:.0f}pt) — three-month wall calendar."
            )
            return profile

        if is_landscape and num_rows <= 5:
            profile = dict(DESIGN_FAMILY_DEFAULTS["deskpad"])
            profile["num_rows"] = num_rows
            profile["confidence"] = confidence
            profile["layout_notes"] = (
                f"Landscape page ({width:.0f}x{height:.0f}pt), {num_rows} rows — desk-pad calendar."
            )
            return profile

        profile = dict(DESIGN_FAMILY_DEFAULTS["wall_single"])
        profile["num_rows"] = num_rows
        profile["confidence"] = confidence
        profile["layout_notes"] = (
            f"Portrait page ({width:.0f}x{height:.0f}pt), {num_rows} rows, "
            f"{num_cols} cols — wall single-month calendar."
        )
        return profile

    except Exception as exc:
        profile = dict(DESIGN_FAMILY_DEFAULTS["wall_single"])
        profile["confidence"] = 0.0
        profile["layout_notes"] = f"Design inference failed: {exc}"
        return profile


# ======================================================
# ── NEW: OVERFLOW CELL COMPUTATION (design-aware)
# ======================================================

def _compute_overflow_cells(year: int, month: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Pure calendar-math overflow computation (fallback)."""
    first_dow = (calendar.monthrange(year, month)[0] + 1) % 7  # Sun=0
    total = calendar.monthrange(year, month)[1]

    prev_month = 12 if month == 1 else month - 1
    prev_year  = year - 1 if month == 1 else year
    prev_total = calendar.monthrange(prev_year, prev_month)[1]
    prev_overflow = []
    if first_dow > 0:
        for i in range(first_dow):
            day = prev_total - (first_dow - 1 - i)
            prev_overflow.append((day, prev_month))

    total_cells_used = first_dow + total
    remaining = (7 - (total_cells_used % 7)) % 7
    next_month = 1 if month == 12 else month + 1
    next_overflow = [(i + 1, next_month) for i in range(remaining)]

    return prev_overflow, next_overflow


def _compute_overflow_cells_adaptive(
    year: int, month: int, design_profile: Dict
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Design-aware overflow computation.
    Uses AI-inferred overflow_prev_cells / overflow_next_cells when confidence is high.
    Falls back to pure calendar math if not confident.
    """
    conf    = design_profile.get("confidence", 0.0) if design_profile else 0.0
    ai_prev = design_profile.get("overflow_prev_cells") if design_profile else None
    ai_next = design_profile.get("overflow_next_cells") if design_profile else None

    if (conf >= 0.75
            and ai_prev is not None
            and ai_next is not None
            and isinstance(ai_prev, (int, float))
            and isinstance(ai_next, (int, float))
            and 0 <= int(ai_prev) <= 6
            and 0 <= int(ai_next) <= 6):

        ai_prev = int(ai_prev)
        ai_next = int(ai_next)

        prev_month = 12 if month == 1 else month - 1
        prev_year  = year - 1 if month == 1 else year
        prev_total = calendar.monthrange(prev_year, prev_month)[1]

        prev_overflow = []
        for i in range(ai_prev):
            day = prev_total - (ai_prev - 1 - i)
            prev_overflow.append((day, prev_month))

        next_month = 1 if month == 12 else month + 1
        next_overflow = [(i + 1, next_month) for i in range(ai_next)]
        return prev_overflow, next_overflow

    return _compute_overflow_cells(year, month)


# ======================================================
# ── NEW: DESIGN BADGE HTML RENDERER
# ======================================================

def _design_badge(design_profile: Dict) -> str:
    """Renders a coloured design-family badge for display in the holiday report."""
    dt    = design_profile.get("design_type", "unknown")
    conf  = design_profile.get("confidence", 0.0)
    icon, color, label = DESIGN_TYPE_META.get(dt, DESIGN_TYPE_META["unknown"])
    dr    = design_profile.get("date_rendering_mode", "")
    notes = design_profile.get("layout_notes", "")[:100]
    ws    = design_profile.get("week_start", "")
    mc    = design_profile.get("month_count", 1)
    nr    = design_profile.get("num_rows", "?")

    dr_chip = (f'<span style="background:rgba(255,255,255,.25);padding:1px 8px;'
               f'border-radius:10px;font-size:.75em;margin-left:6px;">{dr}</span>'
               if dr else "")
    conf_txt = f"{int(conf*100)}% confidence" if conf else ""

    _conf_span = (f'<span style="opacity:.75;font-weight:400;font-size:.85em;margin-left:6px;">{conf_txt}</span>' if conf_txt else '')
    badge_html = (
        f'<div style="background:{color};color:#fff;display:inline-flex;align-items:center;'
        f'gap:6px;padding:5px 16px;border-radius:20px;font-size:.82em;font-weight:700;'
        f'margin:4px 0 8px;flex-wrap:wrap;">'
        f'{icon} {label}{dr_chip}{_conf_span}'
        f'</div>'
    )
    meta_parts = []
    if ws:
        meta_parts.append(f"Week starts: <b>{ws}</b>")
    if mc and mc > 1:
        meta_parts.append(f"<b>{mc} months</b> on page")
    if nr:
        meta_parts.append(f"Grid rows: <b>{nr}</b>")
    meta_html = ""
    if meta_parts:
        meta_html = (
            f'<div style="font-size:.76em;color:#555;padding:0 4px 4px;display:flex;gap:12px;flex-wrap:wrap;">'
            + " &nbsp;|&nbsp; ".join(meta_parts)
            + "</div>"
        )
    notes_html = ""
    if notes:
        notes_html = (
            f'<div style="font-size:.75em;color:#666;padding:0 4px 6px;font-style:italic;">'
            f'🔍 {html_module.escape(notes)}</div>'
        )
    return badge_html + meta_html + notes_html


# ======================================================
# ── NEW: HOLIDAY VISUAL GRID GENERATOR (all design patterns)
# ======================================================

def generate_holiday_visual_grid_html(
    month: int,
    year: int,
    validation_df: pd.DataFrame,
    design_profile: Optional[Dict] = None,
    page_extractions: Optional[List[Dict]] = None,
) -> str:
    """
    Generate a design-aware HTML visual calendar grid for a single month,
    colour-coding each date cell by its validation status.
    - Green  = Verified Exact Match
    - Blue   = Verified Within Tolerance
    - Red    = Not Found / Wrong Date / Wording Mistake / Duplicate
    - Orange = Misplaced / New Holiday
    - Yellow = Warning / Wrong Date Needs Review
    - Gray   = Overflow cells (prev/next month) — holidays from these cells are NOT considered
    - Purple = Duplicate
    """
    if design_profile is None:
        design_profile = {}

    total_days = calendar.monthrange(year, month)[1]
    month_name = MONTH_NAMES[month - 1]

    # ── Compute overflow cells (design-aware) ──────────────────────────
    try:
        prev_overflow, next_overflow = _compute_overflow_cells_adaptive(year, month, design_profile)
    except Exception:
        prev_overflow, next_overflow = _compute_overflow_cells(year, month)

    overflow_prev_days = {d for d, _ in prev_overflow}
    overflow_next_days = {d for d, _ in next_overflow}

    # ── Build day → [holidays + statuses] map from validation_df ──────
    # Only for current month; we rely on Expected Day for matching.
    day_holiday_map: Dict[int, List[Dict]] = {}
    if not validation_df.empty:
        for _, row in validation_df.iterrows():
            try:
                expected_day = int(row.get("Expected Day", 0))
                expected_date_str = str(row.get("Expected Date", ""))
                if expected_date_str and expected_day:
                    ts = pd.Timestamp(expected_date_str)
                    if ts.month == month and ts.year == year:
                        if expected_day not in day_holiday_map:
                            day_holiday_map[expected_day] = []
                        day_holiday_map[expected_day].append({
                            "holiday": str(row.get("Holiday", "")),
                            "status": str(row.get("Status", "")),
                            "found_in_pdf": str(row.get("Found In PDF", "")),
                        })
            except Exception:
                continue

    # ── Also include PDF-extracted holidays that had no match (new/unexpected) ──
    if page_extractions:
        for ext in page_extractions:
            ext_month = ext.get("month")
            ext_year  = ext.get("year")
            ext_day   = ext.get("date")
            ext_label = ext.get("holiday", "")
            if ext_month == month and ext_year == year and ext_day:
                # Only add if not already captured from validation
                already = any(
                    h["found_in_pdf"].lower() == ext_label.lower()
                    for h in day_holiday_map.get(ext_day, [])
                )
                if not already:
                    if ext_day not in day_holiday_map:
                        day_holiday_map[ext_day] = []
                    day_holiday_map[ext_day].append({
                        "holiday": ext_label,
                        "status": "🆕 Extracted from PDF",
                        "found_in_pdf": ext_label,
                    })

    def _cell_color(statuses: List[str]) -> Tuple[str, str, str]:
        """Return (background, border, text) CSS for a cell based on its statuses."""
        combined = " ".join(statuses)
        if "Not Found" in combined:
            return "#ffcccc", "#cc0000", "#7a0000"
        if "Duplicate" in combined:
            return "#e8d5f5", "#6a0dad", "#3d0070"
        if "Misplaced" in combined:
            return "#ffe0b2", "#e65100", "#8d2e00"
        if "Wrong Date" in combined:
            return "#fff3cc", "#f0ad00", "#6b4900"
        if "Wording/Spelling Mistake" in combined or "Wording Mismatch" in combined:
            return "#ffe8e8", "#cc2200", "#7a0000"
        if "Within" in combined:
            return "#cce5ff", "#0066cc", "#003d99"
        if "Exact Match" in combined or "Verified" in combined:
            return "#d4edda", "#28a745", "#155724"
        if "New Holiday" in combined or "Extracted from PDF" in combined:
            return "#fff3e0", "#ff9800", "#8d4a00"
        return "#f8f9fa", "#dee2e6", "#555"

    def _status_icon(status: str) -> str:
        if "Exact Match" in status or "Verified" in status:
            return "✅"
        if "Within" in status:
            return "🔵"
        if "Not Found" in status:
            return "❌"
        if "Duplicate" in status:
            return "🔁"
        if "Misplaced" in status:
            return "🗓️"
        if "Wrong Date" in status:
            return "⚠️"
        if "Wording/Spelling" in status or "Wording Mismatch" in status:
            return "✏️"
        if "New Holiday" in status or "Extracted" in status:
            return "🆕"
        return "•"

    # ── Column order from design profile ──────────────────────────────
    col_order = design_profile.get("column_order", ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    if not isinstance(col_order, list) or len(col_order) != 7:
        col_order = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    is_multimonth = design_profile.get("month_count", 1) > 1

    # ── CSS ───────────────────────────────────────────────────────────
    css = """
<style>
.hv-grid-wrap{margin:0;padding:0;}
.hv-title{font-size:.88em;font-weight:700;color:#333;margin:8px 0 6px;display:flex;align-items:center;gap:8px;}
.hv-overflow-note{font-size:.72em;color:#888;font-style:italic;margin:0 0 6px;}
.hv-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;}
.hv-ch{background:#2c3e50;color:#fff;text-align:center;padding:5px 2px;font-size:.72em;font-weight:700;border-radius:3px;}
.hv-cell{border-radius:4px;padding:4px 5px;min-height:76px;border:1px solid #ddd;font-size:.7em;line-height:1.3;overflow:hidden;}
.hv-cell-overflow{background:#f1f1f1;border:1px dashed #bbb;min-height:64px;border-radius:4px;padding:4px 5px;}
.hv-day{font-weight:700;font-size:1.0em;margin-bottom:2px;}
.hv-day-ovf{font-size:.85em;color:#aaa;font-style:italic;}
.hv-ovf-lbl{font-size:.6em;color:#bbb;display:block;}
.hv-holiday{margin-top:1px;padding:1px 3px;border-radius:2px;font-size:.75em;display:flex;gap:2px;align-items:center;white-space:nowrap;overflow:hidden;line-height:1.25;}
.hv-legend{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0;font-size:.72em;}
.hv-leg-item{display:flex;align-items:center;gap:3px;}
.hv-leg-box{width:12px;height:12px;border-radius:2px;border:1px solid #ccc;display:inline-block;flex-shrink:0;}
</style>
"""

    # ── Grid header ───────────────────────────────────────────────────
    source_note = "AI design profile" if design_profile.get("confidence", 0) >= 0.75 else "calendar math fallback"
    multimonth_note = f" · Primary month only (3-month view)" if is_multimonth else ""
    html_parts = [css, f'<div class="hv-grid-wrap">']
    html_parts.append(
        f'<div class="hv-title">📅 {html_module.escape(month_name)} {year} — Holiday Visual Grid'
        f'<span style="font-weight:400;font-size:.82em;color:#888;">'
        f'(overflow: {source_note}{multimonth_note})</span></div>'
    )

    if prev_overflow or next_overflow:
        prev_str = ", ".join(str(d) for d, _ in prev_overflow) if prev_overflow else "none"
        next_str = ", ".join(str(d) for d, _ in next_overflow) if next_overflow else "none"
        html_parts.append(
            f'<div class="hv-overflow-note">'
            f'⬅ Prev-month overflow: {prev_str} &nbsp;|&nbsp; Next-month overflow: {next_str} ➡'
            f'&nbsp;— Unbold/overflow dates and their holidays are NOT counted in validation.'
            f'</div>'
        )

    # ── Column headers ────────────────────────────────────────────────
    html_parts.append('<div class="hv-grid">')
    for dh in col_order:
        html_parts.append(f'<div class="hv-ch">{html_module.escape(str(dh)[:3])}</div>')

    # ── Prev-month overflow cells ─────────────────────────────────────
    for ovf_day, ovf_month_num in prev_overflow:
        ovf_month_name = MONTH_NAMES[ovf_month_num - 1][:3]
        html_parts.append(
            f'<div class="hv-cell-overflow">'
            f'<div class="hv-day-ovf">{ovf_day}</div>'
            f'<span class="hv-ovf-lbl">← {ovf_month_name} (not counted)</span>'
            f'</div>'
        )

    # ── Current month cells ───────────────────────────────────────────
    for day in range(1, total_days + 1):
        holidays_on_day = day_holiday_map.get(day, [])
        if holidays_on_day:
            statuses = [h["status"] for h in holidays_on_day]
            bg, border, txt = _cell_color(statuses)
            inner = f'<div class="hv-day" style="color:{txt};">{day}</div>'
            for h in holidays_on_day:
                icon = _status_icon(h["status"])
                h_label = h["holiday"] or h["found_in_pdf"] or "?"
                inner += (
                    f'<div class="hv-holiday" style="color:{txt};">'
                    f'<span style="flex-shrink:0;">{icon}</span>'
                    f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;">{html_module.escape(h_label)}</span>'
                    f'</div>'
                )
            html_parts.append(
                f'<div class="hv-cell" style="background:{bg};border-color:{border};">'
                f'{inner}</div>'
            )
        else:
            html_parts.append(
                f'<div class="hv-cell" style="background:#f8f9fa;border-color:#e0e0e0;">'
                f'<div class="hv-day" style="color:#333;">{day}</div>'
                f'</div>'
            )

    # ── Next-month overflow cells ─────────────────────────────────────
    for ovf_day, ovf_month_num in next_overflow:
        ovf_month_name = MONTH_NAMES[ovf_month_num - 1][:3]
        html_parts.append(
            f'<div class="hv-cell-overflow">'
            f'<div class="hv-day-ovf">{ovf_day}</div>'
            f'<span class="hv-ovf-lbl">{ovf_month_name} → (not counted)</span>'
            f'</div>'
        )

    html_parts.append('</div>')  # .hv-grid

    # ── Legend ────────────────────────────────────────────────────────
    html_parts.append("""
<div class="hv-legend">
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#d4edda;border-color:#28a745;"></span>✅ Verified Exact</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#cce5ff;border-color:#0066cc;"></span>🔵 Within Tolerance</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#ffcccc;border-color:#cc0000;"></span>❌ Not Found</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#ffe8e8;border-color:#cc2200;"></span>✏️ Spelling/Wording</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#fff3cc;border-color:#f0ad00;"></span>⚠️ Wrong Date</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#ffe0b2;border-color:#e65100;"></span>🗓️ Misplaced</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#e8d5f5;border-color:#6a0dad;"></span>🔁 Duplicate</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#fff3e0;border-color:#ff9800;"></span>🆕 New/Unmatched</span>
  <span class="hv-leg-item"><span class="hv-leg-box" style="background:#f1f1f1;border:1px dashed #bbb;"></span>Overflow (not counted)</span>
</div>
""")
    html_parts.append('</div>')  # .hv-grid-wrap
    return "\n".join(html_parts)


# =========================================
# FULL VALIDATION PIPELINE
# =========================================

def build_expected_lookup(expected_df: pd.DataFrame) -> Dict[Tuple, Dict]:
    lookup: Dict[Tuple, Dict] = {}
    for _, row in expected_df.iterrows():
        try:
            ts = pd.Timestamp(row["date"])
            key = (
                normalize_holiday(str(row["Holiday"])),
                ts.day,
                ts.month,
                ts.year,
            )
            lookup[key] = row.to_dict()
        except Exception:
            continue
    return lookup


def extract_pdf_pages_metadata(pdf_bytes: bytes, fallback_year: Optional[int] = None) -> List[Dict]:
    """
    First pass: read every page, detect month+year header using the strict detector,
    then repair any missing or out-of-sequence months globally.
    Returns a list of dicts: [{"page": 1, "month": 1, "year": 2026, ...}, ...]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    meta: List[Dict] = []
    for i in range(len(doc)):
        page = doc[i]
        large_dates, holiday_labels = extract_calendar_grid(page)
        month, year = detect_page_month_year_strict(page, large_dates)
        if year is None:
            year = fallback_year
        meta.append({
            "page": i + 1,
            "month": month,
            "year": year,
            "date_count": len([d for d in large_dates if d.get("bold")]),
            "holiday_label_count": len(holiday_labels),
        })
    meta = repair_page_month_sequence(meta)
    return meta


def validate_calendar_pdf(
    pdf_bytes: bytes,
    expected_df: pd.DataFrame,
    use_llm: bool = True,
) -> Tuple[pd.DataFrame, List[Dict]]:
    if "Holiday" not in expected_df.columns or "date" not in expected_df.columns:
        return pd.DataFrame([{
            "Status": "❌ Configuration Error",
            "Holiday": "N/A",
            "Expected Date": "",
            "Expected Day": "",
            "Found In PDF": "",
            "Notes": "The reference calendar is missing 'Holiday' or 'date' columns."
        }]), []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n_pages = len(doc)
    known_names = list(expected_df["Holiday"].dropna().unique())

    expected_lookup: Dict[Tuple[str, int], Dict] = {}
    for _, row in expected_df.iterrows():
        try:
            d = pd.Timestamp(row["date"]).day
            key = (normalize_holiday(str(row["Holiday"])), d)
            expected_lookup[key] = dict(row)
        except Exception:
            continue

    native_all: List[Dict] = []
    fallback_year = None
    try:
        fallback_year = pd.Timestamp(expected_df.iloc[0]["date"]).year
    except Exception:
        fallback_year = datetime.now().year

    # ── Page metadata pass: detect + repair month/year sequence globally ──
    pages_meta = extract_pdf_pages_metadata(pdf_bytes, fallback_year=fallback_year)
    page_meta_by_num: Dict[int, Dict] = {m["page"]: m for m in pages_meta}

    for pg in range(n_pages):
        try:
            native_all.extend(
                extract_holidays_from_page_native(
                    pdf_bytes, pg, fallback_year,
                    page_meta=page_meta_by_num.get(pg + 1),
                )
            )
        except Exception:
            pass

    llm_all: List[Dict] = []
    if use_llm and OPENROUTER_API_KEY and OPENROUTER_API_KEY != "YOUR_OPENROUTER_API_KEY":
        for pg in range(n_pages):
            try:
                llm_all.extend(extract_holidays_from_page_llm(pdf_bytes, pg))
            except Exception:
                pass

    all_extractions_raw = native_all + llm_all

    # ── DEDUPLICATION ──
    seen_ext_keys: set = set()
    all_extractions: List[Dict] = []
    for ext in all_extractions_raw:
        raw_h = ext.get("holiday", "").strip().lower()
        d = ext.get("date")
        m = ext.get("month")
        pg = ext.get("page")
        key = (raw_h, d, m, pg)
        if key not in seen_ext_keys:
            seen_ext_keys.add(key)
            all_extractions.append(ext)

    # ── Flag extractions with missing holiday name or missing date ──
    missing_name_entries: List[Dict] = []
    missing_date_entries: List[Dict] = []
    for ext in all_extractions:
        raw = ext.get("holiday", "").strip()
        day = ext.get("date")
        if not raw and day:
            missing_name_entries.append(ext)
        elif raw and not day:
            missing_date_entries.append(ext)

    exact_found_set: set = set()
    fuzzy_found_set: set = set()
    exact_found_set_with_month: set = set()
    fuzzy_found_set_with_month: set = set()
    found_raw: Dict[str, List[str]] = {}
    found_location: Dict[str, Tuple[Optional[int], int]] = {}
    day_text_map: Dict[int, List[str]] = {}
    month_day_text_map: Dict[Tuple, List[str]] = {}

    for ext in all_extractions:
        raw = ext.get("holiday", "").strip()
        day = ext.get("date")
        month = ext.get("month")
        if not raw or not day:
            continue
        try:
            day = int(day)
        except (ValueError, TypeError):
            continue

        day_text_map.setdefault(day, [])
        if raw not in day_text_map[day]:
            day_text_map[day].append(raw)
        mkey = (month, day)
        month_day_text_map.setdefault(mkey, [])
        if raw not in month_day_text_map[mkey]:
            month_day_text_map[mkey].append(raw)

        matched_name = fuzzy_match_holiday(raw, known_names)
        if matched_name:
            norm_canonical = normalize_holiday(matched_name)
            if is_exact_name_match(raw, matched_name):
                exact_found_set.add((norm_canonical, day))
                exact_found_set_with_month.add((norm_canonical, day, month))
            else:
                fuzzy_found_set.add((norm_canonical, day))
                fuzzy_found_set_with_month.add((norm_canonical, day, month))
            if norm_canonical not in found_raw:
                found_raw[norm_canonical] = []
            if raw not in found_raw[norm_canonical]:
                found_raw[norm_canonical].append(raw)
            found_location.setdefault(norm_canonical, (month, day))

    def _found_raw_display(norm_canonical: str, fallback: str = "?") -> str:
        labels = found_raw.get(norm_canonical, [])
        if not labels:
            return fallback
        return " / ".join(labels)

    def get_texts_on_day(day: int, month: Optional[int] = None) -> List[str]:
        if month is not None:
            return month_day_text_map.get((month, day), [])
        return day_text_map.get(day, [])

    report_rows = []
    wrong_date_pending: List[Dict] = []
    wording_mistake_norm_names: set = set()

    for _, row in expected_df.iterrows():
        try:
            h_name = str(row["Holiday"]).strip()
            date_str = row["date"]
            expected_ts = pd.Timestamp(date_str)
            expected_day = expected_ts.day
            expected_month = expected_ts.month
        except Exception:
            continue

        norm_name = normalize_holiday(h_name)
        norm_key = (norm_name, expected_day)

        if h_name in FLEXIBLE_DATE_HOLIDAYS:
            tolerance = FLEXIBLE_TOLERANCE
            tol_reason = "astronomical/lunar variation"
        elif h_name in OBSERVED_SHIFT_HOLIDAYS:
            tolerance = OBSERVED_TOLERANCE
            tol_reason = "weekend observation shift"
        else:
            tolerance = 0
            tol_reason = ""

        # ── 1. TRUE EXACT MATCH ──
        def _no_cross_month_conflict_exact(nm, d, em):
            return not any(
                k[0] == nm and k[1] == d and k[2] is not None and k[2] != em
                for k in exact_found_set_with_month
            )
        exact_match_found = (
            (norm_name, expected_day, expected_month) in exact_found_set_with_month
            or (norm_name, expected_day, None) in exact_found_set_with_month
            or (norm_key in exact_found_set and _no_cross_month_conflict_exact(norm_name, expected_day, expected_month))
        )
        if exact_match_found:
            _exact_pdf_label = _found_raw_display(norm_name, "✓")
            _co_holidays = [t for t in get_texts_on_day(expected_day, expected_month) if t != _exact_pdf_label]
            _exact_notes = "Holiday name, date, and month/year all match exactly."
            if _co_holidays:
                _exact_notes += f" Note: additional holiday(s) also on this date in PDF: {'; '.join(_co_holidays)}."
            report_rows.append({
                "Status": "✅ Verified – Exact Match",
                "Holiday": h_name,
                "Expected Date": date_str,
                "Expected Day": expected_day,
                "Found In PDF": _exact_pdf_label,
                "Notes": _exact_notes,
            })
            continue

        # ── 2. EXACT NAME – WITHIN TOLERANCE ──
        found_by_exact_name_tolerance = False
        if tolerance > 0:
            for delta in range(-tolerance, tolerance + 1):
                if delta == 0:
                    continue
                nearby_key = (norm_name, expected_day + delta)
                if nearby_key in exact_found_set:
                    found_day = expected_day + delta
                    abs_d = abs(delta)
                    day_word = "day" if abs_d == 1 else "days"
                    report_rows.append({
                        "Status": f"✅ Verified – Within ±{abs_d} {day_word.title()}",
                        "Holiday": h_name,
                        "Expected Date": date_str,
                        "Expected Day": expected_day,
                        "Found In PDF": _found_raw_display(norm_name, f"day {found_day}"),
                        "Notes": (
                            f"Name matched exactly. PDF shows day {found_day} vs expected {expected_day} "
                            f"(±{abs_d} {day_word}). Acceptable due to {tol_reason}."
                        ),
                    })
                    found_by_exact_name_tolerance = True
                    break
        if found_by_exact_name_tolerance:
            continue

        # ── 3. WORDING/SPELLING MISTAKE – CORRECT DATE ──
        def _no_cross_month_conflict_fuzzy(nm, d, em):
            return not any(
                k[0] == nm and k[1] == d and k[2] is not None and k[2] != em
                for k in fuzzy_found_set_with_month
            )
        fuzzy_correct_month = (
            (norm_name, expected_day, expected_month) in fuzzy_found_set_with_month
            or (norm_name, expected_day, None) in fuzzy_found_set_with_month
            or (norm_key in fuzzy_found_set and _no_cross_month_conflict_fuzzy(norm_name, expected_day, expected_month))
        )
        if fuzzy_correct_month:
            pdf_label = _found_raw_display(norm_name, "?")
            diff_str = make_spelling_diff(pdf_label, h_name)
            wording_mistake_norm_names.add(norm_name)
            report_rows.append({
                "Status": "✏️ Wording/Spelling Mistake – Correct Date",
                "Holiday": h_name,
                "Expected Date": date_str,
                "Expected Day": expected_day,
                "Found In PDF": pdf_label,
                "Notes": (
                    f"Date (day {expected_day}) and month ({expected_month}) are correct but the holiday name "
                    f"is misspelled or worded differently. {diff_str}. "
                    f"Please correct the label to: \"{h_name}\"."
                ),
            })
            continue

        # ── 4. WORDING/SPELLING MISTAKE – NEAR DATE ──
        found_by_fuzzy_tolerance = False
        if tolerance > 0:
            for delta in range(-tolerance, tolerance + 1):
                if delta == 0:
                    continue
                nearby_day = expected_day + delta
                nearby_key_fuzzy = (norm_name, nearby_day)
                month_ok_fuzzy = (
                    (norm_name, nearby_day, expected_month) in fuzzy_found_set_with_month
                    or (norm_name, nearby_day, None) in fuzzy_found_set_with_month
                    or (nearby_key_fuzzy in fuzzy_found_set and not any(
                        k[0] == norm_name and k[1] == nearby_day and k[2] is not None and k[2] != expected_month
                        for k in fuzzy_found_set_with_month
                    ))
                )
                if month_ok_fuzzy:
                    found_day = nearby_day
                    abs_d = abs(delta)
                    day_word = "day" if abs_d == 1 else "days"
                    pdf_label = _found_raw_display(norm_name, "?")
                    diff_str = make_spelling_diff(pdf_label, h_name)
                    wording_mistake_norm_names.add(norm_name)
                    report_rows.append({
                        "Status": f"✏️ Wording/Spelling Mistake – ±{abs_d} {day_word.title()} Off",
                        "Holiday": h_name,
                        "Expected Date": date_str,
                        "Expected Day": expected_day,
                        "Found In PDF": pdf_label,
                        "Notes": (
                            f"Misspelled/different wording found on day {found_day} "
                            f"(±{abs_d} {day_word} from expected {expected_day}, month {expected_month}). "
                            f"{diff_str}. Within {tol_reason} tolerance."
                        ),
                    })
                    found_by_fuzzy_tolerance = True
                    break
        if found_by_fuzzy_tolerance:
            continue

        # ── 5. WORDING MISMATCH – SAME DATE ──
        texts_on_exact = get_texts_on_day(expected_day, expected_month)
        if texts_on_exact:
            pdf_label = "; ".join(texts_on_exact)
            import calendar as _cal_m
            month_name_str = _cal_m.month_name[expected_month]
            report_rows.append({
                "Status": "🔴 Wording Mismatch – Same Date",
                "Holiday": h_name,
                "Expected Date": date_str,
                "Expected Day": expected_day,
                "Found In PDF": pdf_label,
                "Notes": (
                    f"Day {expected_day} of {month_name_str} (month {expected_month}) is correct, "
                    f"but the PDF label(s) on that date — \"{pdf_label}\" — "
                    f"do not match the expected holiday name \"{h_name}\". "
                    f"Please update the label to \"{h_name}\"."
                ),
            })
            continue

        # ── 6. WORDING MISMATCH – NEAR DATE ──
        found_by_presence = False
        if tolerance > 0:
            for delta in range(-tolerance, tolerance + 1):
                if delta == 0:
                    continue
                check_day = expected_day + delta
                texts_nearby = get_texts_on_day(check_day, expected_month)
                if texts_nearby:
                    pdf_label = "; ".join(texts_nearby)
                    abs_d = abs(delta)
                    day_word = "day" if abs_d == 1 else "days"
                    import calendar as _cal_m2
                    month_name_str2 = _cal_m2.month_name[expected_month]
                    report_rows.append({
                        "Status": f"🔴 Wording Mismatch – ±{abs_d} {day_word.title()} Off",
                        "Holiday": h_name,
                        "Expected Date": date_str,
                        "Expected Day": expected_day,
                        "Found In PDF": pdf_label,
                        "Notes": (
                            f"Different wording found on day {check_day} of {month_name_str2} "
                            f"(±{abs_d} {day_word} from expected day {expected_day}, same month {expected_month}). "
                            f"PDF label(s): \"{pdf_label}\". Expected: \"{h_name}\". "
                            f"Within {tol_reason} tolerance but wording differs."
                        ),
                    })
                    found_by_presence = True
                    break
        if found_by_presence:
            continue

        # ── 7. WRONG DATE / MISPLACED ──
        wrong_days_exact = [k[1] for k in exact_found_set if k[0] == norm_name]
        wrong_days_fuzzy = [k[1] for k in fuzzy_found_set if k[0] == norm_name]
        wrong_days = wrong_days_exact or wrong_days_fuzzy
        if wrong_days:
            row_idx = len(report_rows)
            found_loc = found_location.get(norm_name)
            found_month_in_pdf = found_loc[0] if found_loc else None
            if found_month_in_pdf is not None and found_month_in_pdf != expected_month:
                import calendar as _cal
                found_month_name = _cal.month_name[found_month_in_pdf]
                expected_month_name = _cal.month_name[expected_month]
                report_rows.append({
                    "Status": "🗓️ Misplaced – Wrong Month Page",
                    "Holiday": h_name,
                    "Expected Date": date_str,
                    "Expected Day": expected_day,
                    "Found In PDF": _found_raw_display(norm_name, "?"),
                    "Notes": (
                        f"Holiday is misplaced: found in {found_month_name} (day {wrong_days[0]}) "
                        f"but should be in {expected_month_name} (day {expected_day}, year {expected_ts.year}). "
                        f"Check the correct month/year page in the PDF."
                    ),
                })
            else:
                _wrong_day = wrong_days[0]
                _found_loc = found_location.get(norm_name)
                _found_month = _found_loc[0] if _found_loc else None
                _all_on_wrong_day = get_texts_on_day(_wrong_day, _found_month)
                _primary_label = _found_raw_display(norm_name, "?")
                _extra = [t for t in _all_on_wrong_day if t != _primary_label]
                _found_in_pdf = _primary_label
                if _extra:
                    _found_in_pdf = _primary_label + " (also on this date: " + "; ".join(_extra) + ")"
                report_rows.append({
                    "Status": "⚠️ Wrong Date – Needs Review",
                    "Holiday": h_name,
                    "Expected Date": date_str,
                    "Expected Day": expected_day,
                    "Found In PDF": _found_in_pdf,
                    "Notes": "__PENDING_AI_NOTE__",
                })
                wrong_date_pending.append({
                    "row_idx": row_idx,
                    "holiday_name": h_name,
                    "expected_date": date_str,
                    "found_day": _wrong_day,
                    "found_label": _primary_label,
                })
        else:
            # ── 8. NOT FOUND ──
            report_rows.append({
                "Status": "❌ Not Found in PDF",
                "Holiday": h_name,
                "Expected Date": date_str,
                "Expected Day": expected_day,
                "Found In PDF": "",
                "Notes": "Holiday not detected anywhere in the PDF. Verify it is printed on the calendar.",
            })

    if wrong_date_pending:
        batch_notes = get_ai_notes_batch(wrong_date_pending)
        for i, item in enumerate(wrong_date_pending):
            note = batch_notes.get(i, "") or _rule_based_wrong_date_note(
                item["holiday_name"], item["expected_date"], item["found_day"], item["found_label"]
            )
            report_rows[item["row_idx"]]["Notes"] = note

    # ── New holidays found in PDF but not in reference ──
    all_norm_expected = {normalize_holiday(n) for n in known_names}
    unexpected_items: List[Dict] = []
    checked_unexpected: set = set()
    for (norm_name, day) in list(exact_found_set) + list(fuzzy_found_set):
        if norm_name in checked_unexpected:
            continue
        if norm_name not in all_norm_expected:
            checked_unexpected.add(norm_name)
            unexpected_items.append({
                "norm_name": norm_name,
                "found_label": _found_raw_display(norm_name, norm_name),
                "day": day,
            })

    if unexpected_items:
        ai_unexpected_notes = get_ai_unexpected_notes_batch(unexpected_items)
        for i, item in enumerate(unexpected_items):
            ai_note = ai_unexpected_notes.get(i, "") or \
                f"Not in reference list. PDF label: \"{item['found_label']}\" on day {item['day']}. Manually verify."
            report_rows.append({
                "Status": "🆕 New Holiday – Not in Reference",
                "Holiday": item["found_label"],
                "Expected Date": "",
                "Expected Day": "",
                "Found In PDF": item["found_label"],
                "Notes": f"[AI Check] {ai_note}",
            })

    # ── Missing holiday name in PDF ──
    for ext in missing_name_entries:
        day = ext.get("date", "?")
        pg = ext.get("page", "?")
        report_rows.append({
            "Status": "🟠 Missing Holiday Name in PDF",
            "Holiday": "",
            "Expected Date": "",
            "Expected Day": str(day),
            "Found In PDF": f"(no name) on day {day} — page {pg}",
            "Notes": f"A date cell (day {day}, page {pg}) was detected in the PDF but the holiday name label is absent or unreadable.",
        })

    # ── Missing date in PDF ──
    for ext in missing_date_entries:
        raw = ext.get("holiday", "").strip()
        pg = ext.get("page", "?")
        report_rows.append({
            "Status": "🔵 Missing Date in PDF",
            "Holiday": raw,
            "Expected Date": "",
            "Expected Day": "",
            "Found In PDF": f"'{raw}' (no date) — page {pg}",
            "Notes": f"Holiday label '{raw}' was found on page {pg} but no date number could be associated with it.",
        })

    if not report_rows:
        return pd.DataFrame(), all_extractions

    df_report = pd.DataFrame(report_rows)

    def sort_key(s: str) -> int:
        if "Missing Holiday Name" in s:  return 0
        if "Missing Date" in s:          return 1
        if "Not Found" in s:             return 2
        if "Misplaced" in s:             return 3
        if "Wrong Date" in s:            return 4
        if "Wording/Spelling Mistake" in s: return 5
        if "Wording Mismatch" in s:      return 6
        if "New Holiday" in s:           return 7
        if "Within" in s:                return 8
        if "Exact" in s:                 return 9
        return 10

    df_report["_sort"] = df_report["Status"].apply(sort_key)
    df_report = df_report.sort_values(["_sort", "Expected Date"]).drop(columns="_sort").reset_index(drop=True)
    return df_report, all_extractions


# ======================================================
# UI
# ======================================================
st.set_page_config(page_title=APP_TITLE, page_icon="📅", layout="wide")

# ═══════════════════════════════════════════════════════════════════════════════
# [ADDED] Robot Header + Back-to-Dashboard — matching datechecker.py style
# ═══════════════════════════════════════════════════════════════════════════════
import streamlit.components.v1 as _hc_components

# ── Back-nav query-param handler ─────────────────────────────────────────────
if st.query_params.get("nav") == "back":
    st.query_params.clear()
    try:
        st.switch_page("dashboard.py")
    except Exception:
        try:
            st.switch_page("pages/dashboard.py")
        except Exception:
            pass

# ── postMessage listener injected into parent frame ──────────────────────────
_hc_components.html("""<script>
(function(){
  window.addEventListener('message',function(e){
    if(e.data&&e.data.type==='BACK_TO_DASHBOARD'){
      var b=window.location.origin;
      var paths=['/dashboard','/Dashboard','/home','/'];
      for(var i=0;i<paths.length;i++){
        try{window.top.location.href=b+paths[i];break;}catch(err){}
      }
    }
  },false);
})();
</script>""", height=0, scrolling=False)

# ── Animated Robot Header HTML ────────────────────────────────────────────────
_HC_ROBOT_HEADER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,Arial,sans-serif;}
html,body{width:100%;background:transparent;overflow:hidden;}

.header-wrap{
  width:100%;
  background:linear-gradient(135deg,#dff0ff 0%,#f0f8ff 55%,#eaf4ff 100%);
  border:1px solid rgba(25,118,210,.13);
  border-radius:1.1rem;
  display:flex;align-items:center;
  gap:1.4rem;
  padding:.85rem 1.4rem .85rem 1.2rem;
  box-shadow:0 4px 22px rgba(25,118,210,.10);
  position:relative;
  overflow:hidden;
}
.header-wrap::before{
  content:"";position:absolute;top:-30px;right:-30px;
  width:200px;height:200px;border-radius:50%;
  background:radial-gradient(circle,rgba(25,118,210,.07),transparent 70%);
  pointer-events:none;
}

/* ── Back Button ── */
.back-btn{
  display:flex;align-items:center;gap:.42rem;
  padding:.52rem 1.05rem;border-radius:.7rem;
  background:linear-gradient(135deg,#1565c0,#1976d2);
  color:#fff;font-size:.82rem;font-weight:800;
  border:none;cursor:pointer;letter-spacing:.3px;
  box-shadow:0 4px 14px rgba(25,118,210,.35);
  transition:all .2s ease;white-space:nowrap;flex-shrink:0;
  text-decoration:none;
}
.back-btn:hover{
  background:linear-gradient(135deg,#0d47a1,#1565c0);
  transform:translateY(-2px);
  box-shadow:0 8px 22px rgba(25,118,210,.48);
}
.back-btn svg{width:14px;height:14px;flex-shrink:0;}

/* ── Robot SVG container ── */
.robot-mini{width:120px;height:130px;flex-shrink:0;}
.robot-mini svg{width:100%;height:100%;overflow:visible;
  filter:drop-shadow(0 8px 18px rgba(0,140,255,.30)) drop-shadow(0 2px 5px rgba(0,0,0,.06));}

/* ── Float animation ── */
.r-float{animation:rFloat 3.8s ease-in-out infinite;}
@keyframes rFloat{0%,100%{transform:translateY(0);}45%{transform:translateY(-8px);}75%{transform:translateY(-4px);}}
.r-head{animation:rBob 4.5s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%;}
@keyframes rBob{0%{transform:rotate(-2deg);}25%{transform:rotate(0);}50%{transform:rotate(2deg);}75%{transform:rotate(0);}100%{transform:rotate(-2deg);}}
.r-arm-l{animation:armL 3.8s ease-in-out infinite;transform-box:fill-box;transform-origin:90% 20%;}
@keyframes armL{0%,100%{transform:rotate(0);}32%{transform:rotate(14deg);}65%{transform:rotate(-7deg);}}
.r-arm-r{animation:armR 3.8s ease-in-out infinite;transform-box:fill-box;transform-origin:10% 20%;}
@keyframes armR{0%,100%{transform:rotate(0);}32%{transform:rotate(-12deg);}65%{transform:rotate(6deg);}}
.r-eye-glow{animation:eyeGlowPulse 2s ease-in-out infinite;}
@keyframes eyeGlowPulse{0%,100%{opacity:.45;}50%{opacity:.9;}}

/* ── Title/subtitle ── */
.header-text{flex:1;min-width:0;}
.header-title{
  font-size:clamp(.96rem,2vw,1.22rem);font-weight:900;
  background:linear-gradient(90deg,#0b2258 0%,#1565c0 40%,#1976d2 60%,#0b2258 100%);
  background-size:220% auto;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  animation:shimmerT 4s linear infinite;
  line-height:1.2;margin-bottom:.28rem;
}
@keyframes shimmerT{0%{background-position:0%}100%{background-position:220%}}
.header-sub{font-size:clamp(.7rem,1.1vw,.82rem);color:#4a6fa5;line-height:1.55;}
.header-badge{
  display:inline-flex;align-items:center;gap:4px;
  background:rgba(25,118,210,.10);border:1px solid rgba(25,118,210,.22);
  border-radius:999px;padding:.18rem .55rem;
  font-size:.62rem;font-weight:800;color:#1565c0;letter-spacing:.5px;text-transform:uppercase;
  margin-top:.35rem;
}
.dot-live{width:6px;height:6px;border-radius:50%;background:#4ade80;
  box-shadow:0 0 7px rgba(74,222,128,.65);animation:pulse 1.8s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:.5;}50%{opacity:1;box-shadow:0 0 14px rgba(74,222,128,.85);}}
</style>
</head>
<body>
<div class="header-wrap">


  <!-- Robot SVG -->
  <div class="robot-mini">
    <svg viewBox="0 0 200 250" fill="none" xmlns="http://www.w3.org/2000/svg" overflow="visible">
      <defs>
        <radialGradient id="hcgHead" cx="32%" cy="20%" r="72%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="38%" stop-color="#e0f7ff"/>
          <stop offset="75%" stop-color="#b0e8f8"/>
          <stop offset="100%" stop-color="#8ecee8"/>
        </radialGradient>
        <radialGradient id="hcgBody" cx="34%" cy="22%" r="74%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#d8f3ff"/>
          <stop offset="78%" stop-color="#a4dcf5"/>
          <stop offset="100%" stop-color="#80c8e8"/>
        </radialGradient>
        <radialGradient id="hcgFace" cx="48%" cy="28%" r="68%">
          <stop offset="0%" stop-color="#1c2d6e"/>
          <stop offset="55%" stop-color="#0e1a4a"/>
          <stop offset="100%" stop-color="#080f2e"/>
        </radialGradient>
        <radialGradient id="hcgEye" cx="38%" cy="22%" r="72%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="28%" stop-color="#b8f0ff"/>
          <stop offset="60%" stop-color="#00c8ff"/>
          <stop offset="100%" stop-color="#0060cc"/>
        </radialGradient>
        <radialGradient id="hcgNavy" cx="28%" cy="20%" r="75%">
          <stop offset="0%" stop-color="#2a4ab8"/>
          <stop offset="55%" stop-color="#0e1a5a"/>
          <stop offset="100%" stop-color="#060e30"/>
        </radialGradient>
        <radialGradient id="hcgBadge" cx="38%" cy="25%" r="70%">
          <stop offset="0%" stop-color="#1e3598"/>
          <stop offset="55%" stop-color="#0b1655"/>
          <stop offset="100%" stop-color="#050c30"/>
        </radialGradient>
        <linearGradient id="hcgSmile" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#60d8ff"/>
          <stop offset="50%" stop-color="#c0f4ff"/>
          <stop offset="100%" stop-color="#60d8ff"/>
        </linearGradient>
        <filter id="hcfEyeBloom" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="hcfSoft" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="6"/>
        </filter>
        <filter id="hcfSmile" x="-40%" y="-60%" width="180%" height="220%">
          <feGaussianBlur stdDeviation="4" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <g class="r-float">
        <ellipse cx="100" cy="243" rx="46" ry="7" fill="rgba(0,100,200,.14)" filter="url(#hcfSoft)"/>

        <!-- Body -->
        <path d="M100 155 C62 155 48 168 48 186 C48 210 66 232 100 240 C134 232 152 210 152 186 C152 168 138 155 100 155Z"
              fill="url(#hcgBody)"/>
        <path d="M100 155 C62 155 48 168 48 186 C48 210 66 232 100 240 C134 232 152 210 152 186 C152 168 138 155 100 155Z"
              fill="none" stroke="rgba(140,210,240,.7)" stroke-width="1.8"/>

        <!-- Left arm -->
        <g class="r-arm-l">
          <ellipse cx="50" cy="168" rx="10" ry="10" fill="url(#hcgNavy)"/>
          <rect x="30" y="162" width="24" height="36" rx="12" fill="url(#hcgNavy)"/>
          <rect x="30" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.3)" stroke-width="1.2"/>
        </g>

        <!-- Right arm -->
        <g class="r-arm-r">
          <ellipse cx="150" cy="168" rx="10" ry="10" fill="url(#hcgNavy)"/>
          <rect x="146" y="162" width="24" height="36" rx="12" fill="url(#hcgNavy)"/>
          <rect x="146" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.3)" stroke-width="1.2"/>
        </g>

        <!-- Chest AI badge -->
        <path d="M100 170 C82 170 76 180 76 192 C76 207 86 220 100 225 C114 220 124 207 124 192 C124 180 118 170 100 170Z"
              fill="url(#hcgBadge)"/>
        <path d="M100 170 C82 170 76 180 76 192 C76 207 86 220 100 225 C114 220 124 207 124 192 C124 180 118 170 100 170Z"
              fill="none" stroke="rgba(60,110,220,.5)" stroke-width="1.4"/>
        <text x="100" y="200" text-anchor="middle" fill="#a8f0ff" font-size="19" font-weight="900"
              font-family="Arial Black,Arial,sans-serif" letter-spacing="3">AI</text>

        <!-- HEAD -->
        <g class="r-head">
          <circle cx="100" cy="82" r="65" fill="url(#hcgHead)"/>
          <circle cx="100" cy="82" r="65" fill="none" stroke="rgba(130,200,235,.6)" stroke-width="1.8"/>
          <ellipse cx="68" cy="42" rx="30" ry="18" fill="rgba(255,255,255,.86)" transform="rotate(-28 68 42)"/>
          <ellipse cx="64" cy="38" rx="17" ry="10" fill="rgba(255,255,255,.95)" transform="rotate(-28 64 38)"/>
          <path d="M44 84 C44 32 156 32 156 84" fill="none" stroke="#0e1a50" stroke-width="6" stroke-linecap="round"/>
          <ellipse cx="41" cy="86" rx="14" ry="18" fill="url(#hcgNavy)"/>
          <ellipse cx="41" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.35)" stroke-width="1.2"/>
          <ellipse cx="159" cy="86" rx="14" ry="18" fill="url(#hcgNavy)"/>
          <ellipse cx="159" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.35)" stroke-width="1.2"/>
          <path d="M41 100 C44 112 54 118 64 120" fill="none" stroke="#0e1a50" stroke-width="3.5" stroke-linecap="round"/>
          <circle cx="66" cy="121" r="5.5" fill="#0e1a50"/>
          <circle cx="66" cy="121" r="3.5" fill="#1e3080"/>
          <rect x="56" y="52" width="88" height="70" rx="20" fill="url(#hcgFace)"/>
          <rect x="56" y="52" width="88" height="70" rx="20" fill="none" stroke="rgba(30,80,180,.4)" stroke-width="1.4"/>
          <rect x="66" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".22" filter="url(#hcfEyeBloom)">
            <animate attributeName="opacity" values=".12;.36;.12" dur="2.2s" repeatCount="indefinite"/>
          </rect>
          <rect x="68" y="62" width="22" height="30" rx="8" fill="#040e28"/>
          <rect x="69" y="63" width="20" height="28" rx="7" fill="url(#hcgEye)" class="r-eye-glow"/>
          <rect x="73" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.9)"/>
          <rect x="108" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".22" filter="url(#hcfEyeBloom)">
            <animate attributeName="opacity" values=".12;.36;.12" dur="2.2s" begin=".35s" repeatCount="indefinite"/>
          </rect>
          <rect x="110" y="62" width="22" height="30" rx="8" fill="#040e28"/>
          <rect x="111" y="63" width="20" height="28" rx="7" fill="url(#hcgEye)" class="r-eye-glow"/>
          <rect x="115" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.9)"/>
          <path d="M72 103 Q100 122 128 103" stroke="#00d0ff" stroke-width="6" fill="none"
                stroke-linecap="round" opacity=".2" filter="url(#hcfSmile)">
            <animate attributeName="opacity" values=".12;.32;.12" dur="3.2s" repeatCount="indefinite"/>
          </path>
          <path d="M74 103 Q100 120 126 103" stroke="url(#hcgSmile)" stroke-width="4" fill="none" stroke-linecap="round">
            <animate attributeName="opacity" values=".78;1;.78" dur="3.2s" repeatCount="indefinite"/>
          </path>
          <circle cx="68" cy="108" r="7" fill="#60d8ff" opacity=".16" filter="url(#hcfSoft)">
            <animate attributeName="opacity" values=".08;.26;.08" dur="3.5s" repeatCount="indefinite"/>
          </circle>
          <circle cx="132" cy="108" r="7" fill="#60d8ff" opacity=".16" filter="url(#hcfSoft)">
            <animate attributeName="opacity" values=".08;.26;.08" dur="3.5s" begin=".6s" repeatCount="indefinite"/>
          </circle>
        </g>
      </g>
    </svg>
  </div>

  <!-- Title & subtitle -->
  <div class="header-text">
    <div class="header-title">&#127881; AI Holiday Checker &amp; Calendar Report Generator</div>
    <div class="header-sub">
      AI-powered holiday validation powered by <strong>LangGraph Agent &middot; Design Inference &middot; RAG &middot; LangChain LLM</strong>.<br>
      Supports Desk-Pad, Wall, Three-Month, Large-Format, Mini-Wall &amp; Digital calendar designs.
    </div>
    <div class="header-badge">
      <div class="dot-live"></div>
      AI Pipeline Active &middot; LangGraph QC Engine
    </div>
  </div>

</div>


</body>
</html>"""

_hc_components.html(_HC_ROBOT_HEADER_HTML, height=155, scrolling=False)

# ── Native Streamlit back button (reliable multipage navigation) ──────────────
_hc_back_col, _hc_spacer = st.columns([1.4, 8])
with _hc_back_col:
    if st.button("⬅️ Back to Dashboard", key="_hc_back_btn",
                 use_container_width=True,
                 help="Return to the main AI-Powered Dashboard"):
        try:
            st.switch_page("dashboard.py")
        except Exception:
            try:
                st.switch_page("pages/dashboard.py")
            except Exception:
                st.query_params["nav"] = "back"
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# [END ADDED BLOCK]
# ═══════════════════════════════════════════════════════════════════════════════


st.title(f"📅 {APP_TITLE}")
st.caption(
    "Generate a holiday report automatically, or upload your own CSV/Excel holiday calendar file. "
    "**Supports ALL calendar design patterns** — Desk-Pad, Wall (Single / Three-Month / Large-Format), Mini-Wall, Digital — "
    "with AI design inference, adaptive visual grid, duplicate detection, misplacement checks, and spelling validation."
)

# ── Pipeline badge ────────────────────────────────────────────────────
st.markdown(
    """<div style="background:linear-gradient(90deg,#6f42c1,#0d6efd);color:#fff;
    display:inline-block;padding:5px 16px;border-radius:20px;font-size:.82em;font-weight:700;margin-bottom:12px;">
    🤖 Pipeline: Native Extraction → AI Design Inference → LangGraph QC → Adaptive Visual Grid
    </div>""",
    unsafe_allow_html=True,
)

llm = get_langchain_llm()
if llm and LANGCHAIN_AVAILABLE:
    st.sidebar.success("🤖 LangChain + LangGraph AI: Active")
else:
    st.sidebar.warning("⚠️ LangChain unavailable — falling back to direct API calls.")

# ── Sidebar info ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    show_visual_grid = st.toggle(
        "📅 Show Visual Holiday Grid", value=True,
        help="Display an interactive per-month calendar grid colour-coded by validation status."
    )
    st.markdown("---")
    st.markdown("**🎨 Supported Design Patterns:**")
    for k, (icon, _, lbl) in DESIGN_TYPE_META.items():
        if k != "unknown":
            st.markdown(f"{icon} {lbl}")
    st.markdown("---")
    st.markdown("**🔍 Holiday Checks Performed:**")
    st.markdown("✅ Exact name + date match")
    st.markdown("🔵 Within tolerance (seasonal/observed)")
    st.markdown("✏️ Spelling / wording mistakes")
    st.markdown("🔴 Wording mismatch (same date)")
    st.markdown("⚠️ Wrong date — needs review")
    st.markdown("🗓️ Misplaced — wrong month page")
    st.markdown("🔁 Duplicate holiday name in PDF")
    st.markdown("❌ Not found in PDF")
    st.markdown("🆕 New holiday not in reference list")
    st.markdown("🟠 Missing holiday name label")
    st.markdown("🔵 Missing date association")
    st.markdown("---")
    st.markdown("**🎨 Design Inference:**")
    st.markdown(
        "The app auto-detects the calendar design type (Desk-Pad, Wall Single, "
        "Wall Three-Month) and applies design-specific extraction settings "
        "(x_tolerance, row_padding, bold-date rule, merge gap) for accuracy."
    )
    st.markdown("---")
    st.markdown("**📋 Unbold Date Rule:**")
    st.markdown(
        "Dates in NON-BOLD font are prev/next month overflow cells. "
        "Holidays from these cells are **never counted** in validation."
    )

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    base_year = st.number_input("Enter Year", min_value=2000, max_value=2100, value=datetime.now().year, step=1)

with col2:
    mode = st.selectbox("Report Type", ["Fiscal", "Academic"], index=0,
                        help="Fiscal = Jan to Dec, Academic = Jul to Jun")

with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    uploaded_pdf = st.file_uploader("Upload Calendar PDF (for validation)", type=["pdf"])
    uploaded_calendar = st.file_uploader(
        "Upload Holiday Calendar File — CSV or Excel (optional)",
        type=["csv", "xlsx", "xls", "xlsm", "xlsb", "ods"],
        help="If uploaded, AI will analyze year/type/pattern and extract the correct holiday table."
    )
    generate_btn = st.button("Generate / Load Calendar and Analyze PDF", type="primary", use_container_width=True)

if generate_btn:
    try:
        missing_libs = validate_required_libraries()
        if missing_libs:
            st.error("Missing libraries: " + ", ".join(missing_libs))
            st.stop()

        use_llm = bool(OPENROUTER_API_KEY and OPENROUTER_API_KEY != "YOUR_OPENROUTER_API_KEY")
        if not use_llm:
            st.warning("⚠️ No valid OpenRouter API key — LLM vision and AI notes disabled. Native extraction + rule-based notes will still run.")

        # ── STEP 1: Build reference calendar ──────────────────────────────
        uploaded_display_df = None
        reference_df = None
        used_uploaded = False
        excel_ai_meta = None

        if uploaded_calendar is not None:
            fname = uploaded_calendar.name.lower()
            try:
                if fname.endswith(".csv"):
                    raw_df = pd.read_csv(uploaded_calendar)
                else:
                    try:
                        raw_df = pd.read_excel(uploaded_calendar, engine="openpyxl")
                    except Exception:
                        try:
                            raw_df = pd.read_excel(uploaded_calendar, engine="xlrd")
                        except Exception:
                            raw_df = pd.read_excel(uploaded_calendar)

                uploaded_display_df = raw_df.copy()
                st.success(f"✅ Uploaded file loaded — {len(raw_df)} rows, {len(raw_df.columns)} columns.")

                with st.spinner("🤖 AI analyzing uploaded file (year, type, design pattern)…"):
                    excel_ai_meta = analyze_excel_with_langchain(raw_df, llm)

                if excel_ai_meta and excel_ai_meta.get("detected_year"):
                    confidence = excel_ai_meta.get("confidence", "Low")
                    confidence_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "⚪")

                    st.markdown("---")
                    st.subheader("🤖 AI Calendar Intelligence Report")

                    ai_cols = st.columns(4)
                    ai_cols[0].metric("📅 Detected Year", str(excel_ai_meta.get("detected_year", "?")))
                    ai_cols[1].metric("🗂️ Calendar Type", excel_ai_meta.get("calendar_type", "Unknown"))
                    ai_cols[2].metric("🖼️ Design Pattern", excel_ai_meta.get("design_pattern", "Unknown"))
                    ai_cols[3].metric("📊 Confidence", f"{confidence_emoji} {confidence}")

                    st.info(
                        f"**📆 Period:** {excel_ai_meta.get('year_range', '?')}\n\n"
                        f"**🔍 AI Notes:** {excel_ai_meta.get('notes', '')}"
                    )
                    st.markdown("---")

                    reference_df = excel_ai_meta["filtered_df"]
                    used_uploaded = True
                    st.success(
                        f"✅ AI extracted **{len(reference_df)} holidays** for "
                        f"**{excel_ai_meta.get('calendar_type')} {excel_ai_meta.get('detected_year')}** "
                        f"({excel_ai_meta.get('year_range')}) — used as reference for PDF validation."
                    )
                else:
                    norm_df, norm_ok = normalize_uploaded_df(raw_df, int(base_year))
                    if norm_ok and not norm_df.empty:
                        reference_df = norm_df
                        used_uploaded = True
                        st.info(f"ℹ️ Uploaded file mapped to standard format ({len(reference_df)} holidays).")
                    else:
                        st.warning("⚠️ Could not auto-detect Holiday/Date columns. Auto-generated calendar will be used instead.")

            except Exception as e:
                st.error(f"❌ Error reading uploaded file: {e}")
                st.info("Falling back to auto-generated calendar.")

        if reference_df is None:
            reference_df = build_report(int(base_year), mode)

            bosses_row = reference_df[reference_df["Holiday"] == "National Bosses Day (US)"]
            if not bosses_row.empty:
                raw_oct16 = date(int(base_year), 10, 16)
                obs = nearest_observed_weekday(raw_oct16)
                if obs.day != 16:
                    st.info(f"ℹ️ **National Bosses Day (US)**: Oct 16 falls on a {raw_oct16.strftime('%A')} in {base_year} "
                            f"→ observed on **{obs.strftime('%A, %B')} {obs.day}** (nearest weekday).")

            st.success(f"✅ Auto-generated calendar — {len(reference_df)} holidays.")

        # ── STEP 2: Display reference data ────────────────────────────────
        st.subheader("📅 Holiday Calendar Data")
        display_df = uploaded_display_df if uploaded_display_df is not None else reference_df
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        if uploaded_display_df is not None and reference_df is not None and used_uploaded:
            with st.expander("📋 AI-Filtered Holiday Reference Table (used for PDF validation)", expanded=False):
                st.dataframe(reference_df, use_container_width=True, hide_index=True)

        # ── STEP 3: PDF Validation ─────────────────────────────────────────
        if uploaded_pdf is not None:
            pdf_bytes = uploaded_pdf.read()

            # ── Stage 1: Infer design type from first page ─────────────────────
            inferred_design_profile = infer_design_type(pdf_bytes, page_num=0)
            design_type = inferred_design_profile.get("design_type", "unknown")
            extraction_cfg = get_design_extraction_config(design_type)

            # ── Stage 2: Build per-page design profiles ─────────────────────────
            page_design_profiles: Dict[int, Dict] = {}
            doc_tmp = fitz.open(stream=pdf_bytes, filetype="pdf")
            for _pg in range(len(doc_tmp)):
                _profile = dict(inferred_design_profile)
                page_design_profiles[_pg] = _profile

            with st.spinner("🔍 Analyzing PDF (native extraction + AI vision + AI notes)…"):
                error_df, all_extractions = validate_calendar_pdf(pdf_bytes, reference_df, use_llm=use_llm)

            # Detect PDF year
            pdf_year_detected = None
            for ext in all_extractions:
                if ext.get("year") and isinstance(ext["year"], int):
                    pdf_year_detected = ext["year"]
                    break

            # ── Run LangGraph quality checks (duplicates, missing, spelling) ──
            quality_results = {
                "duplicates": [], "missing_holidays": [], "spelling_issues": [], "llm_summary": ""
            }
            if LANGGRAPH_AVAILABLE and all_extractions:
                with st.spinner("🔍 Running LangGraph quality checks (duplicates, misplacement & wording/spelling)…"):
                    quality_results = run_pdf_quality_langgraph(
                        all_extractions, reference_df, llm, pdf_year=pdf_year_detected
                    )

            # ── LangGraph summary banner ──
            if quality_results.get("llm_summary"):
                summary_txt = quality_results["llm_summary"]
                if "✅" in summary_txt:
                    st.success(f"🤖 LangGraph QC: {summary_txt}")
                else:
                    st.warning(f"🤖 LangGraph QC: {summary_txt}")

            # ── Collect norm names already shown as wording mistakes ──
            already_in_main_table_as_wording: set = set()
            if not error_df.empty:
                for _, r in error_df.iterrows():
                    if "Wording/Spelling Mistake" in str(r.get("Status", "")):
                        already_in_main_table_as_wording.add(
                            normalize_holiday(str(r.get("Holiday", "")))
                        )

            # ── Merge duplicate rows into main table ──
            for dup in quality_results.get("duplicates", []):
                error_df = pd.concat([error_df, pd.DataFrame([{
                    "Status": "🔁 Duplicate Holiday Name in PDF",
                    "Holiday": dup["holiday"],
                    "Expected Date": "",
                    "Expected Day": "",
                    "Found In PDF": dup["holiday"],
                    "Notes": dup["details"],
                }])], ignore_index=True)

            # ── Merge spelling/wording rows ──
            for spell in quality_results.get("spelling_issues", []):
                canonical = spell.get("correct_name", "")
                norm_canonical = normalize_holiday(canonical)
                if norm_canonical in already_in_main_table_as_wording:
                    continue
                diff_str = make_spelling_diff(spell["extracted_label"], canonical)
                error_df = pd.concat([error_df, pd.DataFrame([{
                    "Status": "✏️ Wording/Spelling Mistake in PDF",
                    "Holiday": canonical,
                    "Expected Date": "",
                    "Expected Day": "",
                    "Found In PDF": spell["extracted_label"],
                    "Notes": (
                        f"WORDING/SPELLING ERROR — {diff_str}. "
                        f"{spell['issue']} (Similarity: {spell['similarity']:.0%})"
                    ),
                }])], ignore_index=True)

            # ── Display Unified Validation Report ─────────────────────────
            st.markdown("---")
            st.subheader("📋 Calendar Holiday Validation Report")

            # ── Colour legend ──
            legend_html = """
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">
              <span style="background:#ccffcc;padding:4px 10px;border-radius:4px;font-size:0.82em;">✅ Exact Match</span>
              <span style="background:#aed6f1;color:#0b3d6b;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">✅ Within Tolerance</span>
              <span style="background:#ff2222;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">✏️ Wording/Spelling Mistake (Correct Date)</span>
              <span style="background:#cc6600;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">✏️ Wording/Spelling Mistake (Wrong Date)</span>
              <span style="background:#ff4444;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">🔴 Wording Mismatch (Same Date)</span>
              <span style="background:#e65100;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">🔴 Wording Mismatch (±N Days)</span>
              <span style="background:#fff3cc;padding:4px 10px;border-radius:4px;font-size:0.82em;">⚠️ Wrong Date</span>
              <span style="background:#ff6600;color:#fff;padding:4px 10px;border-radius:4px;font-size:0.82em;">🗓️ Misplaced</span>
              <span style="background:#ffcccc;padding:4px 10px;border-radius:4px;font-size:0.82em;">❌ Not Found</span>
              <span style="background:#ff9999;color:#7a0000;padding:4px 10px;border-radius:4px;font-size:0.82em;">🆕 New Holiday</span>
              <span style="background:#e8d5f5;color:#5a007a;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">🔁 Duplicate Name</span>
              <span style="background:#ff9800;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">🟠 Missing Holiday Name</span>
              <span style="background:#1565c0;color:#fff;font-weight:bold;padding:4px 10px;border-radius:4px;font-size:0.82em;">🔵 Missing Date</span>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)

            if error_df.empty:
                st.success("✅ No issues detected — all holidays validated!")
            else:
                counts = error_df["Status"].value_counts()

                all_statuses = [
                    ("✅ Verified – Exact Match",                       "✅ Exact Match"),
                    ("✅ Verified – Within ±1 Day",                     "✅ ±1 Day"),
                    ("✅ Verified – Within ±2 Days",                    "✅ ±2 Days"),
                    ("✅ Verified – Within ±3 Days",                    "✅ ±3 Days"),
                    ("✅ Verified – Within ±4 Days",                    "✅ ±4 Days"),
                    ("✏️ Wording/Spelling Mistake – Correct Date",      "✏️ Spelling (Right Date)"),
                    ("✏️ Wording/Spelling Mistake – ±1 Day Off",        "✏️ Spelling ±1d"),
                    ("✏️ Wording/Spelling Mistake – ±2 Days Off",       "✏️ Spelling ±2d"),
                    ("✏️ Wording/Spelling Mistake – ±3 Days Off",       "✏️ Spelling ±3d"),
                    ("✏️ Wording/Spelling Mistake – ±4 Days Off",       "✏️ Spelling ±4d"),
                    ("✏️ Wording/Spelling Mistake in PDF",              "✏️ Spelling (Other)"),
                    ("🔴 Wording Mismatch – Same Date",                 "🔴 Wording (Same Date)"),
                    ("🔴 Wording Mismatch – ±1 Day Off",               "🔴 Wording ±1d"),
                    ("🔴 Wording Mismatch – ±2 Days Off",              "🔴 Wording ±2d"),
                    ("🔴 Wording Mismatch – ±3 Days Off",              "🔴 Wording ±3d"),
                    ("🔴 Wording Mismatch – ±4 Days Off",              "🔴 Wording ±4d"),
                    ("🗓️ Misplaced – Wrong Month Page",                 "🗓️ Misplaced"),
                    ("⚠️ Wrong Date – Needs Review",                    "⚠️ Wrong Date"),
                    ("❌ Not Found in PDF",                             "❌ Not Found"),
                    ("🆕 New Holiday – Not in Reference",               "🆕 New Holiday"),
                    ("🔁 Duplicate Holiday Name in PDF",                "🔁 Duplicate Name"),
                    ("🟠 Missing Holiday Name in PDF",                  "🟠 Missing Name"),
                    ("🔵 Missing Date in PDF",                          "🔵 Missing Date"),
                ]
                present = [(full, short) for full, short in all_statuses if counts.get(full, 0) > 0]
                if present:
                    cols = st.columns(min(len(present), 6))
                    for col, (full, short) in zip(cols, present):
                        col.metric(short, counts.get(full, 0))

                # ── Alert banners ──
                misplaced_count = counts.get("🗓️ Misplaced – Wrong Month Page", 0)
                if misplaced_count:
                    st.markdown(
                        f"""<div style="background-color:#fff3e0;border-left:5px solid #e65100;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#e65100;">🗓️ {misplaced_count} Holiday(s) Found on Wrong Month Page</b>
                        </div>""", unsafe_allow_html=True)

                new_count = counts.get("🆕 New Holiday – Not in Reference", 0)
                if new_count:
                    st.markdown(
                        f"""<div style="background-color:#ffe0e0;border-left:5px solid #cc0000;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#cc0000;">🆕 {new_count} Holiday(s) in PDF Not in Reference List</b>
                        </div>""", unsafe_allow_html=True)

                dup_count = counts.get("🔁 Duplicate Holiday Name in PDF", 0)
                if dup_count:
                    st.markdown(
                        f"""<div style="background-color:#ede7f6;border-left:5px solid #6a0dad;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#6a0dad;">🔁 {dup_count} Holiday Name(s) Appear More Than Once in PDF (same exact name)</b>
                        </div>""", unsafe_allow_html=True)

                spell_correct_date = sum(
                    counts.get(s, 0) for s, _ in all_statuses if "Wording/Spelling Mistake" in s
                )
                if spell_correct_date:
                    st.markdown(
                        f"""<div style="background-color:#ffe8e8;border-left:5px solid #cc0000;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#cc0000;">✏️ {spell_correct_date} Holiday Name(s) Have Wording or Spelling Mistakes in PDF — shown in red below</b>
                        </div>""", unsafe_allow_html=True)

                miss_name_count = counts.get("🟠 Missing Holiday Name in PDF", 0)
                miss_date_count = counts.get("🔵 Missing Date in PDF", 0)
                if miss_name_count:
                    st.markdown(
                        f"""<div style="background-color:#fff3e0;border-left:5px solid #e65100;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#bf360c;">🟠 {miss_name_count} Date Cell(s) Missing Holiday Name in PDF</b>
                        </div>""", unsafe_allow_html=True)
                if miss_date_count:
                    st.markdown(
                        f"""<div style="background-color:#e3f2fd;border-left:5px solid #1565c0;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#1565c0;">🔵 {miss_date_count} Holiday Label(s) with No Associated Date in PDF</b>
                        </div>""", unsafe_allow_html=True)

                wording_mismatch_count = sum(
                    counts.get(s, 0) for s, _ in all_statuses if "Wording Mismatch" in s
                )
                if wording_mismatch_count:
                    st.markdown(
                        f"""<div style="background-color:#ffebee;border-left:5px solid #c62828;padding:10px 14px;border-radius:5px;margin:8px 0;">
                        <b style="color:#c62828;">🔴 {wording_mismatch_count} Holiday(s) Have Different Wording in PDF vs Reference</b>
                        </div>""", unsafe_allow_html=True)

                def highlight_status(row):
                    s = str(row.get("Status", ""))
                    if "Missing Holiday Name" in s:
                        return ["background-color: #ff9800; color: #fff; font-weight: bold"] * len(row)
                    elif "Missing Date" in s:
                        return ["background-color: #1565c0; color: #fff; font-weight: bold"] * len(row)
                    elif "Not Found" in s:
                        return ["background-color: #ffcccc"] * len(row)
                    elif "Misplaced" in s:
                        return ["background-color: #ff6600; color: #fff; font-weight: bold"] * len(row)
                    elif "Wrong Date" in s:
                        return ["background-color: #fff3cc"] * len(row)
                    elif "Wording/Spelling Mistake – Correct Date" in s:
                        return ["background-color: #ff2222; color: #fff; font-weight: bold"] * len(row)
                    elif "Wording/Spelling Mistake" in s:
                        return ["background-color: #cc6600; color: #fff; font-weight: bold"] * len(row)
                    elif "Wording Mismatch – Same Date" in s:
                        return ["background-color: #ff4444; color: #fff; font-weight: bold"] * len(row)
                    elif "Wording Mismatch" in s:
                        return ["background-color: #e65100; color: #fff; font-weight: bold"] * len(row)
                    elif "New Holiday" in s:
                        return ["background-color: #ff9999; color: #7a0000; font-weight: bold"] * len(row)
                    elif "Duplicate" in s:
                        return ["background-color: #e8d5f5; color: #5a007a; font-weight: bold"] * len(row)
                    elif "Within ±1" in s:
                        return ["background-color: #aed6f1; color: #0b3d6b; font-weight: bold"] * len(row)
                    elif "Within" in s:
                        return ["background-color: #d4edda"] * len(row)
                    elif "Exact" in s:
                        return ["background-color: #ccffcc"] * len(row)
                    return [""] * len(row)

                styled = error_df.style.apply(highlight_status, axis=1)
                st.dataframe(styled, use_container_width=True, hide_index=True)
                st.download_button(
                    "⬇️ Download Full Validation Report (CSV)",
                    error_df.to_csv(index=False),
                    "calendar_validation.csv",
                )

            # ── [NEW] VISUAL HOLIDAY GRID (per month, design-aware) ────────
            if show_visual_grid and not error_df.empty:
                st.markdown("---")
                st.subheader("📅 Adaptive Visual Holiday Grid (All Design Patterns)")
                st.caption(
                    "Each month's calendar grid is rendered with colour-coded holiday cells. "
                    "Overflow/unbold dates (prev/next month) are shown in gray and are NOT counted. "
                    "Grid geometry uses AI design inference when available."
                )

                # Group reference_df by (month, year) to know which months to render
                months_to_render: List[Tuple[int, int]] = []
                if not reference_df.empty:
                    for _, row in reference_df.iterrows():
                        try:
                            ts = pd.Timestamp(row["date"])
                            key = (ts.month, ts.year)
                            if key not in months_to_render:
                                months_to_render.append(key)
                        except Exception:
                            continue

                # Also add months from PDF extractions not in reference
                for ext in all_extractions:
                    em = ext.get("month")
                    ey = ext.get("year")
                    if em and ey:
                        key = (em, ey)
                        if key not in months_to_render:
                            months_to_render.append(key)

                months_to_render.sort()

                # Build page number → (month, year) map from design profiles or page metadata
                page_month_year: Dict[int, Tuple[int, int]] = {}
                if page_design_profiles:
                    # Use page metadata from extract step
                    try:
                        doc_meta_tmp = fitz.open(stream=pdf_bytes, filetype="pdf")
                        pages_meta_tmp = extract_pdf_pages_metadata(pdf_bytes)
                        for pm in pages_meta_tmp:
                            pg_idx = pm["page"] - 1
                            if pm.get("month") and pm.get("year"):
                                page_month_year[pg_idx] = (pm["month"], pm["year"])
                    except Exception:
                        pass

                for month_num, year_num in months_to_render:
                    month_name_str = MONTH_NAMES[month_num - 1]

                    # Find the best design profile for this month's page
                    dp_for_month: Dict = {}
                    for pg_idx, (pm_m, pm_y) in page_month_year.items():
                        if pm_m == month_num and pm_y == year_num:
                            dp_for_month = page_design_profiles.get(pg_idx, {})
                            break

                    # Filter validation rows for this month
                    month_val_df = pd.DataFrame()
                    if not error_df.empty:
                        def _row_matches_month(r):
                            try:
                                ed = str(r.get("Expected Date", ""))
                                if ed:
                                    ts = pd.Timestamp(ed)
                                    return ts.month == month_num and ts.year == year_num
                            except Exception:
                                pass
                            return False
                        month_val_df = error_df[error_df.apply(_row_matches_month, axis=1)].copy()

                    # Filter extractions for this month
                    month_extractions = [
                        e for e in all_extractions
                        if e.get("month") == month_num and e.get("year") == year_num
                    ]

                    with st.expander(
                        f"{'🎨 ' if dp_for_month.get('confidence', 0) >= 0.75 else ''}📅 {month_name_str} {year_num} — Visual Grid",
                        expanded=(months_to_render.index((month_num, year_num)) < 3),
                    ):
                        # Design badge
                        if dp_for_month and dp_for_month.get("confidence", 0) >= 0.5:
                            st.markdown(_design_badge(dp_for_month), unsafe_allow_html=True)
                        elif not dp_for_month:
                            st.info("ℹ️ No design profile available — using calendar-math overflow fallback.")

                        # Render grid
                        grid_html = generate_holiday_visual_grid_html(
                            month=month_num,
                            year=year_num,
                            validation_df=month_val_df,
                            design_profile=dp_for_month,
                            page_extractions=month_extractions,
                        )
                        st.components.v1.html(grid_html, height=600, scrolling=True)

                        # Per-month issue summary
                        if not month_val_df.empty:
                            issue_rows = month_val_df[
                                ~month_val_df["Status"].str.contains("Exact Match|Within", na=False)
                            ]
                            if not issue_rows.empty:
                                st.markdown(
                                    f'<div style="background:#fff3f3;border-left:4px solid #dc3545;'
                                    f'padding:8px 12px;border-radius:4px;font-size:.82em;margin-top:8px;">'
                                    f'⚠️ <b>{len(issue_rows)} issue(s)</b> in {month_name_str} {year_num}:'
                                    + ", ".join(
                                        f'<b>{s}</b> ({n}×)'
                                        for s, n in issue_rows["Status"].value_counts().items()
                                    )
                                    + "</div>",
                                    unsafe_allow_html=True,
                                )

        elif uploaded_pdf is None:
            st.info("📎 Upload a Calendar PDF above and click the button again to run validation.")

        # ── STEP 4: Downloads ──────────────────────────────────────────────
        st.markdown("---")
        dl_df = reference_df
        csv_bytes = dl_df.to_csv(index=False).encode("utf-8")
        excel_bytes = to_excel_bytes(dl_df)
        dc1, dc2 = st.columns(2)
        dc1.download_button("⬇️ Download Reference Calendar (CSV)", csv_bytes, "calendar.csv")
        dc2.download_button("⬇️ Download Reference Calendar (Excel)", excel_bytes, "calendar.xlsx")

    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)
