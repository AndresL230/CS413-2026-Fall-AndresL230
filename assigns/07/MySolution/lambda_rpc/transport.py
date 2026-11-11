"""Flask transport: POST /rpc only. Knows nothing about LAMBDA3."""

import json
import sys

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

from . import config
from .jsonrpc import Dispatcher
from .methods import build_registry
from .service import LambdaService


def _text(status, message, headers=None):
    resp = Response(message + "\n", status=status, mimetype="text/plain")
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def create_app(overrides=None, service=None):
    sys.set_int_max_str_digits(0)
    app = Flask(__name__)
    app.config.update(config.DEFAULTS)
    app.config.update(overrides or {})
    app.extensions["lambda_service"] = service or LambdaService(app.config)

    registry = build_registry(
        get_service=lambda: app.extensions["lambda_service"],
        get_max_source=lambda: app.config["MAX_SOURCE_CHARS"],
    )
    app.extensions["dispatcher"] = Dispatcher(registry)

    @app.route("/rpc", methods=["POST"])
    def rpc():
        mimetype = request.mimetype
        if mimetype != "application/json":
            return _text(415, "Unsupported Media Type: use application/json")
        raw = request.get_data()  # raises RequestEntityTooLarge -> 413
        result = app.extensions["dispatcher"].handle_bytes(raw)
        if result is None:
            return Response(status=204)
        return Response(
            json.dumps(result), status=200, mimetype="application/json"
        )

    @app.errorhandler(HTTPException)
    def http_error(exc):
        status = exc.code or 500
        if status == 405:
            return _text(405, "Method Not Allowed: use POST", {"Allow": "POST"})
        if status == 404:
            return _text(404, "Not Found")
        if status == 413:
            return _text(413, "Content Too Large: body exceeds 1 MiB")
        if status == 415:
            return _text(415, "Unsupported Media Type: use application/json")
        return _text(status, exc.name)

    return app
