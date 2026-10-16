"""Worker process: run one source tool and print its result as JSON.

Started by `backend.LambdaBackend` as `python -m lambda_workbench.tool_worker`.
The request arrives on standard input as {"operation": ..., "source": ...}.
Running in a separate process is what lets the backend stop a program that
does not terminate.
"""
import json
import sys

from .tools import interpret_source, lint_source

# The interpreter recurses once per nested LAMBDA call, far past Python's
# default limit of 1000 frames for ordinary recursive programs.
RECURSION_LIMIT = 50_000
MEMORY_LIMIT_BYTES = 2 * 1024 ** 3

_TOOLS = {"lint": lint_source, "interpret": interpret_source}


def _limit_memory() -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except (ImportError, ValueError, OSError):
        pass  # Not available on this platform; the timeout still applies.


def main() -> int:
    request = json.load(sys.stdin)
    sys.setrecursionlimit(RECURSION_LIMIT)
    _limit_memory()
    output = _TOOLS[request["operation"]](request["source"])
    json.dump({"outcome": output.outcome.value, "text": output.text}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
