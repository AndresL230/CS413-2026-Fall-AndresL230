"""Import the supplied LAMBDA3 interpreter from ../LAMBDA3 (never cwd based)."""

import sys
from pathlib import Path

# MySolution/queens/lambda3_loader.py -> assigns/08/LAMBDA3
LAMBDA3_DIR = Path(__file__).resolve().parent.parent.parent / "LAMBDA3"


def load_lambda3():
    """Return the lambda3 module, importing it without writing bytecode."""
    path = str(LAMBDA3_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        import lambda3
    finally:
        sys.dont_write_bytecode = previous
    return lambda3
