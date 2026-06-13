# OpenMAIC Immersive Classroom And Narrated Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repository-contained OpenMAIC module that `/assistant` can invoke to generate a personalized immersive classroom and a narrated, subtitled knowledge-point MP4.

**Architecture:** Keep OpenMAIC as an independent Next.js service under `third_party/openmaic`, protected by an internal API token and short-lived signed playback access. Keep zhixue as the source of truth: FastAPI builds a minimal RAG/profile brief, persists `media_jobs` and `media_assets`, polls OpenMAIC through arq, exports MP4, and exposes artifacts in the existing Agent conversation.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, arq/Redis, httpx, MoviePy/Pillow, Next.js 16, TypeScript, OpenMAIC, Xiaomi MiMo TTS.

---

## File Structure

### Vendored OpenMAIC module

- Create: `third_party/openmaic/**` from the local modified OpenMAIC working tree, excluding `.git`, `.env.local`, `.next`, `node_modules`, generated classroom data, caches, and build artifacts.
- Create: `third_party/openmaic/UPSTREAM.md`
- Create: `third_party/openmaic/CHANGES_ZHIXUE.md`
- Create: `third_party/openmaic/lib/server/internal-auth.ts`
- Create: `third_party/openmaic/app/api/classrooms/[id]/manifest/route.ts`
- Modify: `third_party/openmaic/app/api/generate-classroom/route.ts`
- Modify: `third_party/openmaic/app/api/generate-classroom/[jobId]/route.ts`
- Modify: `third_party/openmaic/middleware.ts`
- Modify: `third_party/openmaic/.env.example`
- Test: `third_party/openmaic/tests/server/internal-auth.test.ts`

### zhixue backend

- Create: `backend/app/integrations/openmaic/__init__.py`
- Create: `backend/app/integrations/openmaic/client.py`
- Create: `backend/app/services/immersive_classroom_service.py`
- Create: `backend/app/services/classroom_video_export_service.py`
- Create: `backend/app/workers/immersive_classroom_worker.py`
- Create: `backend/tests/test_openmaic_client.py`
- Create: `backend/tests/test_immersive_classroom.py`
- Create: `backend/tests/test_classroom_video_export.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/schemas/multimodal.py`
- Modify: `backend/app/api/v1/multimodal.py`
- Modify: `backend/app/api/v1/media_assets.py`
- Modify: `backend/app/repositories/media_repository.py`
- Modify: `backend/app/workers/agent_worker.py`
- Modify: `backend/app/agent_runtime/service_tools.py`
- Modify: `backend/app/agent_runtime/supervisor_intents.py`
- Modify: `backend/app/agent_runtime/supervisor.py`
- Modify: `.env.example`

### zhixue frontend and docs

- Create: `frontend/components/assistant/ImmersiveClassroomCard.tsx`
- Modify: `frontend/components/assistant/extractChatArtifacts.ts`
- Modify: `frontend/components/assistant/InlineMediaArtifacts.tsx`
- Modify: `frontend/types/agent.ts`
- Modify: `docs/当前实现基线.md`
- Modify: `docs/功能完成度与待完善清单.md`

## Task 1: Vendor The Modified OpenMAIC Snapshot

- [ ] Copy the local OpenMAIC tree into `third_party/openmaic` while excluding secrets, Git metadata, dependencies, build outputs, generated classrooms, and caches.
- [ ] Add `UPSTREAM.md` with upstream URL, local source path, baseline commit, snapshot date, and AGPL disclosure.
- [ ] Add `CHANGES_ZHIXUE.md` documenting the existing MiMo V2.5, Token Plan, MiMo TTS/ASR changes and this integration.
- [ ] Verify excluded paths are absent with:

```powershell
Get-ChildItem third_party/openmaic -Force
Get-ChildItem third_party/openmaic -Recurse -Force -Directory |
  Where-Object Name -in '.git','.next','node_modules'
```

Expected: source files and license exist; excluded directories and `.env.local` do not exist.

## Task 2: Secure OpenMAIC Internal APIs And Playback

- [ ] Write `tests/server/internal-auth.test.ts` first. Assert internal requests accept `x-openmaic-internal-token`, invalid requests are rejected, and short-lived playback signatures verify only before expiry.
- [ ] Run:

```powershell
pnpm vitest run tests/server/internal-auth.test.ts
```

Expected: FAIL because `lib/server/internal-auth.ts` does not exist.

- [ ] Implement `internal-auth.ts` with constant-time token comparison and HMAC-SHA256 playback token verification.
- [ ] Protect classroom create, job polling, and manifest APIs with the internal token.
- [ ] Add the manifest endpoint returning persisted `stage` and `scenes`.
- [ ] Update middleware to exchange a valid `zhixue_token` query parameter for a short-lived HttpOnly cookie and allow that cookie to access classroom playback/media APIs.
- [ ] Run the focused Vitest test and `pnpm build`.

Expected: PASS and successful OpenMAIC build.

## Task 3: Implement The FastAPI OpenMAIC Client

