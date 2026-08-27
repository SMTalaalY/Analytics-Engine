"""
Shared preprocessing applied before any analytics function runs.

Every module calls preprocess_shared() exactly once per request. It handles
tenant scoping, row-level authority filtering, date coercion, and dimension
filters, so individual analytics functions receive a frame they can trust.
"""

import pandas as pd

from config.constants import (
    CLIENT_INDEX,
    CITY_INDEX,
    LOCATION_INDEX,
    DEPARTMENT_INDEX,
    EMPLOYEE_INDEX,
)

DATE_COLUMNS = ["ServiceStartDate", "ServiceEndDate", "DateOfBirth"]


def preprocess_shared(
    df,
    df_authorities,
    client_index,
    city_index,
    location_index,
    department_index,
    start_date,
    end_date,
    user_emp_index,
):
    """
    Scope, authorise, and filter the employee frame.

    Args:
        df: full employee frame from the cache layer.
        df_authorities: row-level access map (user -> visible employees).
        client_index: int or list of tenant identifiers.
        city_index / location_index / department_index: optional filter lists.
        start_date / end_date: ISO strings or None.
        user_emp_index: identifier of the requesting user.

    Returns:
        (df_filtered, filters_applied, start_date_parsed, end_date_parsed)
    """
    clients = client_index if isinstance(client_index, list) else [client_index]
    df = df[df[CLIENT_INDEX].isin(clients)].copy()

    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Row-level security: restrict to employees this user is permitted to see.
    visible = df_authorities[df_authorities["UserEmpIndex"] == user_emp_index][[EMPLOYEE_INDEX]]
    df = pd.merge(df, visible, on=EMPLOYEE_INDEX, how="inner")

    start_date_parsed = pd.to_datetime(start_date) if start_date else None
    end_date_parsed = pd.to_datetime(end_date) if end_date else pd.Timestamp.today()

    filters_applied = []
    for index_list, column_name in [
        (city_index, CITY_INDEX),
        (location_index, LOCATION_INDEX),
        (department_index, DEPARTMENT_INDEX),
    ]:
        if index_list:
            df = df[df[column_name].isin(index_list)]
            filters_applied.append(
                {"column": column_name, "values": df[column_name].unique().tolist()}
            )

    return df, filters_applied, start_date_parsed, end_date_parsed


def previous_month_frame(df, end_date):
    """Snapshot of employees active during the calendar month before end_date."""
    prev_end = end_date.replace(day=1) - pd.Timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    return df[
        (df["ServiceStartDate"] <= prev_end)
        & (df["ServiceEndDate"].isna() | (df["ServiceEndDate"] >= prev_start))
    ]


def active_frame(df):
    """Rows for currently-active employees only."""
    from config.constants import STATUS_ACTIVE

    if "ServiceStatus" not in df.columns:
        return df.copy()
    return df[df["ServiceStatus"] == STATUS_ACTIVE].copy()
