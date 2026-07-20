---
name: chat-git
description: Git and GitHub conventions for the chat project — commit message style, branching, and PR flow. Use for any git operation (commit, branch, push, PR).
---

# Chat — Git

- **Remote:** `git@github.com:fimkap/chat.git`. **Default branch:** `main`.

## Commit messages

Short, imperative/descriptive, **sentence case**, capitalized first word. A
trailing period is common. **No** conventional-commit prefixes (`feat:`/`fix:`)
here — that's the ADK repo's style, not this one.

Observed examples:

```
Notify room on disconnect
Add simple token-based authentication
Replace pytest_mock_resources with local FakeRedis
Fix http status.
```

When Claude Code makes the commit, end the message with:

```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

## Branching & PRs

- **Don't commit directly to `main`.** Branch first, then open a PR — the history
  is entirely PR-merged (`Merge pull request #N from fimkap/<branch>`).
- Feature branches use a `<topic>/<slug>` shape (existing ones are `codex/...`);
  pick a short descriptive slug.
- Use the `gh` CLI for PRs. End PR bodies with the Claude Code generation line.
- Only commit or push when the user asks.
