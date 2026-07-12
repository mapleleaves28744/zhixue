# Real Provider Full Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce repeatable evidence that every configured student-facing generation capability completes with a real provider, then remove only measured reliability, latency, or output-quality regressions.

**Architecture:** Extend the existing `main_chain_check.py` and `agent_demo_check.py` patterns with one serial real-provider runner. The runner creates an isolated user/course, makes API requests, polls asynchronous tasks/jobs, validates provider/fallback metadata and persisted artifacts, and writes sanitized JSON plus a Markdown acceptance record. Optimizations are implemented only after a baseline record identifies the exact failing boundary.

**Tech Stack:** Python 3.12, `httpx`, FastAPI `/api/v1`, PostgreSQL task/resource records, ARQ Worker, Docker Compose, pytest.

## Global Constraints

- Never print, persist, or commit API keys; report only whether a provider is configured.
- A real-generation pass requires a non-Mock provider, no fallback, terminal success, and an owner-accessible persisted result.
- Run scenarios serially; use a dedicated test account/course and bounded polling timeouts.
- Do not change database schema, permissions, Docker topology, or user-owned learning data.
- Reuse running Docker services; after an approved code fix restart only its affected service through `scripts/fast_deploy_code.sh`.
- All Router, Schema, or SQLAlchemy Model edits require `python scripts/export_implementation_docs.py`; none are planned unless a verified defect requires them.

---

## File Structure

- Create: `scripts/real_provider_acceptance.py` — serial authenticated API runner, provider preflight, scenario timing, task/job polling, assertions, sanitized JSON output.
- Create: `backend/tests/test_real_provider_acceptance_helpers.py` — unit tests for provider classification, response assertions, timeout classification, and report sanitization without a network call.
- Create: `docs/19_测试方案/25_真实Provider全量验收记录.md` — durable matrix containing commands, environment (without secrets), pass/fail/not-configured results, latency, artifacts, failures, and retained optimizations.
- Modify: `docs/19_测试方案/19_测试方案.md` — add the new real-provider acceptance runner and record to the existing test entrypoint.
- Potentially modify, only after a measured failure: the single service/provider/worker/frontend file proven to be on the failing boundary, together with its focused regression test.

## Task 1: Build the deterministic real-provider acceptance runner

**Files:**
- Create: `scripts/real_provider_acceptance.py`
- Create: `backend/tests/test_real_provider_acceptance_helpers.py`

**Interfaces:**
- Consumes: the authenticated API contracts used by `scripts/main_chain_check.py` and `scripts/agent_demo_check.py`.
- Produces: `RealProviderAcceptance.run() -> dict[str, Any]`, JSON `{scenarios, provider_preflight, summary}` written only to an explicit output path, and nonzero exit status on any configured capability failure.

- [ ] **Step 1: Write pure helper tests before adding the runner**

```python
from scripts.real_provider_acceptance import (
    classify_provider,
    require_real_response,
    sanitize_error,
)


def test_classify_provider_rejects_mock_and_fallback() -> None:
    assert classify_provider({"provider": "xiaomi_mimo", "fallback_used": False}) == "real"
    assert classify_provider({"provider": "mock", "fallback_used": False}) == "mock"
    assert classify_provider({"provider": "fallback", "fallback_used": True}) == "fallback"


def test_require_real_response_rejects_mock_even_when_http_succeeds() -> None:
    try:
        require_real_response({"provider": "mock", "fallback_used": False}, "tutor")
    except RuntimeError as exc:
        assert "tutor" in str(exc)
    else:
        raise AssertionError("mock response must not pass real-provider acceptance")


def test_sanitize_error_removes_bearer_tokens() -> None:
    assert "secret-value" not in sanitize_error("Bearer secret-value provider failed")
```

- [ ] **Step 2: Run the helper tests and confirm they fail before implementation**

Run:

```bash
docker exec zhixue-backend pytest tests/test_real_provider_acceptance_helpers.py -q
```

Expected: collection failure because `scripts.real_provider_acceptance` does not exist.

- [ ] **Step 3: Implement the runner primitives and provider preflight**

```python
REAL_PROVIDER_DENYLIST = {"", "mock", "fallback", "mock_multimodal", "mock_audio"}


def classify_provider(payload: dict[str, Any]) -> str:
    provider = str(payload.get("provider") or "").strip().lower()
    if payload.get("fallback_used") or provider == "fallback":
        return "fallback"
    return "real" if provider not in REAL_PROVIDER_DENYLIST else "mock"


def require_real_response(payload: dict[str, Any], scenario: str) -> None:
    state = classify_provider(payload)
    if state != "real":
        raise RuntimeError(f"{scenario}: expected real provider, got {state} ({payload.get('provider')!r})")
```

