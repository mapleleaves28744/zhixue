# Task 3 Report — Supervisor Runtime Responsibility Split

## Scope

- Added focused completion formatting, prompt construction, and safety-policy modules.
- Kept `MiMoSupervisor.decide()` and the established private forwarding surface used by tests and services.
- Added `supervisor_duration_ms` to each `plan_created` / `replanned` event payload.
- Did not modify structured outputs, provider acceptance files, API/database/frontend code, or demo data.

## Implementation

- `supervisor_completion.py` owns search-result formatting plus normal and artifact-aware completion answers.
- `supervisor_prompt.py` owns the Supervisor system/context message construction while preserving the existing prompt text and message protocol.
- `supervisor_policy.py` owns the deterministic safety-net decision boundary, including completed-tool filtering, required-deliverable enforcement, explicit retrieval/web-search requirements, fallback selection, and safe tool-call continuation.
- `supervisor.py` delegates to the extracted modules and retains compatibility methods for existing callers.
- `graph.py` measures the awaited Supervisor decision with `time.perf_counter()` and records integer milliseconds in the plan event payload.

## Test evidence

1. Red: `backend/.venv/bin/python -m pytest tests/test_supervisor_intents.py tests/test_agent_runtime.py -k 'empty_course_search or supervisor_receives_intent_scoped_schemas_and_plan_counts' -v`
   - Failed first for the missing `supervisor_completion` module, then for the missing duration event key.
2. Green: the same focused command passed after implementation (2 passed).
3. Regression: `backend/.venv/bin/python -m pytest tests/test_supervisor_intents.py tests/test_agent_harness.py tests/test_agent_runtime.py -v`
   - 91 passed; six existing FastAPI/pytest deprecation warnings only.
4. Direct completion-consumer regression: `backend/.venv/bin/python -m pytest tests/test_web_search_service.py tests/test_multimodal_review.py -v`
   - 9 passed.
5. Review-fix RED: `backend/.venv/bin/python -m pytest tests/test_supervisor_intents.py -k safe_arguments_compatibility -v`
   - Failed at collection because `supervisor_policy.safe_arguments` did not yet exist.
6. Review-fix GREEN: the same targeted command passed (1 passed), followed by the required runtime regression command with 92 passed.
7. Final review-fix: moved the remaining policy helpers into `SupervisorPolicy`, reduced `MiMoSupervisor` to decision orchestration plus compatibility forwarding methods, and removed both legacy safety-net and prompt bodies. The required Supervisor/runtime command passed again: 92 passed.
8. Follow-up review fix: profile-only routing now preserves its original summary, plan text, and direct update-profile tool call; `_PolicyHost` and import-time alias mutation were removed. RED first failed because the profile branch did not preserve the expected plan; GREEN: required suite passed with 93 tests.

## Files in task commit

- `backend/app/agent_runtime/supervisor.py`
- `backend/app/agent_runtime/supervisor_policy.py`
- `backend/app/agent_runtime/supervisor_prompt.py`
- `backend/app/agent_runtime/supervisor_completion.py`
- `backend/app/agent_runtime/graph.py`
- `backend/tests/test_supervisor_intents.py`
- `backend/tests/test_agent_runtime.py`
