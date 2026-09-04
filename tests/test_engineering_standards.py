from __future__ import annotations

import ast
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("core", "analysis", "agent", "watch", "actions", "api", "sanket_mcp")
EXEMPT = ("forked", "board", ".venv", "notebooks", "node_modules")

MAX_FUNCTION_LINES = 40
MAX_FILE_LINES = 400


def source_files() -> list[Path]:
    files: list[Path] = []
    for package in PACKAGES:
        for path in (ROOT / package).rglob("*.py"):
            if any(part in EXEMPT for part in path.parts):
                continue
            files.append(path)
    return files


def test_no_comments_in_any_source_file() -> None:
    offenders: list[str] = []
    for path in source_files():
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type == tokenize.COMMENT and not token.string.startswith("#!"):
                    offenders.append(f"{path.relative_to(ROOT)}:{token.start[0]} {token.string}")
    assert not offenders, "comments are forbidden:\n" + "\n".join(offenders)


def test_every_signature_has_type_hints() -> None:
    offenders: list[str] = []
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.returns is None:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name} return")
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                if arg.arg in {"self", "cls"}:
                    continue
                if arg.annotation is None:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} {node.name}({arg.arg})"
                    )
    assert not offenders, "missing type hints:\n" + "\n".join(offenders)


def test_files_stay_under_four_hundred_lines() -> None:
    offenders = [
        f"{p.relative_to(ROOT)}: {len(p.read_text(encoding='utf-8').splitlines())}"
        for p in source_files()
        if len(p.read_text(encoding="utf-8").splitlines()) > MAX_FILE_LINES
    ]
    assert not offenders, "files over 400 lines:\n" + "\n".join(offenders)


def test_functions_stay_under_forty_lines() -> None:
    offenders: list[str] = []
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.end_lineno is None:
                continue
            length = node.end_lineno - node.lineno
            if length > MAX_FUNCTION_LINES:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}={length}")
    assert not offenders, "functions over 40 lines:\n" + "\n".join(offenders)
