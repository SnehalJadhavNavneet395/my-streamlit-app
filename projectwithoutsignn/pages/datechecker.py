
import io
import os
import re
import difflib
import calendar
import html as html_module
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any, TypedDict

import fitz  # PyMuPDF
import base64
import requests
from PIL import Image
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as _st_components
import threading
import time
import socket as _socket

# ── LangChain / LangGraph ──────────────────────────────────────────────────────
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END

# ======================================================
# CONFIG
# ======================================================
APP_TITLE = "Calendar QC Auditor — Zero Defect Standard"
APP_ICON  = "📅"

OPENROUTER_API_KEY = "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"
MODEL        = "openai/gpt-4o-mini"
ZOOM_FACTOR  = 4.0

BOLD_FONT_KEYWORDS = ["bold", "extrabold", "heavy", "black", "demi", "semibold"]

MONTH_MAP = {m.lower(): i for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"], 1)}

MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]

DAY_HEADERS_SHORT = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat",
                     "Su","Mo","Tu","We","Th","Fr","Sa","S","M","T","W","F"}
DAY_HEADERS_LONG  = {"Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"}
ALL_DAY_HEADERS   = DAY_HEADERS_SHORT | DAY_HEADERS_LONG

# ======================================================
# DESIGN FAMILY LIBRARY  (session-level cache)
# Grows as new designs are encountered.  Reused when confidence is high.
# ======================================================
# ── Flask API thread (mirrors dashboard.py pattern, port 5002) ──────────────
_DATECHECKER_API_PORT = 5002

def _start_datechecker_api():
    s = _socket.socket()
    try:
        s.bind(("0.0.0.0", _DATECHECKER_API_PORT)); s.close()
    except OSError:
        return  # already running
    from flask import Flask, jsonify, request as freq
    api = Flask("datechecker_api")

    @api.after_request
    def _cors(resp):
        resp.headers["Access-Control-Allow-Origin"]  = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @api.route("/api/<path:p>", methods=["OPTIONS"])
    def _preflight(p):
        r = jsonify(ok=True)
        r.headers["Access-Control-Allow-Origin"]  = "*"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return r, 200

    @api.get("/api/status")
    def status():
        return jsonify(ok=True, service="AI DateChecker", port=_DATECHECKER_API_PORT)

    @api.get("/api/ping")
    def ping():
        return jsonify(ok=True, msg="pong")

    api.run(host="0.0.0.0", port=_DATECHECKER_API_PORT, debug=False, use_reloader=False)


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

# ======================================================
# CALENDAR QC KNOWLEDGE BASE  (for RAG)
# ======================================================
CALENDAR_QC_RULES = [
    "A leap year occurs when the year is divisible by 4, except centuries, which must be divisible by 400. "
    "In a leap year, February must contain exactly 29 days.",
    "In a non-leap year, February must contain exactly 28 days. Day 29 must NOT appear.",
    "All month date numbers must appear sequentially from 1 to the last day of the month without any gaps.",
    "Date numbers must appear in left-to-right, top-to-bottom reading order matching the calendar grid layout.",
    "Overflow or filler dates (dates belonging to the previous or next month shown at the edges of the grid) "
    "must always be printed in non-bold, light font weight.",
    "Slash dates such as '23/30' represent two weeks in one cell. The second number must equal the first plus 7.",
    "The second number in a slash date must not exceed the total number of days in that month.",
    "Day-of-week column headers must be spelled correctly: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday "
    "or their standard abbreviations Sun Mon Tue Wed Thu Fri Sat.",
    "The month name in the header must be spelled correctly and match the calendar month being displayed.",
    "Holiday and event text labels must be fully visible within their cells and must not be truncated by cell borders.",
    "Holiday labels alignment: all holiday text labels should be positioned at a consistent vertical and horizontal "
    "offset within their respective date cells across the entire grid.",
    "Date number alignment: all date numbers within the same column should be left-aligned or right-aligned consistently.",
    "US calendar week starts on Sunday. The first column must be Sunday.",
    "Grid completeness: every week row must have exactly 7 cells corresponding to the 7 days of the week.",
    "Each month must have a visible, correctly spelled month name header above the date grid.",
    "Year must be clearly visible and correctly printed on each calendar page.",
    "Color contrast of date numbers and holiday text must be sufficient for readability against the cell background.",
    "Bold dates indicate current month. Non-bold or lighter dates indicate overflow from adjacent months.",
    "Holiday label position consistency: all holiday labels should appear at the same relative position "
    "(top, bottom, left, right) within their cells uniformly across the entire calendar grid.",
]

@st.cache_resource
def build_rag_retriever() -> BM25Retriever:
    docs = [Document(page_content=rule, metadata={"id": i})
            for i, rule in enumerate(CALENDAR_QC_RULES)]
    retriever = BM25Retriever.from_documents(docs, k=5)
    return retriever


def retrieve_relevant_rules(retriever: BM25Retriever, query: str) -> str:
    docs = retriever.invoke(query)
    return "\n".join(f"- {d.page_content}" for d in docs)


# ======================================================
# LANGCHAIN LLM SETUP (OpenRouter)
# ======================================================
@st.cache_resource
def get_llm(max_tokens: int = 4000) -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=500,
    )


# ======================================================
# LANGGRAPH  — Audit Agent State & Graph
# ======================================================
class AuditState(TypedDict):
    pdf_bytes:      bytes
    page_num:       int
    use_ai:         bool
    structure:      Dict
    design_profile: Dict          # ← NEW: learned layout template
    year:           Optional[int]
    month:          Optional[int]
    native_results: Dict
    rag_context:    str
    ai_results:     Dict
    final_result:   Dict


# ─── Node 1: Extract ──────────────────────────────────
def node_extract(state: AuditState) -> AuditState:
    doc  = fitz.open(stream=state["pdf_bytes"], filetype="pdf")
    page = doc[state["page_num"]]
    structure = extract_calendar_structure(page)
    year  = structure.get("year") or detect_page_year(page)
    month = (structure["month_header"]["month"]
             if structure.get("month_header")
             else detect_page_month(page, structure["date_numbers"]))
    return {**state, "structure": structure, "year": year, "month": month}


# ─── Node 2: Design Inference (NEW) ─────────────────
def node_design_inference(state: AuditState) -> AuditState:
    """
    AI Vision reads the page and returns a design-profile JSON that describes
    the calendar's layout family, grid geometry, overflow cell counts, date
    rendering mode, and typography anchors.  The profile is then merged into
    the extracted structure so all downstream checks are design-aware.
    """
    if not state.get("use_ai"):
        return {**state, "design_profile": {}}

    try:
        img    = render_pdf_page(state["pdf_bytes"], state["page_num"])
        b64    = image_to_base64(img)
        profile = ai_infer_design_template(b64)
    except Exception as e:
        profile = {
            "design_type": "unknown",
            "error": str(e),
            "confidence": 0.0,
        }

    # Merge AI layout knowledge back into the extracted structure
    merged_structure = merge_native_and_ai_structure(state["structure"], profile)

    return {**state, "design_profile": profile, "structure": merged_structure}


# ─── Node 3: Native Checks ───────────────────────────
def node_native_checks(state: AuditState) -> AuditState:
    structure = state["structure"]
    year      = state["year"]
    month     = state["month"]
    if not year or not month:
        return {**state, "native_results": {}}
    native = {
        "leap_year_check":       native_leap_year_check(structure, year, month),
        "sequential_continuity": native_sequential_continuity(structure, year, month),
        "date_misplacement":     native_date_misplacement(structure, year, month),
        "data_alignment":        native_data_alignment(structure),
        "slash_dates":           native_slash_dates(structure, year, month),
        "non_bold_overflow":     native_non_bold_overflow(structure, year, month),
        "spelling":              native_spelling(structure, month),
        "holiday_alignment":     native_holiday_alignment(structure),
    }
    return {**state, "native_results": native}


# ─── Node 4: RAG Retrieve ────────────────────────────
def node_rag_retrieve(state: AuditState) -> AuditState:
    if not state.get("year") or not state.get("month"):
        return {**state, "rag_context": ""}
    retriever = build_rag_retriever()
    m_name    = month_name_for(state["month"])
    query     = (f"Calendar audit {m_name} {state['year']} leap year sequential "
                 "dates alignment spelling holiday overflow bold")
    context   = retrieve_relevant_rules(retriever, query)
    return {**state, "rag_context": context}


# ─── Node 5: AI Vision Audit ─────────────────────────
def node_ai_vision(state: AuditState) -> AuditState:
    if not state.get("use_ai") or not state.get("year") or not state.get("month"):
        return {**state, "ai_results": {}}
    try:
        img = render_pdf_page(state["pdf_bytes"], state["page_num"])
        b64 = image_to_base64(img)
        ai  = ai_audit_page_full(
            b64,
            month_name_for(state["month"]),
            state["year"],
            days_in_month(state["year"], state["month"]),
            is_leap_year(state["year"]),
            state.get("rag_context", ""),
            state.get("design_profile", {}),   # ← pass design context
        )
    except Exception as e:
        ai = {"error": str(e)}
    return {**state, "ai_results": ai}


# ─── Node 6: Synthesize ──────────────────────────────
def node_synthesize(state: AuditState) -> AuditState:
    year   = state.get("year")
    month  = state.get("month")
    native = state.get("native_results", {})
    ai     = state.get("ai_results", {})

    if not year or not month:
        result = {
            "page":           state["page_num"] + 1,
            "month": month, "year": year,
            "error":          "Could not detect month/year for this page.",
            "overall_status": "UNKNOWN",
            "design_profile": state.get("design_profile", {}),
        }
        return {**state, "final_result": result}

    m_name   = month_name_for(month)
    leap     = is_leap_year(year)
    exp_days = days_in_month(year, month)

    def priority(s: str) -> int:
        return {"FAIL": 3, "WARN": 2, "PASS": 1, "N/A": 0, "UNKNOWN": 0}.get(s, 0)

    def merge_status(key: str) -> str:
        ns  = native.get(key, {}).get("status", "N/A")
        if key == "date_misplacement":
            if ns not in ("N/A", "UNKNOWN"):
                return ns
            as_ = ai.get(key, {}).get("status", "N/A") if isinstance(ai, dict) else "N/A"
            return as_ if priority(as_) > priority(ns) else ns
        as_ = ai.get(key, {}).get("status", "N/A") if isinstance(ai, dict) else "N/A"
        return ns if priority(ns) >= priority(as_) else as_

    check_statuses = {c: merge_status(c) for c in CHECKS}
    has_fail = any(v == "FAIL" for v in check_statuses.values())
    has_warn = any(v == "WARN" for v in check_statuses.values())
    overall  = "FAIL" if has_fail else ("WARN" if has_warn else "PASS")

    result = {
        "page":           state["page_num"] + 1,
        "month":          month,
        "month_name":     m_name,
        "year":           year,
        "is_leap_year":   leap,
        "expected_days":  exp_days,
        "native":         native,
        "ai":             ai,
        "check_statuses": check_statuses,
        "overall_status": overall,
        "design_profile": state.get("design_profile", {}),   # ← carry forward
    }
    return {**state, "final_result": result}


# ─── Build the LangGraph ─────────────────────────────
@st.cache_resource
def build_audit_graph():
    graph = StateGraph(AuditState)
    graph.add_node("extract",          node_extract)
    graph.add_node("design_inference", node_design_inference)   # NEW
    graph.add_node("native_checks",    node_native_checks)
    graph.add_node("rag_retrieve",     node_rag_retrieve)
    graph.add_node("ai_vision",        node_ai_vision)
    graph.add_node("synthesize",       node_synthesize)

    graph.set_entry_point("extract")
    graph.add_edge("extract",          "design_inference")      # NEW edge
    graph.add_edge("design_inference", "native_checks")         # NEW edge
    graph.add_edge("native_checks",    "rag_retrieve")
    graph.add_edge("rag_retrieve",     "ai_vision")
    graph.add_edge("ai_vision",        "synthesize")
    graph.add_edge("synthesize",       END)

    return graph.compile()


def audit_page_agent(pdf_bytes: bytes, page_num: int, use_ai: bool = True) -> Dict:
    agent = build_audit_graph()
    initial_state: AuditState = {
        "pdf_bytes":      pdf_bytes,
        "page_num":       page_num,
        "use_ai":         use_ai,
        "structure":      {},
        "design_profile": {},       # ← NEW
        "year":           None,
        "month":          None,
        "native_results": {},
        "rag_context":    "",
        "ai_results":     {},
        "final_result":   {},
    }
    final_state = agent.invoke(initial_state)
    return final_state["final_result"]


# ======================================================
# BASIC HELPERS
# ======================================================

def is_leap_year(year: int) -> bool:
    return calendar.isleap(year)


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def month_name_for(month: int) -> str:
    return MONTH_NAMES[month - 1] if 1 <= month <= 12 else "Unknown"


def is_bold_span(span: Dict) -> bool:
    flags = span.get("flags", 0)
    font  = span.get("font", "").lower()
    return bool(flags & 16) or any(kw in font for kw in BOLD_FONT_KEYWORDS)


def render_pdf_page(pdf_bytes: bytes, page_number: int) -> Image.Image:
    doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number]
    mat  = fitz.Matrix(ZOOM_FACTOR, ZOOM_FACTOR)
    pix  = page.get_pixmap(matrix=mat)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    # Resize very large images to keep token cost reasonable
    w, h = img.size
    max_dim = 1800
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def extract_json_from_text(text: str) -> Any:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    for start_ch, end_ch in [('{', '}'), ('[', ']')]:
        start = text.find(start_ch)
        end   = text.rfind(end_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
    return None


# ======================================================
# ── NEW: AI DESIGN TEMPLATE INFERENCE ─────────────────
# ======================================================

def ai_infer_design_template(image_b64: str) -> Dict:
    """
    Calls GPT-4o-mini vision to analyze the page layout and return a
    structured design-profile JSON.  This profile drives the adaptive
    visual grid renderer and informs all downstream checks.
    """
    prompt = """You are an expert calendar layout analyst for a printing company.
Carefully examine this calendar page image and return ONLY a valid JSON object — no prose, no markdown.

Identify every visual design feature and return this exact structure:
{
  "design_type": "deskpad|wall_single|wall_three_month|wall_large_format|mini_wall|digital|unknown",
  "page_orientation": "landscape|portrait|square",
  "week_start": "Sunday|Monday",
  "num_columns": 7,
  "num_rows": 5,
  "month_count": 1,
  "months_shown": ["January 2028"],
  "date_rendering_mode": "single|slash|stacked|mixed",
  "overflow_prev_cells": 3,
  "overflow_next_cells": 2,
  "column_order": ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"],
  "has_mini_calendar": false,
  "has_notes_area": false,
  "holiday_label_anchor": "top-left|top-right|bottom-left|bottom-right|top-center|bottom-center|none",
  "date_number_anchor": "top-left|top-right|top-center|bottom-left|bottom-right",
  "grid_style": "lined|bordered|open|minimal|shadowed",
  "cell_aspect_ratio": "square|tall|wide",
  "three_month_layout": "vertical_stack|horizontal_row|primary_plus_mini",
  "confidence": 0.95,
  "layout_notes": "Brief plain-text description of notable design features"
}

Definitions:
- overflow_prev_cells: number of date cells at the START of the first row showing PREVIOUS month's dates (0 if month starts on Sunday)
- overflow_next_cells: number of date cells at the END of the last row showing NEXT month's dates (0 if month ends on Saturday)
- num_rows: total calendar grid rows (including overflow rows, typically 5 or 6)
- month_count: 1 for single-month page, 3 for three-month view page, etc.
- date_rendering_mode: "slash" if cells like "23/30" are visible, "stacked" if two date numbers are stacked vertically in one cell, "mixed" if both exist, "single" if all cells have exactly one date number
- three_month_layout: only relevant when month_count > 1; describe how the months are arranged
- For a three-month view page, months_shown should list all visible month names

Return ONLY valid JSON. Do not add any text outside the JSON object."""

    try:
        llm = get_llm(max_tokens=800)
        messages = [
            SystemMessage(content="You are a calendar layout analyst. Return only valid JSON."),
            HumanMessage(content=[
                {"type": "text",      "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]),
        ]
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw, list):
            raw = " ".join(item.get("text", "") for item in raw if isinstance(item, dict))
    except Exception:
        raw = _call_llm_raw_simple(image_b64, prompt, max_tokens=800)

    parsed = extract_json_from_text(raw)
    if parsed and isinstance(parsed, dict):
        # Normalise key fields
        parsed.setdefault("design_type",          "wall_single")
        parsed.setdefault("week_start",            "Sunday")
        parsed.setdefault("num_columns",           7)
        parsed.setdefault("num_rows",              6)
        parsed.setdefault("month_count",           1)
        parsed.setdefault("date_rendering_mode",   "single")
        parsed.setdefault("overflow_prev_cells",   None)
        parsed.setdefault("overflow_next_cells",   None)
        parsed.setdefault("confidence",            0.8)
        parsed.setdefault("layout_notes",          "")
        return parsed

    # Silent fallback
    return {
        "design_type": "unknown",
        "confidence":  0.0,
        "_inference_failed": True,
    }


def _call_llm_raw_simple(image_b64: str, prompt: str, max_tokens: int = 800) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text",      "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]}],
        "temperature": 0, "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload, timeout=60,
        )
        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            return str(content).strip()
    except Exception:
        pass
    return ""


