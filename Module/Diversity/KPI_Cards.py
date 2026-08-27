"""
Diversity KPI cards.

Each function returns a single headline figure plus the previous calendar
month's value so the frontend can render a delta. All of them share the same
signature, which is what lets the route dispatch them concurrently without
special-casing.
"""

import pandas as pd

from config.constants import XVALUE, YVALUE1, YVALUE2, YVALUE3, YVALUE4, NAME1, NAME2, NAME3, NAME4
from config.settings import LEADERSHIP_GRADES, LEADERSHIP_KEYWORDS, FLEXIBLE_WORK_KEYWORDS
from src.common.graph_config import get_graph_config, resolve_grade_column, resolve_first_present
from src.common.preprocessing import previous_month_frame, active_frame
from src.common.result_builders import (
    build_card_result,
    employee_details,
    safe_pct,
)

SALARY_COLUMNS = ["BasicSalary", "GrossSalary", "Salary", "TotalSalary"]
TRAINING_COLUMNS = ["TrainingCount", "TrainingsAttended", "TrainingHours"]
DISABILITY_COLUMNS = ["IsDisabled", "HasDisability", "DisabilityFlag", "Disability"]
PROMOTION_COLUMNS = ["PromotionDate", "LastPromotionDate", "GradeChangeDate", "PromotionFlag"]
WORK_MODE_COLUMNS = ["WorkArrangement", "EmploymentType", "ContractType", "WorkMode"]
TRUTHY = [1, True, "Yes", "Y", "yes", "true", "True"]


def _config(df_graph_authorities, df_graph_columns, graph_key, client_index, user_emp_index):
    return get_graph_config(df_graph_authorities, df_graph_columns, graph_key, client_index, user_emp_index)


def gender_pay_gap(df_filtered, filters_applied, start_date, end_date,
                   df_graph_columns, df_graph_authorities, client_index,
                   user_emp_index, currency_code=None):
    """Percentage gap between mean male and mean female salary."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_pay_gap", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    salary_col = resolve_first_present(df, SALARY_COLUMNS)

    gap = prev_gap = 0.0
    if salary_col:
        avg_male = df[df["Gender"] == "M"][salary_col].mean() or 0
        avg_female = df[df["Gender"] == "F"][salary_col].mean() or 0
        gap = round((avg_male - avg_female) / avg_male * 100, 2) if avg_male > 0 else 0.0

        prev = active_frame(previous_month_frame(df_filtered, end_date))
        pm_male = prev[prev["Gender"] == "M"][salary_col].mean() or 0
        pm_female = prev[prev["Gender"] == "F"][salary_col].mean() or 0
        prev_gap = round((pm_male - pm_female) / pm_male * 100, 2) if pm_male > 0 else 0.0

    details, active_cols = employee_details(df, columns)
    return build_card_result(
        gap, prev_gap, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Gender Pay Gap %", unit="%",
        description="Difference between average male and average female salary.",
        formula="((Avg Male Salary - Avg Female Salary) / Avg Male Salary) x 100",
        details=details, active_columns=active_cols,
    )


def diversity_in_leadership(df_filtered, filters_applied, start_date, end_date,
                            df_graph_columns, df_graph_authorities, client_index,
                            user_emp_index, currency_code=None):
    """Share of leadership-grade roles held by female employees."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_in_leadership", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    grade_col = resolve_grade_column(df)

    def leaders_of(frame):
        if not grade_col or grade_col not in frame.columns:
            return frame
        return frame[frame[grade_col].astype(str).str.strip().isin(LEADERSHIP_GRADES)]

    leaders = leaders_of(df)
    pct = safe_pct(len(leaders[leaders["Gender"] == "F"]), len(leaders))

    prev_leaders = leaders_of(active_frame(previous_month_frame(df_filtered, end_date)))
    prev_pct = safe_pct(
        len(prev_leaders[prev_leaders["Gender"] == "F"]) if not prev_leaders.empty else 0,
        len(prev_leaders),
    )

    details, active_cols = employee_details(leaders, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="% Female Leaders", unit="%",
        description="Percentage of leadership/senior-grade roles held by female employees.",
        formula="(Female Leaders / Total Leaders) x 100",
        details=details, active_columns=active_cols,
    )


