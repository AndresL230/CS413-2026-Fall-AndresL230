"""Interpretation in a fresh, killable process (spawn, never fork)."""

import logging
import multiprocessing
import sys
import threading
import time
import traceback

from .errors import (
    INTERNAL_ERROR,
    LAMBDA_RUNTIME_ERROR,
    LAMBDA_TIMEOUT,
    RpcError,
)

log = logging.getLogger("lambda_rpc")

RECURSION_DETAIL = "recursion depth limit exceeded"
_TRACEBACK_MAX = 20_000

_RUNTIME_KINDS = (
    (ZeroDivisionError, "division_by_zero"),
    (ValueError, "invalid_operation"),
    (IndexError, "index_out_of_range"),
)


def _internal():
    """Internal-failure outcome carrying the (bounded) traceback for the server log."""
    return ("internal", traceback.format_exc()[-_TRACEBACK_MAX:])


def _evaluate(source):
    """Runs inside the child's big-stack thread. Returns a result tuple."""
    from .config import load_lambda3

    l3 = load_lambda3()
    try:
        expr, _typ = l3.d0exp_parse_and_typecheck(source)
        text = l3.d0val_format(l3.d0exp_evaluate(expr))
        return ("ok", text)
    except RecursionError:
        return ("runtime", "recursion_depth_exceeded", RECURSION_DETAIL)
    except Exception as err:
        for exc_type, kind in _RUNTIME_KINDS:
            if isinstance(err, exc_type):
                return ("runtime", kind, str(err))
        return _internal()


def _child_main(conn, source, recursion_limit, stack_bytes):
    outcome = ("internal", "worker produced no result")
    try:
        sys.set_int_max_str_digits(0)
        sys.setrecursionlimit(recursion_limit)
        threading.stack_size(stack_bytes)
        box = []
        thread = threading.Thread(target=lambda: box.append(_evaluate(source)))
        thread.start()
        thread.join()
        if box:
            outcome = box[0]
    except BaseException:
        outcome = _internal()
    try:
        conn.send(outcome)
    finally:
        conn.close()


def run_interpretation(source, deadline, recursion_limit, stack_bytes):
    """Return the formatted value string or raise RpcError."""
    ctx = multiprocessing.get_context("spawn")
    started = time.monotonic()
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_child_main,
        args=(child_conn, source, recursion_limit, stack_bytes),
        daemon=True,
    )
    proc.start()
    child_conn.close()
    died = False
    try:
        remaining = max(0.0, deadline - (time.monotonic() - started))
        outcome = None
        try:
            if parent_conn.poll(remaining):
                outcome = parent_conn.recv()
                proc.join(1)  # let a finished child exit on its own
            else:
                seconds = int(deadline) if float(deadline).is_integer() else deadline
                raise RpcError(
                    LAMBDA_TIMEOUT,
                    "Interpretation timed out",
                    {"seconds": seconds},
                )
        except (EOFError, OSError):
            died = True
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(1)
        if proc.is_alive():
            proc.kill()
            proc.join()

    if died:
        log.error(
            "interpretation worker exited without a result (exitcode=%s)",
            proc.exitcode,
        )
        raise RpcError(INTERNAL_ERROR)

    tag = outcome[0]
    if tag == "ok":
        return outcome[1]
    if tag == "runtime":
        _, kind, detail = outcome
        raise RpcError(
            LAMBDA_RUNTIME_ERROR,
            f"LAMBDA runtime error: {detail}",
            {"kind": kind, "detail": detail},
        )
    log.error("interpretation worker failed unexpectedly:\n%s", outcome[1])
    raise RpcError(INTERNAL_ERROR)
