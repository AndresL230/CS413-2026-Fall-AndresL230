"""JSON-RPC 2.0 envelope handling and dispatch. Knows nothing about LAMBDA3."""

import json
import logging

from .errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    RpcError,
    invalid_params,
)

log = logging.getLogger("lambda_rpc")

_ALLOWED_KEYS = frozenset({"jsonrpc", "method", "params", "id"})


def _reject_constant(name):
    raise ValueError("non-standard JSON constant")


def _success(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _failure(req_id, error):
    return {"jsonrpc": "2.0", "id": req_id, "error": error.to_error_object()}


def _invalid(reason):
    return RpcError(INVALID_REQUEST, data={"reason": reason})


def _validate_envelope(obj):
    """Steps 1-6 of RPC.md section 3. Raises RpcError(-32600)."""
    if not isinstance(obj, dict):
        raise _invalid("request must be an object")
    if obj.get("jsonrpc") != "2.0":
        raise _invalid('jsonrpc must be "2.0"')
    if not isinstance(obj.get("method"), str):
        raise _invalid("method must be a string")
    if "id" in obj:
        rid = obj["id"]
        if rid is not None and (
            isinstance(rid, bool) or not isinstance(rid, (str, int, float))
        ):
            raise _invalid("id must be a string, number, or null")
    if "params" in obj and not isinstance(obj["params"], (dict, list)):
        raise _invalid("params must be an object")
    extra = [k for k in obj if k not in _ALLOWED_KEYS]
    if extra:
        raise _invalid("unexpected member in request")


class Dispatcher:
    """Decodes bytes, validates envelopes, calls handlers from a registry.

    registry: dict mapping method name -> callable(params: dict) -> result.
    """

    def __init__(self, registry):
        self.registry = registry

    def handle_bytes(self, raw):
        """Return a response object, a response list, or None (no content)."""
        try:
            text = raw.decode("utf-8")
            payload = json.loads(text, parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):
            return _failure(None, RpcError(PARSE_ERROR))
        return self.handle_payload(payload)

    def handle_payload(self, payload):
        if isinstance(payload, list):
            if not payload:
                return _failure(None, _invalid("empty batch"))
            responses = []
            for member in payload:
                resp = self._handle_one(member)
                if resp is not None:
                    responses.append(resp)
            return responses or None
        return self._handle_one(payload)

    def _handle_one(self, obj):
        try:
            _validate_envelope(obj)
        except RpcError as err:
            return _failure(None, err)
        is_notification = "id" not in obj
        req_id = obj.get("id")
        try:
            result = self._execute(obj)
            response = _success(req_id, result)
        except RpcError as err:
            response = _failure(req_id, err)
        except Exception:
            log.exception("unexpected failure handling method %r", obj["method"][:128])
            response = _failure(req_id, RpcError(INTERNAL_ERROR))
        return None if is_notification else response

    def _execute(self, obj):
        method = obj["method"]
        handler = self.registry.get(method)
        if handler is None:
            raise RpcError(METHOD_NOT_FOUND, data={"method": method[:128]})
        params = obj.get("params", {})
        if isinstance(params, list):
            raise invalid_params("params must be an object")
        return handler(params)