def hiring_rate(df_filtered, filters_applied, start_date, end_date,
                df_graph_columns, df_graph_authorities, client_index,
                user_emp_index, currency_code=None):
    """Share of new hires in the period who are female."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_hiring_rate", client_index, user_emp_index
    )
    df = df_filtered.copy()
    window_start = start_date or df["ServiceStartDate"].min()

    hires = df[(df["ServiceStartDate"] >= window_start) & (df["ServiceStartDate"] <= end_date)]
    pct = safe_pct(len(hires[hires["Gender"] == "F"]), len(hires))

    prev_end = end_date.replace(day=1) - pd.Timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_hires = df[(df["ServiceStartDate"] >= prev_start) & (df["ServiceStartDate"] <= prev_end)]
    prev_pct = safe_pct(len(prev_hires[prev_hires["Gender"] == "F"]), len(prev_hires))

    details, active_cols = employee_details(hires, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Diversity Hiring Rate %", unit="%",
        description="Percentage of new hires in the selected period who are female.",
        formula="(Female Hires / Total Hires) x 100",
        details=details, active_columns=active_cols,
    )


def training_participation(df_filtered, filters_applied, start_date, end_date,
                           df_graph_columns, df_graph_authorities, client_index,
                           user_emp_index, currency_code=None):
    """Female share of employees who attended training.

    Falls back to overall female share when no training column is present in
    the deployment's schema.
    """
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_training_participation", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    training_col = resolve_first_present(df, TRAINING_COLUMNS)

    source = df[df[training_col] > 0] if training_col else df
    pct = safe_pct(len(source[source["Gender"] == "F"]), len(source))

    prev = active_frame(previous_month_frame(df_filtered, end_date))
    prev_pct = safe_pct(len(prev[prev["Gender"] == "F"]) if not prev.empty else 0, len(prev))

    details, active_cols = employee_details(source, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Training Participation %", unit="%",
        description="Percentage of training participants who are female.",
        formula="(Female Trained / Total Trained) x 100",
        details=details, active_columns=active_cols,
    )


def candidates_interviewed(df_filtered, filters_applied, start_date, end_date,
                           df_graph_columns, df_graph_authorities, client_index,
                           user_emp_index, currency_code=None, df_recruitment=None):
    """Female share of interviewed candidates.

    Uses the recruitment frame when available; otherwise approximates from the
    employee frame.
    """
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_candidates_interviewed", client_index, user_emp_index
    )
    source = active_frame(df_filtered)
    prev_pct = 0.0

    if df_recruitment is not None and "Gender" in df_recruitment.columns:
        rec = df_recruitment.copy()
        if "HiringStartDate" in rec.columns:
            rec["HiringStartDate"] = pd.to_datetime(rec["HiringStartDate"], errors="coerce")
            window_start = start_date or rec["HiringStartDate"].min()
            rec = rec[(rec["HiringStartDate"] >= window_start) & (rec["HiringStartDate"] <= end_date)]
        pct = safe_pct(len(rec[rec["Gender"] == "F"]), len(rec))
        source = rec
    else:
        pct = safe_pct(len(source[source["Gender"] == "F"]), len(source))
        prev = previous_month_frame(df_filtered, end_date)
        prev_pct = safe_pct(len(prev[prev["Gender"] == "F"]) if not prev.empty else 0, len(prev))

    details, active_cols = employee_details(source, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Diverse Candidates %", unit="%",
        description="Percentage of interviewed candidates who are female.",
        formula="(Female Candidates / Total Candidates) x 100",
        details=details, active_columns=active_cols,
    )


def disability_inclusion_rate(df_filtered, filters_applied, start_date, end_date,
                              df_graph_columns, df_graph_authorities, client_index,
                              user_emp_index, currency_code=None):
    """Share of active employees recorded as having a disability."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_disability_inclusion_rate", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    col = resolve_first_present(df, DISABILITY_COLUMNS)

    disabled = df[df[col].isin(TRUTHY)] if col else df.iloc[0:0]
    pct = safe_pct(len(disabled), len(df))

    prev = active_frame(previous_month_frame(df_filtered, end_date))
    prev_disabled = len(prev[prev[col].isin(TRUTHY)]) if col and col in prev.columns else 0
    prev_pct = safe_pct(prev_disabled, len(prev))

    details, active_cols = employee_details(disabled if not disabled.empty else df, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Disability Inclusion Rate %", unit="%",
        description="Percentage of active employees identified as having a disability.",
        formula="(Employees with Disability / Total Active Headcount) x 100",
        details=details, active_columns=active_cols,
    )