# ======================================================
# ── NEW: MERGE NATIVE + AI STRUCTURE ──────────────────
# ======================================================

def merge_native_and_ai_structure(native: Dict, profile: Dict) -> Dict:
    """
    Combines PyMuPDF text-extracted data (precise numbers/positions) with
    the AI-inferred design profile (layout geometry & rendering mode).

    Strategy:
    - Numbers/text/positions always come from PyMuPDF (ground truth)
    - Rendering mode (slash/stacked/single) validated against AI profile
    - Overflow tagging refined using AI's overflow_prev_cells count
    - Week-start awareness from AI profile
    """
    if not native or not profile or profile.get("confidence", 0) < 0.5:
        return native

    merged = dict(native)

    # ── 1. Re-tag overflow dates using AI's overflow count ─────────────
    ai_prev = profile.get("overflow_prev_cells")
    date_nums = list(native.get("date_numbers", []))

    if ai_prev is not None and isinstance(ai_prev, (int, float)) and date_nums:
        ai_prev = int(ai_prev)
        # Sort by position (top-left reading order)
        sorted_dates = sorted(date_nums, key=lambda d: (d.get("y0", 0), d.get("x0", 0)))
        # First ai_prev non-bold dates in the first row are overflow
        first_row_y = sorted_dates[0]["y0"] if sorted_dates else 0
        row_thresh  = 20.0
        first_row   = [d for d in sorted_dates if abs(d.get("y0", 0) - first_row_y) <= row_thresh]
        non_bold_first = [d for d in first_row if not d.get("bold", True)]
        # Mark those as overflow
        overflow_ids = {id(d) for d in non_bold_first[:ai_prev]}
        updated = []
        for d in date_nums:
            if id(d) in overflow_ids:
                updated.append({**d, "is_overflow": True})
            else:
                updated.append(d)
        merged["date_numbers"] = updated

    # ── 2. Note date rendering mode from AI for downstream checks ──────
    merged["_ai_rendering_mode"] = profile.get("date_rendering_mode", "single")
    merged["_ai_week_start"]     = profile.get("week_start", "Sunday")
    merged["_ai_design_type"]    = profile.get("design_type", "unknown")
    merged["_ai_month_count"]    = profile.get("month_count", 1)
    merged["_ai_column_order"]   = profile.get("column_order",
                                               ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"])

    # ── 3. For three-month views, tag secondary-month dates ────────────
    month_count = profile.get("month_count", 1)
    if month_count > 1:
        merged["_is_multi_month"] = True
        merged["_secondary_months"] = profile.get("months_shown", [])

    return merged


# ======================================================
# NATIVE PDF EXTRACTION
# ======================================================

def detect_font_size_ranges(page) -> Tuple[float, float, float, float]:
    all_sizes = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if t and len(t) <= 40:
                    all_sizes.append(span["size"])
    if not all_sizes:
        return 14.0, 5.0, 14.0, 4.0
    all_sizes.sort()
    max_sz    = max(all_sizes)
    date_min  = max(12.0, max_sz * 0.55)
    label_max = date_min - 0.5
    label_min = max(4.0, min(all_sizes) + 0.5) if len(all_sizes) > 5 else 4.0
    return date_min, label_min, label_max, 4.0


def extract_all_spans_from_page(page) -> List[Dict]:
    spans = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                t = span["text"].strip()
                if not t:
                    continue
                bbox = span["bbox"]
                spans.append({
                    "text":  t,
                    "raw":   span["text"],
                    "font":  span.get("font", ""),
                    "size":  span.get("size", 0),
                    "flags": span.get("flags", 0),
                    "bold":  is_bold_span(span),
                    "bbox":  bbox,
                    "x":     (bbox[0] + bbox[2]) / 2,
                    "y":     (bbox[1] + bbox[3]) / 2,
                    "x0":    bbox[0], "y0": bbox[1],
                    "x1":    bbox[2], "y1": bbox[3],
                    "color": span.get("color", 0),
                })
    return spans


def _is_day_of_year_counter(text: str, sz: float, bold: bool) -> bool:
    m = re.match(r'^(\d{1,3})/(\d{1,3})$', text)
    if not m:
        return False
    d1, d2 = int(m.group(1)), int(m.group(2))
    if d2 > 31:
        return True
    if sz < 8.0 and not bold:
        return True
    if 360 <= (d1 + d2) <= 370:
        return True
    return False


def _detect_stacked_pairs(date_numbers: List[Dict]) -> List[Dict]:
    if not date_numbers:
        return date_numbers

    y_vals = [d["y0"] for d in date_numbers if not d.get("is_slash")]
    if not y_vals:
        return date_numbers
    y_span = max(y_vals) - min(y_vals)
    estimated_row_h = max(y_span / 6.0, 20.0)

    col_thresh = 24.0
    cols: Dict[float, List[Dict]] = {}
    for d in date_numbers:
        if d.get("is_slash"):
            continue
        placed = False
        for cx in list(cols.keys()):
            if abs(d["x0"] - cx) <= col_thresh:
                cols[cx].append(d)
                placed = True
                break
        if not placed:
            cols[d["x0"]] = [d]

    stacked_pairs: Dict[int, int] = {}

    for cx, col_dates in cols.items():
        if len(col_dates) < 2:
            continue
        col_sorted = sorted(col_dates, key=lambda d: d["y0"])
        for i in range(len(col_sorted) - 1):
            d1 = col_sorted[i]
            d2 = col_sorted[i + 1]
            if d2["day"] != d1["day"] + 7:
                continue
            y_diff = d2["y0"] - d1["y0"]
            if y_diff < estimated_row_h * 0.70:
                stacked_pairs[id(d1)] = d2["day"]

    absorbed_ids = set()
    result = []
    for d in date_numbers:
        if id(d) in absorbed_ids:
            continue
        if id(d) in stacked_pairs:
            slash_day = stacked_pairs[id(d)]
            new_d = {**d, "is_slash": True, "slash_day": slash_day, "is_stacked": True}
            result.append(new_d)
            for d2 in date_numbers:
                if d2["day"] == slash_day and abs(d2["x0"] - d["x0"]) <= col_thresh:
                    absorbed_ids.add(id(d2))
                    break
        else:
            result.append(d)

    return result


def extract_calendar_structure(page) -> Dict:
    date_min_sz, label_min_sz, label_max_sz, _ = detect_font_size_ranges(page)
    spans = extract_all_spans_from_page(page)

    date_numbers:   List[Dict] = []
    holiday_labels: List[Dict] = []
    month_header:   Optional[Dict] = None
    year_found:     Optional[int]  = None
    day_headers:    List[Dict] = []
    other_text:     List[Dict] = []

    for sp in spans:
        text = sp["text"]
        sz   = sp["size"]
        bold = sp["bold"]

        m = re.search(r'\b(20\d{2})\b', text)
        if m and not year_found:
            year_found = int(m.group(1))

        text_lower = text.lower()
        for mname, mnum in MONTH_MAP.items():
            if mname in text_lower and sz >= 10:
                if month_header is None or sz > month_header.get("size", 0):
                    month_header = {"month": mnum, "text": text, "size": sz, **sp}

        if text in ALL_DAY_HEADERS:
            day_headers.append(sp)
            continue

        is_date_sized = sz >= date_min_sz
        is_bold_date  = bold and sz >= 8.0
        if (is_date_sized or is_bold_date) and re.match(r'^\d{1,2}$', text):
            day = int(text)
            if 1 <= day <= 31:
                date_numbers.append({**sp, "day": day})
            continue

        slash_m = re.match(r'^(\d{1,2})/(\d{1,2})$', text)
        if slash_m and (is_date_sized or is_bold_date):
            d1, d2 = int(slash_m.group(1)), int(slash_m.group(2))
            if (1 <= d1 <= 31 and 1 <= d2 <= 31
                    and not _is_day_of_year_counter(text, sz, bold)):
                date_numbers.append({**sp, "day": d1, "slash_day": d2, "is_slash": True})
            continue

        slash_large = re.match(r'^(\d{1,3})/(\d{2,3})$', text)
        if slash_large:
            d2_val = int(slash_large.group(2))
            if d2_val > 31:
                other_text.append(sp)
                continue

        in_range = (label_min_sz <= sz <= label_max_sz) or (4.0 <= sz <= 14.0)
        if in_range and len(text) >= 3:
            if re.match(r'^[\d/\s\t]+$', text):
                continue
            clean = re.sub(r'[\d\s/\t]', '', text)
            if len(clean) >= 3:
                holiday_labels.append(sp)
                continue

        other_text.append(sp)

    if date_numbers:
        deduped: Dict = {}
        for d in date_numbers:
            key = (d["day"], round(d["x"] / 10), round(d["y0"] / 10))
            if key not in deduped or d["bold"]:
                deduped[key] = d
        date_numbers = list(deduped.values())

    date_numbers = _tag_overflow_dates(date_numbers)
    date_numbers = _detect_stacked_pairs(date_numbers)

    return {
        "date_numbers":   date_numbers,
        "holiday_labels": holiday_labels,
        "month_header":   month_header,
        "year":           year_found,
        "day_headers":    day_headers,
        "other_text":     other_text,
        "all_spans":      spans,
    }


def _tag_overflow_dates(date_numbers: List[Dict]) -> List[Dict]:
    if not date_numbers:
        return date_numbers

    y_vals = [d["y0"] for d in date_numbers]
    min_y  = min(y_vals)
    max_y  = max(y_vals)
    y_span = max_y - min_y
    row_h  = max(y_span / 6.0, 15.0)

    tagged = []
    for d in date_numbers:
        is_overflow = False
        if not d.get("bold", True):
            in_first_row = (d["y0"] - min_y) <= row_h * 1.2
            in_last_row  = (max_y - d["y0"]) <= row_h * 1.2
            if in_first_row and d["day"] >= 25:
                is_overflow = True
            if in_last_row and d["day"] <= 7:
                is_overflow = True
        tagged.append({**d, "is_overflow": is_overflow})

    return tagged


def detect_page_year(page) -> Optional[int]:
    best_year = None
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"]
                range_m = re.search(r'\b(20\d{2})[-/](20\d{2}|\d{2})\b', text)
                if range_m:
                    return int(range_m.group(1))
                m = re.search(r'\b(20\d{2})\b', text)
                if m and not best_year:
                    best_year = int(m.group(1))
    return best_year


def detect_page_month(page, date_numbers: List[Dict]) -> Optional[int]:
    if not date_numbers:
        return None
    grid_y_top = min(d["y0"] for d in date_numbers)
    candidates = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                txt  = span["text"].strip().lower()
                sz   = span["size"]
                bbox = span["bbox"]
                cy   = (bbox[1] + bbox[3]) / 2
                if sz < 10:
                    continue
                for mname, mnum in MONTH_MAP.items():
                    if mname in txt:
                        candidates.append({
                            "month": mnum, "y": cy, "size": sz,
                            "dist_above": grid_y_top - cy,
                        })
    if not candidates:
        return None
    above = [c for c in candidates if c["dist_above"] > -50]
    if above:
        return sorted(above, key=lambda c: (c["dist_above"], -c["size"]))[0]["month"]
    return sorted(candidates, key=lambda c: -c["size"])[0]["month"]


# ======================================================
# AI VISION AUDIT (LangChain + RAG + Design context)
# ======================================================

def ai_audit_page_full(image_b64: str, month_name: str, year: int,
                       expected_days: int, is_leap: bool,
                       rag_context: str = "",
                       design_profile: Dict = {}) -> Dict:
    leap_note = "a LEAP YEAR — February MUST have 29 days" if is_leap else "NOT a leap year"
    feb_note  = (
        "Day 29 MUST be present in the grid." if month_name == "February" and is_leap
        else "Day 29 must NOT appear in February." if month_name == "February" else ""
    )

    rag_section = ""
    if rag_context:
        rag_section = f"\nRELEVANT QC RULES (retrieved from knowledge base):\n{rag_context}\n"

    # ── Build design-context section from inferred profile ───────────
    design_section = ""
    if design_profile and design_profile.get("confidence", 0) >= 0.5:
        dt    = design_profile.get("design_type", "unknown")
        dr    = design_profile.get("date_rendering_mode", "unknown")
        ws    = design_profile.get("week_start", "Sunday")
        nr    = design_profile.get("num_rows", "unknown")
        mc    = design_profile.get("month_count", 1)
        notes = design_profile.get("layout_notes", "")
        col_o = design_profile.get("column_order", ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"])
        design_section = f"""
DESIGN PROFILE (AI-inferred for this page):
- Design family: {dt}
- Date rendering mode: {dr} (single numbers | slash like 23/30 | stacked two numbers in one cell | mixed)
- Week starts on: {ws}
- Grid rows: {nr}
- Months on page: {mc}
- Column order: {col_o}
- Layout notes: {notes}
Use this profile to correctly interpret the grid geometry. For example:
  - If rendering_mode is "slash" or "stacked", expect dual-date cells and do NOT flag them as missing.
  - If month_count > 1, only audit the PRIMARY/LARGEST month grid in detail.
  - Column order tells you which day of the week each column represents.
"""

    import calendar as cal_mod
    month_num = MONTH_NAMES.index(month_name) + 1 if month_name in MONTH_NAMES else 1
    dow_ref_lines = []
    for d in range(1, expected_days + 1):
        wd = cal_mod.weekday(year, month_num, d)
        dow_name = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][wd]
        dow_ref_lines.append(f"  Day {d} = {dow_name}")
    dow_reference = "\n".join(dow_ref_lines)

    prompt = f"""You are a Senior Quality Control Auditor AI for a mass-production calendar printing company.
This is the calendar page for {month_name} {year}.
{rag_section}{design_section}
CRITICAL FACTS:
- {year} is {leap_note}.
- {month_name} {year} has exactly {expected_days} days.
- {feb_note}
- Week starts on SUNDAY (standard US desk-pad layout) unless the design profile says otherwise.
- This may be a Regular Year (RY), Academic Year (AY), or Fiscal Year calendar — treat all as valid.

REFERENCE — Correct day-of-week for each date in {month_name} {year}:
{dow_reference}

IMPORTANT: The calendar grid may show filler/overflow dates from the previous or next month in the
first and/or last row. These are expected and should appear in NON-BOLD (light) font.
DO NOT count overflow dates as missing or misplaced current-month dates.
Only flag overflow dates if they appear in BOLD font weight (that is the actual error).

IMPORTANT ABOUT DUAL-DATE CELLS (SLASH DATES AND STACKED DATES):
Some desk-pad calendars combine two dates into one cell when space is limited. This appears in TWO ways:
  1. SLASH FORMAT: "23/30" printed as a single text (the slash is visible)
  2. STACKED FORMAT: "23" printed at the top of the cell and "30" printed below it in the SAME cell
     (no slash character — they are stacked one above the other within a single grid cell)
BOTH formats are VALID layouts. DO NOT flag them as missing or misplaced.
For stacked cells: report them in slash_dates.found as "23/30" format.
They count as BOTH dates being present.

IMPORTANT ABOUT DAY-OF-YEAR COUNTERS:
Some calendars print very small text like "1/365", "45/321", "200/166" beside each date.
These are day-of-year counters — NOT slash dates. Do NOT include them in slash_dates.found.
The second number in day-of-year counters is always > 31 (remaining days in year).

DATE MISPLACEMENT — STRICT RULES (READ CAREFULLY):
ONLY flag date_misplacement as FAIL if you see CLEAR, OBVIOUS out-of-order sequences within a single row.
Example: Row reads left-to-right as "16, 18, 17" — this means 17 and 18 are swapped = FAIL.
Example: Row reads "9, 10, 11, 12, 13, 14, 15" — this is correct = PASS.
DO NOT flag misplacement based on column-header assumptions — the column positions may vary by calendar design.
DO NOT flag misplacement if dates are sequential (1,2,3...) even if you think they're in wrong columns.
DO NOT flag dual-date cells (slash or stacked) as misplaced — they are valid layout choices.
ONLY flag if within a SINGLE ROW the numbers go backwards or skip non-sequentially (excluding dual-date cells).
If ALL rows have dates increasing left-to-right → status MUST be "PASS".

NON-BOLD OVERFLOW — CRITICAL CHECK:
Look at the very first row and very last row of the calendar grid.
Any date from a PREVIOUS or NEXT month visible in those edge rows:
- If it appears in LIGHT/NON-BOLD font → CORRECT (do not flag)
- If it appears in BOLD font → FAIL — flag it specifically with the date number

HOLIDAY LABEL POSITION CHECK — CONSERVATIVE:
Only flag holiday_alignment as FAIL/WARN if you can see at least 3 holiday labels on this page
AND at least one is CLEARLY positioned differently from the others (e.g., top vs bottom).
If there are fewer than 3 holiday labels, OR if all labels follow the same general pattern → PASS.
Do NOT flag minor pixel-level differences. Only flag OBVIOUS inconsistencies.

PERFORM ALL 8 AUDITS BELOW.

1. LEAP YEAR CHECK (February only — mark N/A for other months)
2. SEQUENTIAL CONTINUITY: List all current-month dates found. Identify gaps.
3. DATE MISPLACEMENT: ONLY flag if rows have backwards/out-of-order sequences. See strict rules above.
4. DATA ALIGNMENT: Check date number position consistency.
5. SLASH DATE CALCULATION: Find all dual-date cells and verify math (d2 = d1 + 7).
6. NON-BOLD OVERFLOW RULE: Check first/last row overflow dates for bold violations.
7. SPELLING & CHARACTER PROOFING: Month name, day headers, holiday text, year.
8. HOLIDAY LABEL POSITION: Conservative check — only flag obvious inconsistencies with 3+ labels.

RESPOND ONLY with valid JSON (no prose, no markdown fences):
{{
  "month": "{month_name}",
  "year": {year},
  "page_summary": "One clear paragraph describing ALL errors and warnings found. If no errors, state clearly. Be specific.",
  "leap_year_check": {{
    "status": "PASS|FAIL|N/A",
    "details": "one sentence explanation"
  }},
  "sequential_continuity": {{
    "status": "PASS|FAIL",
    "dates_found": [list of all current-month integer dates including both halves of dual-date cells],
    "missing_dates": [list of missing integers],
    "details": "explanation"
  }},
  "date_misplacement": {{
    "status": "PASS|FAIL",
    "issues": [{{"date": N, "expected_column": "Sun|Mon|Tue|Wed|Thu|Fri|Sat", "actual_column": "Sun|Mon|Tue|Wed|Thu|Fri|Sat", "issue": "exact row sequence seen e.g. row had 16,18,17 — 18 and 17 are swapped"}}],
    "details": "explanation — describe the exact out-of-order sequence if any"
  }},
  "data_alignment": {{
    "status": "PASS|FAIL|WARN",
    "issues": [{{"date": N, "issue": "description"}}],
    "details": "explanation"
  }},
  "slash_dates": {{
    "status": "PASS|FAIL|N/A",
    "found": ["23/30"],
    "issues": [{{"slash": "X/Y", "issue": "description"}}],
    "details": "explanation — include whether cells are slash-format or stacked-format"
  }},
  "non_bold_overflow": {{
    "status": "PASS|FAIL|N/A",
    "overflow_dates_visible": [],
    "bold_violations": [],
    "details": "explanation — list any overflow dates seen and whether they are bold or not"
  }},
  "spelling": {{
    "status": "PASS|FAIL",
    "issues": [{{"text": "found text", "correction": "correct text", "location": "where"}}],
    "details": "explanation"
  }},
  "holiday_alignment": {{
    "status": "PASS|FAIL|WARN|N/A",
    "alignment_pattern": "top-left|top-right|top-center|bottom|mixed|none",
    "issues": [{{"cell_date": N, "issue": "description of position mismatch"}}],
    "details": "explanation — how many holiday labels found and what pattern"
  }},
  "overall_status": "PASS|FAIL|WARN",
  "critical_errors": ["only list truly critical errors not already captured in specific checks above"],
  "warnings": ["only list warnings not already captured above"]
}}"""

    try:
        llm = get_llm()
        messages = [
            SystemMessage(content="You are an expert calendar QC auditor. Always respond with valid JSON only."),
            HumanMessage(content=[
                {"type": "text",      "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]),
        ]
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw, list):
            raw = " ".join(item.get("text","") for item in raw if isinstance(item, dict))
    except Exception:
        raw = _call_llm_raw(image_b64, prompt)

    parsed = extract_json_from_text(raw)
    if parsed and isinstance(parsed, dict):
        return parsed

    return {
        "month": month_name, "year": year,
        "page_summary": "",
        "leap_year_check":       {"status": "N/A", "details": ""},
        "sequential_continuity": {"status": "N/A", "dates_found": [], "missing_dates": [], "details": ""},
        "date_misplacement":     {"status": "N/A", "issues": [], "details": ""},
        "data_alignment":        {"status": "N/A", "issues": [], "details": ""},
        "slash_dates":           {"status": "N/A", "found": [], "issues": [], "details": ""},
        "non_bold_overflow":     {"status": "N/A", "overflow_dates_visible": [], "bold_violations": [], "details": ""},
        "spelling":              {"status": "N/A", "issues": [], "details": ""},
        "holiday_alignment":     {"status": "N/A", "alignment_pattern": "none", "issues": [], "details": ""},
        "overall_status": "N/A",
        "critical_errors": [],
        "warnings": [],
        "_ai_unavailable": True,
        "_raw": raw,
    }


def _call_llm_raw(image_b64: str, prompt: str) -> str:
    return _call_llm_raw_simple(image_b64, prompt, max_tokens=4000)


# ======================================================
# NATIVE STRUCTURAL CHECKS
# ======================================================

def _get_bold_dates_only(structure: Dict, year: int, month: int) -> List[Dict]:
    total = days_in_month(year, month)
    return [
        d for d in structure["date_numbers"]
        if d.get("bold", False)
        and 1 <= d["day"] <= total
        and not d.get("is_overflow", False)
    ]


def _get_current_month_dates(structure: Dict, year: int, month: int) -> List[Dict]:
    total = days_in_month(year, month)
    all_in_range = [d for d in structure["date_numbers"] if 1 <= d["day"] <= total]
    non_overflow = [d for d in all_in_range if not d.get("is_overflow", False)]
    bold_dates   = [d for d in non_overflow if d.get("bold", False)]
    if bold_dates:
        return bold_dates
    if non_overflow:
        return non_overflow
    return all_in_range


def native_leap_year_check(structure: Dict, year: int, month: int) -> Dict:
    if month != 2:
        return {"status": "N/A", "details": "Not February — leap year check skipped."}
    leap    = is_leap_year(year)
    current = _get_current_month_dates(structure, year, month)
    days_seen = {d["day"] for d in current}
    for d in current:
        if d.get("is_slash") and d.get("slash_day"):
            days_seen.add(d["slash_day"])
    if leap:
        if 29 in days_seen:
            return {"status": "PASS",
                    "details": f"✅ Leap year {year}: Feb has 29 days and day 29 is present."}
        return {"status": "FAIL",
                "details": f"❌ CRITICAL: {year} IS a leap year. Day 29 is MISSING from February grid!"}
    else:
        if 29 in days_seen:
            return {"status": "FAIL",
                    "details": f"❌ CRITICAL: {year} is NOT a leap year. Day 29 must NOT appear — but it was found!"}
        return {"status": "PASS",
                "details": f"✅ Non-leap year {year}: February correctly shows 28 days (no day 29)."}


def native_sequential_continuity(structure: Dict, year: int, month: int) -> Dict:
    total     = days_in_month(year, month)
    bold_only = _get_bold_dates_only(structure, year, month)

    if not bold_only:
        return {
            "status": "N/A",
            "dates_found": [], "missing_dates": [], "extra_dates": [],
            "details": "No bold current-month dates found — cannot check sequential continuity.",
        }

    days_seen = set()
    for d in bold_only:
        days_seen.add(d["day"])
        if d.get("is_slash") and d.get("slash_day"):
            slash_d2 = d["slash_day"]
            if 1 <= slash_d2 <= total:
                days_seen.add(slash_d2)

    days_seen_sorted = sorted(days_seen)
    expected  = set(range(1, total + 1))
    missing   = sorted(expected - days_seen)
    extra     = sorted(days_seen - expected)

    if not missing and not extra:
        return {
            "status": "PASS",
            "dates_found": days_seen_sorted, "missing_dates": [], "extra_dates": [],
            "details": f"✅ All {total} bold dates (1–{total}) present and accounted for.",
        }

    details = []
    if missing:
        details.append(f"MISSING bold dates: {missing}")
    if extra:
        details.append(f"Unexpected bold dates > {total}: {extra}")
    return {
        "status": "FAIL",
        "dates_found": days_seen_sorted, "missing_dates": missing, "extra_dates": extra,
        "details": "❌ " + " | ".join(details),
    }


def native_date_misplacement(structure: Dict, year: int, month: int) -> Dict:
    current = _get_current_month_dates(structure, year, month)
    if not current:
        return {"status": "N/A", "issues": [],
                "details": "ℹ️ No current-month dates found for row-order check."}

    current = [d for d in current if not d.get("is_overflow", False)]

    ROW_THRESH = 18.0
    rows: Dict[float, List[Dict]] = {}
    for d in current:
        placed = False
        for ry in list(rows.keys()):
            if abs(d["y0"] - ry) <= ROW_THRESH:
                rows[ry].append(d)
                placed = True
                break
        if not placed:
            rows[d["y0"]] = [d]

    issues = []
    for ry in sorted(rows.keys()):
        row_dates = rows[ry]
        if len(row_dates) < 2:
            continue
        row_sorted = sorted(row_dates, key=lambda d: d["x0"])

        days_in_row: List[int] = []
        is_slash_boundary: List[bool] = []

        for d in row_sorted:
            days_in_row.append(d["day"])
            is_slash_boundary.append(False)
            if d.get("is_slash") and d.get("slash_day"):
                days_in_row.append(d["slash_day"])
                is_slash_boundary.append(True)

        for i in range(len(days_in_row) - 1):
            if is_slash_boundary[i]:
                continue
            if days_in_row[i + 1] < days_in_row[i]:
                issues.append({
                    "date": days_in_row[i + 1],
                    "expected_column": "—",
                    "actual_column": "—",
                    "issue": (
                        f"Out-of-order sequence detected in row: dates read as "
                        f"{days_in_row} left-to-right — "
                        f"date {days_in_row[i+1]} appears AFTER {days_in_row[i]}."
                    ),
                })

    if issues:
        return {
            "status": "FAIL", "issues": issues,
            "details": f"❌ {len(issues)} out-of-order date sequence(s) detected.",
        }
    return {
        "status": "PASS", "issues": [],
        "details": "✅ All dates appear in correct left-to-right sequential order within each row.",
    }


def native_data_alignment(structure: Dict) -> Dict:
    dnums = structure["date_numbers"]
    if not dnums:
        return {"status": "N/A", "issues": [], "details": "No date numbers found."}
    col_thresh = 15.0
    cols: Dict[float, List[Dict]] = {}
    for d in dnums:
        placed = False
        for cx in list(cols.keys()):
            if abs(d["x0"] - cx) <= col_thresh:
                cols[cx].append(d)
                placed = True
                break
        if not placed:
            cols[d["x0"]] = [d]
    issues = []
    for cx, col_dates in cols.items():
        if len(col_dates) < 2:
            continue
        x0s    = [d["x0"] for d in col_dates]
        mean_x = sum(x0s) / len(x0s)
        for d in col_dates:
            dev = abs(d["x0"] - mean_x)
            if dev > 6.0:
                issues.append({"date": d["day"],
                               "issue": f"Date {d['day']} X-pos deviates {dev:.1f}pt from column avg ({mean_x:.1f}pt)."})
    if issues:
        return {"status": "WARN", "issues": issues,
                "details": f"⚠️ {len(issues)} alignment deviation(s) detected."}
    return {"status": "PASS", "issues": [],
            "details": "✅ Date number alignment is consistent across columns."}


def native_slash_dates(structure: Dict, year: int, month: int) -> Dict:
    total  = days_in_month(year, month)
    slashs = [d for d in structure["date_numbers"] if d.get("is_slash")]
    if not slashs:
        return {"status": "N/A", "found": [], "issues": [],
                "details": "No dual-date cells (slash or stacked) detected on this page."}
    issues = []
    found  = []
    for sd in slashs:
        d1 = sd["day"]
        d2 = sd.get("slash_day")
        cell_type = "stacked" if sd.get("is_stacked") else "slash"
        found.append(f"{d1}/{d2}")
        if d2 is None:
            continue
        if d2 != d1 + 7:
            issues.append({"slash": f"{d1}/{d2}",
                           "issue": f"Math error in {cell_type} cell: {d1}/{d2} — should be {d1}/{d1+7} (diff must equal 7)."})
        if d2 > total:
            issues.append({"slash": f"{d1}/{d2}",
                           "issue": f"Day {d2} in {cell_type} cell exceeds {month_name_for(month)} total ({total} days)."})
    if issues:
        return {"status": "FAIL", "found": found, "issues": issues,
                "details": f"❌ {len(issues)} dual-date cell error(s) found."}
    return {"status": "PASS", "found": found, "issues": [],
            "details": f"✅ Dual-date cells verified: {found}"}


def native_non_bold_overflow(structure: Dict, year: int, month: int) -> Dict:
    total      = days_in_month(year, month)
    all_dates  = structure["date_numbers"]

    if not all_dates:
        return {"status": "N/A", "overflow_dates": [], "bold_violations": [],
                "details": "No date numbers found on this page."}

    y_vals = [d["y0"] for d in all_dates]
    min_y  = min(y_vals)
    max_y  = max(y_vals)
    y_span = max_y - min_y
    row_h  = max(y_span / 6.0, 15.0)

    overflow_dates = []
    for d in all_dates:
        is_ov = False
        if d["day"] > total:
            is_ov = True
        elif d.get("is_overflow", False):
            is_ov = True
        elif (not d.get("bold", True)
              and d["day"] >= 25
              and (d["y0"] - min_y) <= row_h * 1.3):
            is_ov = True
        elif (not d.get("bold", True)
              and d["day"] <= 7
              and (max_y - d["y0"]) <= row_h * 1.3):
            is_ov = True
        elif (d.get("bold", False)
              and d["day"] >= 25
              and (d["y0"] - min_y) <= row_h * 0.8):
            first_dow = (calendar.monthrange(year, month)[0] + 1) % 7
            if first_dow > 0:
                is_ov = True

        if is_ov:
            overflow_dates.append(d)

    bold_vio = [d for d in overflow_dates if d.get("bold", False)]

    if bold_vio:
        return {
            "status": "FAIL",
            "overflow_dates": [d["day"] for d in overflow_dates],
            "bold_violations": [d["day"] for d in bold_vio],
            "details": (f"❌ CRITICAL: {len(bold_vio)} overflow date(s) are BOLD: "
                        f"{[d['day'] for d in bold_vio]}. "
                        f"Filler/overflow dates from prev/next month MUST be non-bold."),
        }
    return {
        "status": "PASS",
        "overflow_dates": [d["day"] for d in overflow_dates],
        "bold_violations": [],
        "details": (f"✅ No bold overflow/filler dates detected. "
                    f"{len(overflow_dates)} overflow date(s) correctly non-bold."),
    }


def native_spelling(structure: Dict, month: int) -> Dict:
    issues = []
    expected_month = MONTH_NAMES[month - 1]
    mh = structure.get("month_header")
    if mh:
        txt = mh["text"]
        if expected_month.lower() not in txt.lower():
            ratio = difflib.SequenceMatcher(None, expected_month.lower(), txt.lower()).ratio()
            if ratio < 0.8:
                issues.append({"text": txt, "correction": expected_month, "location": "Month header"})
    valid_all = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat","Su","Mo","Tu","We","Th","Fr","Sa",
                 "S","M","T","W","F","Sunday","Monday","Tuesday","Wednesday",
                 "Thursday","Friday","Saturday"}
    for dh in structure.get("day_headers", []):
        txt = dh["text"]
        if txt not in valid_all:
            closest = difflib.get_close_matches(txt, list(valid_all), n=1, cutoff=0.6)
            issues.append({"text": txt, "correction": closest[0] if closest else "?",
                           "location": "Day-of-week header"})
    if issues:
        return {"status": "FAIL", "issues": issues,
                "details": f"❌ {len(issues)} spelling/labelling issue(s) found."}
    return {"status": "PASS", "issues": [],
            "details": "✅ Month name and day headers look correct."}


def native_holiday_alignment(structure: Dict) -> Dict:
    labels = structure.get("holiday_labels", [])

    if not labels:
        return {"status": "N/A", "issues": [],
                "details": "No holiday/event labels found on this page."}
    if len(labels) < 3:
        return {"status": "N/A", "issues": [],
                "details": f"Only {len(labels)} holiday label(s) found — need at least 3 to assess alignment consistency."}

    V_THRESHOLD = 20.0
    H_THRESHOLD = 25.0
    row_thresh  = 35.0

    rows: Dict[float, List[Dict]] = {}
    for sp in labels:
        placed = False
        for ry in list(rows.keys()):
            if abs(sp["y0"] - ry) <= row_thresh:
                rows[ry].append(sp)
                placed = True
                break
        if not placed:
            rows[sp["y0"]] = [sp]

    offset_issues = []
    for ry, row_labels in rows.items():
        if len(row_labels) < 2:
            continue
        y0s    = [sp["y0"] for sp in row_labels]
        mean_y = sum(y0s) / len(y0s)
        for sp in row_labels:
            dev = abs(sp["y0"] - mean_y)
            if dev > V_THRESHOLD:
                offset_issues.append({
                    "cell_date": "—",
                    "issue": (
                        f"Holiday '{sp['text'][:30]}' is vertically misaligned — "
                        f"positioned {dev:.0f}pt away from row average."
                    ),
                })

    col_thresh = 25.0
    xcols: Dict[float, List[Dict]] = {}
    for sp in labels:
        placed = False
        for cx in list(xcols.keys()):
            if abs(sp["x0"] - cx) <= col_thresh:
                xcols[cx].append(sp)
                placed = True
                break
        if not placed:
            xcols[sp["x0"]] = [sp]

    h_issues = []
    for cx, col_labels in xcols.items():
        if len(col_labels) < 2:
            continue
        x0s    = [sp["x0"] for sp in col_labels]
        mean_x = sum(x0s) / len(x0s)
        for sp in col_labels:
            dev = abs(sp["x0"] - mean_x)
            if dev > H_THRESHOLD:
                h_issues.append({
                    "cell_date": "—",
                    "issue": (
                        f"Holiday '{sp['text'][:30]}' is horizontally misaligned — "
                        f"offset {dev:.0f}pt from column average."
                    ),
                })

    all_issues = offset_issues + h_issues
    if all_issues:
        return {
            "status": "WARN", "issues": all_issues,
            "details": f"⚠️ {len(all_issues)} holiday label position inconsistency(ies) detected among {len(labels)} labels.",
        }
    return {
        "status": "PASS", "issues": [],
        "details": f"✅ All {len(labels)} holiday labels are consistently positioned.",
    }


# ======================================================
# CHECK REGISTRY
# ======================================================
CHECKS = [
    "leap_year_check",
    "sequential_continuity",
    "date_misplacement",
    "data_alignment",
    "slash_dates",
    "non_bold_overflow",
    "spelling",
    "holiday_alignment",
]

CHECK_LABELS = {
    "leap_year_check":       "1. Leap Year Logic",
    "sequential_continuity": "2. Sequential Continuity",
    "date_misplacement":     "3. Date Misplacement",
    "data_alignment":        "4. Data Alignment",
    "slash_dates":           "5. Slash/Stacked Date Calculation",
    "non_bold_overflow":     "6. Non-Bold Overflow Rule",
    "spelling":              "7. Spelling & Proofing",
    "holiday_alignment":     "8. Holiday Label Alignment",
}

CHECK_ICONS = {
    "leap_year_check":       "🗓️",
    "sequential_continuity": "🔢",
    "date_misplacement":     "🔀",
    "data_alignment":        "📐",
    "slash_dates":           "➗",
    "non_bold_overflow":     "𝗕̶",
    "spelling":              "🔤",
    "holiday_alignment":     "📌",
}

# ── Design-type display metadata ─────────────────────
DESIGN_TYPE_META = {
    "deskpad":             ("📋", "#6f42c1", "Desk Pad"),
    "wall_single":         ("🖼️",  "#0d6efd", "Wall Calendar (Single Month)"),
    "wall_three_month":    ("📅", "#20c997", "Wall Calendar (Three-Month View)"),
    "wall_large_format":   ("🗺️",  "#fd7e14", "Wall Calendar (Large Format)"),
    "mini_wall":           ("🗒️",  "#6c757d", "Mini Wall Calendar"),
    "digital":             ("💻", "#17a2b8", "Digital Calendar"),
    "unknown":             ("❓", "#adb5bd", "Unknown Design"),
}


# ======================================================
# SLASH PAIRS HELPER
# ======================================================

def _extract_slash_pairs(result: Dict) -> Dict[int, int]:
    pairs: Dict[int, int] = {}

    native_slash = result.get("native", {}).get("slash_dates", {})
    for s in native_slash.get("found", []):
        m = re.match(r'^(\d{1,2})/(\d{1,2})$', str(s))
        if m:
            pairs[int(m.group(1))] = int(m.group(2))

    ai_data = result.get("ai", {})
    if isinstance(ai_data, dict):
        ai_slash = ai_data.get("slash_dates", {})
        for s in ai_slash.get("found", []):
            m = re.match(r'^(\d{1,2})/(\d{1,2})$', str(s))
            if m:
                pairs[int(m.group(1))] = int(m.group(2))

    return pairs


# ======================================================
# ── ADAPTIVE OVERFLOW GRID HELPER (design-aware) ──────
# ======================================================

def _compute_overflow_cells(year: int, month: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Fallback: pure calendar-math overflow computation."""
    first_dow = (calendar.monthrange(year, month)[0] + 1) % 7
    total = days_in_month(year, month)

    prev_month = 12 if month == 1 else month - 1
    prev_year  = year - 1 if month == 1 else year
    prev_total = days_in_month(prev_year, prev_month)
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
    Uses AI-inferred overflow_prev_cells / overflow_next_cells when confidence is high,
    otherwise falls back to pure calendar math.
    """
    conf     = design_profile.get("confidence", 0.0)
    ai_prev  = design_profile.get("overflow_prev_cells")
    ai_next  = design_profile.get("overflow_next_cells")

    # Use AI counts only when confident and values are plausible
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
        prev_total = days_in_month(prev_year, prev_month)

        prev_overflow = []
        for i in range(ai_prev):
            day = prev_total - (ai_prev - 1 - i)
            prev_overflow.append((day, prev_month))

        next_month = 1 if month == 12 else month + 1
        next_overflow = [(i + 1, next_month) for i in range(ai_next)]

        return prev_overflow, next_overflow

    # Fallback
    return _compute_overflow_cells(year, month)


# ======================================================
# HTML REPORT GENERATOR
# ======================================================
_STATUS_COLOR = {
    "PASS":    ("#28a745", "#d4edda", "✅"),
    "FAIL":    ("#dc3545", "#f8d7da", "❌"),
    "WARN":    ("#856404", "#fff3cd", "⚠️"),
    "N/A":     ("#6c757d", "#e2e3e5", "—"),
    "UNKNOWN": ("#6c757d", "#e2e3e5", "?"),
}


def _badge(status: str) -> str:
    col, _, icon = _STATUS_COLOR.get(status, ("#6c757d", "#e2e3e5", "?"))
    return (f'<span style="background:{col};color:white;padding:2px 10px;'
            f'border-radius:4px;font-weight:bold;font-size:0.82em;">'
            f'{icon} {status}</span>')


def _design_badge(design_profile: Dict) -> str:
    """Renders a coloured design-family badge for the report header."""
    dt    = design_profile.get("design_type", "unknown")
    conf  = design_profile.get("confidence", 0.0)
    icon, color, label = DESIGN_TYPE_META.get(dt, DESIGN_TYPE_META["unknown"])
    dr    = design_profile.get("date_rendering_mode", "")
    notes = design_profile.get("layout_notes", "")[:80]
    dr_chip = (f'<span style="background:rgba(255,255,255,.25);padding:1px 8px;'
               f'border-radius:10px;font-size:.75em;margin-left:6px;">{dr}</span>'
               if dr else "")
    conf_txt = f"{int(conf*100)}% confidence" if conf else ""
    conf_span = ("<span style='opacity:.75;font-weight:400;font-size:.85em;margin-left:6px;'>" + conf_txt + "</span>") if conf_txt else ""
    notes_div = ("<div style='font-size:.76em;color:#555;padding:0 24px 6px;'><i>🔍 Design notes: " + html_module.escape(notes) + "</i></div>") if notes else ""
    return (
        f'<div style="background:{color};color:#fff;display:inline-flex;align-items:center;'
        f'gap:6px;padding:4px 14px;border-radius:20px;font-size:.8em;font-weight:700;'
        f'margin:4px 0 8px;flex-wrap:wrap;">'
        f'{icon} {label}{dr_chip}'
        f'{conf_span}'
        f'</div>'
        f'{notes_div}'
    )


def _render_three_month_grid_section(result: Dict, design: Dict) -> str:
    """
    For three-month view pages, renders three side-by-side simplified month summaries.
    The primary month (matching result["month"]) gets full QC colouring;
    secondary months get a neutral info display.
    """
    months_shown = design.get("months_shown", [])
    m_name  = result.get("month_name", "?")
    yr      = result.get("year", "")
    exp_d   = result.get("expected_days", 31)
    slash_pairs   = _extract_slash_pairs(result)
    slash_absorbed = set(slash_pairs.values())
    native_results = result.get("native", {})
    native_seq     = native_results.get("sequential_continuity", {})
    missing_set    = set(native_seq.get("missing_dates", []))
    ai_data        = result.get("ai", {})
    ai_unavailable = isinstance(ai_data, dict) and ai_data.get("_ai_unavailable", False)
    if isinstance(ai_data, dict) and not ai_unavailable:
        ai_seq = ai_data.get("sequential_continuity", {})
        missing_set |= set(ai_seq.get("missing_dates", []))
    missing_set -= slash_absorbed

    parts = []
    parts.append(
        f'<div style="padding:0 24px 6px;font-size:.82em;color:#555;font-weight:700;">'
        f'📆 Three-Month View — Primary Audit: <b>{m_name} {yr}</b> &nbsp;'
        f'<span style="font-weight:400;color:#888;">'
        f'Secondary months shown for reference only</span></div>'
    )

    # Grid panel for primary month
    first_dow = (calendar.monthrange(yr, result.get("month", 1))[0] + 1) % 7
    try:
        prev_overflow, next_overflow = _compute_overflow_cells_adaptive(
            yr, result.get("month", 1), design)
    except Exception:
        prev_overflow, next_overflow = [], []

    # Determine bold violations
    native_ovf = native_results.get("non_bold_overflow", {})
    native_bold_violations = set(native_ovf.get("bold_violations", [])) if native_ovf else set()
    ai_bold_violations = set()
    if isinstance(ai_data, dict) and not ai_unavailable:
        ai_ovf_data = ai_data.get("non_bold_overflow", {})
        if isinstance(ai_ovf_data, dict):
            ai_bold_violations = set(ai_ovf_data.get("bold_violations", []))
    all_bold_violations = ai_bold_violations | native_bold_violations

    native_mis_data = native_results.get("date_misplacement", {})
    native_misplace_set = set()
    if isinstance(native_mis_data, dict) and native_mis_data.get("status") == "FAIL":
        for i in native_mis_data.get("issues", []):
            if isinstance(i, dict) and i.get("date") is not None:
                native_misplace_set.add(i["date"])

    native_seq_found = set(native_seq.get("dates_found", []))

    parts.append('<div style="display:flex;gap:16px;padding:0 24px 16px;flex-wrap:wrap;">')

    # ── Primary month mini-grid ──
    parts.append(
        f'<div style="flex:1;min-width:300px;">'
        f'<div style="font-weight:700;font-size:.85em;margin-bottom:6px;color:#0d6efd;">'
        f'📅 {m_name} {yr} (PRIMARY — full QC)</div>'
    )
    parts.append('<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;">')
    for dh in ["S","M","T","W","T","F","S"]:
        parts.append(f'<div style="background:#343a40;color:#fff;text-align:center;'
                     f'padding:3px;font-size:.7em;font-weight:700;border-radius:2px;">{dh}</div>')

    for i, (ovf_day, _) in enumerate(prev_overflow):
        is_bv = ovf_day in all_bold_violations
        bg  = "#ffe8e8" if is_bv else "#f1f1f1"
        bdr = "2px solid #dc3545" if is_bv else "1px dashed #aaa"
        parts.append(
            f'<div style="background:{bg};border:{bdr};min-height:36px;padding:3px;'
            f'border-radius:3px;font-size:.72em;color:#999;font-style:italic;">{ovf_day}</div>'
        )

    day = 1
    while day <= exp_d:
        if day in slash_absorbed:
            day += 1
            continue
        is_dual = day in slash_pairs
        d2      = slash_pairs.get(day)
        if is_dual:
            is_miss = (day in missing_set) or (d2 is not None and d2 in missing_set)
            bg  = "#f8d7da" if is_miss else "#cfe2ff"
            bdr = "2px solid #084298" if not is_miss else "2px solid #dc3545"
            inner = (f'<span style="display:block;border-bottom:1px solid #9ec5fe;padding-bottom:1px;'
                     f'font-weight:700;font-size:.8em;color:#084298;">{day}</span>'
                     f'<span style="display:block;font-weight:700;font-size:.8em;color:#0550ae;">{d2}</span>'
                     if d2 else f'<span style="font-weight:700;font-size:.85em;">{day}</span>')
        else:
            is_miss = day in missing_set
            is_mis  = day in native_misplace_set
            bg  = "#f8d7da" if is_miss else ("#ffe0f0" if is_mis else "#d4edda")
            bdr = "1px solid #c3e6cb" if (not is_miss and not is_mis) else "1px solid #f5c6cb"
            inner = f'<span style="font-weight:700;font-size:.85em;">{day}</span>'
        parts.append(
            f'<div style="background:{bg};border:{bdr};min-height:36px;'
            f'padding:3px;border-radius:3px;">{inner}</div>'
        )
        day += 1

    for ovf_day, _ in next_overflow:
        is_bv = ovf_day in all_bold_violations
        bg  = "#ffe8e8" if is_bv else "#f1f1f1"
        bdr = "2px solid #dc3545" if is_bv else "1px dashed #aaa"
        parts.append(
            f'<div style="background:{bg};border:{bdr};min-height:36px;padding:3px;'
            f'border-radius:3px;font-size:.72em;color:#999;font-style:italic;">{ovf_day}</div>'
        )
    parts.append('</div></div>')

    # ── Secondary month placeholders ──
    for ms in months_shown:
        if m_name.lower() in ms.lower() or str(yr) in ms:
            continue
        parts.append(
            f'<div style="flex:1;min-width:200px;">'
            f'<div style="font-weight:700;font-size:.85em;margin-bottom:6px;color:#6c757d;">'
            f'📌 {html_module.escape(ms)} (secondary — not audited in detail)</div>'
            f'<div style="background:#f8f9fa;border:1px dashed #dee2e6;border-radius:6px;'
            f'padding:16px;font-size:.8em;color:#6c757d;text-align:center;">'
            f'Secondary month visible on this page.<br>'
            f'QC audit covers primary month only.<br>'
            f'Review secondary months separately.</div>'
            f'</div>'
        )

    parts.append('</div>')
    return "\n".join(parts)


def generate_html_report(batch_results: List[Dict], batch_label: str) -> str:
    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Calendar QC Report — {html_module.escape(batch_label)}</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:20px;background:#f4f6f9;color:#222;}}
.hdr{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:24px 32px;border-radius:12px;margin-bottom:24px;}}
.hdr h1{{margin:0 0 6px;font-size:1.7em;}} .hdr p{{margin:0;opacity:.8;font-size:.9em;}}
.agent-badge{{display:inline-block;background:linear-gradient(90deg,#6f42c1,#0d6efd);color:#fff;
  padding:3px 12px;border-radius:20px;font-size:.78em;font-weight:700;margin-top:8px;}}
.card{{background:#fff;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,.10);margin-bottom:32px;overflow:hidden;}}
.mhdr{{padding:16px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;}}
.mhdr.pass{{background:linear-gradient(135deg,#28a745,#20c997);color:#fff;}}
.mhdr.fail{{background:linear-gradient(135deg,#dc3545,#b02a37);color:#fff;}}
.mhdr.warn{{background:linear-gradient(135deg,#ffc107,#d39e00);color:#333;}}
.mhdr.unknown{{background:#6c757d;color:#fff;}}
.mhdr h2{{margin:0;font-size:1.25em;}} .mmeta{{font-size:.85em;opacity:.9;}}
.grid8{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:18px 24px;}}
.chk{{text-align:center;padding:12px 8px;border-radius:8px;border:1px solid #ddd;}}
.chk.pass{{background:#d4edda;border-color:#c3e6cb;color:#155724;}}
.chk.fail{{background:#f8d7da;border-color:#f5c6cb;color:#721c24;}}
.chk.warn{{background:#fff3cd;border-color:#ffeeba;color:#856404;}}
.chk.na{{background:#e9ecef;border-color:#ced4da;color:#6c757d;}}
.chk.unknown{{background:#e9ecef;border-color:#ced4da;color:#6c757d;}}
.chk-icon{{font-size:1.4em;margin-bottom:3px;}}
.chk-lbl{{font-size:.72em;font-weight:700;}}
.disc{{padding:0 24px 20px;}}
.disc h3{{color:#c82333;font-size:.95em;margin:12px 0 8px;}}
.ai-summary-box{{margin:12px 24px 16px;padding:14px 18px;border-radius:8px;
  background:linear-gradient(135deg,#e8f4fd,#dbeafe);border-left:5px solid #0d6efd;
  font-size:.88em;color:#1e3a5f;line-height:1.6;}}
.ai-summary-box strong{{color:#0d6efd;}}
.native-summary-box{{margin:0 24px 12px;padding:12px 16px;border-radius:8px;
  background:linear-gradient(135deg,#f0fff4,#dcfce7);border-left:5px solid #16a34a;
  font-size:.84em;color:#14532d;line-height:1.5;}}
.native-summary-box strong{{color:#16a34a;}}
.design-info-box{{margin:0 24px 10px;padding:10px 16px;border-radius:8px;
  background:linear-gradient(135deg,#f3e8ff,#ede9fe);border-left:5px solid #7c3aed;
  font-size:.82em;color:#3b0764;}}
.design-info-box strong{{color:#7c3aed;}}
table{{width:100%;border-collapse:collapse;font-size:.84em;}}
th{{background:#343a40;color:#fff;padding:8px 12px;text-align:left;}}
td{{padding:7px 12px;border-bottom:1px solid #eee;vertical-align:top;}}
tr:hover td{{background:#f8f9fa;}}
.bfail{{background:#dc3545;color:#fff;padding:1px 7px;border-radius:3px;font-size:.8em;}}
.bwarn{{background:#ffc107;color:#333;padding:1px 7px;border-radius:3px;font-size:.8em;}}
.bpass{{background:#28a745;color:#fff;padding:1px 7px;border-radius:3px;font-size:.8em;}}
.src-native{{background:#16a34a;color:#fff;padding:1px 6px;border-radius:3px;font-size:.72em;}}
.src-ai{{background:#6f42c1;color:#fff;padding:1px 6px;border-radius:3px;font-size:.72em;}}
.calgrid{{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;padding:12px 24px 18px;}}
.ch{{background:#343a40;color:#fff;text-align:center;padding:5px;font-size:.75em;font-weight:700;border-radius:3px;}}
.cd{{background:#f8f9fa;border:1px solid #dee2e6;min-height:52px;padding:4px 5px;border-radius:4px;font-size:.78em;}}
.cd.cerr{{background:#f8d7da;border-color:#f5c6cb;}}
.cd.cwarn{{background:#ffe0f0;border-color:#f48fb1;color:#880e4f;}}
.cd.cok{{background:#d4edda;border-color:#c3e6cb;}}
.cd.cgray{{background:#e9ecef;border-color:#ced4da;color:#888;}}
.cd.cslash{{background:#cfe2ff;border-color:#084298;border-width:2px;}}
.cd.cslash-err{{background:#f8d7da;border-color:#f5c6cb;border-width:2px;}}
.cd.cslash-warn{{background:#ffe0f0;border-color:#f48fb1;border-width:2px;color:#880e4f;}}
.cd.c-prev-ok{{background:#f1f1f1;border:1px dashed #aaa;color:#999;min-height:52px;}}
.cd.c-prev-bold{{background:#ffe8e8;border:2px solid #dc3545;color:#dc3545;min-height:52px;}}
.cd.c-next-ok{{background:#f1f1f1;border:1px dashed #aaa;color:#999;min-height:52px;}}
.cd.c-next-bold{{background:#ffe8e8;border:2px solid #dc3545;color:#dc3545;min-height:52px;}}
.cdn{{font-weight:700;font-size:1em;}}
.cdn-ovf{{font-weight:400;font-size:.85em;font-style:italic;color:#999;}}
.cdn-ovf-bold{{font-weight:700;font-size:.9em;color:#dc3545;}}
.cdn-slash{{font-weight:700;font-size:.88em;color:#084298;line-height:1.3;}}
.cdn-slash .slash-d1{{display:block;border-bottom:1px solid #9ec5fe;padding-bottom:2px;margin-bottom:2px;}}
.cdn-slash .slash-d2{{display:block;color:#0550ae;}}
.cdn2{{font-size:.65em;color:#555;margin-top:2px;line-height:1.2;}}
.cdn-ovf-lbl{{font-size:.6em;color:#aaa;display:block;margin-top:2px;}}
.cdn-bold-lbl{{font-size:.6em;color:#dc3545;font-weight:700;display:block;margin-top:2px;}}
.noissue{{padding:16px 24px;color:#28a745;font-weight:700;}}
.leap-banner{{margin:0 24px 12px;padding:10px 14px;border-radius:6px;font-size:.88em;font-weight:600;}}
.leap-yes{{background:#cfe2ff;border-left:4px solid #0d6efd;color:#084298;}}
.leap-no{{background:#e2e3e5;border-left:4px solid #6c757d;color:#41464b;}}
.grid-legend{{padding:4px 24px 10px;font-size:.75em;display:flex;gap:12px;flex-wrap:wrap;}}
.leg-item{{display:flex;align-items:center;gap:4px;}}
.leg-box{{width:14px;height:14px;border-radius:3px;border:1px solid #ccc;display:inline-block;}}
.ai-mis-note{{margin:0 24px 8px;padding:8px 14px;border-radius:6px;background:#fce4ec;
  border-left:4px solid #e91e63;font-size:.8em;color:#880e4f;}}
.both-badge{{display:inline-block;background:linear-gradient(90deg,#16a34a,#6f42c1);
  color:#fff;padding:2px 10px;border-radius:12px;font-size:.75em;font-weight:700;margin-left:8px;vertical-align:middle;}}
.debug-section{{margin:0 24px 16px;padding:12px 16px;border-radius:8px;background:#f8f9fa;
  border:1px dashed #adb5bd;font-size:.78em;color:#495057;}}
.debug-section h4{{margin:0 0 8px;color:#6c757d;font-size:.85em;text-transform:uppercase;letter-spacing:.05em;}}
.debug-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:4px;}}
.debug-key{{font-weight:700;color:#343a40;min-width:160px;}}
.debug-val{{color:#0d6efd;font-family:monospace;}}
@media(max-width:600px){{.grid8{{grid-template-columns:repeat(2,1fr);}}}}
</style>
</head>
<body>
<div class="hdr">
  <h1>📅 Calendar QC Audit Report</h1>
  <p>Batch: <b>{html_module.escape(batch_label)}</b> &nbsp;|&nbsp;
     Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp;
     Role: Senior QC Auditor — Zero Defect Standard &nbsp;|&nbsp;
     Mass Production Pre-Press Review</p>
  <div class="agent-badge">🤖 Powered by LangGraph AI Agent + Design Inference + RAG Knowledge Base</div>
</div>
"""]

    for result in batch_results:
        if "error" in result:
            parts.append(
                f'<div class="card"><div class="mhdr unknown">'
                f'<h2>Page {result.get("page","?")} — Error</h2>'
                f'<div class="mmeta">{html_module.escape(str(result["error"]))}</div>'
                f'</div></div>')
            continue

        m_name       = result.get("month_name", "Unknown")
        yr           = result.get("year", "")
        overall      = result.get("overall_status", "UNKNOWN")
        cs           = result.get("check_statuses", {})
        leap         = result.get("is_leap_year", False)
        exp_d        = result.get("expected_days", 0)
        month_n      = result.get("month", 1)
        hcls         = overall.lower() if overall in ("PASS","FAIL","WARN") else "unknown"
        design       = result.get("design_profile", {})
        dt           = design.get("design_type", "unknown")
        is_multimonth = design.get("month_count", 1) > 1 or dt == "wall_three_month"

        parts.append(f"""
<div class="card">
  <div class="mhdr {hcls}">
    <h2>{html_module.escape(m_name)} {yr} &nbsp; {_badge(overall)}</h2>
    <div class="mmeta">
      {"🗓️ <b>LEAP YEAR</b>" if leap else "Regular year"} &nbsp;|&nbsp;
      {exp_d} days &nbsp;|&nbsp; Page {result.get("page","?")}
    </div>
  </div>""")

        # ── Design profile banner ─────────────────────────────────────────
        if design and design.get("confidence", 0) >= 0.5:
            parts.append(f'<div style="padding:6px 24px 0;">{_design_badge(design)}</div>')
        else:
            # Show design info box with what was inferred
            parts.append(
                f'<div class="design-info-box">'
                f'<strong>🔍 Design Inference:</strong> '
                f'Low confidence or inference not available for this page. '
                f'Falling back to standard calendar-math layout rules.</div>'
            )

        if leap and month_n == 2:
            parts.append('<div class="leap-banner leap-yes">🗓️ LEAP YEAR — February must show 29 days. Day 29 presence is critical.</div>')
        elif not leap and month_n == 2:
            parts.append('<div class="leap-banner leap-no">Regular year — February must have exactly 28 days. Day 29 must NOT appear.</div>')

        # ── 8-check status grid ───────────────────────────────────────────
        parts.append('<div class="grid8">')
        for key in CHECKS:
            s    = cs.get(key, "N/A")
            lbl  = CHECK_LABELS[key].split(". ", 1)[1]
            _, _, badge_icon = _STATUS_COLOR.get(s, ("#6c757d","#e2e3e5","?"))
            cls  = s.lower() if s in ("PASS","FAIL","WARN","N/A") else "unknown"
            parts.append(
                f'<div class="chk {cls}">'
                f'<div class="chk-icon">{badge_icon}</div>'
                f'<div class="chk-lbl">{html_module.escape(lbl)}</div>'
                f'</div>')
        parts.append('</div>')

        # ── AI summary ───────────────────────────────────────────────────
        ai_data = result.get("ai", {})
        ai_summary     = ""
        ai_unavailable = False
        if isinstance(ai_data, dict):
            ai_summary     = ai_data.get("page_summary", "")
            ai_unavailable = bool(ai_data.get("_ai_unavailable", False))

        if ai_summary and not ai_unavailable:
            parts.append(
                f'<div class="ai-summary-box">'
                f'<strong>🤖 AI Auditor Assessment:</strong><br>'
                f'{html_module.escape(ai_summary)}'
                f'</div>'
            )

        # ── Slash pairs ──────────────────────────────────────────────────
        slash_pairs    = _extract_slash_pairs(result)
        slash_absorbed = set(slash_pairs.values())

        # ── Missing dates ────────────────────────────────────────────────
        native_results  = result.get("native", {})
        native_seq      = native_results.get("sequential_continuity", {})
        missing_set     = set(native_seq.get("missing_dates", []))
        dates_found_set = set(native_seq.get("dates_found", []))

        if isinstance(ai_data, dict) and not ai_unavailable:
            ai_seq  = ai_data.get("sequential_continuity", {})
            ai_found = set(ai_seq.get("dates_found", []))
            if ai_found and len(ai_found) > exp_d * 0.5:
                missing_set     |= set(ai_seq.get("missing_dates", []))
                dates_found_set = dates_found_set | ai_found if dates_found_set else ai_found

        missing_set -= slash_absorbed

        # ── Misplacement sets ────────────────────────────────────────────
        misplace_set: set = set()
        if isinstance(ai_data, dict) and not ai_unavailable:
            ai_mis = ai_data.get("date_misplacement", {})
            if isinstance(ai_mis, dict) and ai_mis.get("status") == "FAIL":
                for i in ai_mis.get("issues", []):
                    if isinstance(i, dict) and i.get("date") is not None:
                        misplace_set.add(i["date"])

        native_mis_data = native_results.get("date_misplacement", {})
        native_misplace_set: set = set()
        if isinstance(native_mis_data, dict) and native_mis_data.get("status") == "FAIL":
            for i in native_mis_data.get("issues", []):
                if isinstance(i, dict) and i.get("date") is not None:
                    native_misplace_set.add(i["date"])

        all_misplace_set = misplace_set | native_misplace_set

        # ── Unified issue harvester ───────────────────────────────────────
        all_issues: List[Dict] = []

        def harvest_issues(src: Dict, src_name: str, skip_keys: set = None) -> None:
            if skip_keys is None:
                skip_keys = set()
            for key in CHECKS:
                if key in skip_keys:
                    continue
                data = src.get(key, {})
                if not isinstance(data, dict):
                    continue
                s = data.get("status", "N/A")
                if s not in ("FAIL", "WARN"):
                    continue
                lbl   = CHECK_LABELS[key]
                items = (
                    data.get("issues", []) +
                    [{"date": d, "issue": "Overflow date is incorrectly BOLD"} for d in data.get("bold_violations", [])] +
                    [{"date": d, "issue": "Date missing from grid"} for d in data.get("missing_dates", [])]
                )
                if items:
                    for iss in items:
                        if isinstance(iss, dict):
                            all_issues.append({
                                "check":    lbl,
                                "source":   src_name,
                                "severity": s,
                                "date":     str(iss.get("date", iss.get("slash", iss.get("cell_date", "—")))),
                                "issue":    str(iss.get("issue", "")),
                            })
                        else:
                            all_issues.append({
                                "check": lbl, "source": src_name, "severity": s,
                                "date": str(iss), "issue": "See check details",
                            })
                else:
                    details = data.get("details", "")
                    if details and not details.startswith("✅") and not details.startswith("ℹ️"):
                        all_issues.append({
                            "check": lbl, "source": src_name, "severity": s,
                            "date": "—", "issue": details,
                        })

        harvest_issues(native_results, "Native PDF")
        if isinstance(ai_data, dict) and not ai_unavailable:
            harvest_issues(ai_data, "AI Vision", skip_keys={"date_misplacement"})

        seen_issues = set()
        deduped_issues = []
        for iss in all_issues:
            key = (iss["check"], iss["date"], iss["issue"][:80])
            if key not in seen_issues:
                seen_issues.add(key)
                deduped_issues.append(iss)
        all_issues = deduped_issues

        if all_issues:
            parts.append(
                '<div class="disc">'
                '<h3>⚠️ Discrepancies Requiring Immediate Action'
                '<span class="both-badge">🔬 Native + AI Vision</span></h3>'
            )
            parts.append(
                '<table><tr>'
                '<th>Check</th><th>Source</th><th>Date/Item</th>'
                '<th>Issue Description</th><th>Severity</th>'
                '</tr>'
            )
            for iss in all_issues:
                sev_badge  = '<span class="bfail">FAIL</span>' if iss["severity"] == "FAIL" else '<span class="bwarn">WARN</span>'
                src_badge  = (
                    '<span class="src-native">Native PDF</span>'
                    if iss["source"] == "Native PDF"
                    else '<span class="src-ai">AI Vision</span>'
                )
                parts.append(
                    f'<tr>'
                    f'<td>{html_module.escape(iss["check"])}</td>'
                    f'<td>{src_badge}</td>'
                    f'<td>{html_module.escape(iss["date"])}</td>'
                    f'<td>{html_module.escape(iss["issue"])}</td>'
                    f'<td>{sev_badge}</td>'
                    f'</tr>')
            parts.append('</table></div>')
        else:
            parts.append(
                '<div class="noissue">✅ No discrepancies found — Native PDF checks and AI Vision both report clean for this month.</div>'
            )

        # ── AI detail sub-tables ──────────────────────────────────────────
        if isinstance(ai_data, dict) and not ai_unavailable:
            ai_mis_data   = ai_data.get("date_misplacement", {})
            ai_mis_issues = ai_mis_data.get("issues", []) if isinstance(ai_mis_data, dict) else []
            if ai_mis_issues and ai_mis_data.get("status") == "FAIL":
                parts.append('<div class="disc"><h3>🔀 AI Vision — Date Misplacement Details (Informational)</h3>')
                parts.append('<p style="font-size:.8em;color:#856404;margin:0 0 8px;">ℹ️ Verify manually against the PDF before actioning.</p>')
                parts.append('<table><tr><th>Date</th><th>Expected Column</th><th>Actual Column</th><th>Issue</th></tr>')
                for mi in ai_mis_issues:
                    parts.append(
                        f'<tr>'
                        f'<td><b>{html_module.escape(str(mi.get("date","—")))}</b></td>'
                        f'<td style="color:#28a745;font-weight:bold;">{html_module.escape(str(mi.get("expected_column","—")))}</td>'
                        f'<td style="color:#dc3545;font-weight:bold;">{html_module.escape(str(mi.get("actual_column","—")))}</td>'
                        f'<td>{html_module.escape(str(mi.get("issue","")))}</td>'
                        f'</tr>')
                parts.append('</table></div>')

            sp_iss = ai_data.get("spelling", {}).get("issues", [])
            if sp_iss:
                parts.append('<div class="disc"><h3>🔤 AI Vision — Spelling Issues</h3>')
                parts.append('<table><tr><th>Found Text</th><th>Correction</th><th>Location</th></tr>')
                for si in sp_iss:
                    parts.append(
                        f'<tr>'
                        f'<td style="color:#dc3545;font-weight:bold;">{html_module.escape(str(si.get("text","")))}</td>'
                        f'<td style="color:#28a745;">{html_module.escape(str(si.get("correction","")))}</td>'
                        f'<td>{html_module.escape(str(si.get("location","")))}</td>'
                        f'</tr>')
                parts.append('</table></div>')

            ha     = ai_data.get("holiday_alignment", {})
            ha_iss = ha.get("issues", [])
            if ha_iss:
                parts.append('<div class="disc"><h3>📌 AI Vision — Holiday Label Position Issues</h3>')
                parts.append(f'<p style="font-size:.82em;margin:4px 0 8px;">Pattern: <b>{ha.get("alignment_pattern","—")}</b></p>')
                parts.append('<table><tr><th>Cell Date</th><th>Position Issue</th></tr>')
                for hi in ha_iss:
                    parts.append(
                        f'<tr><td>{html_module.escape(str(hi.get("cell_date","—")))}</td>'
                        f'<td style="color:#856404;">{html_module.escape(str(hi.get("issue","")))}</td></tr>')
                parts.append('</table></div>')

            ai_ovf = ai_data.get("non_bold_overflow", {})
            if isinstance(ai_ovf, dict) and ai_ovf.get("status") == "FAIL":
                bold_vios = ai_ovf.get("bold_violations", [])
                if bold_vios:
                    parts.append('<div class="disc"><h3>🔴 AI Vision — Bold Overflow Date Violations</h3>')
                    parts.append('<table><tr><th>Date</th><th>Issue</th></tr>')
                    for bv in bold_vios:
                        parts.append(
                            f'<tr><td style="color:#dc3545;font-weight:bold;">{html_module.escape(str(bv))}</td>'
                            f'<td>Overflow/filler date from prev/next month appears in BOLD — must be non-bold</td></tr>'
                        )
                    parts.append('</table></div>')

        # ── Native summary ────────────────────────────────────────────────
        native_highlights = []
        for key in CHECKS:
            nd = native_results.get(key, {})
            if isinstance(nd, dict) and nd.get("status") in ("FAIL", "WARN", "PASS"):
                native_highlights.append(
                    f"<b>{CHECK_LABELS[key]}:</b> {nd.get('status','')} — "
                    f"{html_module.escape(str(nd.get('details',''))[:150])}"
                )
        if native_highlights:
            parts.append(
                '<div class="native-summary-box">'
                '<strong>📋 Native PDF Analysis Summary:</strong><br>'
                + "<br>".join(native_highlights)
                + '</div>'
            )

        # ── Debug panel ───────────────────────────────────────────────────
        native_slash_found = native_results.get("slash_dates", {}).get("found", [])
        ai_slash_found     = ai_data.get("slash_dates", {}).get("found", []) if isinstance(ai_data, dict) else []
        combined_pairs_str = str(slash_pairs) if slash_pairs else "none detected"
        missing_str        = str(sorted(missing_set))  if missing_set  else "none"
        misplace_str       = str(sorted(all_misplace_set)) if all_misplace_set else "none"
        native_ovf         = native_results.get("non_bold_overflow", {})
        ovf_dates_str      = str(native_ovf.get("overflow_dates", [])) if native_ovf else "none"
        bold_vio_str       = str(native_ovf.get("bold_violations", [])) if native_ovf else "none"
        dp_type            = design.get("design_type", "—")
        dp_conf            = f"{int(design.get('confidence', 0)*100)}%" if design else "—"
        dp_render          = design.get("date_rendering_mode", "—")
        dp_prev            = str(design.get("overflow_prev_cells", "—"))
        dp_next            = str(design.get("overflow_next_cells", "—"))
        dp_rows            = str(design.get("num_rows", "—"))
        dp_mcnt            = str(design.get("month_count", "—"))

        parts.append(
            f'<div class="debug-section">'
            f'<h4>🔬 Extraction + Design Debug Panel — {html_module.escape(m_name)} {yr}</h4>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Design type (AI):</span>'
            f'  <span class="debug-val">{html_module.escape(dp_type)} ({dp_conf})</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Date rendering (AI):</span>'
            f'  <span class="debug-val">{html_module.escape(dp_render)}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Overflow prev/next (AI):</span>'
            f'  <span class="debug-val">{dp_prev} / {dp_next} cells</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Grid rows (AI):</span>'
            f'  <span class="debug-val">{dp_rows} &nbsp;&nbsp; Month count: {dp_mcnt}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Native slash/stacked:</span>'
            f'  <span class="debug-val">{html_module.escape(str(native_slash_found) if native_slash_found else "none")}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">AI slash/stacked:</span>'
            f'  <span class="debug-val">{html_module.escape(str(ai_slash_found) if ai_slash_found else "none")}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Combined pairs (grid):</span>'
            f'  <span class="debug-val">{html_module.escape(combined_pairs_str)}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Missing dates:</span>'
            f'  <span class="debug-val" style="color:#dc3545;">{html_module.escape(missing_str)}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Out-of-order dates:</span>'
            f'  <span class="debug-val" style="color:#856404;">{html_module.escape(misplace_str)}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Overflow dates (native):</span>'
            f'  <span class="debug-val">{html_module.escape(ovf_dates_str)}</span>'
            f'</div>'
            f'<div class="debug-row">'
            f'  <span class="debug-key">Bold violations (overflow):</span>'
            f'  <span class="debug-val" style="color:#dc3545;">{html_module.escape(bold_vio_str)}</span>'
            f'</div>'
            f'</div>'
        )

        # ── Adaptive Visual Calendar Grid ────────────────────────────────
        if is_multimonth:
            # Three-month / multi-month view: special renderer
            parts.append(_render_three_month_grid_section(result, design))
        else:
            # Standard single-month adaptive grid
            parts.append(
                f'<div style="padding:0 24px 6px;font-size:.82em;color:#555;font-weight:700;">'
                f'📆 Adaptive Visual Grid — {html_module.escape(m_name)} {yr} '
                f'<span style="font-weight:400;color:#888;">'
                f'(overflow cells sourced from {"AI design profile" if design.get("confidence",0)>=0.75 else "calendar math fallback"})'
                f'</span></div>'
            )
            parts.append(
                '<div class="grid-legend">'
                '<span class="leg-item"><span class="leg-box" style="background:#d4edda;border-color:#c3e6cb;"></span> Present</span>'
                '<span class="leg-item"><span class="leg-box" style="background:#f8d7da;border-color:#f5c6cb;"></span> Missing/Error</span>'
                '<span class="leg-item"><span class="leg-box" style="background:#ffe0f0;border-color:#f48fb1;"></span> Out-of-order (pink)</span>'
                '<span class="leg-item"><span class="leg-box" style="background:#cfe2ff;border-color:#084298;border-width:2px;"></span> Dual-date cell</span>'
                '<span class="leg-item"><span class="leg-box" style="background:#f1f1f1;border:1px dashed #aaa;"></span> Prev/Next month ✓</span>'
                '<span class="leg-item"><span class="leg-box" style="background:#ffe8e8;border:2px solid #dc3545;"></span> Prev/Next BOLD ❌</span>'
                '</div>'
            )

            if all_misplace_set:
                parts.append(
                    '<div class="ai-mis-note">🔀 <b>Out-of-order date sequence detected</b> — '
                    'pink cells indicate dates appearing in wrong left-to-right order within a row.</div>'
                )

            # Use adaptive overflow computation
            try:
                prev_overflow, next_overflow = _compute_overflow_cells_adaptive(yr, month_n, design)
            except Exception:
                prev_overflow, next_overflow = [], []

            ai_bold_violations = set()
            if isinstance(ai_data, dict) and not ai_unavailable:
                ai_ovf_data = ai_data.get("non_bold_overflow", {})
                if isinstance(ai_ovf_data, dict):
                    ai_bold_violations = set(ai_ovf_data.get("bold_violations", []))
            native_bold_violations = set(native_ovf.get("bold_violations", [])) if native_ovf else set()
            all_bold_violations = ai_bold_violations | native_bold_violations

            # Column headers — use AI-inferred column order if available
            col_order = design.get("column_order", ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"])
            if not isinstance(col_order, list) or len(col_order) != 7:
                col_order = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]

            parts.append('<div class="calgrid">')
            for dh in col_order:
                parts.append(f'<div class="ch">{html_module.escape(str(dh)[:3])}</div>')

            # Render prev-month overflow cells
            for i, (ovf_day, ovf_month) in enumerate(prev_overflow):
                is_bold_violation = ovf_day in all_bold_violations
                if is_bold_violation:
                    cls = "c-prev-bold"
                    num_cls = "cdn-ovf-bold"
                    lbl = '<span class="cdn-bold-lbl">⚠ BOLD — MUST BE NON-BOLD</span>'
                else:
                    cls = "c-prev-ok"
                    num_cls = "cdn-ovf"
                    lbl = '<span class="cdn-ovf-lbl">prev month</span>'
                parts.append(
                    f'<div class="cd {cls}">'
                    f'<div class="{num_cls}">{ovf_day}</div>'
                    f'{lbl}'
                    f'</div>'
                )

            # Render current month days
            day = 1
            while day <= exp_d:
                if day in slash_absorbed:
                    day += 1
                    continue

                note         = ""
                is_dual_cell = day in slash_pairs
                d2           = slash_pairs.get(day)

                if is_dual_cell:
                    d1_missing = day in missing_set
                    d2_missing = (d2 is not None and d2 in missing_set)
                    d1_mis     = day in all_misplace_set
                    d2_mis     = (d2 is not None and d2 in all_misplace_set)

                    if d1_missing or d2_missing:
                        cls  = "cslash-err"
                        note = "⚠ MISSING"
                    elif d1_mis or d2_mis:
                        cls  = "cslash-warn"
                        note = "↕ OUT-OF-ORDER"
                    else:
                        cls  = "cslash"

                    if d2 is not None:
                        inner_html = (
                            f'<div class="cdn-slash">'
                            f'<span class="slash-d1">{day}</span>'
                            f'<span class="slash-d2">{d2}</span>'
                            f'</div>'
                        )
                    else:
                        inner_html = f'<div class="cdn-slash"><span class="slash-d1">{day}</span></div>'

                    parts.append(
                        f'<div class="cd {cls}">'
                        + inner_html
                        + (f'<div class="cdn2">{note}</div>' if note else
                           '<div class="cdn2" style="color:#084298;font-size:.6em;">two dates · one cell</div>')
                        + '</div>'
                    )
                else:
                    if day in all_misplace_set:
                        cls  = "cwarn"
                        note = "↕ INORDER?"
                    elif day in missing_set:
                        cls  = "cerr"
                        note = "⚠ MISSING"
                    elif dates_found_set and day not in dates_found_set:
                        cls  = "cgray"
                        note = "– not detected"
                    else:
                        cls  = "cok"

                    parts.append(
                        f'<div class="cd {cls}"><div class="cdn">{day}</div>'
                        + (f'<div class="cdn2">{note}</div>' if note else '')
                        + '</div>'
                    )

                day += 1

            # Render next-month overflow cells
            for ovf_day, ovf_month in next_overflow:
                is_bold_violation = ovf_day in all_bold_violations
                if is_bold_violation:
                    cls = "c-next-bold"
                    num_cls = "cdn-ovf-bold"
                    lbl = '<span class="cdn-bold-lbl">⚠ BOLD — MUST BE NON-BOLD</span>'
                else:
                    cls = "c-next-ok"
                    num_cls = "cdn-ovf"
                    lbl = '<span class="cdn-ovf-lbl">next month</span>'
                parts.append(
                    f'<div class="cd {cls}">'
                    f'<div class="{num_cls}">{ovf_day}</div>'
                    f'{lbl}'
                    f'</div>'
                )

            parts.append('</div>')   # calgrid

        parts.append('</div>')   # card

    parts.append('</body></html>')
    return "\n".join(parts)


# ======================================================
# STREAMLIT UI
# ======================================================
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

# ── [ADDED] Back-navigation listener + page routing ────────────────────────────
# Intercept the postMessage from the iframe back button and perform st.switch_page
_back_nav_js = """
<script>
(function() {
  // Listen for postMessage from child iframes (the robot header component)
  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'BACK_TO_DASHBOARD') {
      // Try Streamlit multipage routing first
      var base = window.location.origin;
      var paths = ['/dashboard', '/Dashboard', '/home', '/'];
      for (var i = 0; i < paths.length; i++) {
        try {
          window.top.location.href = base + paths[i];
          break;
        } catch(err) {}
      }
    }
  }, false);
})();
</script>
"""
import streamlit.components.v1 as _st_nav_comp
_st_nav_comp.html(_back_nav_js, height=0, scrolling=False)

# Handle query-param back navigation (fallback)
if st.query_params.get("nav") == "back":
    st.query_params.clear()
    try:
        st.switch_page("dashboard.py")
    except Exception:
        try:
            st.switch_page("pages/dashboard.py")
        except Exception:
            pass
# ── [END ADDED BLOCK 1] ─────────────────────────────────────────────────────


# ── Start Flask API thread once per session ──────────────────────────────────
if "datechecker_api_started" not in st.session_state:
    th = threading.Thread(target=_start_datechecker_api, daemon=True)
    th.start()
    st.session_state.datechecker_api_started = True
    time.sleep(0.3)

# ── Robot header + Back button (blue/white theme matching dashboard.py) ───────
_ROBOT_HEADER_HTML = """<!DOCTYPE html>
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


  <!-- Robot SVG (same design as dashboard.py — white/cyan dome, dark navy face) -->
  <div class="robot-mini">
    <svg viewBox="0 0 200 250" fill="none" xmlns="http://www.w3.org/2000/svg" overflow="visible">
      <defs>
        <radialGradient id="h2gHead" cx="32%" cy="20%" r="72%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="38%" stop-color="#e0f7ff"/>
          <stop offset="75%" stop-color="#b0e8f8"/>
          <stop offset="100%" stop-color="#8ecee8"/>
        </radialGradient>
        <radialGradient id="h2gBody" cx="34%" cy="22%" r="74%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#d8f3ff"/>
          <stop offset="78%" stop-color="#a4dcf5"/>
          <stop offset="100%" stop-color="#80c8e8"/>
        </radialGradient>
        <radialGradient id="h2gFace" cx="48%" cy="28%" r="68%">
          <stop offset="0%" stop-color="#1c2d6e"/>
          <stop offset="55%" stop-color="#0e1a4a"/>
          <stop offset="100%" stop-color="#080f2e"/>
        </radialGradient>
        <radialGradient id="h2gEye" cx="38%" cy="22%" r="72%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="28%" stop-color="#b8f0ff"/>
          <stop offset="60%" stop-color="#00c8ff"/>
          <stop offset="100%" stop-color="#0060cc"/>
        </radialGradient>
        <radialGradient id="h2gNavy" cx="28%" cy="20%" r="75%">
          <stop offset="0%" stop-color="#2a4ab8"/>
          <stop offset="55%" stop-color="#0e1a5a"/>
          <stop offset="100%" stop-color="#060e30"/>
        </radialGradient>
        <radialGradient id="h2gBadge" cx="38%" cy="25%" r="70%">
          <stop offset="0%" stop-color="#1e3598"/>
          <stop offset="55%" stop-color="#0b1655"/>
          <stop offset="100%" stop-color="#050c30"/>
        </radialGradient>
        <linearGradient id="h2gSmile" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#60d8ff"/>
          <stop offset="50%" stop-color="#c0f4ff"/>
          <stop offset="100%" stop-color="#60d8ff"/>
        </linearGradient>
        <filter id="h2fEyeBloom" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="h2fSoft" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="6"/>
        </filter>
        <filter id="h2fSmile" x="-40%" y="-60%" width="180%" height="220%">
          <feGaussianBlur stdDeviation="4" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <g class="r-float">
        <!-- Ground shadow -->
        <ellipse cx="100" cy="243" rx="46" ry="7" fill="rgba(0,100,200,.14)" filter="url(#h2fSoft)"/>

        <!-- Body -->
        <path d="M100 155 C62 155 48 168 48 186 C48 210 66 232 100 240 C134 232 152 210 152 186 C152 168 138 155 100 155Z"
              fill="url(#h2gBody)"/>
        <path d="M100 155 C62 155 48 168 48 186 C48 210 66 232 100 240 C134 232 152 210 152 186 C152 168 138 155 100 155Z"
              fill="none" stroke="rgba(140,210,240,.7)" stroke-width="1.8"/>

        <!-- Left arm -->
        <g class="r-arm-l">
          <ellipse cx="50" cy="168" rx="10" ry="10" fill="url(#h2gNavy)"/>
          <rect x="30" y="162" width="24" height="36" rx="12" fill="url(#h2gNavy)"/>
          <rect x="30" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.3)" stroke-width="1.2"/>
        </g>

        <!-- Right arm -->
        <g class="r-arm-r">
          <ellipse cx="150" cy="168" rx="10" ry="10" fill="url(#h2gNavy)"/>
          <rect x="146" y="162" width="24" height="36" rx="12" fill="url(#h2gNavy)"/>
          <rect x="146" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.3)" stroke-width="1.2"/>
        </g>

        <!-- Chest AI badge -->
        <path d="M100 170 C82 170 76 180 76 192 C76 207 86 220 100 225 C114 220 124 207 124 192 C124 180 118 170 100 170Z"
              fill="url(#h2gBadge)"/>
        <path d="M100 170 C82 170 76 180 76 192 C76 207 86 220 100 225 C114 220 124 207 124 192 C124 180 118 170 100 170Z"
              fill="none" stroke="rgba(60,110,220,.5)" stroke-width="1.4"/>
        <text x="100" y="200" text-anchor="middle" fill="#a8f0ff" font-size="19" font-weight="900"
              font-family="Arial Black,Arial,sans-serif" letter-spacing="3">AI</text>

        <!-- HEAD -->
        <g class="r-head">
          <!-- Dome -->
          <circle cx="100" cy="82" r="65" fill="url(#h2gHead)"/>
          <circle cx="100" cy="82" r="65" fill="none" stroke="rgba(130,200,235,.6)" stroke-width="1.8"/>
          <!-- Gloss -->
          <ellipse cx="68" cy="42" rx="30" ry="18" fill="rgba(255,255,255,.86)" transform="rotate(-28 68 42)"/>
          <ellipse cx="64" cy="38" rx="17" ry="10" fill="rgba(255,255,255,.95)" transform="rotate(-28 64 38)"/>

          <!-- Headset arc -->
          <path d="M44 84 C44 32 156 32 156 84" fill="none" stroke="#0e1a50" stroke-width="6" stroke-linecap="round"/>

          <!-- Left ear cup -->
          <ellipse cx="41" cy="86" rx="14" ry="18" fill="url(#h2gNavy)"/>
          <ellipse cx="41" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.35)" stroke-width="1.2"/>

          <!-- Right ear cup -->
          <ellipse cx="159" cy="86" rx="14" ry="18" fill="url(#h2gNavy)"/>
          <ellipse cx="159" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.35)" stroke-width="1.2"/>

          <!-- Mic -->
          <path d="M41 100 C44 112 54 118 64 120" fill="none" stroke="#0e1a50" stroke-width="3.5" stroke-linecap="round"/>
          <circle cx="66" cy="121" r="5.5" fill="#0e1a50"/>
          <circle cx="66" cy="121" r="3.5" fill="#1e3080"/>

          <!-- Face panel -->
          <rect x="56" y="52" width="88" height="70" rx="20" fill="url(#h2gFace)"/>
          <rect x="56" y="52" width="88" height="70" rx="20" fill="none" stroke="rgba(30,80,180,.4)" stroke-width="1.4"/>

          <!-- Left eye bloom -->
          <rect x="66" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".22" filter="url(#h2fEyeBloom)">
            <animate attributeName="opacity" values=".12;.36;.12" dur="2.2s" repeatCount="indefinite"/>
          </rect>
          <rect x="68" y="62" width="22" height="30" rx="8" fill="#040e28"/>
          <rect x="69" y="63" width="20" height="28" rx="7" fill="url(#h2gEye)" class="r-eye-glow"/>
          <rect x="73" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.9)"/>

          <!-- Right eye bloom -->
          <rect x="108" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".22" filter="url(#h2fEyeBloom)">
            <animate attributeName="opacity" values=".12;.36;.12" dur="2.2s" begin=".35s" repeatCount="indefinite"/>
          </rect>
          <rect x="110" y="62" width="22" height="30" rx="8" fill="#040e28"/>
          <rect x="111" y="63" width="20" height="28" rx="7" fill="url(#h2gEye)" class="r-eye-glow"/>
          <rect x="115" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.9)"/>

          <!-- Smile -->
          <path d="M72 103 Q100 122 128 103" stroke="#00d0ff" stroke-width="6" fill="none"
                stroke-linecap="round" opacity=".2" filter="url(#h2fSmile)">
            <animate attributeName="opacity" values=".12;.32;.12" dur="3.2s" repeatCount="indefinite"/>
          </path>
          <path d="M74 103 Q100 120 126 103" stroke="url(#h2gSmile)" stroke-width="4" fill="none" stroke-linecap="round">
            <animate attributeName="opacity" values=".78;1;.78" dur="3.2s" repeatCount="indefinite"/>
          </path>

          <!-- Cheek blush -->
          <circle cx="68" cy="108" r="7" fill="#60d8ff" opacity=".16" filter="url(#h2fSoft)">
            <animate attributeName="opacity" values=".08;.26;.08" dur="3.5s" repeatCount="indefinite"/>
          </circle>
          <circle cx="132" cy="108" r="7" fill="#60d8ff" opacity=".16" filter="url(#h2fSoft)">
            <animate attributeName="opacity" values=".08;.26;.08" dur="3.5s" begin=".6s" repeatCount="indefinite"/>
          </circle>
        </g><!-- /r-head -->
      </g><!-- /r-float -->
    </svg>
  </div>

  <!-- Title & subtitle -->
  <div class="header-text">
    <div class="header-title">📅 AI DateChecker &amp; Calendar QC Auditor</div>
    <div class="header-sub">
      Zero-defect pre-press QC powered by <strong>LangGraph AI Agent · Design Inference · RAG · LangChain LLM</strong>.<br>
      Supports desk-pad, wall, three-month, large-format, fiscal &amp; academic calendars.
    </div>
    <div class="header-badge">
      <div class="dot-live"></div>
      AI Pipeline Active · 6-Node LangGraph
    </div>
  </div>

</div>

</body>
</html>"""

_st_components.html(_ROBOT_HEADER_HTML, height=155, scrolling=False)

# ── [ADDED] Native Streamlit back button (reliable multipage navigation) ──────
_back_col, _spacer = st.columns([1.4, 8])
with _back_col:
    if st.button("⬅️ Back to Dashboard", key="_qc_back_btn",
                 use_container_width=True,
                 help="Return to the main AI-Powered Dashboard"):
        try:
            st.switch_page("dashboard.py")
        except Exception:
            try:
                st.switch_page("pages/dashboard.py")
            except Exception:
                # Last resort: navigate via query param + rerun
                st.query_params["nav"] = "back"
                st.rerun()
# ── [END ADDED BLOCK 2] ─────────────────────────────────────────────────────


st.title(f"{APP_ICON} {APP_TITLE}")
st.caption(
    "Zero-defect pre-press QC powered by **LangGraph AI Agent + AI Design Inference + RAG Knowledge Base + LangChain LLM**. "
    "Supports ANY calendar design — desk-pad, wall, three-month, large-format, fiscal year, academic year."
)

st.markdown(
    """<div style="background:linear-gradient(90deg,#6f42c1,#0d6efd);color:#fff;
    display:inline-block;padding:5px 16px;border-radius:20px;font-size:.82em;font-weight:700;margin-bottom:12px;">
    🤖 Pipeline: Extract → <b>Design Inference</b> → Native Checks → RAG → AI Vision → Synthesize
    </div>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Audit Settings")
    use_ai_vision = st.toggle("Enable AI Vision Analysis", value=True,
                              help="Uses GPT-4o-mini vision for design inference + QC audit")
    batch_size = st.selectbox("Months per HTML Report Batch", [3, 6, 12], index=0)
    show_debug = st.toggle("Show Per-Page Debug Panel", value=True)
    st.markdown("---")
    st.markdown("**🤖 Agent Architecture (6 Nodes):**")
    st.markdown("1. **Extract** — PyMuPDF native text extraction")
    st.markdown("2. **Design Inference** ✨ *NEW* — AI learns page layout family")
    st.markdown("3. **Native Checks** — Rule-based structural checks")
    st.markdown("4. **RAG Retrieve** — BM25 knowledge base")
    st.markdown("5. **AI Vision** — GPT-4o-mini visual QC audit")
    st.markdown("6. **Synthesize** — Merge + final verdict")
    st.markdown("---")
    st.markdown("**🎨 Design Families Supported:**")
    for k, (icon, _, lbl) in DESIGN_TYPE_META.items():
        if k != "unknown":
            st.markdown(f"{icon} {lbl}")
    st.markdown("---")
    st.markdown("**8 QC Checks Performed:**")
    for k, v in CHECK_LABELS.items():
        st.markdown(f"{CHECK_ICONS[k]} {v}")
    st.markdown("---")
    st.markdown("**✨ Design-Aware Features:**")
    st.markdown("- AI infers layout family before auditing")
    st.markdown("- Overflow cells sourced from AI profile (not just math)")
    st.markdown("- Column order validated against inferred week-start")
    st.markdown("- Three-month views get adaptive multi-panel grid")
    st.markdown("- Date rendering mode (slash/stacked/single) detected per design")
    st.markdown("- Design confidence score shown per page")

col1, col2 = st.columns([2, 1])
with col1:
    uploaded_pdf = st.file_uploader("📄 Upload Calendar PDF (any design)", type=["pdf"])
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    audit_btn = st.button("🔍 Run Full Zero-Defect QC Audit",
                          type="primary", use_container_width=True)

if audit_btn:
    if not uploaded_pdf:
        st.error("⚠️ Please upload a Calendar PDF first.")
        st.stop()

    pdf_bytes = uploaded_pdf.read()
    doc       = fitz.open(stream=pdf_bytes, filetype="pdf")
    n_pages   = len(doc)
    st.info(f"📄 PDF has **{n_pages}** page(s). Initialising LangGraph audit agent…")

    retriever = build_rag_retriever()
    st.success(f"🔍 RAG knowledge base ready — {len(CALENDAR_QC_RULES)} QC rules indexed.")

    all_results: List[Dict] = []
    progress_bar = st.progress(0)
    status_text  = st.empty()

    # Stage indicator
    stage_cols = st.columns(6)
    stages = ["Extract", "Design Inference", "Native Checks", "RAG", "AI Vision", "Synthesize"]

    for pg in range(n_pages):
        month_label = f"page {pg+1}"
        status_text.text(
            f"🤖 Agent auditing {month_label} of {n_pages}… "
            f"[Extract → Design Inference → NativeChecks → RAG → AIVision → Synthesize]"
        )
        try:
            res = audit_page_agent(pdf_bytes, pg, use_ai=use_ai_vision)
            all_results.append(res)
            if res.get("month_name") and res.get("year"):
                month_label = f"{res['month_name']} {res['year']}"
        except Exception as e:
            all_results.append({"page": pg + 1, "error": str(e), "overall_status": "UNKNOWN"})
        progress_bar.progress((pg + 1) / n_pages)

    status_text.text("✅ Agent audit complete!")
    progress_bar.empty()

    st.markdown("---")
    st.subheader("📊 Audit Summary Dashboard")

    total   = len(all_results)
    passed  = sum(1 for r in all_results if r.get("overall_status") == "PASS")
    failed  = sum(1 for r in all_results if r.get("overall_status") == "FAIL")
    warned  = sum(1 for r in all_results if r.get("overall_status") == "WARN")
    unknown = total - passed - failed - warned

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📄 Total Pages", total)
    c2.metric("✅ PASS",        passed)
    c3.metric("❌ FAIL",        failed)
    c4.metric("⚠️ WARN",        warned)
    c5.metric("❓ Unknown",      unknown)

    # Design family breakdown
    design_counts: Dict[str, int] = {}
    for r in all_results:
        dp = r.get("design_profile", {})
        dt = dp.get("design_type", "unknown") if dp else "unknown"
        design_counts[dt] = design_counts.get(dt, 0) + 1

    if design_counts:
        st.markdown("**🎨 Design Families Detected:**")
        dc_cols = st.columns(min(len(design_counts), 5))
        for i, (dt, cnt) in enumerate(design_counts.items()):
            icon, _, lbl = DESIGN_TYPE_META.get(dt, DESIGN_TYPE_META["unknown"])
            dc_cols[i % len(dc_cols)].metric(f"{icon} {lbl}", cnt)

    summary_rows = []
    for r in all_results:
        dp = r.get("design_profile", {})
        dt = dp.get("design_type", "—") if dp else "—"
        if "error" in r:
            row = {
                "Page": r.get("page"), "Month/Year": "Error", "Design": dt,
                "Leap Yr":"—","Seq.":"—","Misplace":"—","Align":"—",
                "Slash":"—","Non-Bold":"—","Spelling":"—","Hol.Align":"—","OVERALL":"ERROR",
            }
        else:
            cs  = r.get("check_statuses", {})
            row = {
                "Page":       r.get("page"),
                "Month/Year": f"{r.get('month_name','?')} {r.get('year','')}",
                "Design":     dt,
                "Leap Yr":    cs.get("leap_year_check",       "N/A"),
                "Seq.":       cs.get("sequential_continuity", "N/A"),
                "Misplace":   cs.get("date_misplacement",     "N/A"),
                "Align":      cs.get("data_alignment",        "N/A"),
                "Slash":      cs.get("slash_dates",           "N/A"),
                "Non-Bold":   cs.get("non_bold_overflow",     "N/A"),
                "Spelling":   cs.get("spelling",              "N/A"),
                "Hol.Align":  cs.get("holiday_alignment",     "N/A"),
                "OVERALL":    r.get("overall_status",         "UNKNOWN"),
            }
        summary_rows.append(row)

    if summary_rows:
        sdf = pd.DataFrame(summary_rows)

        def colour_cell(val):
            v = str(val)
            if v == "FAIL":      return "background-color:#f8d7da;color:#721c24;font-weight:bold"
            if v == "PASS":      return "background-color:#d4edda;color:#155724"
            if v == "WARN":      return "background-color:#fff3cd;color:#856404"
            if v in ("N/A","—"): return "color:#999"
            return ""

        skip   = {"Page", "Month/Year", "Design"}
        styled = sdf.style.map(colour_cell, subset=[c for c in sdf.columns if c not in skip])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # Leap year banner
    leap_pages = [r for r in all_results if r.get("is_leap_year") and r.get("month_name") == "February"]
    if leap_pages:
        lp  = leap_pages[0]
        lyr = lp.get("year", "")
        lcs = lp.get("check_statuses", {}).get("leap_year_check", "UNKNOWN")
        color  = "#cfe2ff" if lcs == "PASS" else "#f8d7da"
        border = "#0d6efd" if lcs == "PASS" else "#dc3545"
        msg    = (f"✅ Leap year {lyr}: February has 29 days and day 29 is present."
                  if lcs == "PASS"
                  else f"❌ CRITICAL: {lyr} is a leap year — February day 29 issue detected!")
        st.markdown(
            f'<div style="background:{color};border-left:5px solid {border};'
            f'padding:12px 16px;border-radius:6px;margin-bottom:12px;font-weight:600;">'
            f'🗓️ {msg}</div>', unsafe_allow_html=True)

    # ── Per-page debug expander ───────────────────────────────────────────
    if show_debug:
        st.markdown("---")
        st.subheader("🔬 Per-Page Design + Extraction Debug")
        for r in all_results:
            if "error" in r:
                continue
            m_lbl = f"{r.get('month_name','?')} {r.get('year','')}"
            dp    = r.get("design_profile", {})
            dt    = dp.get("design_type", "unknown") if dp else "unknown"
            icon, _, _ = DESIGN_TYPE_META.get(dt, DESIGN_TYPE_META["unknown"])
            with st.expander(f"{icon} {m_lbl} — {dt} — Debug", expanded=False):
                # Design profile columns
                st.markdown("#### 🎨 AI Design Profile")
                if dp:
                    dp_disp = {k: v for k, v in dp.items()
                               if not k.startswith("_") and k != "layout_notes"}
                    dp_col1, dp_col2 = st.columns(2)
                    items = list(dp_disp.items())
                    half  = len(items) // 2
                    with dp_col1:
                        for k, v in items[:half]:
                            st.markdown(f"**{k}:** `{v}`")
                    with dp_col2:
                        for k, v in items[half:]:
                            st.markdown(f"**{k}:** `{v}`")
                    if dp.get("layout_notes"):
                        st.info(f"📝 Layout notes: {dp['layout_notes']}")
                else:
                    st.warning("No design profile available.")

                st.markdown("#### 🔍 Extraction Data")
                native_r   = r.get("native", {})
                ai_r       = r.get("ai", {}) if isinstance(r.get("ai"), dict) else {}
                ai_available = not ai_r.get("_ai_unavailable", False)
                n_slash    = native_r.get("slash_dates", {}).get("found", [])
                a_slash    = ai_r.get("slash_dates", {}).get("found", []) if ai_available else []
                pairs      = _extract_slash_pairs(r)
                n_seq      = native_r.get("sequential_continuity", {})
                a_seq      = ai_r.get("sequential_continuity", {}) if ai_available else {}
                miss_n     = n_seq.get("missing_dates", [])
                miss_a     = a_seq.get("missing_dates", [])
                n_mis      = native_r.get("date_misplacement", {})
                a_mis      = ai_r.get("date_misplacement", {}) if ai_available else {}
                n_mis_dates = [i.get("date") for i in n_mis.get("issues", []) if isinstance(i, dict)] if isinstance(n_mis, dict) else []
                a_mis_dates = [i.get("date") for i in a_mis.get("issues", []) if isinstance(i, dict)] if isinstance(a_mis, dict) else []
                n_ovf      = native_r.get("non_bold_overflow", {})
                ovf_dates  = n_ovf.get("overflow_dates", []) if isinstance(n_ovf, dict) else []
                bold_vios  = n_ovf.get("bold_violations", []) if isinstance(n_ovf, dict) else []

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.markdown("**Native slash/stacked:**")
                    st.code(str(n_slash) if n_slash else "none", language=None)
                    st.markdown("**Native missing dates:**")
                    st.code(str(miss_n) if miss_n else "none", language=None)
                    st.markdown("**Native out-of-order:**")
                    st.code(str(n_mis_dates) if n_mis_dates else "none", language=None)
                with col_b:
                    st.markdown("**AI slash/stacked:**")
                    st.code(str(a_slash) if a_slash else "none", language=None)
                    st.markdown("**AI missing dates:**")
                    st.code(str(miss_a) if miss_a else "none", language=None)
                    st.markdown("**AI misplaced (info):**")
                    st.code(str(a_mis_dates) if a_mis_dates else "none", language=None)
                with col_c:
                    st.markdown("**Combined grid pairs:**")
                    st.code(str(pairs) if pairs else "none", language=None)
                    st.markdown("**Overflow dates:**")
                    st.code(str(ovf_dates) if ovf_dates else "none", language=None)
                    st.markdown("**Bold violations:**")
                    st.code(str(bold_vios) if bold_vios else "none", language=None)

                if ai_available:
                    st.success("✅ AI Vision analysis complete")

    st.markdown("---")
    st.subheader("📋 Detailed QC Reports (by Batch)")

    for i in range(0, len(all_results), batch_size):
        batch  = all_results[i:i + batch_size]
        labels = [f"{r.get('month_name','?')} {r.get('year','')}" for r in batch if "error" not in r]
        b_label        = " | ".join(labels) if labels else f"Pages {i+1}–{i+len(batch)}"
        has_fail_batch = any(r.get("overall_status") == "FAIL" for r in batch)

        with st.expander(f"{'❌' if has_fail_batch else '✅'} Batch: {b_label}", expanded=(i == 0)):
            html_rpt = generate_html_report(batch, b_label)
            st.components.v1.html(html_rpt, height=900, scrolling=True)
            st.download_button(
                f"⬇️ Download HTML Report — {b_label}",
                html_rpt.encode("utf-8"),
                f"qc_report_{b_label.replace(' | ','_').replace(' ','_')}.html",
                mime="text/html",
                key=f"dl_{i}",
            )

    if summary_rows:
        st.download_button(
            "⬇️ Download Full Audit Summary (CSV)",
            pd.DataFrame(summary_rows).to_csv(index=False).encode("utf-8"),
            "calendar_qc_audit_summary.csv",
            mime="text/csv",
        )

    st.markdown("---")
    if failed > 0:
        st.error(
            f"🚨 **AUDIT VERDICT: {failed} PAGE(S) FAILED QC CHECKS.**\n\n"
            "**DO NOT send to print.** Fix all ❌ FAIL items first. "
            "A single error on a print run of millions will result in total financial loss."
        )
    elif warned > 0:
        st.warning(
            f"⚠️ **AUDIT VERDICT: {warned} page(s) have WARNINGS.**\n\n"
            "Review all ⚠️ items carefully before approving for print."
        )
    else:
        st.success(
            "✅ **AUDIT VERDICT: All pages passed automated QC checks.**\n\n"
            "Mandatory: Perform final manual sign-off review before approving for mass production."
        )
