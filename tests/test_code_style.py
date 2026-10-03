import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".claude", ".venv", "node_modules", "dist", ".git", "data", "__pycache__", ".pytest_cache"}
PRAGMAS = ("noqa", "type: ignore", "pragma: no cover", "eslint-disable")
HASH_SUFFIXES = {".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
SLASH_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".css"}
STRING_LITERAL = re.compile(r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")


def source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix in {".py", *HASH_SUFFIXES, *SLASH_SUFFIXES} or path.name == "Dockerfile":
            yield path
        elif path.parent.name == ".githooks":
            yield path


def is_pragma(text: str) -> bool:
    return any(pragma in text for pragma in PRAGMAS)


def python_comments(text: str):
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and not is_pragma(token.string):
            if not (token.start[0] == 1 and token.string.startswith("#!")):
                yield token.start[0]


def hash_comments(text: str):
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if number == 1 and stripped.startswith("#!"):
            continue
        if stripped.startswith("#") and not is_pragma(stripped):
            yield number


def slash_comments(text: str):
    for number, line in enumerate(text.splitlines(), start=1):
        code = STRING_LITERAL.sub('""', line)
        if re.search(r"(^|\s|\{)(//|/\*)", code) and not is_pragma(code):
            yield number


def comment_lines(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return list(python_comments(text))
    if path.suffix in SLASH_SUFFIXES:
        return list(slash_comments(text))
    return list(hash_comments(text))


@pytest.mark.parametrize("path", sorted(source_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_comments(path):
    lines = comment_lines(path)
    assert not lines, f"{path.relative_to(ROOT)} has comments on lines {lines}"


def test_detector_catches_comments():
    assert list(python_comments("x = 1  # set x\n")) == [1]
    assert list(python_comments("#!/usr/bin/env python\nx = 1  # noqa\n")) == []
    assert list(slash_comments('const url = "http://x"; // note')) == [1]
    assert list(slash_comments('const url = "http://x";')) == []
    assert list(slash_comments("{/* jsx */}")) == [1]
    assert list(hash_comments("#!/bin/bash\n# hi\necho")) == [2]
