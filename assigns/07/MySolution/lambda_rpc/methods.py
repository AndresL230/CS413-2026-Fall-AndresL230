"""Method registry: parameter validation (RPC.md section 4) + service calls."""

from .errors import invalid_params

_TARGETS = ("python", "javascript")


def _check_keys(params, allowed):
    for key in params:
        if key not in allowed:
            raise invalid_params("unknown parameter", param=key)


def _source(params, max_chars):
    if "source" not in params:
        raise invalid_params("missing required parameter", param="source")
    source = params["source"]
    if not isinstance(source, str) or not source.strip():
        raise invalid_params("source must be a nonempty string", param="source")
    if len(source) > max_chars:
        raise invalid_params(
            "source exceeds maximum size",
            param="source",
            limit=max_chars,
            actual=len(source),
        )
    return source


def _target(params):
    if "target" not in params:
        raise invalid_params("missing required parameter", param="target")
    target = params["target"]
    if not isinstance(target, str) or target not in _TARGETS:
        raise invalid_params(
            'target must be "python" or "javascript"', param="target"
        )
    return target


def build_registry(get_service, get_max_source):
    """get_service / get_max_source are callables so config stays dynamic."""

    def health(params):
        _check_keys(params, ())
        return get_service().health()

    def typecheck(params):
        _check_keys(params, ("source",))
        return get_service().typecheck(_source(params, get_max_source()))

    def interpret(params):
        _check_keys(params, ("source",))
        return get_service().interpret(_source(params, get_max_source()))

    def compile_(params):
        _check_keys(params, ("source", "target"))
        source = _source(params, get_max_source())
        target = _target(params)
        return get_service().compile(source, target)

    return {
        "service.health": health,
        "lambda.typecheck": typecheck,
        "lambda.interpret": interpret,
        "lambda.compile": compile_,
    }
