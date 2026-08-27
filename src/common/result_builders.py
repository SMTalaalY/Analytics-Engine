"""
Payload builders.

Every analytics function returns the same envelope, so the frontend can render
any chart without knowing which module produced it. Three shapes exist:

  build_chart_result  - multi-point series (bar, line, stacked, donut)
  build_card_result   - single KPI with a previous-period comparison
  build_empty_result  - graceful empty state when a required column is absent
"""

import pandas as pd

from config.constants import (
    XVALUE, YVALUE1, YVALUE2, YVALUE3, YVALUE4,
    NAME1, NAME2, NAME3, NAME4,
    EMPLOYEE_INDEX,
)
from config.settings import DEFAULT_CURRENCY, SENTINEL_DATE


def employee_details(frame, columns):
    """
    Drill-down records behind a chart, limited to configured columns.

    Datetime columns are rendered as YYYY-MM-DD. The source system's sentinel
    date (meaning "not set") and genuine nulls both render as '-' rather than
    leaking a literal 1900 date into the UI.
    """
    if frame is None or frame.empty:
        return [], []

    available = [c for c in columns if c in frame.columns and c != EMPLOYEE_INDEX]
    if not available:
        return [], []

    if EMPLOYEE_INDEX in frame.columns:
        details = frame.drop_duplicates(EMPLOYEE_INDEX)[available].copy()
    else:
        details = frame[available].copy()

    sentinel = pd.Timestamp(SENTINEL_DATE)
    for col in details.columns:
        if pd.api.types.is_datetime64_any_dtype(details[col]):
            details[col] = details[col].where(details[col] != sentinel, pd.NaT)
            details[col] = details[col].dt.strftime("%Y-%m-%d").fillna("-")

    return details.to_dict("records"), available


def point(x, y1="", y2="", y3="", y4="", n1="", n2="", n3="", n4=""):
    """Build one data point in the canonical shape."""
    return {
        XVALUE: x,
        YVALUE1: y1, YVALUE2: y2, YVALUE3: y3, YVALUE4: y4,
        NAME1: n1, NAME2: n2, NAME3: n3, NAME4: n4,
    }


def build_chart_result(
    data, filters_applied, xlabel, ylabel, title, col_map, columns,
    color_config, graph_type, text_color, graph_size, currency_code,
    description, formula, details=None, active_columns=None,
):
    keys = active_columns if active_columns is not None else columns
    return {
        "as_off": {
            "data": data,
            "filters_applied": filters_applied,
            "xlabel": xlabel,
            "ylabel": ylabel,
            "title": title,
            "display_names": {c: col_map.get(c, "") for c in keys if c != EMPLOYEE_INDEX},
            "color_config": color_config,
            "graph_type": graph_type,
            "text_color": text_color,
            "graph_size": graph_size,
            "currency": currency_code or DEFAULT_CURRENCY,
            "unique_employee_details": details or [],
            "formula": {"Description": description, "Formula": formula},
        }
    }


def build_card_result(
    value, previous_value, title, color_config, graph_type, text_color,
    graph_size, col_map, filters_applied, value_label="Value", unit="%",
    description="", formula="", details=None, active_columns=None,
):
    change = round(value - previous_value, 2) if previous_value is not None else 0.0
    display_names = (
        {c: col_map.get(c, "") for c in active_columns}
        if active_columns is not None
        else col_map
    )
    return {
        "as_off": {
            "data": [
                point(
                    title,
                    value,
                    previous_value if previous_value is not None else 0,
                    change,
                    "",
                    value_label,
                    "Previous Month",
                    "Change",
                    "",
                )
            ],
            "filters_applied": filters_applied,
            "xlabel": "",
            "ylabel": unit,
            "title": title,
            "display_names": display_names,
            "color_config": color_config,
            "graph_type": graph_type,
            "text_color": text_color,
            "graph_size": graph_size,
            "unit": unit,
            "unique_employee_details": details or [],
            "formula": {"Description": description, "Formula": formula},
        }
    }


def build_empty_result(
    filters_applied, xlabel, ylabel, title, col_map, color_config,
    graph_type, text_color, graph_size, currency_code, description, reason,
):
    """Returned when a required column is missing — the chart renders empty
    rather than the request failing."""
    return {
        "as_off": {
            "data": [],
            "filters_applied": filters_applied,
            "xlabel": xlabel,
            "ylabel": ylabel,
            "title": title,
            "display_names": col_map,
            "color_config": color_config,
            "graph_type": graph_type,
            "text_color": text_color,
            "graph_size": graph_size,
            "currency": currency_code or DEFAULT_CURRENCY,
            "unique_employee_details": [],
            "formula": {"Description": description, "Formula": reason},
        }
    }


def safe_pct(numerator, denominator, digits=2):
    """Percentage with divide-by-zero guarded."""
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, digits)
