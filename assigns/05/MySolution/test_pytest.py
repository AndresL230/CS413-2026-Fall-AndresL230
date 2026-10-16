"""pytest suite for pretty printing and capture-avoiding substitution.

Run from assigns/05:
    python3 -m pytest MySolution/test_pytest.py -v
"""
from __future__ import annotations

import copy

import pytest

# lambda1_visitors puts the assignment directory on sys.path, so it is
# imported before lambda1_vp.
from lambda1_visitors import (
    d0exp_pretty, d0exp_substitute, d0exp_allnames, d0exp_rename,
    FreshNames, PrettyPrintVisitor, SubstitutionVisitor,
)
import lambda1_vp
from lambda1_vp import (
    d0exp_fvset, d0exp_evaluate, ENVnil, ENVcns, D0Vint,
    D0Elam, D0Elet, D0Efix, D0Epair, D0Eop2,
)
from shared_cases import (
    V, I, add,
    PRETTY_CONSTRUCTOR_CASES, PRETTY_NESTED_CASES, SUBST_CONSTRUCTOR_CASES,
    SHADOWING_CASES, CAPTURE_CASES, RENAMING_CASES, LET_INIT_BODY_CASES,
    ALL_SCOPE_CASES, FV_TARGET_FREE_CASES, FV_TARGET_NOT_FREE_CASES,
    SEMANTIC_CASES, NO_EVAL_CASES,
)


def cases(rows):
    """Parametrize rows, using each row's leading label as its test id."""
    return [pytest.param(*row[1:], id=row[0]) for row in rows]


SUBST_INPUTS = [row[:4] for row in SUBST_CONSTRUCTOR_CASES + ALL_SCOPE_CASES]

########################################################################
# Pretty printing
########################################################################

@pytest.mark.parametrize("e, expected", cases(PRETTY_CONSTRUCTOR_CASES))
def test_pretty_every_constructor(e, expected):
    assert d0exp_pretty(e) == expected


@pytest.mark.parametrize("e, expected", cases(PRETTY_NESTED_CASES))
def test_pretty_nested(e, expected):
    assert d0exp_pretty(e) == expected


@pytest.mark.parametrize("e, expected",
                         cases(PRETTY_CONSTRUCTOR_CASES + PRETTY_NESTED_CASES))
def test_pretty_is_single_line_without_surrounding_whitespace(e, expected):
    s = d0exp_pretty(e)
    assert s == s.strip()
    assert "\n" not in s


def test_pretty_visitor_dispatches_through_accept():
    assert add(V("a"), I(2)).accept(PrettyPrintVisitor()) == "(a + 2)"

########################################################################
# Substitution through every constructor
########################################################################

@pytest.mark.parametrize("e, x, r, expected", cases(SUBST_CONSTRUCTOR_CASES))
def test_substitute_every_constructor(e, x, r, expected):
    assert d0exp_substitute(e, x, r) == expected


def test_matching_variable_returns_replacement():
    r = add(V("x"), I(1))
    assert d0exp_substitute(V("x"), "x", r) is r


def test_nonmatching_variable_is_unchanged():
    assert d0exp_substitute(V("y"), "x", I(3)) == V("y")


def test_operator_and_constructor_preserved():
    result = d0exp_substitute(D0Eop2("<", V("x"), V("x")), "x", I(1))
    assert type(result) is D0Eop2
    assert result.name == "<"

########################################################################
# Scope: shadowing, capture, renaming, let
########################################################################

@pytest.mark.parametrize("e, x, r, expected", cases(SHADOWING_CASES))
def test_shadowing(e, x, r, expected):
    result = d0exp_substitute(e, x, r)
    assert d0exp_pretty(result) == expected
    if x not in d0exp_fvset(e):
        assert result == e


@pytest.mark.parametrize("e, x, r, expected", cases(CAPTURE_CASES))
def test_capture_avoidance(e, x, r, expected):
    assert d0exp_pretty(d0exp_substitute(e, x, r)) == expected


def test_formerly_free_name_is_not_captured():
    result = d0exp_substitute(D0Elam("y", add(V("x"), V("y"))), "x", V("y"))
    assert d0exp_pretty(result) != "(lam y. (y + y))"
    assert "y" in d0exp_fvset(result)


@pytest.mark.parametrize("e, x, r, expected", cases(RENAMING_CASES))
def test_nested_shadowing_and_fresh_names(e, x, r, expected):
    assert d0exp_pretty(d0exp_substitute(e, x, r)) == expected


