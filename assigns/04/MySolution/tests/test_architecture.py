"""Dependency rules between the components, checked from their imports."""
import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "lambda_workbench"
STATIC = Path(__file__).resolve().parent.parent / "static"

# Application modules each module is allowed to import.
ALLOWED = {
    "contract": set(),
    "reader": {"lambda1"},
    "tools": {"contract", "reader", "lambda1"},
    "tool_worker": {"tools"},
    "backend": {"contract"},
    "model": {"contract"},
    "examples": set(),
    "controller": {"contract", "examples", "model"},
    "view": {"contract", "controller", "examples", "model"},
    "web": {"backend", "controller", "examples", "model", "view"},
}
LANGUAGE_TOOLS = {"lambda1", "reader", "tools", "tool_worker", "backend"}


def imports_of(module: str) -> tuple[set[str], set[str]]:
    """Return (application modules, outside packages) imported by `module`."""
    tree = ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))
    internal, external = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            internal.update([node.module] if node.module else [name.name for name in node.names])
        elif isinstance(node, ast.ImportFrom):
            external.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            external.update(name.name.split(".")[0] for name in node.names)
    return internal, external


class Dependencies(unittest.TestCase):
    def test_every_module_imports_only_what_its_role_allows(self):
        modules = {path.stem for path in PACKAGE.glob("*.py")} - {"__init__", "lambda1"}
        self.assertEqual(modules, set(ALLOWED))
        for module, allowed in ALLOWED.items():
            with self.subTest(module=module):
                self.assertLessEqual(imports_of(module)[0], allowed)

    def test_model_controller_and_view_do_not_reach_the_language_tools(self):
        for module in ["model", "controller", "view"]:
            with self.subTest(module=module):
                self.assertFalse(imports_of(module)[0] & LANGUAGE_TOOLS)

    def test_only_the_http_boundary_depends_on_the_web_framework(self):
        for module in set(ALLOWED) - {"web"}:
            with self.subTest(module=module):
                self.assertNotIn("flask", imports_of(module)[1])

    def test_only_the_backend_starts_processes(self):
        for module in set(ALLOWED) - {"backend"}:
            with self.subTest(module=module):
                self.assertNotIn("subprocess", imports_of(module)[1])

    def test_browser_view_contains_no_language_logic(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        for term in ["D0E", "D0V", "fvset", "evaluate"]:
            self.assertNotIn(term, script)


if __name__ == "__main__":
    unittest.main()