def retention_rate(df_filtered, filters_applied, start_date, end_date,
                   df_graph_columns, df_graph_authorities, client_index,
                   user_emp_index, currency_code=None):
    """Retention rate among female employees hired within the period."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_retention_rate", client_index, user_emp_index
    )
    df = df_filtered.copy()
    window_start = start_date or df["ServiceStartDate"].min()

    hired = df[
        (df["Gender"] == "F")
        & (df["ServiceStartDate"] >= window_start)
        & (df["ServiceStartDate"] <= end_date)
    ]
    retained = hired[hired["ServiceEndDate"].isna() | (hired["ServiceEndDate"] > end_date)]
    pct = safe_pct(len(retained), len(hired))

    prev_end = end_date.replace(day=1) - pd.Timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_hired = df[
        (df["Gender"] == "F")
        & (df["ServiceStartDate"] >= prev_start)
        & (df["ServiceStartDate"] <= prev_end)
    ]
    prev_retained = prev_hired[
        prev_hired["ServiceEndDate"].isna() | (prev_hired["ServiceEndDate"] > prev_end)
    ]
    prev_pct = safe_pct(len(prev_retained), len(prev_hired))

    details, active_cols = employee_details(retained, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Diverse Retention Rate %", unit="%",
        description="Retention rate of female employees hired within the period.",
        formula="(Female Retained / Female Hired) x 100",
        details=details, active_columns=active_cols,
    )


def gender_balance_in_promotion(df_filtered, filters_applied, start_date, end_date,
                                df_graph_columns, df_graph_authorities, client_index,
                                user_emp_index, currency_code=None):
    """Female share of promotions. Handles both date-based and flag-based
    promotion columns, since deployments model this differently."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_balance_in_promotion", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    window_start = start_date or df["ServiceStartDate"].min()
    promo_col = resolve_first_present(df, PROMOTION_COLUMNS)

    if promo_col and "Date" in promo_col:
        df[promo_col] = pd.to_datetime(df[promo_col], errors="coerce")
        promoted = df[(df[promo_col] >= window_start) & (df[promo_col] <= end_date)]
    elif promo_col:
        promoted = df[df[promo_col].isin(TRUTHY)]
    else:
        promoted = df.iloc[0:0]

    female_promoted = len(promoted[promoted["Gender"] == "F"]) if not promoted.empty else 0
    pct = safe_pct(female_promoted, len(promoted))

    details, active_cols = employee_details(promoted, columns)
    return build_card_result(
        pct, 0.0, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Gender Balance in Promotion %", unit="%",
        description="Percentage of promotions awarded to female employees.",
        formula="(Female Promotions / Total Promotions) x 100",
        details=details, active_columns=active_cols,
    )


