# Task 1 Report: Intent-scoped tool selection

## Scope

- Added `backend/app/agent_runtime/tool_selector.py` with the internal
  `select_tool_schemas(state, tool_schemas)` selector.
- Updated `LearningAgentGraph._supervise()` to give `Supervisor.decide()` the
  selected candidate schemas rather than the complete registry.
- Extended the existing `plan_created` / `replanned` event payload with
  `total_tool_count` and `candidate_tool_count`.
- Added selector and graph-integration regression coverage in
  `backend/tests/test_agent_runtime.py`.

No public API, `Supervisor.decide()` signature, Agent Tool schema, provider
contract, database model, router, or migration changed.

## Behavior

- Course QA goals select the grounded retrieval and course-answer tools when
  both are registered, excluding unrelated tools such as quiz generation.
- PPT/courseware goals select course retrieval plus interactive courseware and
  exclude video generation.
- Explicit tool hints are deduplicated with intent candidates; skipped tools
  are excluded. If recognized candidates are all skipped, the selector returns
  no schemas rather than exposing unrelated tools. If no candidate is present
  in the registry, it preserves the prior full-registry fallback.
- The graph records both the full registry count and the actual candidate count
  in its plan event payload.

The task brief's sample selector delegated entirely to `plan_required_tools`,
but the required test goal `解释栈` produces no planned tool in the current
`supervisor_intents` implementation. The selector therefore recognizes concise
course-QA wording and adds the grounded pair; it also applies the existing
runtime's course-grounding rule to planned generation tools. This is required
to satisfy the specified observable behavior without modifying the established
intent-planning contract.

## TDD evidence

1. Added the selector tests first.
2. Ran the requested RED command with the project virtual environment:
   `./.venv/bin/python -m pytest tests/test_agent_runtime.py -k 'grounded_tools or excludes_video' -v`.
   It failed during collection with the expected
   `ModuleNotFoundError: No module named 'app.agent_runtime.tool_selector'`.
   (`python` itself is not installed on PATH; `backend/.venv/bin/python` is the
   project interpreter.)
3. Implemented the selector, reran the focused test, and observed both tests
   pass.
4. Added the graph integration/event-count test, observed it fail while the
   graph still passed every registry schema to the supervisor, then connected
   the selector and observed it pass.

## Verification

Executed from `backend/`:

```text
./.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py -v
```

Result: `79 passed, 6 warnings in 2.54s`.

Also ran `git diff --check` successfully before staging. The environment does
not have `ruff` or `black` installed, so their checks could not be run.

## Commit

`fb9ca0f20e6ecbaf2274e15b096de901960ce5c9 feat: limit agent tools by intent`

Only these task files are committed:

- `backend/app/agent_runtime/tool_selector.py`
- `backend/app/agent_runtime/graph.py`
- `backend/tests/test_agent_runtime.py`

The report and pre-existing untracked planning files remain uncommitted.

## Review follow-up

An independent review identified that the initial full-registry fallback would
re-expose unrelated tools when every recognized candidate was skipped. Added a
failing regression test (`test_skipping_every_candidate_does_not_expose_unrelated_tools`),
changed the selector to return an empty candidate list in that case, and reran
the focused and full regression suites above.

## Follow-up review fix

The subsequent review found that the compatibility fallback still returned a
skipped tool when no intent candidate matched the registered schemas. Added
`test_fallback_excludes_skipped_tools` for `随便聊聊` with
`skip_tools=["generate_quiz"]` and `generate_quiz` / `search_web` schemas.

TDD evidence:

1. The focused command
   `./.venv/bin/python -m pytest tests/test_agent_runtime.py -k 'fallback_excludes_skipped_tools' -v`
   failed first because the fallback returned both tools.
2. The fallback now filters the original schema sequence by `skip_tools`; the
   same focused test passed.
3. `./.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_supervisor_intents.py -v`
   then passed: `80 passed, 6 warnings in 2.43s`.

Follow-up commit (task files only):

`426a39a33bf17afeb3b972ec2487e847d985bbea fix: honor skipped tools in selector fallback`
