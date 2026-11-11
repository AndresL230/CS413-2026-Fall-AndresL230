"""Constants, defaults, and the LAMBDA3 import path helper."""

import sys
from pathlib import Path

API_VERSION = "1.0"
MAX_SOURCE_CHARS = 32768
MAX_CONTENT_LENGTH = 1048576
INTERPRET_DEADLINE_SECONDS = 5.0
WORKER_RECURSION_LIMIT = 100_000
WORKER_STACK_BYTES = 512 * 1024 * 1024
HOST = "127.0.0.1"
PORT = 8000

# MySolution/lambda_rpc/config.py -> MySolution/../LAMBDA3 (never cwd based)
LAMBDA3_DIR = (Path(__file__).resolve().parent.parent.parent / "LAMBDA3")

DEFAULTS = {
    "MAX_SOURCE_CHARS": MAX_SOURCE_CHARS,
    "MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH,
    "INTERPRET_DEADLINE_SECONDS": INTERPRET_DEADLINE_SECONDS,
    "WORKER_RECURSION_LIMIT": WORKER_RECURSION_LIMIT,
    "WORKER_STACK_BYTES": WORKER_STACK_BYTES,
}


def ensure_lambda3_on_path():
    """Put LAMBDA3/ on sys.path and import lambda3 without writing bytecode."""
    path = str(LAMBDA3_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import lambda3  # noqa: F401
    finally:
        sys.dont_write_bytecode = previous


def load_lambda3():
    """Return the lambda3 module (import path set up on first use)."""
    ensure_lambda3_on_path()
    import lambda3
    return lambda3
