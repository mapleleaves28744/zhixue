# Phase 2/3 Agent Task And Planner Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conversational AgentTask entry that converts natural-language learning requests into validated plans, executes those plans through existing services, and shows a persistent step timeline with real artifacts.

**Architecture:** Phase 2 introduces user-owned AgentTask persistence, deterministic intent routing, state transitions, APIs, and the `/assistant` task card. Phase 3 adds a strict Pydantic plan schema, an agent/action whitelist, and a synchronous `LearningTaskGraph` that calls existing Service boundaries and persists each step result.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, PostgreSQL JSONB, existing Agent/Service layer, pytest, Stitch static HTML/JavaScript.

---

## File Map

Create:

- `backend/app/models/agent_task.py`: AgentTask and AgentTaskStep ORM.
- `backend/app/schemas/agent_task.py`: API schemas, plan schemas, status constants, whitelist validation.
- `backend/app/repositories/agent_task_repository.py`: user-filtered task and step persistence.
- `backend/app/services/agent_task_service.py`: task state machine and intent-to-plan creation.
- `backend/app/agents/intent_router_agent.py`: deterministic natural-language intent parser.
- `backend/app/agent_graphs/__init__.py`: execution graph package.
- `backend/app/agent_graphs/learning_task_graph.py`: whitelist executor and step lifecycle.
- `backend/app/api/v1/agent_tasks.py`: AgentTask API.
- `backend/alembic/versions/20260607_0100_c9d0e1f2a3b4_agent_tasks.py`: two new tables.
- `backend/tests/test_agent_tasks.py`: Phase 2/3 behavior and execution tests.
- `docs/19_测试方案/15_Phase2与Phase3Agent任务执行器阶段验收记录.md`: formal acceptance record.

Modify:

- `backend/app/models/__init__.py`: export new ORM models.
- `backend/app/agents/__init__.py`: register IntentRouterAgent.
- `backend/app/agents/orchestrator.py`: add `route_intent`.
- `backend/app/api/v1/router.py`: mount AgentTask router.
- `frontend/public/stitch-pages/zhixue-static-api.js`: AgentTask API methods.
- `frontend/public/stitch-pages/assistant.html`: task detection, card, controls, timeline polling.
- Current implementation facts and Phase 2/3 status documents.

## Task 1: Specify AgentTask Behavior With Failing Tests

- [ ] Add `backend/tests/test_agent_tasks.py` tests for:
  - IntentRouterAgent parsing “图和排序” plus four requested artifacts.
  - high-risk wording requiring confirmation.
  - `AgentTaskPlan` rejecting an unknown action.
  - fixed personalized package plan containing path, resource, quiz, and review.
  - service state transitions rejecting run before confirmation.
  - user-filtered repository access.
  - LearningTaskGraph preserving completed steps and skipping later steps after failure.
- [ ] Run `python -m pytest tests/test_agent_tasks.py -q`.
- [ ] Verify RED fails because AgentTask modules do not exist.

## Task 2: Add AgentTask ORM And Migration

- [ ] Implement `AgentTask` and `AgentTaskStep` with JSONB payloads, lifecycle timestamps, ownership foreign keys, step uniqueness, and query indexes.
- [ ] Export models from `backend/app/models/__init__.py`.
- [ ] Add migration `c9d0e1f2a3b4` with downgrade support.
- [ ] Run `python -m alembic upgrade head`.
- [ ] Verify PostgreSQL contains `agent_tasks` and `agent_task_steps`.

## Task 3: Implement Intent Routing And Validated Plans

- [ ] Implement `IntentRouterAgent` with deterministic artifact, knowledge-point, task-type, and risk extraction.
- [ ] Register it and add Orchestrator route `route_intent`.
- [ ] Implement `AgentTaskPlanStep` and `AgentTaskPlan` Pydantic schemas.
- [ ] Define exact agent/action whitelist and fixed plans for:
  - `personalized_learning_package`
  - `profile_interview_plan`
  - `html_classroom_request`
- [ ] Run focused Intent and plan tests until GREEN.

## Task 4: Implement Repository, State Machine, And API

- [ ] Implement repository methods for create, user-filtered get, list steps, status update, step update, and pending-step skip.
- [ ] Implement `AgentTaskService.create_task`, `get_task`, `get_steps`, `confirm_task`, `cancel_task`, and `run_task`.
- [ ] Enforce:
  - readable course validation;
  - current-user task isolation;
  - `waiting_confirmation → planned`;
  - only `planned` tasks can run;
  - only active tasks can cancel.
- [ ] Add six AgentTask API routes using unified responses.
- [ ] Mount router and run focused service/API tests until GREEN.

## Task 5: Implement LearningTaskGraph

- [ ] Implement synchronous execution that marks task and each step lifecycle.
- [ ] Dispatch only exact whitelist pairs to existing services:
  - learning path;
  - explanation or HTML classroom draft resource;
  - quiz;
  - profile rebuild;
  - recommendation refresh;
  - ReviewAgent.
- [ ] Store compact output payloads, evidence, related AgentRun IDs when available, and artifact refs.
- [ ] On failure, mark current step failed, remaining steps skipped, and task failed without deleting completed artifacts.
- [ ] Run complete Mock personalized package test and verify at least two artifact types plus step logs.

## Task 6: Connect The Stitch Assistant

- [ ] Add `createAgentTask`, `getAgentTask`, `getAgentTaskSteps`, `confirmAgentTask`, `runAgentTask`, and `cancelAgentTask` to `zhixue-static-api.js`.
- [ ] Add complex-task detection while preserving ordinary Tutor questions.
- [ ] Render AgentTask card with risk, plan, controls, artifact summary, and step timeline.
- [ ] Poll while running and stop on terminal states.
- [ ] Run `npm run typecheck` and `npm run build`.

## Task 7: Verify And Synchronize Facts

- [ ] Run `python -m alembic upgrade head`.
- [ ] Run `python -m pytest`.
- [ ] Run `python scripts/export_implementation_docs.py`.
- [ ] Run `python scripts/check_docs.py`.
- [ ] Start current backend/frontend if needed.
- [ ] In a real browser, create and run a complex `/assistant` task and verify:
  - structured card;
  - visible timeline;
  - terminal status;
  - real artifact refs.
- [ ] Update current baseline, completion list, test index, sprint plan status, and formal acceptance record with actual counts and evidence.

## Self-Review

- Spec coverage: Phase 2 task persistence, IntentRouter, APIs, task card, Phase 3 whitelist, executor, Review, timeline, tests, and documentation are all assigned.
- Placeholder scan: no implementation placeholders or unspecified error-handling steps remain.
- Type consistency: task/step statuses, plan field names, API names, and whitelist actions are identical across design and plan.

