"""
Generate a synthetic employee dataset matching the schema the analytics
modules expect.

No real data is committed to this repository. Run this once to produce a
frame you can develop and test against:

    python data/sample/generate_sample_data.py --rows 2000
"""

import argparse
import os

import numpy as np
import pandas as pd

DEPARTMENTS = ["Engineering", "Finance", "Sales", "Operations", "People", "Legal"]
UNITS = ["Retail", "Corporate", "Digital", "Manufacturing"]
LOCATIONS = ["North Office", "South Office", "Remote", "Regional Hub"]
GRADES = ["Entry", "Mid-Level", "High-Level", "Executive"]
WORK_MODES = ["Full-time", "Part-time", "Contract", "Remote", "Hybrid"]

SENTINEL_DATE = pd.Timestamp("1900-01-01")


def generate(rows, seed=42):
    rng = np.random.default_rng(seed)

    start = pd.Timestamp("2015-01-01")
    span_days = (pd.Timestamp.today() - start).days

    df = pd.DataFrame({
        "EmployeeIndex": np.arange(1, rows + 1),
        "ClientIndex": 1,
        "Gender": rng.choice(["M", "F"], size=rows, p=[0.62, 0.38]),
        "DepartmentIndex": rng.integers(1, len(DEPARTMENTS) + 1, size=rows),
        "UnitIndex": rng.integers(1, len(UNITS) + 1, size=rows),
        "LocationIndex": rng.integers(1, len(LOCATIONS) + 1, size=rows),
        "CityIndex": rng.integers(1, 5, size=rows),
        "GroupName": rng.choice(GRADES, size=rows, p=[0.45, 0.35, 0.15, 0.05]),
        "WorkArrangement": rng.choice(WORK_MODES, size=rows),
        "BasicSalary": rng.normal(75000, 22000, size=rows).round(0).clip(28000),
        "TrainingCount": rng.integers(0, 6, size=rows),
        "IsDisabled": rng.choice([0, 1], size=rows, p=[0.96, 0.04]),
    })

    df["DepartmentName"] = [DEPARTMENTS[i - 1] for i in df["DepartmentIndex"]]
    df["UnitName"] = [UNITS[i - 1] for i in df["UnitIndex"]]
    df["LocationName"] = [LOCATIONS[i - 1] for i in df["LocationIndex"]]

    df["ServiceStartDate"] = start + pd.to_timedelta(
        rng.integers(0, span_days, size=rows), unit="D"
    )
    df["DateOfBirth"] = pd.Timestamp("1965-01-01") + pd.to_timedelta(
        rng.integers(0, 365 * 38, size=rows), unit="D"
    )

    # ~20% have left. Leavers get a real end date; active staff get the
    # sentinel value the source system uses to mean "no end date".
    left = rng.random(rows) < 0.20
    df["ServiceStatus"] = np.where(left, 0, 1)
    df["ServiceEndDate"] = SENTINEL_DATE
    leaver_offsets = rng.integers(90, 2500, size=int(left.sum()))
    df.loc[left, "ServiceEndDate"] = (
        df.loc[left, "ServiceStartDate"] + pd.to_timedelta(leaver_offsets, unit="D")
    )

    # Introduce a deliberate gender skew at senior grades so the diversity
    # charts show a realistic, non-uniform picture.
    senior = df["GroupName"].isin(["High-Level", "Executive"])
    flip = senior & (rng.random(rows) < 0.35)
    df.loc[flip, "Gender"] = "M"

    return df


def build_config_frames(df, user_emp_index=1):
    """Minimal authority and presentation config for local development."""
    df_authorities = pd.DataFrame({
        "UserEmpIndex": user_emp_index,
        "EmployeeIndex": df["EmployeeIndex"],
    })

    df_graph_authorities = pd.DataFrame(columns=[
        "Graphs", "GraphIndex", "UserEmpIndex", "Title",
        "Color", "GraphType", "TextColor", "GraphSize",
    ])

    df_graph_columns = pd.DataFrame(columns=["Graph", "ClientIndex", "ColumnName", "DisplayName"])

    return df_authorities, df_graph_authorities, df_graph_columns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--out", default="data/sample/employees_sample.parquet")
    args = parser.parse_args()

    df = generate(args.rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_parquet(args.out, index=False)

    print(f"Wrote {len(df):,} synthetic rows to {args.out}")
    print(df["Gender"].value_counts().to_string())


if __name__ == "__main__":
    main()
