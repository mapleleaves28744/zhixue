# 智学工坊 V3 网页端悬浮桌宠落地方案 - Part 2：后端接口与前端 Store

---

## 9. 后端落地代码

### 9.1 扩展 AgentTaskRepository：查询活跃任务

文件：

```text
backend/app/repositories/agent_task_repository.py
```

新增 import：

```python
from sqlalchemy import desc
```

在 `AgentTaskRepository` 类中新增：

```python
async def list_active_for_user(
    self,
    user_id: UUID,
    *,
    course_id: UUID | None = None,
    limit: int = 5,
) -> list[AgentTask]:
    active_statuses = {
        "queued",
        "planned",
        "waiting_confirmation",
        "running",
    }

    stmt = (
        select(AgentTask)
        .where(
            AgentTask.user_id == user_id,
            AgentTask.status.in_(active_statuses),
        )
        .order_by(
            desc(AgentTask.last_event_at),
            desc(AgentTask.created_at),
        )
        .limit(limit)
    )

    if course_id is not None:
        stmt = stmt.where(AgentTask.course_id == course_id)

    result = await self.db.execute(stmt)
    return list(result.scalars().all())
```

再新增最近完成任务查询，用于刷新页面后仍能看到“刚完成”的提示：

```python
async def list_recent_finished_for_user(
    self,
    user_id: UUID,
    *,
    course_id: UUID | None = None,
    limit: int = 3,
) -> list[AgentTask]:
    finished_statuses = {"succeeded", "failed", "cancelled"}

    stmt = (
        select(AgentTask)
        .where(
            AgentTask.user_id == user_id,
            AgentTask.status.in_(finished_statuses),
        )
        .order_by(desc(AgentTask.finished_at), desc(AgentTask.updated_at))
        .limit(limit)
    )

    if course_id is not None:
        stmt = stmt.where(AgentTask.course_id == course_id)

    result = await self.db.execute(stmt)
    return list(result.scalars().all())
```

---

### 9.2 扩展 AgentConversationService：活跃任务读取

文件：

```text
backend/app/services/agent_conversation_service.py
```

新增方法：

```python
async def list_active_tasks(
    self,
    current_user: User,
    *,
    course_id: UUID | None = None,
    include_recent_finished: bool = True,
) -> list[AgentTaskRead]:
    active = await self.tasks.list_active_for_user(
        current_user.id,
        course_id=course_id,
        limit=5,
    )

    items = list(active)

    if include_recent_finished and len(items) < 5:
        recent = await self.tasks.list_recent_finished_for_user(
            current_user.id,
            course_id=course_id,
            limit=5 - len(items),
        )
        existing_ids = {item.id for item in items}
        items.extend([item for item in recent if item.id not in existing_ids])

    return [AgentTaskRead.model_validate(item) for item in items]
```

说明：

```text
active task 用于桌宠显示当前生成中任务；
recent finished 用于刷新后仍提醒用户“刚刚生成完成”。
```

---

### 9.3 新增 API：GET /agent/tasks/active

文件：

```text
backend/app/api/v1/agent.py
```

新增 import：

```python
from fastapi import APIRouter, Depends, Query, Request
```

如果原文件已有 `APIRouter, Depends, Request`，只补 `Query`。

新增接口，注意要放在 `/tasks/{task_id}` 之前，避免路由把 `active` 当成 UUID：

```python
@router.get("/tasks/active")
async def list_active_tasks(
    request: Request,
    course_id: UUID | None = Query(default=None),
    include_recent_finished: bool = Query(default=True),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    items = await AgentConversationService(db).list_active_tasks(
        current_user,
        course_id=course_id,
        include_recent_finished=include_recent_finished,
    )
    return success_response(
        {"items": [item.model_dump(mode="json") for item in items]},
        request=request,
    )
```

返回示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "task-uuid",
        "course_id": "course-uuid",
        "conversation_id": "conversation-uuid",
        "task_goal": "帮我生成 BFS 的讲解视频和练习题",
        "task_type": "dynamic_learning_agent",
        "status": "running",
        "plan_json": {
          "artifact_refs": [],
          "citations": [],
          "decision_summary": "正在生成学习资源"
        }
      }
    ]
  }
}
```

---

## 10. 前端类型定义

文件：

```text
frontend/types/mascot.ts
```

代码：

```ts
export type MascotName = "zhizhi" | "lulu" | "diandian";

