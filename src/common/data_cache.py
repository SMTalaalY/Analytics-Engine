"""
Data cache layer.

Analytics functions run against pandas frames, not live SQL. Pulling the full
employee frame per request is too slow for a dashboard that fires 20+ chart
calls at once, so the frame is materialised to parquet once and served from
memory thereafter.

Three properties this layer guarantees:

1. **Atomic writes.** The parquet file is written to a temp path and renamed.
   A reader never sees a half-written file.
2. **Scheduled refresh.** A background thread rebuilds the cache at a
   configured hour so overnight ETL changes are picked up without a restart.
3. **Copy-on-read.** Callers get a copy of the cached frame. Without this, one
   module mutating a column (adding `Tenure`, say) corrupts every subsequent
   request.

Per-user configuration — row-level authority and chart permissions — is
deliberately NOT cached. It is fetched live per request, because a permission
change must take effect immediately rather than at the next cache refresh.
"""

import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd

from config.settings import CACHE_DIR, CACHE_REFRESH_HOUR, DB_URL


class DataCacheService:
    """In-memory + parquet cache, keyed by server code."""

    def __init__(self, cache_dir=CACHE_DIR, db_url=DB_URL):
        self.cache_dir = cache_dir
        self.db_url = db_url
        self.cache = {}
        self._lock = threading.Lock()
        self._refresh_thread = None
        os.makedirs(self.cache_dir, exist_ok=True)

    # -- public API ---------------------------------------------------------

    def check_and_load_data(self, server_code):
        """Load from memory, then parquet, then the database."""
        if server_code in self.cache:
            return

        path = self._parquet_path(server_code)
        if os.path.exists(path):
            with self._lock:
                self.cache[server_code] = {"df": pd.read_parquet(path), "loaded_at": datetime.now()}
            return

        self.fetch_and_cache_data(server_code)

    def fetch_and_cache_data(self, server_code):
        """Force a rebuild from the source database."""
        df = self._query_employee_frame(server_code)
        self._write_atomic(df, self._parquet_path(server_code))
        with self._lock:
            self.cache[server_code] = {"df": df, "loaded_at": datetime.now()}

    def get_employee_frame(self, server_code):
        """Return a defensive copy. Callers mutate their copy freely."""
        self.check_and_load_data(server_code)
        return self.cache[server_code]["df"].copy()

    def fetch_analytics_config_data(self, server_code, user_emp_index, client_index):
        """
        Live per-request fetch of user-scoped configuration.

        Returns df_authorities (row-level access), df_graph_authorities
        (per-chart permission and presentation), and df_graph_columns
        (drill-down column display names).
        """
        return {
            "df_authorities": self._query_authorities(server_code, user_emp_index),
            "df_graph_authorities": self._query_graph_authorities(server_code, user_emp_index),
            "df_graph_columns": self._query_graph_columns(server_code, client_index),
        }

    def start_scheduled_refresh(self, server_codes):
        """Kick off the background refresh thread."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            return
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop, args=(server_codes,), daemon=True
        )
        self._refresh_thread.start()

    # -- internals ----------------------------------------------------------

    def _parquet_path(self, server_code):
        return os.path.join(self.cache_dir, f"employees_{server_code}.parquet")

    @staticmethod
    def _write_atomic(df, path):
        """Write to a temp file then rename, so readers never see a partial file."""
        tmp = f"{path}.tmp"
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)

    def _refresh_loop(self, server_codes):
        while True:
            now = datetime.now()
            target = now.replace(hour=CACHE_REFRESH_HOUR, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            time.sleep((target - now).total_seconds())
            for code in server_codes:
                try:
                    self.fetch_and_cache_data(code)
                except Exception:
                    # A failed refresh must not kill the thread; the previous
                    # cache stays valid until the next attempt.
                    continue

    # -- query layer --------------------------------------------------------
    # Replace these with your own data access. Column names below define the
    # contract the analytics modules expect; see docs/SCHEMA.md.

    def _query_employee_frame(self, server_code):
        raise NotImplementedError(
            "Implement _query_employee_frame() against your database, or use "
            "data/sample/generate_sample_data.py to work with synthetic data."
        )

    def _query_authorities(self, server_code, user_emp_index):
        raise NotImplementedError("Implement _query_authorities() against your database.")

    def _query_graph_authorities(self, server_code, user_emp_index):
        raise NotImplementedError("Implement _query_graph_authorities() against your database.")

    def _query_graph_columns(self, server_code, client_index):
        raise NotImplementedError("Implement _query_graph_columns() against your database.")
