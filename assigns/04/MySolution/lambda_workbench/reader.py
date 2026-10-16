"""Restricted reader: constructor-expression text -> d0exp.

The text is parsed with Python's own parser, so comments, nesting and
multiline layout come for free, but it is never executed. The reader walks
the syntax tree and accepts only calls to the LAMBDA expression constructors
with literal arguments of the right type. Anything else (names, attribute
access, operators, imports, other calls) is rejected with its position.
"""
import ast
import dataclasses

from . import lambda1

# Argument kinds, in field order, for every expression constructor.
_INT, _BOOL, _STR, _EXP = "an integer", "True or False", "a string", "an expression"

_SIGNATURES: dict[str, tuple[str, ...]] = {
    "D0Eint": (_INT,),
    "D0Ebtf": (_BOOL,),
    "D0Eop1": (_STR, _EXP),
    "D0Eop2": (_STR, _EXP, _EXP),
    "D0Evar": (_STR,),
    "D0Elam": (_STR, _EXP),
    "D0Efix": (_STR, _STR, _EXP),
    "D0Eapp": (_EXP, _EXP),
    "D0Eif0": (_EXP, _EXP, _EXP),
    "D0Elet": (_STR, _EXP, _EXP),
    "D0Epair": (_EXP, _EXP),
    "D0Epfst": (_EXP,),
    "D0Epsnd": (_EXP,),
}

CONSTRUCTOR_NAMES = tuple(_SIGNATURES)


class ReaderError(Exception):
    """The text is not a valid constructor expression."""

    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        self.line = line
        self.column = column
        where = f"line {line}, column {column}: " if line is not None else ""
        super().__init__(where + message)


def read_expression(text: str) -> lambda1.d0exp:
    """Return the d0exp written in `text`, or raise ReaderError."""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        column = exc.offset if exc.lineno is not None else None
        raise ReaderError(f"not a constructor expression ({exc.msg})", exc.lineno, column) from None
    except (ValueError, RecursionError, MemoryError) as exc:
        raise ReaderError(f"cannot read the source ({exc})") from None
    try:
        return _expression(tree.body)
    except RecursionError:
        raise ReaderError("the expression is nested too deeply") from None


def _fail(node: ast.AST, message: str):
    raise ReaderError(message, getattr(node, "lineno", None), getattr(node, "col_offset", -1) + 1)


def _expression(node: ast.expr) -> lambda1.d0exp:
    if not isinstance(node, ast.Call):
        _fail(node, f"expected a constructor such as D0Eint(...), found {_describe(node)}")
    if not isinstance(node.func, ast.Name) or node.func.id not in _SIGNATURES:
        _fail(node, f"{_describe(node.func)} is not a LAMBDA expression constructor")
    name = node.func.id
    kinds = _SIGNATURES[name]
    fields = [field.name for field in dataclasses.fields(getattr(lambda1, name))]

    if len(node.args) > len(kinds):
        _fail(node, f"{name} takes {len(kinds)} argument(s), found {len(node.args)}")
    supplied: dict[str, ast.expr] = {}
    for field, arg in zip(fields, node.args):
        if isinstance(arg, ast.Starred):
            _fail(arg, "argument unpacking (*) is not allowed")
        supplied[field] = arg
    for keyword in node.keywords:
        if keyword.arg is None:
            _fail(keyword, "argument unpacking (**) is not allowed")
        if keyword.arg not in fields:
            _fail(keyword, f"{name} has no argument named {keyword.arg!r}")
        if keyword.arg in supplied:
            _fail(keyword, f"{name} argument {keyword.arg!r} is given twice")
        supplied[keyword.arg] = keyword.value
    missing = [field for field in fields if field not in supplied]
    if missing:
        _fail(node, f"{name} takes {len(kinds)} argument(s); missing {', '.join(missing)}")

    values = {field: _argument(name, field, kind, supplied[field])
              for field, kind in zip(fields, kinds)}
    return getattr(lambda1, name)(**values)


def _argument(name: str, field: str, kind: str, node: ast.expr):
    if kind is _EXP:
        return _expression(node)
    value = _literal(node)
    # bool is a subclass of int in Python, so integers are checked by exact type.
    wanted = {_INT: int, _BOOL: bool, _STR: str}[kind]
    if type(value) is not wanted:
        _fail(node, f"{name} argument {field!r} must be {kind}, found {_describe(node)}")
    return value


def _literal(node: ast.expr):
    """Return the int, bool or str literal at `node`, or None if it is not one."""
    if isinstance(node, ast.Constant):
        return node.value
    # A negative integer is written as a unary minus applied to a literal.
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int):
        value = node.operand.value
        return -value if isinstance(node.op, ast.USub) else value
    return None


def _describe(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return f"the literal {node.value!r}"
    if isinstance(node, ast.Name):
        return f"the name {node.id!r}"
    if isinstance(node, ast.Call):
        return "a constructor call"
    return f"unsupported syntax ({type(node).__name__})"
