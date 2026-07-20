---
name: chat-style
description: Coding conventions for the chat project — error handling, Pydantic validation, docstrings, logging, string formatting, typing, and the known inconsistencies to converge. Use when writing or reviewing Python code in this repo. Triggers on "code style", "convention", "how should I format", "naming", "lint", "typing".
---

# Chat — Style

Small Flask/Redis codebase. PEP 8, 4-space indent. The conventions below are what
the code *does today*; the **Target** notes are where to converge during the
"improve" phase (don't churn unrelated code mid-task).

## Established patterns (keep these)

- **Errors:** business logic raises `ChatAPIError(message, status_code)`. Wrap
  low-level failures with chaining: `except (RedisError, ValidationError) as e:
  raise ChatAPIError("...", 422) from e`. Routes catch `ChatAPIError` and map it
  to `jsonify({"error": ...}), e.get_status_code()`.
- **Validation:** validate untrusted input through Pydantic models
  (`User`, `Message`, `ChatRoom`) — e.g. `User(name=user_id)` to validate a name.
- **Redis stays in `ChatAPI`.** Routes and socket handlers never call Redis directly.
- **Docstrings:** Google-style with `Args:` / `Returns:` / `Raises:` on public
  `ChatAPI` methods and routes. Match that when adding methods.

## Known inconsistencies (converge, don't spread)

- **String formatting is mixed.** `api.py`/`routes.py` use `%` (`"room:%s" % id`);
  `socket.py`/client use f-strings. **Target:** f-strings everywhere *except*
  logging.
- **Logging uses eager interpolation** — `logger.info("Registered %s" % user)`.
  **Target:** lazy args — `logger.info("Registered %s", user)` — so the string is
  only built when the record is emitted.
- **Type hints are partial.** Some methods are annotated (`login_user(... ) -> str`),
  many aren't (`get_rooms`, `join_room`). **Target:** annotate all public
  signatures; the repo has no type checker yet (adding `mypy`/`ruff` is a good task).
- **Imports aren't ordered** (stdlib mixed with third-party in `api.py`).
  **Target:** stdlib → third-party → local, alphabetized (`ruff`/`isort` can enforce).

## If you add tooling

There's no formatter/linter config yet. `ruff` (format + lint, single tool) is the
lightest way to standardize the above; add it to a `requirements-dev.txt` and a
`[tool.ruff]` section in a new `pyproject.toml`.