The runner must: create/login a unique `real_acceptance_<unix_milliseconds>` student; create one private Data Structures course; capture `perf_counter()` at request start; poll `/agent/tasks/{id}` and `/multimodal/jobs/{id}` until terminal state; verify the relevant response/resource/media URL through the owning token; and append a sanitized scenario result even if a later scenario fails.

- [ ] **Step 4: Implement serial scenario coverage**

Implement `run_text_scenarios()` using these existing API calls and assertions:

```python
POST /wiki/pages/generate-from-material
POST /tutor/chat
POST /resources/generate
POST /quizzes/generate
POST /quizzes/{quiz_id}/submit
POST /diagnosis/analyze?course_id={course_id}&trigger_evolution=false
POST /learning-paths/generate
POST /evolution/analyze
POST /agent/conversations/{conversation_id}/messages
```

Use `main_chain_check.py` for request-body shapes and assertions, and `agent_demo_check.py` for conversation/task polling and event persistence assertions. For each text scenario require a real `provider`, `fallback_used is False` when that field exists, expected structured fields, and persisted IDs. For the Agent scenario also require a `completed` event, `succeeded` status, an assistant message, and at least one tool event for the explicit generation prompt.

Implement `run_media_scenarios()` with image, audio, courseware, video, and immersive-classroom calls only when the preflight confirms the necessary provider configuration. Validate provider/job metadata and owner-accessible media/resource output; otherwise add `not_configured` with the missing configuration name and do not call the endpoint.

- [ ] **Step 5: Run helper tests and static syntax validation**

Run:

```bash
docker exec zhixue-backend pytest tests/test_real_provider_acceptance_helpers.py -q
docker exec zhixue-backend python -m py_compile /app/scripts/real_provider_acceptance.py
```

Expected: helper tests pass and compilation exits 0. If `/app/scripts` is not mounted into the running container, run the command with the project Python environment before deployment and record the exact environment limitation.

- [ ] **Step 6: Commit the runner and unit tests**

```bash
git add scripts/real_provider_acceptance.py backend/tests/test_real_provider_acceptance_helpers.py
git commit -m "test: add real provider acceptance runner"
```

## Task 2: Establish the baseline with configured real providers

**Files:**
- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`
- Modify: `docs/19_测试方案/19_测试方案.md`

**Interfaces:**
- Consumes: `python scripts/real_provider_acceptance.py --base-url http://127.0.0.1/api/v1 --json-output /tmp/real-provider-baseline.json`.
- Produces: a complete Markdown matrix with each scenario’s state, provider/model, latency, artifact/task ID, and failure boundary.

- [ ] **Step 1: Run configuration-only preflight**

Run:

```bash
docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py --preflight --base-url http://127.0.0.1/api/v1
```

Expected: text LLM configuration is reported as configured without exposing key values; each external media provider is explicitly configured or not configured.

- [ ] **Step 2: Run the serial baseline suite**

Run:

```bash
docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py \
  --base-url http://127.0.0.1/api/v1 \
  --timeout 900 \
  --json-output /tmp/real-provider-baseline.json
```

Expected: every configured scenario reaches `passed` or exits nonzero with an individual scenario record; the runner continues after a scenario failure so the result is a full matrix.

- [ ] **Step 3: Write the baseline record from the sanitized JSON**

Create a table with exact columns:

```markdown
| Scenario | Provider / Model | Status | API / First output / Completion | Evidence ID | Result or failure boundary |
|---|---|---|---|---|---|
```

Classify any failure as `request/auth`, `provider`, `structured-output`, `queue/worker`, `persistence`, `artifact`, or `frontend`, and include the reproducible command.

- [ ] **Step 4: Link the runner and record from the test-index document**

Add under “真实LLM专项”:

```markdown
真实 Provider 全量验收使用 `python scripts/real_provider_acceptance.py`。它只接受真实 Provider、无 fallback 且可访问的持久化结果；最新证据见 `25_真实Provider全量验收记录.md`。
```

- [ ] **Step 5: Validate documentation and commit the baseline record**

Run:

```bash
python scripts/check_docs.py
git diff --check
```

Expected: both commands exit 0.

