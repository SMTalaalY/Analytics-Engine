# Schema contract

The analytics modules operate on a denormalised employee frame. Any data
source that produces these columns will work; the query layer in
`src/services/data_cache_service.py` is the only place that needs changing.

## Employee frame

| Column | Type | Required | Notes |
|---|---|---|---|
| `EmployeeIndex` | int | yes | Unique per employee. Used for deduplication in drill-downs. |
| `ClientIndex` | int | yes | Tenant identifier. |
| `Gender` | str | yes | `M` / `F`. Other values are excluded from gender splits rather than dropped from headcount. |
| `ServiceStartDate` | datetime | yes | Hire date. |
| `ServiceEndDate` | datetime | yes | Leave date, or the sentinel `1900-01-01` for active employees. |
| `ServiceStatus` | int | yes | `1` = active. |
| `DateOfBirth` | datetime | for age charts | |
| `DepartmentIndex` / `DepartmentName` | int / str | yes | |
| `UnitIndex` / `UnitName` | int / str | yes | Business unit. |
| `LocationIndex` / `LocationName` | int / str | yes | |
| `CityIndex` | int | yes | |

## Optional columns

These drive specific charts. When absent, the affected chart returns an empty
result with an explanatory reason rather than failing.

| Column group | Candidates checked, in order | Used by |
|---|---|---|
| Grade / job level | `GroupName`, `GradeName`, `GradeIndex`, `ClientGradeIndex` | leadership, job-level, grade-mix charts |
| Salary | `BasicSalary`, `GrossSalary`, `Salary`, `TotalSalary` | gender pay gap |
| Training | `TrainingCount`, `TrainingsAttended`, `TrainingHours` | training participation |
| Disability | `IsDisabled`, `HasDisability`, `DisabilityFlag`, `Disability` | disability inclusion |
| Promotion | `PromotionDate`, `LastPromotionDate`, `GradeChangeDate`, `PromotionFlag` | promotion balance |
| Work mode | `WorkArrangement`, `EmploymentType`, `ContractType`, `WorkMode` | workforce flexibility |

Column resolution is deliberate: deployments name these differently, and
hardcoding one name means the chart silently breaks on the next client.

## Configuration frames

Fetched live per request, never cached, so permission changes take effect
immediately.

**`df_authorities`** — row-level access.

| Column | Notes |
|---|---|
| `UserEmpIndex` | The requesting user. |
| `EmployeeIndex` | An employee that user may see. |

**`df_graph_authorities`** — per-chart permission and presentation.

| Column | Notes |
|---|---|
| `Graphs` | Scope key, e.g. `diversity_gender_mix`. |
| `GraphIndex` | Numeric chart ID used for the permission check. |
| `UserEmpIndex` | |
| `Title`, `Color`, `GraphType`, `TextColor`, `GraphSize` | Presentation. `Color` is a comma-separated hex list. |

**`df_graph_columns`** — drill-down column labels.

| Column | Notes |
|---|---|
| `Graph` | Scope key. |
| `ClientIndex` | Tenant. |
| `ColumnName` | Source column. |
| `DisplayName` | Label shown in the UI. |

## The sentinel date

The source system writes `1900-01-01` into `ServiceEndDate` to mean "still
employed" rather than leaving it null. This matters in two places:

1. **Turnover and retention.** Treating the sentinel as a real end date
   classifies every active employee as a leaver and inflates turnover
   dramatically. Active-employee checks test for `isna() | == sentinel`.
2. **Drill-down output.** `employee_details()` maps the sentinel to `-` so a
   literal 1900 date never reaches the UI.