export type MascotState =
  | "idle"
  | "focus"
  | "remind"
  | "done"
  | "unsure"
  | "waiting_confirmation"
  | "failed";

export type MascotTaskKind = "agent_task" | "media_job";

export type MascotTaskStatus =
  | "queued"
  | "planned"
  | "waiting_confirmation"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "completed";

export type MascotTask = {
  id: string;
  kind: MascotTaskKind;
  courseId?: string | null;
  conversationId?: string | null;
  title: string;
  goal?: string;
  status: MascotTaskStatus;
  progress?: number;
  stage?: string;
  message?: string;
  riskLevel?: string;
  targetUrl?: string;
  createdAt?: string;
  updatedAt?: string;
  lastEventAt?: string;
  artifactCount?: number;
  citationCount?: number;
};

export type MascotSnapshot = {
  mascot: MascotName;
  state: MascotState;
  task: MascotTask | null;
  tasks: MascotTask[];
  message: string;
};
```

---

## 11. 前端 API 封装

文件：

```text
frontend/lib/zhixue-web-api.ts
```

代码：

```ts
import type { MascotTask } from "@/types/mascot";

const ACCESS_TOKEN_KEY = "access_token";

function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  }

  return (
    window.localStorage.getItem("zhixue_api_base") ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000/api/v1"
  );
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new Error("NO_TOKEN");

  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${token}`);

  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, headers });
  const payload = await response.json().catch(() => null);

  if (!response.ok || !payload || payload.code !== 0) {
    const message = payload?.detail || payload?.message || `请求失败：${response.status}`;
    throw new Error(typeof message === "string" ? message : "请求失败");
  }

  return payload.data as T;
}

type AgentTaskRead = {
  id: string;
  course_id: string;
  conversation_id?: string | null;
  task_goal: string;
  task_type: string;
  status: string;
  risk_level: string;
  plan_json?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  last_event_at?: string;
};

function buildTargetUrl(task: AgentTaskRead): string {
  const params = new URLSearchParams();
  if (task.course_id) params.set("course_id", task.course_id);
  if (task.conversation_id) params.set("conversation_id", task.conversation_id);
  params.set("task_id", task.id);
  return `/assistant?${params.toString()}`;
}

export function normalizeAgentTask(item: AgentTaskRead): MascotTask {
  const planJson = item.plan_json || {};
  const artifacts = Array.isArray(planJson.artifact_refs) ? planJson.artifact_refs : [];
  const citations = Array.isArray(planJson.citations) ? planJson.citations : [];

  return {
    id: item.id,
    kind: "agent_task",
    courseId: item.course_id,
    conversationId: item.conversation_id,
    title: item.task_goal || "学习任务",
    goal: item.task_goal,
    status: item.status as MascotTask["status"],
    riskLevel: item.risk_level,
    stage: typeof planJson.decision_summary === "string" ? planJson.decision_summary : undefined,
    targetUrl: buildTargetUrl(item),
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    lastEventAt: item.last_event_at,
    artifactCount: artifacts.length,
    citationCount: citations.length,
  };
}

export async function listActiveAgentTasks(courseId?: string | null): Promise<MascotTask[]> {
  const query = new URLSearchParams({ include_recent_finished: "true" });
  if (courseId) query.set("course_id", courseId);
  const data = await request<{ items: AgentTaskRead[] }>(`/agent/tasks/active?${query.toString()}`);
  return (data.items || []).map(normalizeAgentTask);
}

export async function getAgentTask(taskId: string): Promise<MascotTask> {
  const data = await request<AgentTaskRead>(`/agent/tasks/${taskId}`);
  return normalizeAgentTask(data);
}

export async function streamAgentTaskEvents(
  taskId: string,
  handlers: {
    onEvent?: (eventType: string, data: Record<string, unknown>) => void;
    onClose?: () => void;
    onError?: (error: Error) => void;
  }
): Promise<void> {
  const token = getToken();
  if (!token) throw new Error("NO_TOKEN");

  const response = await fetch(`${getApiBaseUrl()}/agent/tasks/${taskId}/events`, {
    headers: { Accept: "text/event-stream", Authorization: `Bearer ${token}` },
  });

  if (!response.ok || !response.body) throw new Error("Agent 事件流连接失败");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  function consumeEvent(rawEvent: string) {
    const lines = rawEvent.split("\n").map((line) => line.trimEnd());
    const eventName = (lines.find((line) => line.startsWith("event:")) || "event: message").slice(6).trim();
    const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart());
    if (!dataLines.length) return;
    const eventData = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    handlers.onEvent?.(eventName, eventData);
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const eventText of events) {
        if (eventText.trim()) consumeEvent(eventText);
      }
      if (done) break;
    }
    if (buffer.trim()) consumeEvent(buffer);
    handlers.onClose?.();
  } catch (error) {
    handlers.onError?.(error instanceof Error ? error : new Error("事件流读取失败"));
  }
}
```