def workforce_flexibility(df_filtered, filters_applied, start_date, end_date,
                          df_graph_columns, df_graph_authorities, client_index,
                          user_emp_index, currency_code=None):
    """Share of employees on flexible working arrangements."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_workforce_flexibility", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    col = resolve_first_present(df, WORK_MODE_COLUMNS)
    pattern = "|".join(FLEXIBLE_WORK_KEYWORDS)

    def flexible_in(frame):
        if not col or col not in frame.columns:
            return frame.iloc[0:0]
        return frame[frame[col].astype(str).str.lower().str.contains(pattern, na=False)]

    flexible = flexible_in(df)
    pct = safe_pct(len(flexible), len(df))

    prev = previous_month_frame(df_filtered, end_date)
    prev_pct = safe_pct(len(flexible_in(prev)), len(prev))

    details, active_cols = employee_details(flexible if not flexible.empty else df, columns)
    return build_card_result(
        pct, prev_pct, title, colors, gtype, tcolor, gsize, col_map, filters_applied,
        value_label="Workforce Flexibility %", unit="%",
        description="Percentage of employees on flexible work arrangements.",
        formula="(Flexible Employees / Total Active) x 100",
        details=details, active_columns=active_cols,
    )


def score_index(df_filtered, filters_applied, start_date, end_date,
                df_graph_columns, df_graph_authorities, client_index,
                user_emp_index, currency_code=None):
    """Composite diversity score out of 100.

    Weighted blend of overall female representation and female representation
    in leadership. Weights are deliberately explicit in the formula string so
    the number is auditable from the UI.
    """
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_score_index", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    female_pct = safe_pct(len(df[df["Gender"] == "F"]), len(df))

    grade_col = resolve_grade_column(df)
    if grade_col:
        pattern = "|".join(LEADERSHIP_KEYWORDS)
        leaders = df[df[grade_col].astype(str).str.lower().str.contains(pattern, na=False)]
        leader_pct = safe_pct(len(leaders[leaders["Gender"] == "F"]), len(leaders))
    else:
        leader_pct = female_pct

    score = min(round(female_pct * 0.4 + leader_pct * 0.3 + female_pct * 0.3, 2), 100.0)

    prev = previous_month_frame(df_filtered, end_date)
    prev_female_pct = safe_pct(len(prev[prev["Gender"] == "F"]) if not prev.empty else 0, len(prev))
    prev_score = min(round(prev_female_pct, 2), 100.0)

    details, active_cols = employee_details(df, columns)
    return {
        "as_off": {
            "data": [{
                XVALUE: title,
                YVALUE1: score,
                YVALUE2: prev_score,
                YVALUE3: round(score - prev_score, 2),
                YVALUE4: 100,
                NAME1: "Score",
                NAME2: "Previous Month",
                NAME3: "Change",
                NAME4: "Max Score",
            }],
            "filters_applied": filters_applied,
            "xlabel": "",
            "ylabel": "/100",
            "title": title,
            "display_names": {c: col_map.get(c, "") for c in active_cols},
            "color_config": colors,
            "graph_type": gtype,
            "text_color": tcolor,
            "graph_size": gsize,
            "unique_employee_details": details,
            "formula": {
                "Description": "Composite diversity score out of 100.",
                "Formula": "(Female % x 0.4) + (Leadership Female % x 0.3) + (Female % x 0.3), capped at 100",
            },
        }
    }


def gender_ratio(df_filtered, filters_applied, start_date, end_date,
                 df_graph_columns, df_graph_authorities, client_index,
                 user_emp_index, currency_code=None):
    """Male vs female headcount split, with previous-month comparison."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_ratio", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    total = len(df)
    male = len(df[df["Gender"] == "M"])
    female = len(df[df["Gender"] == "F"])

    prev = previous_month_frame(df_filtered, end_date)
    prev_total = len(prev)
    prev_male = len(prev[prev["Gender"] == "M"]) if not prev.empty else 0
    prev_female = len(prev[prev["Gender"] == "F"]) if not prev.empty else 0

    details, active_cols = employee_details(df, columns)
    return {
        "as_off": {
            "data": [
                {
                    XVALUE: "Female", YVALUE1: safe_pct(female, total, 1),
                    YVALUE2: safe_pct(prev_female, prev_total, 1),
                    YVALUE3: female, YVALUE4: "",
                    NAME1: "Female %", NAME2: "Prev Female %", NAME3: "Female Count", NAME4: "",
                },
                {
                    XVALUE: "Male", YVALUE1: safe_pct(male, total, 1),
                    YVALUE2: safe_pct(prev_male, prev_total, 1),
                    YVALUE3: male, YVALUE4: "",
                    NAME1: "Male %", NAME2: "Prev Male %", NAME3: "Male Count", NAME4: "",
                },
            ],
            "filters_applied": filters_applied,
            "xlabel": "Gender",
            "ylabel": "%",
            "title": title,
            "display_names": {c: col_map.get(c, "") for c in active_cols},
            "color_config": colors,
            "graph_type": gtype,
            "text_color": tcolor,
            "graph_size": gsize,
            "unique_employee_details": details,
            "formula": {
                "Description": "Male versus female headcount ratio.",
                "Formula": "(Gender count / Total Active) x 100",
            },
        }
    }
