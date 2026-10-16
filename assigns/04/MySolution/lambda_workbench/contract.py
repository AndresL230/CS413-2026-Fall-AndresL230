"""Language-tool contract shared by the model, the controller and every backend.

This module has no dependencies inside the application. A backend is anything
that implements the five operations below; the rest of the application only
ever sees `ToolOutput` values, never an interpreter or compiler.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Operation(Enum):
    LINT = "lint"
    INTERPRET = "interpret"
    TYPECHECK = "typecheck"
    COMPILE = "compile"
    EXECUTE = "execute"


class Outcome(Enum):
    SUCCESS = "success"
    # The text is not a well-formed constructor expression.
    INPUT_ERROR = "input-error"
    # The expression is well formed but the language rejects it:
    # undeclared variables (Lint) or a failure while running (Interpret).
    LANGUAGE_ERROR = "language-error"
    # The tool did not finish within its execution bound.
    TIMEOUT = "timeout"
    # The tool itself failed; the problem is not in the user's program.
    BACKEND_FAILURE = "backend-failure"
    NOT_IMPLEMENTED = "not-implemented"


@dataclass(frozen=True)
class Artifact:
    """Generated code produced by Compile and consumed by Execute.

    `revision` is the source revision the code was generated from. Execute
    must receive the artifact itself and must never recompile.
    """
    revision: int
    language: str
    code: str


@dataclass(frozen=True)
class ToolOutput:
    """What one backend operation reports back.

    Only a successful Compile may carry an `artifact`. The backend sets the
    artifact's revision to 0; the model stamps the real revision when it
    stores the output.
    """
    outcome: Outcome
    text: str
    artifact: Artifact | None = None


class Backend(Protocol):
    def lint(self, source: str) -> ToolOutput: ...
    def interpret(self, source: str) -> ToolOutput: ...
    def typecheck(self, source: str) -> ToolOutput: ...
    def compile(self, source: str) -> ToolOutput: ...
    def execute(self, artifact: Artifact | None) -> ToolOutput: ...