---

## 12. 前端全局任务 Store

文件：

```text
frontend/lib/mascot-task-store.ts
```

代码：

```ts
import type { MascotTask } from "@/types/mascot";

type Listener = (tasks: MascotTask[]) => void;

const STORAGE_KEY = "zhixue_active_mascot_tasks";
const CHANNEL_NAME = "zhixue-agent-task-events";

let memoryTasks: MascotTask[] = [];
const listeners = new Set<Listener>();

function sortTasks(tasks: MascotTask[]): MascotTask[] {
  const priority: Record<string, number> = {
    waiting_confirmation: 100,
    running: 90,
    planned: 80,
    queued: 70,
    succeeded: 60,
    completed: 60,
    failed: 50,
    cancelled: 10,
  };

  return [...tasks].sort((a, b) => {
    const pa = priority[a.status] ?? 0;
    const pb = priority[b.status] ?? 0;
    if (pa !== pb) return pb - pa;
    const ta = Date.parse(a.lastEventAt || a.updatedAt || a.createdAt || "0");
    const tb = Date.parse(b.lastEventAt || b.updatedAt || b.createdAt || "0");
    return tb - ta;
  });
}

function persist() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memoryTasks.slice(0, 10)));
  } catch {}
}

function emit() {
  const next = sortTasks(memoryTasks);
  memoryTasks = next;
  persist();
  listeners.forEach((listener) => listener(next));
}

export function loadMascotTasksFromStorage(): MascotTask[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as MascotTask[];
    memoryTasks = sortTasks(Array.isArray(parsed) ? parsed : []);
    return memoryTasks;
  } catch {
    return [];
  }
}

export function getMascotTasks(): MascotTask[] {
  return memoryTasks;
}

export function subscribeMascotTasks(listener: Listener): () => void {
  listeners.add(listener);
  listener(memoryTasks);
  return () => listeners.delete(listener);
}

export function upsertMascotTask(task: MascotTask) {
  const index = memoryTasks.findIndex((item) => item.id === task.id && item.kind === task.kind);
  if (index >= 0) {
    memoryTasks[index] = { ...memoryTasks[index], ...task, updatedAt: task.updatedAt || new Date().toISOString() };
  } else {
    memoryTasks.unshift({ ...task, updatedAt: task.updatedAt || new Date().toISOString() });
  }
  memoryTasks = memoryTasks.slice(0, 10);
  emit();
}

export function clearCompletedMascotTasks() {
  memoryTasks = memoryTasks.filter(
    (item) => !["succeeded", "completed", "failed", "cancelled"].includes(item.status)
  );
  emit();
}

export function setupMascotBroadcastListener() {
  if (typeof window === "undefined") return () => {};
  loadMascotTasksFromStorage();
  const channel = "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL_NAME) : null;

  function handleMessage(data: unknown) {
    if (!data || typeof data !== "object") return;
    const event = data as { type?: string; task?: MascotTask };
    if (event.type === "task-upsert" && event.task) upsertMascotTask(event.task);
  }

  channel?.addEventListener("message", (event) => handleMessage(event.data));
  function onWindowMessage(event: MessageEvent) { handleMessage(event.data); }
  window.addEventListener("message", onWindowMessage);

  return () => {
    channel?.close();
    window.removeEventListener("message", onWindowMessage);
  };
}
```
