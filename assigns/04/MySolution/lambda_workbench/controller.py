"""Controller: turns user requests into model changes and backend calls.

The controller is the only component that talks to both the model and the
backend. It asks the model whether a request is allowed, calls the backend
operation outside the model's lock, hands the output back to the model, and
returns a `Reply` holding the snapshot the view should now present. It has no
knowledge of HTTP or HTML and receives its backend as a parameter.
"""
from dataclasses import dataclass
from enum import Enum

from .contract import Backend, Operation, Outcome, ToolOutput
from .examples import Example
from .model import (
    ModelError, Snapshot, SourceRejected, Ticket, Workbench, decode_upload)


class Status(Enum):
    OK = "ok"
    # The proposed source was rejected; the applied source is unchanged.
    REJECTED = "rejected"
    # The current state does not allow the request (busy, unapplied edits, ...).
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Reply:
    status: Status
    message: str
    snapshot: Snapshot


class WorkbenchController:
    def __init__(self, model: Workbench, backend: Backend, examples: tuple[Example, ...] = ()):
        self.model = model
        self.backend = backend
        self.examples = examples

    def current(self) -> Reply:
        return self._reply(Status.OK, "")

    # --- source changes ------------------------------------------------
    #
    # `editor_text` is what the view's editor holds when the request is made.
    # Recording it first lets the model, not the view, decide whether there
    # are unapplied edits.

    def load_example(self, key: str, editor_text: str | None = None) -> Reply:
        example = next((item for item in self.examples if item.key == key), None)
        if example is None:
            return self._reply(Status.UNKNOWN, f"There is no example named {key!r}.")
        return self._change(editor_text, lambda: self.model.load(example.name, example.text))

    def upload(self, filename: str, data: bytes, editor_text: str | None = None) -> Reply:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip() or "Uploaded file"
        return self._change(editor_text, lambda: self.model.load(name, decode_upload(data)))

    def manual_input(self, editor_text: str | None = None) -> Reply:
        reply = self._change(editor_text, self.model.open_manual_input)
        if reply.status is Status.OK:
            return self._reply(Status.OK, "Manual input: type a program, then choose Apply changes.")
        return reply

    def apply(self, editor_text: str) -> Reply:
        reply = self._change(editor_text, self.model.apply_edits)
        if reply.status is Status.OK:
            source = reply.snapshot.source
            return self._reply(Status.OK, f"Applied changes to {source.name} as revision {source.revision}.")
        return reply

    def discard(self) -> Reply:
        try:
            self.model.discard_edits()
        except ModelError as exc:
            return self._refused(exc)
        return self._reply(Status.OK, "Changes discarded.")

    def _change(self, editor_text: str | None, change) -> Reply:
        try:
            if editor_text is not None:
                self.model.edit(editor_text)
            applied = change()
        except ModelError as exc:
            return self._refused(exc)
        if applied is None:
            return self._reply(Status.OK, "")
        return self._reply(Status.OK, f"Loaded {applied.name} as revision {applied.revision}.")

    # --- operations ----------------------------------------------------

    def run(self, operation_name: str, editor_text: str | None = None) -> Reply:
        try:
            operation = Operation(operation_name)
        except ValueError:
            return self._reply(Status.UNKNOWN, f"There is no operation named {operation_name!r}.")
        try:
            if editor_text is not None:
                self.model.edit(editor_text)
            ticket = self.model.begin(operation)
        except ModelError as exc:
            return self._refused(exc)
        # From here the workbench is busy; finish() must run whatever happens.
        try:
            output = self._dispatch(ticket)
            if not isinstance(output, ToolOutput):
                raise TypeError(f"the backend returned {type(output).__name__}, not ToolOutput")
        except Exception as exc:
            output = ToolOutput(
                Outcome.BACKEND_FAILURE,
                f"The language tool failed ({type(exc).__name__}: {exc}). "
                "This is not a problem in your program. The source is unchanged; try again.")
        result = self.model.finish(ticket, output)
        return self._reply(
            Status.OK,
            f"{operation.value} finished for revision {result.revision}: {result.outcome.value}.")

    def _dispatch(self, ticket: Ticket) -> ToolOutput:
        match ticket.operation:
            case Operation.LINT:
                return self.backend.lint(ticket.source)
            case Operation.INTERPRET:
                return self.backend.interpret(ticket.source)
            case Operation.TYPECHECK:
                return self.backend.typecheck(ticket.source)
            case Operation.COMPILE:
                return self.backend.compile(ticket.source)
            case Operation.EXECUTE:
                # Execute consumes the stored artifact; it never recompiles.
                return self.backend.execute(ticket.artifact)

    # --- replies -------------------------------------------------------

    def _refused(self, error: ModelError) -> Reply:
        status = Status.REJECTED if isinstance(error, SourceRejected) else Status.CONFLICT
        return self._reply(status, str(error))

    def _reply(self, status: Status, message: str) -> Reply:
        return Reply(status, message, self.model.snapshot())
