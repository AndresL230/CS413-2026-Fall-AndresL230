"""Adapter around the provided LAMBDA3 module. No language logic lives here."""

import sys

from . import config, worker
from .errors import (
    LAMBDA_SYNTAX_ERROR,
    LAMBDA_TYPE_ERROR,
    RpcError,
    invalid_params,
)

SNIPPET_MAX = 200


def _too_deep():
    return invalid_params("source nesting too deep", param="source")


class LambdaService:
    def __init__(self, app_config=None):
        self._cfg = dict(config.DEFAULTS)
        if app_config:
            self._cfg.update(app_config)
        sys.set_int_max_str_digits(0)
        self._l3 = config.load_lambda3()

    def _parse(self, source):
        l3 = self._l3
        try:
            return l3.d0exp_parse_and_typecheck(source)
        except l3.LambdaSyntaxError as err:
            text = err.text or ""
            raise RpcError(
                LAMBDA_SYNTAX_ERROR,
                f"LAMBDA syntax error: {err.msg}",
                {
                    "line": err.lineno or 1,
                    "column": err.offset or 1,
                    "snippet": text.rstrip("\r\n")[:SNIPPET_MAX],
                },
            ) from None
        except l3.TypeCheckError as err:
            detail = str(err)
            raise RpcError(
                LAMBDA_TYPE_ERROR,
                f"LAMBDA type error: {detail}",
                {"detail": detail},
            ) from None
        except RecursionError:
            raise _too_deep() from None

    def health(self):
        return {"status": "ok", "version": config.API_VERSION}

    def typecheck(self, source):
        _expr, typ = self._parse(source)
        return {"type": self._l3.format_type(typ)}

    def interpret(self, source):
        _expr, typ = self._parse(source)
        type_str = self._l3.format_type(typ)
        value = worker.run_interpretation(
            source,
            deadline=self._cfg["INTERPRET_DEADLINE_SECONDS"],
            recursion_limit=self._cfg["WORKER_RECURSION_LIMIT"],
            stack_bytes=self._cfg["WORKER_STACK_BYTES"],
        )
        return {"type": type_str, "value": value}

    def compile(self, source, target):
        expr, _typ = self._parse(source)
        try:
            if target == "python":
                code = self._l3.d0exp_compile(expr)
            else:
                code = self._l3.d0exp_compile_js(expr)
        except RecursionError:
            raise _too_deep() from None
        return {"target": target, "code": code}
