"""
Request authentication and authorisation helpers.

Two layers of access control run on every request:

  * **Row-level** — which employees a user may see, applied in
    preprocess_shared() via a join against the authority frame.
  * **Chart-level** — which charts a user may request, checked here before a
    scope is dispatched.

The token verification body is intentionally left as an integration point.
Implement it against your own identity provider; nothing about the signing
scheme or key material belongs in source control.
"""

import os
from functools import wraps

from flask import request

from src.common.serialization import error_response

TOKEN_HEADER = os.getenv("AUTH_HEADER_NAME", "Authorization")


def decode_token(raw_token):
    """
    Verify a bearer token and return its claims.

    Must return a dict containing at least:
        {"employee_index": int, "client_index": int}

    Raise ValueError on any verification failure.
    """
    raise NotImplementedError(
        "Wire decode_token() to your identity provider (JWT, session store, etc.)."
    )


def token_required(func):
    """Attach `request.employee_index` and `request.client_index` from the token."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        raw = request.headers.get(TOKEN_HEADER, "")
        if raw.lower().startswith("bearer "):
            raw = raw[7:]
        if not raw:
            return error_response(401, "authentication token is required")

        try:
            claims = decode_token(raw)
        except NotImplementedError:
            raise
        except Exception:
            return error_response(401, "invalid or expired token")

        request.employee_index = claims.get("employee_index")
        request.client_index = claims.get("client_index")
        return func(*args, **kwargs)

    return wrapper


def has_graph_authority(df_graph_authorities, graph_id, user_emp_index):
    """
    True when the user is permitted to see this chart.

    An unmapped chart (graph_id is None) is treated as permitted so that a new
    chart is visible in development before its permission row exists.
    """
    if graph_id is None:
        return True
    if df_graph_authorities is None or df_graph_authorities.empty:
        return False

    matched = df_graph_authorities[
        (df_graph_authorities["GraphIndex"] == graph_id)
        & (df_graph_authorities["UserEmpIndex"] == user_emp_index)
    ]
    return not matched.empty


def to_int_list(values):
    """Coerce repeated query-string args into a list of ints, skipping junk."""
    result = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                try:
                    result.append(int(part))
                except ValueError:
                    continue
    return result


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