```bash
git add docs/19_测试方案/19_测试方案.md docs/19_测试方案/25_真实Provider全量验收记录.md
git commit -m "docs: record real provider acceptance baseline"
```

## Task 3: Repair and measure one verified bottleneck at a time

**Files:**
- Modify: one file at the proven boundary, selected only after Task 2.
- Modify: the corresponding existing test file under `backend/tests/`.
- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`.

**Interfaces:**
- Consumes: a failed or slow scenario row from Task 2 and its sanitized task/provider/error evidence.
- Produces: one focused regression test and before/after measurement for the same scenario.

- [ ] **Step 1: Select exactly one root-cause hypothesis from the baseline**

Write the hypothesis in the acceptance record before editing, for example:

```markdown
Hypothesis: `GroundedQAPipeline` blocks the SSE `done` event on a non-critical structured memory reflection; moving that reflection to its existing post-response event path reduces completion latency without changing the cited answer.
```

Do not combine prompt, queue, timeout, and UI changes in the same iteration.

- [ ] **Step 2: Add a focused failing regression test**

For an SSE completion blocker, use an existing Tutor pipeline test and assert the critical response finishes even if the non-critical post-processing task fails:

```python
async def test_streaming_answer_completes_when_post_response_reflection_fails(
    pipeline: GroundedQAPipeline,
    payload: TutorChatRequest,
    user: User,
) -> None:
    pipeline._schedule_post_response = AsyncMock(side_effect=RuntimeError("reflection unavailable"))
    events = [event async for event in pipeline.stream_chat(payload, user)]
    assert any(event["event"] == "done" for event in events)
```

For a structured-provider failure, assert the provider retry formatter yields valid schema JSON from the captured malformed shape. For a Worker failure, assert a queued task transitions to `failed` with a correlated error rather than remaining `running`.

- [ ] **Step 3: Run only the new regression test and confirm it fails**

Run the exact relevant pytest node, for example:

```bash
docker exec zhixue-backend pytest tests/test_tutor.py::test_streaming_answer_completes_when_post_response_reflection_fails -q
```

Expected: fail for the observed baseline behavior, not for unrelated environment setup.

- [ ] **Step 4: Implement the smallest boundary fix and deploy only its service**

Make one focused change, run the exact test to passing, then use one of:

```bash
./scripts/fast_deploy_code.sh backend
./scripts/fast_deploy_code.sh frontend
```

Expected: only the service containing the fix is refreshed; database, Redis, and OpenMAIC remain running.

- [ ] **Step 5: Re-run the same acceptance scenario and compare results**

Run:

```bash
docker exec zhixue-backend python /app/scripts/real_provider_acceptance.py \
  --scenario tutor_fast \
  --base-url http://127.0.0.1/api/v1 \
  --json-output /tmp/real-provider-after.json
```

Expected: status changes to `passed`, or the measured completion time improves while output/provider/citations/artifact checks remain unchanged.

- [ ] **Step 6: Record the retained change and run relevant checks**

Run the exact focused pytest command, the scenario rerun, `git diff --check`, and—if frontend code changed—`npm run typecheck && npm run build` in the frontend environment. Append before/after timings and remaining external-provider limitations to the acceptance record, then commit the code, test, and record together.

## Task 4: Final full rerun and handoff

**Files:**
- Modify: `docs/19_测试方案/25_真实Provider全量验收记录.md`

**Interfaces:**
- Consumes: the completed runner and any Task 3 fixes.
- Produces: the final all-scenario result matrix and a clear list of not-configured or provider-limited capabilities.

- [ ] **Step 1: Run the full serial suite again**

Run the same command as Task 2 Step 2 with a fresh JSON output path. Do not reuse baseline artifacts as evidence of the final code state.

- [ ] **Step 2: Verify operational state**

Run:

```bash
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1/health
git diff --check
```

Expected: required services are running, health returns `{"status":"ok","service":"zhixue-workshop"}`, and the worktree has no whitespace error.

- [ ] **Step 3: Complete the final acceptance record**

The conclusion must enumerate: pass count, fail count, not-configured count, real providers/models, retained optimizations with before/after data, and remaining risk. Do not describe a Mock/fallback response or unavailable provider as a pass.

- [ ] **Step 4: Commit and hand off**

```bash
git add docs/19_测试方案/25_真实Provider全量验收记录.md
git commit -m "docs: finalize real provider acceptance results"
```

Report the final matrix, exact verification commands, affected files, database/API changes (normally none), and any provider-account limitation that requires user action.
