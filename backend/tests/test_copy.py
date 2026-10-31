"""design_sprint §J (Rexton 08:59): no em dash in text a user can see. Every string literal in the backend that is not a
docstring may reach a screen (report, journey words, reel cards, API messages), so none may contain U+2014."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "spoor"


def test_no_em_dash_in_user_visible_backend_strings():
    hits = []
    for f in SRC.rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}  # fmt: skip
        hits += [f"{f.relative_to(SRC)}:{n.lineno}" for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str) and "—" in n.value and id(n) not in docs]  # fmt: skip
    assert hits == [], f"em dash in visible strings: {hits}"
