"""
Response serialization.

Dashboard payloads are large — dozens of charts, each with drill-down records.
Responses are gzipped before they leave the process, and orjson is used when
available because it handles numpy scalars and datetimes faster than the
stdlib encoder.
"""

import datetime
import gzip
import json

import numpy as np
import pandas as pd
from flask import jsonify, make_response

try:
    import orjson

    USE_ORJSON = True
except ImportError:  # pragma: no cover - optional dependency
    USE_ORJSON = False


def default_converter(obj):
    """Fallback encoder for numpy and pandas types the JSON encoder rejects."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime.datetime, datetime.date)):
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def compressed_json_response(body, code=200, message="success"):
    """Gzip a standard envelope and return it as a Flask response."""
    payload = {"header": {"code": code, "message": message}, "body": body}

    if USE_ORJSON:
        raw = orjson.dumps(payload, default=default_converter)
    else:
        raw = json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False, default=default_converter
        ).encode("utf-8")

    compressed = gzip.compress(raw)
    response = make_response(compressed)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Content-Length"] = str(len(compressed))
    return response


def error_response(code, message):
    return jsonify({"header": {"code": code, "message": message}, "body": {}}), code
