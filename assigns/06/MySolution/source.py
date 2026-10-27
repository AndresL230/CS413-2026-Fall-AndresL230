from __future__ import annotations

########################################################################
########################################################################
# Single entry point to the supplied source AST in
# ../../05/lambda1_vp.py, which is imported, never copied or modified.
# Run with python3 -B so no __pycache__ is written next to that file.
# Requires Python 3.12 or later.
########################################################################
########################################################################
import sys
from pathlib import Path

_ASSIGN05_DIR = str(Path(__file__).resolve().parents[2] / "05")
if _ASSIGN05_DIR not in sys.path:
    sys.path.insert(0, _ASSIGN05_DIR)

from lambda1_vp import (  # noqa: E402,F401
    D0ExpVisitor, D0E000, d0exp, dvar, d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
