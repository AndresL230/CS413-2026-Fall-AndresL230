"""The canned examples offered in the Load source menu."""
from dataclasses import dataclass
from pathlib import Path

EXAMPLES_DIRECTORY = Path(__file__).resolve().parent.parent / "examples"


@dataclass(frozen=True)
class Example:
    key: str
    name: str
    text: str


def load_canned_examples(directory: Path = EXAMPLES_DIRECTORY) -> tuple[Example, ...]:
    canned = (("factorial", "Factorial (canned)"), ("fibonacci", "Fibonacci (canned)"))
    return tuple(
        Example(key, name, (directory / f"{key}.lambda").read_text(encoding="utf-8"))
        for key, name in canned)