@pytest.mark.parametrize("e, x, r, expected", cases(LET_INIT_BODY_CASES))
def test_let_initializer_versus_body(e, x, r, expected):
    assert d0exp_pretty(d0exp_substitute(e, x, r)) == expected

########################################################################
# Helper visitors
########################################################################

def test_allnames_includes_binders_and_bound_names():
    e = D0Elet("y", V("x"), D0Elam("z", D0Efix("f", "n", V("w"))))
    assert d0exp_allnames(e) == {"y", "x", "z", "f", "n", "w"}


def test_fresh_names_skip_used_and_generated():
    names = FreshNames(frozenset({"y", "y_1"}))
    assert names.fresh("y") == "y_2"
    assert names.fresh("y") == "y_3"


def test_rename_respects_shadowing():
    e = D0Epair(V("y"), D0Elam("y", V("y")))
    assert d0exp_pretty(d0exp_rename(e, "y", "q")) == "(pair q (lam y. y))"


def test_rename_enters_let_initializer_only():
    e = D0Elet("y", V("y"), V("y"))
    assert d0exp_pretty(d0exp_rename(e, "y", "q")) == "(let y = q in y)"

########################################################################
# Free-variable property and semantic agreement
########################################################################

@pytest.mark.parametrize("e, x, r", cases(FV_TARGET_FREE_CASES))
def test_fv_property_target_free(e, x, r):
    assert x in d0exp_fvset(e)
    result = d0exp_substitute(e, x, r)
    assert d0exp_fvset(result) == (d0exp_fvset(e) - {x}) | d0exp_fvset(r)


@pytest.mark.parametrize("e, x, r", cases(FV_TARGET_NOT_FREE_CASES))
def test_fv_property_target_not_free(e, x, r):
    assert x not in d0exp_fvset(e)
    result = d0exp_substitute(e, x, r)
    assert d0exp_fvset(result) == d0exp_fvset(e)
    assert result == e


@pytest.mark.parametrize("e, x, r, bindings, expected", cases(SEMANTIC_CASES))
def test_substitution_matches_binding_in_environment(e, x, r, bindings,
                                                     expected):
    env = ENVnil()
    for name, value in bindings.items():
        env = ENVcns(name, D0Vint(value), env)
    env_x = ENVcns(x, d0exp_evaluate(r, env), env)
    assert d0exp_evaluate(e, env_x) == D0Vint(expected)
    assert d0exp_evaluate(d0exp_substitute(e, x, r), env) == D0Vint(expected)

########################################################################
# Inputs preserved, determinism, no evaluation
########################################################################

@pytest.mark.parametrize("e, x, r", cases(SUBST_INPUTS))
def test_inputs_not_mutated(e, x, r):
    e_before, r_before = copy.deepcopy(e), copy.deepcopy(r)
    d0exp_pretty(e)
    d0exp_substitute(e, x, r)
    assert e == e_before
    assert r == r_before


@pytest.mark.parametrize("e, x, r", cases(SUBST_INPUTS))
def test_deterministic_across_calls(e, x, r):
    first = d0exp_substitute(e, x, r)
    d0exp_substitute(D0Elam("y", add(V("x"), V("y"))), "x", V("y"))
    second = d0exp_substitute(e, x, r)
    assert first == second
    assert d0exp_pretty(first) == d0exp_pretty(second)


def test_fresh_supply_is_per_call():
    e, x, r = D0Elam("y", add(V("x"), V("y"))), "x", V("y")
    e.accept(SubstitutionVisitor(x, r, FreshNames(frozenset({"x", "y"}))))
    assert d0exp_pretty(d0exp_substitute(e, x, r)) == "(lam y_1. (y + y_1))"


@pytest.fixture
def evaluation_forbidden(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("evaluation was attempted")
    monkeypatch.setattr(lambda1_vp.EvaluateVisitor, "__init__", forbid)
    monkeypatch.setattr(lambda1_vp, "d0exp_evaluate", forbid)


@pytest.mark.parametrize("e", cases(NO_EVAL_CASES))
def test_no_evaluation(evaluation_forbidden, e):
    assert isinstance(d0exp_pretty(e), str)
    result = d0exp_substitute(e, "x", I(0))
    assert "x" not in d0exp_fvset(result)


def test_division_by_zero_prints():
    assert d0exp_pretty(D0Eop2("/", I(1), I(0))) == "(1 / 0)"
