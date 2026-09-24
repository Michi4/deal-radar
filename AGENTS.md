# AGENTS.md — deal-radar autonomous build rules

## Done condition
Done only when BOTH hold:
1. `./scripts/verify.sh` exits 0
2. Every item in ACCEPTANCE.md is `[x]` with an evidence line (command + result)

## Never stop
- Never end a turn to ask questions or summarize. Choose the reasonable option, log it in DECISIONS.md, continue.
- After every task, open ACCEPTANCE.md, take the next unchecked item.
- Blocked externally (missing key, site block, unverifiable API)? Log in BLOCKERS.md (tried/needed), implement behind an interface with a real fallback, leave unchecked, move on. Blocked is not stopping.
- Long context: keep PROGRESS.md current (state + next 5 steps).

## No faking
- Check an item only after running its verification in this session and seeing it pass. Evidence line required.
- No stubs/`pass`/TODO/hardcoded returns presented as working. A stub keeps its item unchecked.
- Mocks/fixtures only for parser + pipeline unit/contract tests. Drivers, AI workers, notifiers, transports also need live tests (`tests/live/`, `@pytest.mark.live`). No live run → unchecked + BLOCKERS.md.
- Never invent an external API's shape. Read real docs/responses first, save samples as fixtures. Unverifiable → BLOCKERS.md.
- Never skip/delete/xfail/weaken a test for green. Fix the code.
- A red run is information. Report it red.

## Work loop (every change)
1. Test for the behavior first. 2. Implement. 3. `./scripts/verify.sh` green.
4. Exercise end to end against the real app (HTTP, SSE, UI). 5. Commit+push (`feat:|fix:|test:|docs:|refactor:|chore:`), wait for CI, fix red.

## Engineering rules
- Every failure: structured error (source/stage/cause/retryable), logged, counted, retry/fallback/next source. No bare excepts, no silent swallowing.
- Missing/None/malformed fields never crash. Rule = N/A → pass.
- Live tests hit real sites gently (≤1 req/s, cached, small samples).
- Everything user-facing configurable via config + UI. No magic constants.
- Docs match reality. README quickstart works from a clean clone.
