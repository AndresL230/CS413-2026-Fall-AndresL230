"""HTTP boundary: Flask routes that forward browser requests to the controller.

Each route unpacks the request, makes one controller call and returns the
view's rendering of the reply. No state rule and no language logic lives here.
"""
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory

from . import view
from .backend import LambdaBackend
from .controller import Reply, Status, WorkbenchController
from .examples import load_canned_examples
from .model import Workbench

STATIC_DIRECTORY = Path(__file__).resolve().parent.parent / "static"

# Flask refuses larger request bodies outright; the model's own, smaller
# limit produces the message a user normally sees.
MAX_REQUEST_BYTES = 1024 * 1024

_HTTP_STATUS = {Status.OK: 200, Status.REJECTED: 422, Status.CONFLICT: 409, Status.UNKNOWN: 404}


def create_app(controller: WorkbenchController | None = None) -> Flask:
    if controller is None:
        controller = WorkbenchController(Workbench(), LambdaBackend(), load_canned_examples())

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    def respond(reply: Reply):
        return jsonify(view.render_reply(reply, controller.examples)), _HTTP_STATUS[reply.status]

    def editor_text() -> str | None:
        """The editor content sent with the request, if any."""
        if request.is_json:
            text = (request.get_json(silent=True) or {}).get("editorText")
        else:
            text = request.form.get("editorText")
        return text if isinstance(text, str) else None

    @app.before_request
    def refuse_other_origins():
        # A page from another site must not be able to drive the local server.
        origin = request.headers.get("Origin")
        if request.method == "POST" and origin and urlsplit(origin).netloc != request.host:
            return jsonify({"status": "conflict", "message": "Cross-origin request refused."}), 403

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def request_too_large(error):
        reply = controller.current()
        message = f"The upload is larger than {MAX_REQUEST_BYTES} bytes and was not read."
        return respond(Reply(Status.REJECTED, message, reply.snapshot))

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIRECTORY, "index.html")

    @app.get("/static/<path:filename>")
    def static_file(filename):
        return send_from_directory(STATIC_DIRECTORY, filename)

    @app.get("/api/state")
    def state():
        return respond(controller.current())

    @app.post("/api/source/example/<key>")
    def load_example(key):
        return respond(controller.load_example(key, editor_text()))

    @app.post("/api/source/upload")
    def upload():
        uploaded = request.files.get("file")
        if uploaded is None:
            reply = controller.current()
            return respond(Reply(Status.REJECTED, "No file was sent.", reply.snapshot))
        return respond(controller.upload(uploaded.filename or "", uploaded.read(), editor_text()))

    @app.post("/api/source/manual")
    def manual_input():
        return respond(controller.manual_input(editor_text()))

    @app.post("/api/source/apply")
    def apply():
        return respond(controller.apply(editor_text() or ""))

    @app.post("/api/source/discard")
    def discard():
        return respond(controller.discard())

    @app.post("/api/actions/<operation>")
    def run(operation):
        return respond(controller.run(operation, editor_text()))

    return app
