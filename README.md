# Analytics-Engine

A modular HR analytics backend. Serves pre-computed workforce metrics to a
dashboard frontend over a single parameterised endpoint per domain, backed by
PostgreSQL and a parquet cache layer.

Built with Python, Flask, pandas, and PostgreSQL.

---

## What problem this solves

A workforce dashboard fires twenty or more chart requests the moment a page
loads. Each chart needs the same employee population, filtered the same way,
scoped to what the requesting user is permitted to see. Naively, that is
twenty round trips to the database running twenty variations of the same
expensive query.

This engine restructures that:

- **One cached frame, many charts.** The employee population is materialised
  to parquet once and served from memory. Analytics functions run against
  pandas, not SQL.
- **One request, many charts.** A client asks for a comma-separated list of
  scopes; the server dispatches them concurrently and returns a single gzipped
  payload.
- **Configuration over code.** Chart titles, colours, types, and drill-down
  column labels live in the database. Relabelling a chart does not require a
  release.
- **Schema tolerance.** Deployments name columns differently. Column
  resolution is explicit and ordered, and a chart whose source column is
  absent returns an empty state instead of a 500.

---

## Architecture

```
Request
   │
   ├─ token_required ──────────── identity → employee_index, client_index
   │
   ├─ DataCacheService ─────────── employee frame (parquet cache, copy-on-read)
   │                               config frames (live, never cached)
   │
   ├─ preprocess_shared ────────── tenant scope → row-level authority join
   │                               → date coercion → dimension filters
   │
   ├─ ThreadPoolExecutor ───────── N analytics functions, concurrently
   │       │
   │       └─ each: get_graph_config → compute → build_*_result
   │
   └─ gzip(orjson) ─────────────── single response envelope
```

### Two layers of access control

Row-level access (which employees a user may see) is enforced once in
`preprocess_shared()` by joining against the authority frame. Chart-level
access (which charts a user may request) is checked per scope before
dispatch. An unauthorised chart returns an empty object rather than an error,
so a partially authorised dashboard still renders.

### Why the config frames are not cached

Per-user authority and chart permissions are fetched live on every request.
Caching them would mean a permission revocation takes effect at the next cache
refresh rather than immediately. The employee frame is cached; permissions are
not.

### Cache guarantees

The parquet cache is written to a temp path and renamed, so a reader never
sees a partially written file. A background thread rebuilds it at a configured
hour to pick up overnight ETL changes without a restart. Reads return a copy —
without that, one module adding a computed column mutates the shared frame and
corrupts every subsequent request.

---

## Repository layout

```
Analytics-Engine/
├── config/
│   ├── settings.py              Environment-driven config
│   ├── constants.py             Payload key contract
│   └── graph_ids.example.json   Chart ID mapping template
├── src/
│   ├── app.py                   Application factory
│   ├── common/
│   │   ├── preprocessing.py     Scoping, authority join, date coercion
│   │   ├── graph_config.py      Presentation config + column resolution
│   │   ├── result_builders.py   Chart / card / empty payload builders
│   │   └── serialization.py     gzip + orjson response encoding
│   ├── services/
│   │   ├── data_cache_service.py  Parquet cache, atomic writes, refresh
│   │   └── security.py            Token decorator, authority checks
│   └── modules/
│       ├── diversity/           ← implemented
│       │   ├── kpi_cards.py     11 single-figure KPIs
│       │   ├── graphs.py        16 chart series
│       │   ├── registry.py      Scope → function mapping
│       │   └── routes.py        /diversity blueprint
├── data/sample/                 Synthetic data generator
├── docs/SCHEMA.md               Expected columns and config frames
└── tests/
```

---

## Modules

### Diversity

Twenty-seven metrics across two shapes.

**KPI cards** — one headline figure plus the previous calendar month for a
delta: gender pay gap, leadership representation, diversity hiring rate,
training participation, candidates interviewed, disability inclusion,
retention rate, promotion balance, workforce flexibility, composite diversity
score, and gender ratio.

