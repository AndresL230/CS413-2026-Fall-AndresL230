"""Regression tests: the Python translation must print exactly what the ATS original prints.

The files in tests/expected/ were produced from the ATS programs by
`make expected` and are committed, so these tests need only python3.
Run them from MySolution/ with `make test` or
`python3 -m unittest discover -s tests -v`.

Outputs are compared as bytes, so a lost trailing space or a changed line
ending counts as a failure. When outputs differ, lines are shown with repr()
so that such invisible differences can be seen.
"""

import difflib
import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
TRANSLATION = ROOT / "translation" / "queens.py"
CASES = TESTS / "py" / "cases.py"
EXPECTED = TESTS / "expected"

TIMEOUT = 60         # seconds allowed for each program
CONTEXT = 3          # unchanged lines shown around a difference
MAX_DIFF_LINES = 40  # longest diff printed in one report
MAX_STDERR_LINES = 30
PREAMBLE = "(output before the first case)"


def lines(data):
    # latin-1 maps every byte to one character, so no difference is lost in decoding.
    return data.decode("latin-1").splitlines(keepends=True)


def repr_diff(expected, actual, expected_name, actual_name):
    """Unified diff of two line lists, one repr() per line, cut to MAX_DIFF_LINES."""
    diff = list(difflib.unified_diff(
        [repr(line) for line in expected], [repr(line) for line in actual],
        expected_name, actual_name, n=CONTEXT, lineterm=""))
    if len(diff) > MAX_DIFF_LINES:
        more = len(diff) - MAX_DIFF_LINES
        diff = diff[:MAX_DIFF_LINES] + [f"... ({more} more diff lines not shown)"]
    return "\n".join(diff)


def describe_whole_mismatch(expected, actual):
    exp, act = lines(expected), lines(actual)
    first = next((n for n, (e, a) in enumerate(zip(exp, act)) if e != a), min(len(exp), len(act)))
    return "\n".join([
        f"output differs from expected/queens.out starting at line {first + 1}",
        f"(expected {len(exp)} lines, got {len(act)})",
        repr_diff(exp, act, "expected/queens.out", "translation/queens.py"),
    ])


def split_cases(data):
    """Split cases output at its "### <id> ..." headers into {id: lines}, in order."""
    cases = {}
    current = PREAMBLE
    for line in lines(data):
        if line.startswith("### "):
            words = line.split()
            current = words[1] if len(words) > 1 else line
        cases.setdefault(current, []).append(line)
    return cases


def describe_case_mismatch(expected, actual):
    exp, act = split_cases(expected), split_cases(actual)
    differing = [cid for cid in exp if cid in act and exp[cid] != act[cid]]
    missing = [cid for cid in exp if cid not in act]
    extra = [cid for cid in act if cid not in exp]

    report = ["output differs from expected/cases.out"]
    if differing:
        report.append("differing cases: " + ", ".join(differing))
    if missing:
        report.append("missing cases: " + ", ".join(missing))
    if extra:
        report.append("unexpected output: " + ", ".join(extra))
    if not (differing or missing or extra):
        report.append("every case matches, but they come out in a different order")

    if differing:
        cid = differing[0]
        report.append(f"\nfirst differing case, {cid}:")
        report.append(repr_diff(exp[cid], act[cid], "expected", "actual"))
    elif extra:
        cid = extra[0]
        report.append(f"\nstart of {cid}:")
        report.extend(repr(line) for line in act[cid][:MAX_DIFF_LINES])
    return "\n".join(report)


class RegressionTest(unittest.TestCase):
    """Each test runs one Python program and compares its behavior with the ATS original's."""

    def require_translation(self):
        if not TRANSLATION.exists():
            self.fail(f"translation not found: {TRANSLATION.relative_to(ROOT)} does not exist")

    def run_program(self, script):
        """Run a Python program and return its stdout bytes; fail the test if it crashes."""
        self.require_translation()
        name = script.relative_to(ROOT)
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=ROOT,
                                  capture_output=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            proc = None
        if proc is None:
            self.fail(f"{name} did not finish within {TIMEOUT} seconds")
        if proc.returncode != 0:
            headers = [line for line in lines(proc.stdout) if line.startswith("### ")]
            stderr = lines(proc.stderr)[-MAX_STDERR_LINES:]
            self.fail("\n".join(
                [f"{name} exited with code {proc.returncode}"]
                + ([f"last case started: {headers[-1].rstrip()}"] if headers else [])
                + ["stderr (last lines):", "".join(stderr).rstrip()]))
        return proc.stdout

    def test_whole_program(self):
        """translation/queens.py prints exactly what ./queens printed."""
        actual = self.run_program(TRANSLATION)
        expected = (EXPECTED / "queens.out").read_bytes()
        if actual != expected:
            self.fail(describe_whole_mismatch(expected, actual))

    def test_function_cases(self):
        """tests/py/cases.py prints exactly what the ATS tests/ats/cases.dats printed."""
        actual = self.run_program(CASES)
        expected = (EXPECTED / "cases.out").read_bytes()
        if actual != expected:
            self.fail(describe_case_mismatch(expected, actual))

    # The two tests below cover paths the normal run never takes. What the ATS
    # original does on these paths was checked by hand (see TESTING.md).

    def test_failed_count_check(self):
        """If the count is not 92, it prints everything, then only a location on stderr, and exits 1."""
        self.require_translation()
        # The count is always 92, so make search report one fewer, then run main0.
        code = ("import sys; sys.path.insert(0, 'translation'); import queens; "
                "real = queens.search; queens.search = lambda *args: real(*args) - 1; "
                "queens.main0()")
        proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                              capture_output=True, timeout=TIMEOUT)
        stderr = proc.stderr.decode("latin-1")
        self.assertEqual(proc.returncode, 1, stderr)
        self.assertEqual(proc.stdout, (EXPECTED / "queens.out").read_bytes(),
                         "stdout before the failed check should be the normal output")
        # ATS's assertloc prints just the location of the check, with no newline.
        self.assertRegex(stderr, r"\A[^\n]*queens\.py: line \d+\Z")

    @unittest.skipUnless(hasattr(signal, "SIGPIPE"), "needs POSIX signals")
    def test_closed_output_pipe(self):
        """If nobody reads its output, it is stopped by SIGPIPE and prints no error, like ATS."""
        self.require_translation()
        read_end, write_end = os.pipe()
        os.close(read_end)  # closed before the program starts, so its first write fails
        try:
            proc = subprocess.run([sys.executable, str(TRANSLATION)], cwd=ROOT, stdout=write_end,
                                  stderr=subprocess.PIPE, timeout=TIMEOUT)
        finally:
            os.close(write_end)
        stderr = proc.stderr.decode("latin-1")
        self.assertEqual(proc.returncode, -signal.SIGPIPE,
                         f"expected to be stopped by SIGPIPE; stderr:\n{stderr[-2000:]}")
        self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
