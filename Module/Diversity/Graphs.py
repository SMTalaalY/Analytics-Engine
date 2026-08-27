"""
Diversity charts.

Multi-point series: distributions across dimensions (department, business
unit, grade, location) and trends over time (monthly, quarterly, yearly).
A shared _dimension_split() helper covers the several charts that are
structurally identical apart from the grouping column.
"""

import pandas as pd

from config.settings import SENTINEL_DATE
from src.common.graph_config import (
    get_graph_config,
    resolve_grade_column,
    resolve_location_column,
)
from src.common.preprocessing import active_frame
from src.common.result_builders import (
    build_chart_result,
    build_empty_result,
    employee_details,
    point,
    safe_pct,
)


def _config(df_graph_authorities, df_graph_columns, graph_key, client_index, user_emp_index):
    return get_graph_config(df_graph_authorities, df_graph_columns, graph_key, client_index, user_emp_index)


def _clean_dimension(df, column):
    """Drop placeholder and null values from a dimension column."""
    return df[~df[column].isin(["-", ""]) & df[column].notna()]


def _dimension_split(df, dimension_col, mode="count"):
    """
    Group by a dimension and gender.

    mode="count"    -> (male_count, female_count) per dimension value
    mode="female_pct" -> female percentage per dimension value
    """
    df = df[df["Gender"].isin(["M", "F"])]
    grouped = df.groupby([dimension_col, "Gender"]).size().unstack(fill_value=0)

    rows = []
    for key, row in grouped.iterrows():
        male, female = int(row.get("M", 0)), int(row.get("F", 0))
        if mode == "female_pct":
            rows.append(point(str(key), safe_pct(female, male + female), n1="% Female"))
        else:
            rows.append(point(str(key), male, female, n1="Male", n2="Female"))
    return rows


# ---------------------------------------------------------------------------
# Percentage distributions
# ---------------------------------------------------------------------------

def female_percentage_trend(df_filtered, filters_applied, start_date, end_date,
                            df_graph_columns, df_graph_authorities, client_index,
                            user_emp_index, currency_code=None):
    """Monthly female share of headcount."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_female_percentage", client_index, user_emp_index
    )
    sentinel = pd.Timestamp(SENTINEL_DATE)
    df = df_filtered.copy()
    df_female = df[df["Gender"] == "F"]
    window_start = start_date or df["ServiceStartDate"].min()

    data = []
    for month_start in pd.date_range(start=window_start, end=end_date, freq="MS"):
        month_end = month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)

        def active_in_month(frame):
            return frame[
                (frame["ServiceStartDate"] <= month_end)
                & ((frame["ServiceEndDate"] >= month_start) | (frame["ServiceEndDate"] == sentinel))
            ].shape[0]

        total = active_in_month(df)
        female = active_in_month(df_female)
        data.append(point(month_start.strftime("%b-%y"), safe_pct(female, total), n1="% Female"))

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Month", "% Female", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Female share of active headcount per month.",
        "(Female active / Total active) x 100 per month",
        details, active_cols,
    )


def female_percentage_by_business_unit(df_filtered, filters_applied, start_date, end_date,
                                       df_graph_columns, df_graph_authorities, client_index,
                                       user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_female_percentage_by_business_unit",
        client_index, user_emp_index
    )
    df = _clean_dimension(active_frame(df_filtered), "UnitName")
    data = _dimension_split(df, "UnitName", mode="female_pct")

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Business Unit", "% Female", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Female share of headcount by business unit.",
        "(Female in unit / Total in unit) x 100",
        details, active_cols,
    )


def female_percentage_by_department(df_filtered, filters_applied, start_date, end_date,
                                    df_graph_columns, df_graph_authorities, client_index,
                                    user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_female_percentage_by_department",
        client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    data = _dimension_split(df, "DepartmentName", mode="female_pct")

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Department", "% Female", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Female share of headcount by department.",
        "(Female in department / Total in department) x 100",
        details, active_cols,
    )


def headcount_by_gender(df_filtered, filters_applied, start_date, end_date,
                        df_graph_columns, df_graph_authorities, client_index,
                        user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_headcount_by_gender", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    total = len(df)

    data = []
    for code, label in [("M", "Male"), ("F", "Female")]:
        count = len(df[df["Gender"] == code])
        data.append(point(label, safe_pct(count, total), n1=f"{label} %"))

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Gender", "Headcount %", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Headcount percentage by gender.",
        "(Gender count / Total) x 100",
        details, active_cols,
    )


# ---------------------------------------------------------------------------
# Banded distributions
# ---------------------------------------------------------------------------

def _band(series, edges):
    """Cut a numeric series into labelled bands with an open-ended top band."""
    bins = list(edges) + [float("inf")]
    labels = [f"{bins[i]}-{bins[i + 1]} years" for i in range(len(bins) - 1)]
    labels[-1] = f"{bins[-2]}+ years"
    return pd.cut(series, bins=bins, labels=labels, right=False)


def tenure_banding(df_filtered, filters_applied, start_date, end_date,
                   df_graph_columns, df_graph_authorities, client_index,
                   user_emp_index, currency_code=None, range_input=None):
    """Gender split across tenure bands. Band edges are caller-configurable."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_by_tenure", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    df["Tenure"] = (end_date - df["ServiceStartDate"]).dt.days / 365.0
    df["TenureRange"] = _band(df["Tenure"], range_input or (0, 3, 5, 10))

    data = _dimension_split(df, "TenureRange")
    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Tenure Range", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender distribution across tenure bands.",
        "YVALUE1 = Male count; YVALUE2 = Female count per band",
        details, active_cols,
    )