**Charts** — distributions and trends: female share overall and by department
and business unit, headcount by gender, tenure and age banding, gender split
by department, business unit, grade, job level, and location, and gender mix
monthly, quarterly, and yearly.

Every function shares one signature, which is what allows the route to
dispatch any subset of them concurrently without special-casing.

### Demographics and Summary

Scaffolded, not yet implemented. 

---

## API

```
GET /diversity?scope=<comma-separated>&server_code=<env>&client_index=<id>
```

| Parameter | Required | Notes |
|---|---|---|
| `scope` | yes | Comma-separated scope keys. See `src/modules/diversity/registry.py`. |
| `server_code` | yes | Target environment. |
| `client_index` | yes | Tenant. Falls back to the token claim. |
| `start_date` / `end_date` | no | ISO dates. `end_date` defaults to today. |
| `city_index`, `location_index`, `department_index` | no | Repeatable filters. |
| `currency_code` | no | |
| `sync` | no | `true` forces a cache rebuild before reading. |

Authentication is a bearer token; the requesting user's identity comes from
the token, never from a query parameter.

**Response** — gzipped, one entry per requested scope:

```json
{
  "header": { "code": 200, "message": "success" },
  "body": [
    {
      "diversity_gender_mix": {
        "as_off": {
          "data": [
            { "XVALUE": "Male", "YVALUE1": 62.0, "YVALUE2": 1240,
              "NAME1": "Male %", "NAME2": "Male Count" }
          ],
          "title": "Gender Mix",
          "xlabel": "Gender",
          "ylabel": "% Mix",
          "display_names": {},
          "color_config": ["#05668D", "#028090"],
          "graph_type": 3,
          "unique_employee_details": [],
          "formula": {
            "Description": "Overall gender mix.",
            "Formula": "YVALUE1 = Gender %; YVALUE2 = Headcount"
          }
        }
      }
    }
  ]
}
```

Every chart carries its own formula string. Any number on the dashboard can be
traced back to how it was calculated without reading the source.

---

## Getting started

```bash
git clone https://github.com/SMTalaalY/Analytics-Engine.git
cd Analytics-Engine

python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
cp config/graph_ids.example.json config/graph_ids.json
```

To work without a database, generate a synthetic dataset:

```bash
python data/sample/generate_sample_data.py --rows 2000
```

Run the server:

```bash
python -m src.app
```

---

## Notable implementation details

**The sentinel date.** The source system writes `1900-01-01` into
`ServiceEndDate` to mean "still employed" rather than leaving it null.
Treating that as a real end date classifies every active employee as a leaver
and inflates turnover dramatically. Active-employee checks test for
`isna() | == sentinel`, and drill-down output maps the sentinel to `-` so a
literal 1900 date never reaches the UI.

**Copy-on-read.** `get_employee_frame()` returns a copy. Several charts add
computed columns (`Tenure`, `Age`) to the frame they receive. Without the
copy, the first chart to run would mutate the shared cache for everything
after it.

**Ordered column resolution.** Grade might be `GroupName` in one deployment
and `GradeName` in another. `resolve_grade_column()` checks candidates in a
fixed order and returns the first present; a chart with no match returns an
empty state carrying the reason.

**Failure isolation.** One chart raising does not fail the request. The
exception is caught per-future and returned as `{"error": "..."}` under that
scope key, so the rest of the dashboard renders.

---

## Configuration and secrets

No credentials, connection strings, tenant identifiers, or deployment-specific
chart IDs are committed. Everything sensitive is read from the environment or
from gitignored local files:

- `.env` — credentials and connection strings (template: `.env.example`)
- `config/graph_ids.json` — chart ID mapping (template:
  `config/graph_ids.example.json`)
- `data/cache/`, `data/raw/` — never committed

---

## Roadmap

- [ ] Test coverage for the shared preprocessing and result builders
- [ ] Redis-backed cache as an alternative to parquet
- [ ] OpenAPI spec for the scope contract
