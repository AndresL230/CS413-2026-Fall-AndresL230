"""Method registry: parameter validation, then stream-table calls.

All parameters are validated before any stream is allocated or forced.
JSON booleans decode to Python bool, a subclass of int, so they are rejected
explicitly; JSON numbers like 8.0 decode to float and are rejected too.
"""

from . import config
from .errors import TOO_MANY_STREAMS, UNKNOWN_STREAM, RpcError, invalid_params
from .solver import MAX_SIZE, MIN_SIZE
from .streams import TooManyStreams, UnknownStream

_MISSING = object()


def _check_keys(params, allowed):
    for key in params:
        if key not in allowed:
            raise invalid_params("unknown parameter", param=key[:64])


def _int_param(params, name, low, high, default=_MISSING):
    value = params.get(name, default)
    if value is _MISSING:
        raise invalid_params("missing required parameter", param=name)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise invalid_params(f"{name} must be an integer from {low} to {high}", param=name)
    return value


def _stream_id(params):
    if "stream_id" not in params:
        raise invalid_params("missing required parameter", param="stream_id")
    value = params["stream_id"]
    if not isinstance(value, str) or not 0 < len(value) <= config.STREAM_ID_MAX_CHARS:
        raise invalid_params(
            f"stream_id must be a string of 1 to {config.STREAM_ID_MAX_CHARS} characters",
            param="stream_id")
    return value


def _unknown(stream_id):
    return RpcError(UNKNOWN_STREAM, data={"stream_id": stream_id})


def build_registry(get_table):
    """get_table is a callable so the app owns the table instance."""

    def health(params):
        _check_keys(params, ())
        return {"status": "ok", "version": config.API_VERSION}

    def open_(params):
        _check_keys(params, ("size",))
        size = _int_param(params, "size", MIN_SIZE, MAX_SIZE)
        try:
            stream_id = get_table().open(size)
        except TooManyStreams as exc:
            raise RpcError(TOO_MANY_STREAMS, data={"limit": exc.args[0]}) from None
        return {"stream_id": stream_id, "size": size}

    def next_(params):
        _check_keys(params, ("stream_id", "limit"))
        stream_id = _stream_id(params)
        limit = _int_param(params, "limit", 1, config.MAX_LIMIT, default=1)
        try:
            events, done = get_table().next(stream_id, limit)
        except UnknownStream:
            raise _unknown(stream_id) from None
        return {"events": events, "done": done}

    def close(params):
        _check_keys(params, ("stream_id",))
        stream_id = _stream_id(params)
        try:
            get_table().close(stream_id)
        except UnknownStream:
            raise _unknown(stream_id) from None
        return {"closed": True}

    return {
        "service.health": health,
        "queens.open": open_,
        "queens.next": next_,
        "queens.close": close,
    }