def age_banding(df_filtered, filters_applied, start_date, end_date,
                df_graph_columns, df_graph_authorities, client_index,
                user_emp_index, currency_code=None, range_input=None):
    """Gender split across age bands."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_by_age", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    today = pd.Timestamp.today()
    df["Age"] = ((today - df["DateOfBirth"]).dt.days / 365.25).round(0)
    df["AgeRange"] = _band(df["Age"], range_input or (18, 25, 35, 45, 55, 65))

    data = _dimension_split(df, "AgeRange")
    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Age Range", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender distribution across age bands.",
        "YVALUE1 = Male count; YVALUE2 = Female count per band",
        details, active_cols,
    )


# ---------------------------------------------------------------------------
# Gender mix by dimension
# ---------------------------------------------------------------------------

def gender_by_business_unit(df_filtered, filters_applied, start_date, end_date,
                            df_graph_columns, df_graph_authorities, client_index,
                            user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_by_business_unit", client_index, user_emp_index
    )
    df = _clean_dimension(active_frame(df_filtered), "UnitName")
    data = _dimension_split(df, "UnitName")

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Business Unit", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender distribution by business unit.",
        "YVALUE1 = Male count; YVALUE2 = Female count per unit",
        details, active_cols,
    )


def gender_by_department(df_filtered, filters_applied, start_date, end_date,
                         df_graph_columns, df_graph_authorities, client_index,
                         user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_by_department", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    data = _dimension_split(df, "DepartmentName")

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Department", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender distribution by department.",
        "YVALUE1 = Male count; YVALUE2 = Female count per department",
        details, active_cols,
    )


def female_headcount_by_job_level(df_filtered, filters_applied, start_date, end_date,
                                  df_graph_columns, df_graph_authorities, client_index,
                                  user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_female_headcount_by_job_level",
        client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    grade_col = resolve_grade_column(df)
    if grade_col is None or df.empty:
        return build_empty_result(
            filters_applied, "Job Level", "% Female", title, col_map, colors,
            gtype, tcolor, gsize, currency_code,
            "Female and male headcount percentage by job level.",
            "No grade column present in this deployment's schema.",
        )

    grouped = df.groupby([grade_col, "Gender"]).size().unstack(fill_value=0)
    data = []
    for grade, row in grouped.iterrows():
        male, female = int(row.get("M", 0)), int(row.get("F", 0))
        total = male + female
        data.append(point(
            str(grade),
            safe_pct(female, total, 1),
            safe_pct(male, total, 1),
            n1="Female %", n2="Male %",
        ))

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Job Level", "% Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Female and male headcount percentage by job level.",
        f"YVALUE1 = Female %; YVALUE2 = Male % per {grade_col}",
        details, active_cols,
    )


def headcount_by_gender_and_job_level(df_filtered, filters_applied, start_date, end_date,
                                      df_graph_columns, df_graph_authorities, client_index,
                                      user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_headcount_by_gender_and_job_level",
        client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    grade_col = resolve_grade_column(df)
    if grade_col is None or df.empty:
        return build_empty_result(
            filters_applied, "Job Level", "Headcount", title, col_map, colors,
            gtype, tcolor, gsize, currency_code,
            "Headcount by gender and job level.",
            "No grade column present in this deployment's schema.",
        )

    data = _dimension_split(df, grade_col)
    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Job Level", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Headcount split by gender and job level.",
        f"YVALUE1 = Male count; YVALUE2 = Female count per {grade_col}",
        details, active_cols,
    )


def gender_mix(df_filtered, filters_applied, start_date, end_date,
               df_graph_columns, df_graph_authorities, client_index,
               user_emp_index, currency_code=None):
    """Overall gender mix, rendered as a donut."""
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    total = df["EmployeeIndex"].nunique()

    data = []
    for code, label in [("M", "Male"), ("F", "Female")]:
        count = df[df["Gender"] == code]["EmployeeIndex"].nunique()
        data.append(point(label, safe_pct(count, total, 1), count,
                          n1=f"{label} %", n2=f"{label} Count"))

    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Gender", "% Mix", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Overall gender mix.",
        "YVALUE1 = Gender %; YVALUE2 = Headcount",
        details, active_cols,
    )


def gender_mix_by_grade(df_filtered, filters_applied, start_date, end_date,
                        df_graph_columns, df_graph_authorities, client_index,
                        user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix_by_grade", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    grade_col = resolve_grade_column(df)
    if grade_col is None or df.empty:
        return build_empty_result(
            filters_applied, "Grade", "Headcount", title, col_map, colors,
            gtype, tcolor, gsize, currency_code,
            "Gender mix by grade.",
            "No grade column present in this deployment's schema.",
        )

    data = _dimension_split(df, grade_col)
    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Grade", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender mix by grade.",
        f"YVALUE1 = Male count; YVALUE2 = Female count per {grade_col}",
        details, active_cols,
    )


def gender_mix_by_location(df_filtered, filters_applied, start_date, end_date,
                           df_graph_columns, df_graph_authorities, client_index,
                           user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix_by_location", client_index, user_emp_index
    )
    df = active_frame(df_filtered)
    loc_col = resolve_location_column(df)
    if loc_col is None or df.empty:
        return build_empty_result(
            filters_applied, "Location", "Headcount", title, col_map, colors,
            gtype, tcolor, gsize, currency_code,
            "Gender mix by location.",
            "No location column present in this deployment's schema.",
        )

    data = _dimension_split(df, loc_col)
    details, active_cols = employee_details(df, columns)
    return build_chart_result(
        data, filters_applied, "Location", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender mix by location.",
        f"YVALUE1 = Male count; YVALUE2 = Female count per {loc_col}",
        details, active_cols,
    )


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

def _active_between(df, period_start, period_end):
    return df[
        (df["ServiceStartDate"] <= period_end)
        & (df["ServiceEndDate"].isna() | (df["ServiceEndDate"] >= period_start))
    ]


def _gender_mix_over_periods(df, periods, label_fn):
    """Shared body for the monthly/quarterly/yearly mix charts."""
    data = []
    for period_start, period_end, label in periods:
        window = _active_between(df, period_start, period_end)
        male = int(window[window["Gender"] == "M"]["EmployeeIndex"].nunique())
        female = int(window[window["Gender"] == "F"]["EmployeeIndex"].nunique())
        data.append(point(label, male, female, n1="Male", n2="Female"))
    return data


def gender_mix_monthly(df_filtered, filters_applied, start_date, end_date,
                       df_graph_columns, df_graph_authorities, client_index,
                       user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix_monthly", client_index, user_emp_index
    )
    window_start = start_date or df_filtered["ServiceStartDate"].min()
    periods = [
        (m.replace(day=1), m, m.strftime("%b %Y"))
        for m in pd.date_range(start=window_start, end=end_date, freq="ME")
    ]

    data = _gender_mix_over_periods(df_filtered, periods, None)
    details, active_cols = employee_details(df_filtered, columns)
    return build_chart_result(
        data, filters_applied, "Month", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender mix per calendar month.",
        "YVALUE1 = Male active headcount; YVALUE2 = Female active headcount",
        details, active_cols,
    )


def gender_mix_quarterly(df_filtered, filters_applied, start_date, end_date,
                         df_graph_columns, df_graph_authorities, client_index,
                         user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix_quarterly", client_index, user_emp_index
    )
    window_start = start_date or df_filtered["ServiceStartDate"].min()
    periods = []
    for q_end in pd.date_range(start=window_start, end=end_date, freq="QE"):
        q_num = (q_end.month - 1) // 3 + 1
        q_start = pd.Timestamp(q_end.year, (q_num - 1) * 3 + 1, 1)
        periods.append((q_start, q_end, f"Q{q_num} {q_end.year}"))

    data = _gender_mix_over_periods(df_filtered, periods, None)
    details, active_cols = employee_details(df_filtered, columns)
    return build_chart_result(
        data, filters_applied, "Quarter", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender mix per quarter.",
        "YVALUE1 = Male active headcount; YVALUE2 = Female active headcount",
        details, active_cols,
    )


def gender_mix_yearly(df_filtered, filters_applied, start_date, end_date,
                      df_graph_columns, df_graph_authorities, client_index,
                      user_emp_index, currency_code=None):
    title, colors, gtype, tcolor, gsize, col_map, columns = _config(
        df_graph_authorities, df_graph_columns, "diversity_gender_mix_yearly", client_index, user_emp_index
    )
    window_start = start_date or df_filtered["ServiceStartDate"].min()
    periods = [
        (pd.Timestamp(y, 1, 1), pd.Timestamp(y, 12, 31), str(y))
        for y in range(window_start.year, end_date.year + 1)
    ]

    data = _gender_mix_over_periods(df_filtered, periods, None)
    details, active_cols = employee_details(df_filtered, columns)
    return build_chart_result(
        data, filters_applied, "Year", "Headcount", title, col_map, columns,
        colors, gtype, tcolor, gsize, currency_code,
        "Gender mix per year.",
        "YVALUE1 = Male active headcount; YVALUE2 = Female active headcount",
        details, active_cols,
    )