- [ ] Write `backend/tests/test_openmaic_client.py` first with `httpx.MockTransport`. Cover create-job parsing, job-status parsing, manifest parsing, internal-token header, and playback URL signing.
- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_openmaic_client.py -q
```

Expected: FAIL because the client does not exist.

- [ ] Add OpenMAIC settings to `backend/app/core/config.py` and `.env.example`.
- [ ] Implement `OpenMAICClient` with `create_classroom`, `get_job`, `get_manifest`, `health_check`, and `build_signed_playback_url`.
- [ ] Re-run the focused tests.

Expected: PASS.

## Task 4: Build And Persist Personalized Classroom Jobs

- [ ] Write `backend/tests/test_immersive_classroom.py` first. Cover minimal brief construction, course permission validation, secret/private-field exclusion, job creation, and classroom artifact response shape.
- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_immersive_classroom.py -q
```

Expected: FAIL because the service and request schema do not exist.

- [ ] Add `ImmersiveClassroomGenerateRequest`.
- [ ] Implement `ImmersiveClassroomService.create_job()` using the existing multimodal brief, resource repository, media repository, and arq.
- [ ] Add `POST /api/v1/multimodal/classrooms/generate`.
- [ ] Add `MediaRepository.get_job_for_user()` for strict job ownership.
- [ ] Re-run focused tests.

Expected: PASS.

## Task 5: Poll OpenMAIC And Create Classroom Artifacts

- [ ] Extend `backend/tests/test_immersive_classroom.py` first with worker tests for progress mapping, successful classroom asset creation, OpenMAIC failure, and independent video-export enqueueing.
- [ ] Run the worker-focused tests and confirm they fail for the missing worker.
- [ ] Implement `run_immersive_classroom_job`:
  - create the provider job;
  - poll until success/failure/timeout;
  - map OpenMAIC stages into `media_jobs`;
  - publish `multimodal_progress`;
  - save a small authorized classroom descriptor JSON as a `media_asset`;
  - enqueue MP4 export only after classroom success.
- [ ] Register the function in `agent_worker.WorkerSettings`.
- [ ] Add `GET /api/v1/media-assets/{asset_id}/launch` that validates ownership and redirects to a signed OpenMAIC playback URL.
- [ ] Re-run focused tests.

Expected: PASS.

## Task 6: Export Narrated And Subtitled MP4

- [ ] Write `backend/tests/test_classroom_video_export.py` first. Cover scene narration extraction, subtitle timing generation, fallback TTS, and output metadata.
- [ ] Run:

```powershell
cd backend
python -m pytest tests/test_classroom_video_export.py -q
```

Expected: FAIL because the export service does not exist.

- [ ] Implement `ClassroomVideoExportService`:
  - extract speech actions and readable scene titles;
  - prefer OpenMAIC `audioUrl`, otherwise call zhixue audio provider;
  - create one visual frame per narration segment;
  - concatenate audio-backed clips;
  - burn subtitles into frames;
  - store MP4 metadata including classroom asset ID, citations, audio provider, and fallback flags.
- [ ] Implement `run_classroom_video_export_job` and register it in the arq worker.
- [ ] Re-run focused tests.

Expected: PASS.

## Task 7: Add Agent Tool And Intent Routing

- [ ] Extend `backend/tests/test_supervisor_intents.py` first. Assert “沉浸课堂”, “一键课程”, and “知识点讲解视频和沉浸课堂” route to `generate_immersive_classroom`, while ordinary “生成讲解视频” continues to use `generate_lesson_video`.
- [ ] Run the focused tests and confirm they fail.
- [ ] Add the `generate_immersive_classroom` handler and Tool Registry definition.
- [ ] Add intent, deliverable label, required-deliverable routing, and Supervisor argument defaults.
- [ ] Re-run focused tests and existing Agent harness tests.

Expected: PASS.

## Task 8: Display Classroom Artifacts In `/assistant`

- [ ] Add frontend tests only if the existing frontend test runner supports the relevant components; otherwise use TypeScript/build and browser verification.
- [ ] Extend artifact extraction to recognize `immersive_classroom`.
- [ ] Add `ImmersiveClassroomCard` with title, scene count, citation count, personalized reason, degradation labels, and a launch button using the authenticated backend launch endpoint.
- [ ] Render classroom cards separately from generic media previews; keep MP4 on the existing video player.
- [ ] Add the new tool to selectable Agent tools.
- [ ] Run:

```powershell
cd frontend
npm run typecheck
npm run build
```

Expected: both commands exit successfully.

## Task 9: Synchronize Facts, Verify, And Commit

- [ ] Run backend focused tests, then the full backend suite.
- [ ] Run OpenMAIC focused tests and build.
- [ ] Run frontend typecheck and build.
- [ ] Run `python scripts/export_implementation_docs.py`.
- [ ] Update current baseline and completion facts without claiming deferred PBL/interaction feedback features.
- [ ] Run `python scripts/check_docs.py`.
- [ ] Start local backend, worker, frontend, and OpenMAIC module; execute a smoke test that creates a classroom job and verifies progress/error behavior. Use real MiMo only when configured; never report a Mock/fallback result as real generation.
- [ ] Review `git diff --check`, repository status, and secret exclusions.
- [ ] Commit the implementation in scoped commits, leaving unrelated `scripts/_check_server_storage.py` untouched.
