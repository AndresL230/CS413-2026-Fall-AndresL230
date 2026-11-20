"""Flask transport: POST /rpc, plus GET / and /static/* for the browser client.

Knows nothing about LAMBDA3; the solver is reached only via the stream table.
"""

import json
import time

from flask import Flask, Response, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import config, solver
from .jsonrpc import Dispatcher
from .methods import build_registry
from .streams import StreamTable


def _text(status, message, headers=None):
    resp = Response(message + "\n", status=status, mimetype="text/plain")
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def create_app(overrides=None, clock=None, open_stream=None):
    """clock and open_stream are injectable for tests (fake clock, doubles)."""
    app = Flask(__name__, static_folder=str(config.STATIC_DIR), static_url_path="/static")
    app.config.update(config.DEFAULTS)
    app.config.update(overrides or {})

    solver.declarations()  # parse + type-check queens.lam at startup: fail fast
    table = StreamTable(
        open_stream=open_stream or solver.open_stream,
        clock=clock or time.monotonic,
        ttl=app.config["STREAM_TTL_SECONDS"],
        cap=app.config["MAX_STREAMS"],
    )
    app.extensions["streams"] = table
    dispatcher = Dispatcher(build_registry(lambda: table))
    app.extensions["dispatcher"] = dispatcher

    @app.route("/rpc", methods=["POST"])
    def rpc():
        if request.mimetype != "application/json":
            return _text(415, "Unsupported Media Type: use application/json")
        raw = request.get_data()  # raises RequestEntityTooLarge -> 413
        result = dispatcher.handle_bytes(raw)
        if result is None:
            return Response(status=204)
        return Response(json.dumps(result), status=200, mimetype="application/json")

    @app.route("/", methods=["GET"])
    def index():
        return send_from_directory(config.STATIC_DIR, "index.html")

    @app.errorhandler(HTTPException)
    def http_error(exc):
        status = exc.code or 500
        if status == 405:
            allow = exc.valid_methods or ["POST"]
            return _text(405, "Method Not Allowed", {"Allow": ", ".join(allow)})
        if status == 404:
            return _text(404, "Not Found")
        if status == 413:
            return _text(413, f"Content Too Large: body exceeds {app.config['MAX_CONTENT_LENGTH']} bytes")
        return _text(status, exc.name)

    return app
