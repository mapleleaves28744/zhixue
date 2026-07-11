# Real Provider Full Acceptance Design

## Goal

Verify every implemented student-facing generation capability against configured real providers, identify the first failing boundary with evidence, and make only the smallest changes required to remove verified failures or unintended Mock/fallback outcomes.

## Scope

The acceptance run uses a dedicated authenticated demo account and a disposable course. It covers the implemented learning loop and all configured generation surfaces:

1. Fast grounded Tutor SSE and non-streaming fallback path.
2. LangGraph intelligent-agent conversation, tool execution, task events, and final answer persistence.
3. Wiki creation from material, resource generation, quiz generation/submission, diagnosis, learning-path generation, recommendation refresh, profile/memory reflection, and evolution analysis.
4. Audio synthesis/transcription, educational image, interactive courseware, lesson video, and OpenMAIC immersive classroom/MP4 export when the corresponding provider is configured.

This is not a blanket claim about unconfigured vendors. A capability whose external provider key, endpoint, or account entitlement is absent is recorded as **not configured**, never as a successful real generation.

## Acceptance Contract

Each scenario records: request ID/task ID, start/end time, real provider/model returned by the system, fallback metadata, persisted artifact or response ID, and any error. A scenario passes only when all applicable conditions hold:

- HTTP request and asynchronous task terminal state are successful.
- The response names a non-Mock provider and does not report fallback.
- The expected persisted response, resource, media asset, task event, or downloadable output exists and is accessible to its owner.
- Text results contain the requested course concept and required structure; grounded answers have valid source citations when the scenario requires them.
- Multimedia results report a provider job and a usable output URL/file, not a placeholder or Mermaid/Mock substitute.

The report separates latency into synchronous API acceptance, first streaming content, task completion, and final artifact availability. It must not compare slow video/classroom work with ordinary chat as though they have the same service-level expectation.

## Test Design

Tests execute serially by default to avoid contention between the single Worker, real LLM rate limits, and heavy media jobs. The suite first verifies provider configuration without printing secrets, then validates low-cost text paths, then asynchronous agent paths, then costly media paths. Every scenario uses stable prompts about the seeded Data Structures course, and the runner polls task/job state to a bounded timeout.

For every failed condition the runner preserves sanitized API responses, task events, provider status, and container log correlation. It classifies the failure boundary as frontend/API, authorization/data setup, queue/Worker, provider request, structured-output validation, artifact persistence, or external provider completion.

## Optimization Decision Rule

No performance or prompt change is made during the baseline run. After the baseline, changes are eligible only if the evidence shows one of these causes:

- avoidable duplicate LLM call or retrieval;
- a synchronous non-critical follow-up blocking completion;
- incorrect retry/fallback or structured-output handling;
- unnecessary serial wait between independent background operations;
- prompt/output format causing repeated schema validation failure; or
- missing provider-specific timeout, polling, or artifact-readiness handling.

Each optimization has a focused regression test and is measured against the same scenario before being retained. Quality improvements must preserve source attribution, authorization, persistence, and the explicit no-Mock acceptance rule.

## Safety and Data Boundaries

- API keys are checked as configured/not configured only and are never logged, stored in reports, or committed.
- The run uses a dedicated test user/course and labels all generated data as acceptance evidence.
- Existing learner records, source materials, strategy history, and user data are not modified.
- Database schema, permissions, and deployment topology are out of scope.
- Docker services are reused; only the affected service is restarted after a verified code change.

## Deliverables

1. A reusable, parameterized real-provider acceptance runner and a sanitized JSON/Markdown result record outside tracked source data or in the project acceptance-record convention where appropriate.
2. Targeted regression tests for every verified code fix.
3. A final matrix of pass, fail, and not-configured scenarios, with measured latency and real provider evidence.
4. A concise optimization summary stating retained changes, before/after measurements, and remaining provider-side limits.
