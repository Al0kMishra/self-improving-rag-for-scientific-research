# Contributing

## Commits

Every commit follows [Conventional Commits](https://www.conventionalcommits.org/). The `.githooks/commit-msg` hook enforces it (`scripts/setup.sh` enables it through `git config core.hooksPath .githooks`).

```
<type>(<optional scope>): <summary>
```

- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Scopes:** the module touched, e.g. `api`, `db`, `arxiv`, `pdf`, `chunking`, `embeddings`, `ranking`, `llm`, `evaluation`, `adaptation`, `experiments`, `frontend`.
- **Summary:** imperative, lowercase, at most 72 characters, no trailing period.
- One logical change per commit. Tests go in the same commit as the code they cover.

## Comments

The code should explain itself through names and small functions, so comments are not allowed in source files. `tests/test_code_style.py` fails the suite if one appears in Python, JavaScript, CSS, shell, YAML or Dockerfiles.

- Tool pragmas are the only exception: `# noqa`, `# type: ignore`, `# pragma: no cover`, `eslint-disable`.
- No docstrings that restate the function name.
- Design rationale belongs in the README or `docs/`, not inline.

## Checks before committing

```bash
.venv/bin/pytest
(cd frontend && npm run build)
```
