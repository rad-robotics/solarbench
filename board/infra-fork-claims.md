---
id: infra-fork-claims
title: Claims from forks
track: infra
milestone: v1
priority: stretch
needs: cpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "tools/board.py"
  - "tests/test_board.py"
  - "board/README.md"
  - "AGENTS.md"
  - ".github/workflows/check.yml"
done_when:
  - "python tools/board.py shows an item claimed through a draft pull request from a fork as doing, with its owner"
  - "the overlap check covers such claims"
---
## Why
A claim made by pushing a branch here needs write access. Contributors working from a fork claim by opening a pull request, and the tool has to see those.

## What
- `tools/board.py` reads open pull requests whose branch is named after an item as claims, alongside branches.
- The earliest pull request for an item holds it; a later one fails its check.
- Works without credentials on a public repository; `--offline` skips it.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-27 (spartacosan): the tool now reads open pull requests as claims; the ordering rule is unit-tested and the tool was run against the live repository. Not yet seen: a real pull request from a fork showing as `doing`. The first one confirms it, and this item can then be closed.
