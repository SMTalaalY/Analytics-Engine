"""
/diversity endpoint.

Accepts a comma-separated `scope` list, checks per-chart authority, then runs
the requested analytics functions concurrently. Charts the user is not
authorised to see return an empty object rather than an error, so a partially
authorised dashboard still renders.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, request

from config.settings import DEFAULT_CURRENCY
from src.common.preprocessing import preprocess_shared
from src.common.serialization import compressed_json_response, error_response
from src.modules.diversity.registry import SCOPES, graph_id
from src.services.data_cache_service import DataCacheService
from src.services.security import token_required, has_graph_authority, to_int_list

diversity_bp = Blueprint("diversity", __name__)
cache_service = DataCacheService()

MAX_WORKERS = 8


@diversity_bp.route("/diversity", methods=["GET"])
@token_required
def get_diversity():
    server_code = request.args.get("server_code")
    scope = request.args.get("scope")

    if not server_code:
        return error_response(400, "server_code parameter is required")
    if not scope:
        return error_response(400, "scope parameter is required")

    requested_scopes = {s.strip() for s in scope.split(",")}

    client_index = to_int_list(request.args.getlist("client_index")) or (
        [request.client_index] if getattr(request, "client_index", None) is not None else []
    )
    if not client_index:
        return error_response(400, "client_index parameter is required")

    user_emp_index = getattr(request, "employee_index", None)
    if user_emp_index is None:
        return error_response(400, "authenticated user context is required")

    # Warm or refresh the cache before reading from it.
    if request.args.get("sync", "false").lower() == "true":
        cache_service.fetch_and_cache_data(server_code)
    else:
        cache_service.check_and_load_data(server_code)

    config = cache_service.fetch_analytics_config_data(server_code, user_emp_index, client_index)
    df = cache_service.get_employee_frame(server_code)

    df_filtered, filters_applied, start_parsed, end_parsed = preprocess_shared(
        df,
        config["df_authorities"],
        client_index,
        to_int_list(request.args.getlist("city_index")),
        to_int_list(request.args.getlist("location_index")),
        to_int_list(request.args.getlist("department_index")),
        request.args.get("start_date") or None,
        request.args.get("end_date") or None,
        user_emp_index,
    )

    currency_code = request.args.get("currency_code") or DEFAULT_CURRENCY
    shared_args = (
        df_filtered,
        filters_applied,
        start_parsed,
        end_parsed,
        config["df_graph_columns"],
        config["df_graph_authorities"],
        client_index,
        user_emp_index,
        currency_code,
    )

    results = []
    tasks = {}

    for key in requested_scopes:
        if key not in SCOPES:
            continue
        method, needs_range = SCOPES[key]
        if has_graph_authority(config["df_graph_authorities"], graph_id(key), user_emp_index):
            tasks[key] = (method, needs_range)
        else:
            results.append({key: {}})

    if tasks:
        with ThreadPoolExecutor(max_workers=min(len(tasks), MAX_WORKERS)) as executor:
            futures = {}
            for key, (method, needs_range) in tasks.items():
                args = shared_args + (None,) if needs_range else shared_args
                futures[executor.submit(method, *args)] = key

            for future in as_completed(futures):
                key = futures[future]
                try:
                    results.append({key: future.result()})
                except Exception as exc:  # one bad chart must not fail the dashboard
                    results.append({key: {"error": str(exc)}})

    return compressed_json_response(results)
