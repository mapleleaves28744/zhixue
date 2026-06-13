# 智学工坊 V3 网页端悬浮桌宠落地方案 - Part 3：Hook、组件、样式、Stitch 通信

---

## 13. 桌宠 Hook：useAgentTaskPet

文件：

```text
frontend/hooks/useAgentTaskPet.ts
```

代码：

```ts
"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  clearCompletedMascotTasks,
  getMascotTasks,
  setupMascotBroadcastListener,
  subscribeMascotTasks,
  upsertMascotTask,
} from "@/lib/mascot-task-store";
import { getAgentTask, listActiveAgentTasks, streamAgentTaskEvents } from "@/lib/zhixue-web-api";
import type { MascotName, MascotSnapshot, MascotState, MascotTask } from "@/types/mascot";

const runningStatuses = new Set(["queued", "planned", "waiting_confirmation", "running"]);

function stateFromStatus(status?: string): MascotState {
  if (status === "waiting_confirmation") return "waiting_confirmation";
  if (status === "queued" || status === "planned") return "remind";
  if (status === "running") return "focus";
  if (status === "succeeded" || status === "completed") return "done";
  if (status === "failed") return "failed";
  return "idle";
}

function stateFromEvent(eventType: string): MascotState {
  if (eventType === "waiting_confirmation") return "waiting_confirmation";
  if (eventType === "queued") return "remind";
  if (eventType === "completed") return "done";
  if (eventType === "failed") return "failed";
  if (eventType === "cancelled") return "idle";
  return "focus";
}

function pickMascot(task: MascotTask | null): MascotName {
  const text = `${task?.title || ""} ${task?.goal || ""}`.toLowerCase();

  if (text.includes("练习") || text.includes("错题") || text.includes("诊断") || text.includes("quiz")) {
    return "diandian";
  }
  if (text.includes("计划") || text.includes("路径") || text.includes("推荐") || text.includes("path")) {
    return "lulu";
  }
  if (text.includes("wiki") || text.includes("资料") || text.includes("讲解") || text.includes("视频") || text.includes("课件") || text.includes("图解")) {
    return "zhizhi";
  }
  return "lulu";
}

function messageFor(task: MascotTask | null, state: MascotState): string {
  if (!task) return "我会在这里提醒你后台生成进度。";
  if (state === "waiting_confirmation") return "这个操作需要你确认后才能继续。";
  if (state === "remind") return "任务已进入后台队列，你可以先去看别的页面。";
  if (state === "focus") return task.stage || task.message || "我正在帮你生成学习资源。";
  if (state === "done") return (task.artifactCount || 0) > 0 ? `资源生成好了，共 ${task.artifactCount} 个产物，点我查看。` : "学习任务完成了，点我查看结果。";
  if (state === "failed") return "生成遇到问题了，点我查看原因。";
  return "我会在这里陪你盯着后台任务。";
}

function mergeEventIntoTask(task: MascotTask, eventType: string, data: Record<string, unknown>): MascotTask {
  const state = stateFromEvent(eventType);
  const nextStatus = eventType === "completed" ? "succeeded" : eventType === "failed" ? "failed" : eventType === "cancelled" ? "cancelled" : task.status;
  const artifactRefs = Array.isArray(data.artifacts) ? data.artifacts : Array.isArray(data.artifact_refs) ? data.artifact_refs : undefined;
  const citations = Array.isArray(data.citations) ? data.citations : undefined;

  return {
    ...task,
    status: nextStatus as MascotTask["status"],
    stage: typeof data.message === "string" ? data.message : typeof data.summary === "string" ? data.summary : task.stage,
    message: messageFor(task, state),
    progress: eventType === "completed" ? 100 : eventType === "failed" ? task.progress : Math.min(92, (task.progress || 12) + 8),
    artifactCount: artifactRefs ? artifactRefs.length : task.artifactCount,
    citationCount: citations ? citations.length : task.citationCount,
    updatedAt: new Date().toISOString(),
  };
}

export function useAgentTaskPet() {
  const [tasks, setTasks] = useState<MascotTask[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const watchedTaskIds = useRef(new Set<string>());

  useEffect(() => {
    const cleanupBroadcast = setupMascotBroadcastListener();
    const cleanupSubscribe = subscribeMascotTasks(setTasks);

    listActiveAgentTasks()
      .then((items) => items.forEach(upsertMascotTask))
      .catch(() => {});

    return () => {
      cleanupBroadcast();
      cleanupSubscribe();
    };
  }, []);

  useEffect(() => {
    const candidates = getMascotTasks().filter(
      (task) => task.kind === "agent_task" && runningStatuses.has(task.status)
    );

    for (const task of candidates) {
      if (watchedTaskIds.current.has(task.id)) continue;
      watchedTaskIds.current.add(task.id);

      void streamAgentTaskEvents(task.id, {
        onEvent: async (eventType, data) => {
          try {
            const latest = await getAgentTask(task.id);
            upsertMascotTask({ ...mergeEventIntoTask(latest, eventType, data), targetUrl: task.targetUrl || latest.targetUrl });
          } catch {
            upsertMascotTask(mergeEventIntoTask(task, eventType, data));
          }
        },
        onClose: () => watchedTaskIds.current.delete(task.id),
        onError: () => watchedTaskIds.current.delete(task.id),
      });
    }
  }, [tasks]);

  const primaryTask = useMemo(() => tasks[0] || null, [tasks]);
  const state = useMemo(() => stateFromStatus(primaryTask?.status), [primaryTask]);
  const mascot = useMemo(() => pickMascot(primaryTask), [primaryTask]);
  const message = useMemo(() => messageFor(primaryTask, state), [primaryTask, state]);

  const snapshot: MascotSnapshot = { mascot, state, task: primaryTask, tasks, message };

  return { snapshot, collapsed, dismissed, setCollapsed, setDismissed, clearCompleted: clearCompletedMascotTasks };
}
```

---

## 14. GlobalMascot 组件

文件：

```text
frontend/components/GlobalMascot.tsx
```

代码：

```tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bell, CheckCircle2, ChevronDown, ChevronUp, Clock3, XCircle } from "lucide-react";

import { useAgentTaskPet } from "@/hooks/useAgentTaskPet";
import type { MascotName, MascotState, MascotTask } from "@/types/mascot";

function stateImage(mascot: MascotName, state: MascotState): string {
  const petState = state === "focus" ? "focus" : state === "remind" || state === "waiting_confirmation" ? "remind" : state === "done" ? "done" : state === "failed" || state === "unsure" ? "remind" : "idle";
  return `/pets/${mascot}/${petState}.png`;
}

function fallbackSticker(mascot: MascotName, state: MascotState): string {
  const scene = state === "focus" ? "02_thinking" : state === "remind" || state === "waiting_confirmation" ? "07_reminder" : state === "done" ? "12_completed" : state === "failed" || state === "unsure" ? "11_unsure" : "05_sleepy_idle";
  return `/stickers/${mascot}/${scene}.png`;
}

function iconFor(status?: string) {
  if (status === "succeeded" || status === "completed") return <CheckCircle2 className="h-4 w-4" />;
  if (status === "failed") return <XCircle className="h-4 w-4" />;
  if (status === "waiting_confirmation") return <Bell className="h-4 w-4" />;
  return <Clock3 className="h-4 w-4" />;
}

function statusLabel(status?: string): string {
  return { queued: "排队中", planned: "已规划", waiting_confirmation: "待确认", running: "生成中", succeeded: "已完成", completed: "已完成", failed: "失败", cancelled: "已取消" }[status || ""] || "待处理";
}

function progressValue(task: MascotTask | null): number {
  if (!task) return 0;
  if (task.progress !== undefined) return task.progress;
  if (task.status === "queued") return 8;
  if (task.status === "planned") return 18;
  if (task.status === "running") return 48;
  if (task.status === "waiting_confirmation") return 66;
  if (task.status === "succeeded" || task.status === "completed") return 100;
  if (task.status === "failed") return 100;
  return 0;
}

function openTask(task: MascotTask | null) {
  window.location.href = task?.targetUrl || "/assistant";
}

export function GlobalMascot() {
  const { snapshot, collapsed, dismissed, setCollapsed, setDismissed, clearCompleted } = useAgentTaskPet();
  const { mascot, state, task, tasks, message } = snapshot;

  if (dismissed) return null;

  const progress = progressValue(task);
  const hasTask = Boolean(task);
  const isActive = task?.status === "queued" || task?.status === "planned" || task?.status === "running" || task?.status === "waiting_confirmation";

  return (
    <AnimatePresence>
      <motion.aside
        animate={{ opacity: 1, y: 0, scale: 1 }}
        className="zhixue-global-mascot"
        exit={{ opacity: 0, y: 18, scale: 0.96 }}
        initial={{ opacity: 0, y: 18, scale: 0.96 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        <button aria-label={collapsed ? "展开学习伙伴" : "收起学习伙伴"} className="zhixue-global-mascot__avatar" onClick={() => setCollapsed(!collapsed)} type="button">
          <span className={isActive ? "zhixue-global-mascot__pulse" : ""} />
          <img
            alt="智学工坊学习伙伴"
            onError={(event) => {
              const img = event.currentTarget;
              if (!img.dataset.fallback) {
                img.dataset.fallback = "true";
                img.src = fallbackSticker(mascot, state);
              }
            }}
            src={stateImage(mascot, state)}
          />
        </button>

        {!collapsed ? (
          <motion.div animate={{ opacity: 1, x: 0 }} className="zhixue-global-mascot__panel" initial={{ opacity: 0, x: 10 }} transition={{ duration: 0.18 }}>
            <div className="zhixue-global-mascot__header">
              <div>
                <div className="zhixue-global-mascot__eyebrow">
                  {mascot === "zhizhi" ? "知知 · 知识伙伴" : mascot === "diandian" ? "点点 · 练习伙伴" : "露露 · 学习提醒"}
                </div>
                <div className="zhixue-global-mascot__title">{hasTask ? statusLabel(task?.status) : "待命中"}</div>
              </div>
              <button aria-label="收起" className="zhixue-global-mascot__icon-button" onClick={() => setCollapsed(true)} type="button">
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>

            <p className="zhixue-global-mascot__message">{message}</p>

            {task ? (
              <div className="zhixue-global-mascot__task">
                <div className="zhixue-global-mascot__task-title">{iconFor(task.status)}<span>{task.title}</span></div>
                <div className="zhixue-global-mascot__progress"><div style={{ width: `${Math.max(4, Math.min(100, progress))}%` }} /></div>
                <div className="zhixue-global-mascot__meta">
                  {task.artifactCount ? <span>{task.artifactCount} 个产物</span> : null}
                  {task.citationCount ? <span>{task.citationCount} 条引用</span> : null}
                  {tasks.length > 1 ? <span>另有 {tasks.length - 1} 个任务</span> : null}
                </div>
                <div className="zhixue-global-mascot__actions">
                  <button className="zhixue-global-mascot__primary" onClick={() => openTask(task)} type="button">
                    {task.status === "waiting_confirmation" ? "去确认" : "查看任务"}
                  </button>
                  {["succeeded", "completed", "failed", "cancelled"].includes(task.status) ? <button className="zhixue-global-mascot__secondary" onClick={clearCompleted} type="button">清除已完成</button> : null}
                </div>
              </div>
            ) : (
              <button className="zhixue-global-mascot__primary" onClick={() => { window.location.href = "/assistant"; }} type="button">开始学习任务</button>
            )}
          </motion.div>
        ) : (
          <button aria-label="展开" className="zhixue-global-mascot__mini" onClick={() => setCollapsed(false)} type="button">
            {task ? statusLabel(task.status) : "学习伙伴"}<ChevronUp className="h-3.5 w-3.5" />
          </button>
        )}
      </motion.aside>
    </AnimatePresence>
  );
}
```

---

## 15. 挂载到 Next layout

文件：

```text
frontend/app/layout.tsx
```

修改为：

```tsx
import type { Metadata } from "next"
import type { ReactNode } from "react"

import { GlobalMascot } from "@/components/GlobalMascot"
import { Toaster } from "@/components/ui/sonner"

import "../styles/globals.css"

export const metadata: Metadata = {
  title: "智学工坊",
  description: "基于自进化学习智能体与 LLM Wiki 的个性化学习空间"
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link href="/fonts/material-symbols.css" rel="stylesheet" />
      </head>
      <body>
        {children}
        <GlobalMascot />
        <Toaster />
      </body>
    </html>
  )
}
```

如果担心登录页也显示桌宠，可在 `GlobalMascot` 内用 `usePathname()` 判断 `/`、`/login`、`/register` 直接返回 `null`。

---

## 16. 全局 CSS

文件：

```text
frontend/styles/globals.css
```

追加：

```css
.zhixue-global-mascot {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 80;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  pointer-events: none;
}

.zhixue-global-mascot * { pointer-events: auto; }

.zhixue-global-mascot__avatar {
  position: relative;
  width: 92px;
  height: 92px;
  border: 0;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(24px);
  box-shadow: 0 24px 70px rgba(131, 84, 0, 0.14);
  cursor: pointer;
  overflow: visible;
  transition: transform 180ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 180ms cubic-bezier(0.4, 0, 0.2, 1);
}
.zhixue-global-mascot__avatar:hover { transform: translateY(-3px); box-shadow: 0 28px 80px rgba(131, 84, 0, 0.2); }
.zhixue-global-mascot__avatar img { width: 100%; height: 100%; object-fit: contain; transform: translateY(-4px); }

.zhixue-global-mascot__pulse {
  position: absolute;
  inset: 8px;
  border-radius: 24px;
  border: 2px solid rgba(249, 168, 38, 0.45);
  animation: zhixueMascotPulse 2s ease-in-out infinite;
}

@keyframes zhixueMascotPulse {
  0%, 100% { transform: scale(0.98); opacity: 0.5; }
  50% { transform: scale(1.12); opacity: 0.16; }
}

.zhixue-global-mascot__panel {
  width: min(360px, calc(100vw - 140px));
  padding: 18px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: radial-gradient(circle at top left, rgba(249, 168, 38, 0.12), transparent 42%), rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(28px);
  box-shadow: 0 24px 80px rgba(131, 84, 0, 0.16);
}

.zhixue-global-mascot__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.zhixue-global-mascot__eyebrow { font-size: 12px; font-weight: 800; color: #835400; letter-spacing: 0.04em; }
.zhixue-global-mascot__title { margin-top: 2px; font-size: 18px; font-weight: 800; color: #1c1b1b; }
.zhixue-global-mascot__icon-button { width: 30px; height: 30px; border: 0; border-radius: 999px; background: rgba(255,255,255,0.72); color: #524434; display: grid; place-items: center; cursor: pointer; }
.zhixue-global-mascot__message { margin: 12px 0; color: #524434; font-size: 14px; line-height: 1.55; font-weight: 650; }
.zhixue-global-mascot__task { display: grid; gap: 10px; }
.zhixue-global-mascot__task-title { display: flex; align-items: center; gap: 8px; color: #1c1b1b; font-size: 13px; font-weight: 800; line-height: 1.4; }
.zhixue-global-mascot__task-title span { display: -webkit-box; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.zhixue-global-mascot__progress { height: 8px; overflow: hidden; border-radius: 999px; background: rgba(240, 237, 237, 0.8); }
.zhixue-global-mascot__progress div { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #835400, #f9a826); transition: width 360ms cubic-bezier(0.4, 0, 0.2, 1); }
.zhixue-global-mascot__meta { display: flex; flex-wrap: wrap; gap: 6px; }
.zhixue-global-mascot__meta span { padding: 4px 8px; border-radius: 999px; background: rgba(249, 168, 38, 0.12); color: #835400; font-size: 11px; font-weight: 800; }
.zhixue-global-mascot__actions { display: flex; gap: 8px; margin-top: 2px; }
.zhixue-global-mascot__primary, .zhixue-global-mascot__secondary { border: 0; border-radius: 14px; padding: 9px 12px; font-size: 13px; font-weight: 850; cursor: pointer; }
.zhixue-global-mascot__primary { background: #835400; color: #ffffff; box-shadow: 0 8px 20px rgba(131, 84, 0, 0.2); }
.zhixue-global-mascot__secondary { background: rgba(255,255,255,0.7); color: #835400; border: 1px solid rgba(131, 84, 0, 0.16); }
.zhixue-global-mascot__mini { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border: 1px solid rgba(255,255,255,0.72); border-radius: 999px; background: rgba(255,255,255,0.82); color: #835400; font-size: 12px; font-weight: 850; backdrop-filter: blur(20px); box-shadow: 0 12px 36px rgba(131, 84, 0, 0.12); cursor: pointer; }

@media (max-width: 768px) {
  .zhixue-global-mascot { right: 14px; bottom: 14px; align-items: flex-end; }
  .zhixue-global-mascot__avatar { width: 72px; height: 72px; border-radius: 22px; }
  .zhixue-global-mascot__panel { width: min(300px, calc(100vw - 104px)); padding: 14px; border-radius: 22px; }
  .zhixue-global-mascot__title { font-size: 16px; }
  .zhixue-global-mascot__message { font-size: 13px; }
}
```

---

## 17. Stitch 页面与父页面通信

### 17.1 扩展 zhixue-static-api.js：广播 Agent 任务

文件：

```text
frontend/public/stitch-pages/zhixue-static-api.js
```

在工具函数区新增：

```js
function broadcastMascotTask(task) {
  if (!task || !task.id) return;

  const payload = { type: "task-upsert", task };

  try {
    if ("BroadcastChannel" in window) {
      const channel = new BroadcastChannel("zhixue-agent-task-events");
      channel.postMessage(payload);
      channel.close();
    }
  } catch {}

  try {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(payload, window.location.origin);
    }
  } catch {}
}

function normalizeMascotAgentTask(task) {
  if (!task) return null;

  const planJson = task.plan_json || {};
  const artifacts = Array.isArray(planJson.artifact_refs) ? planJson.artifact_refs : [];
  const citations = Array.isArray(planJson.citations) ? planJson.citations : [];

  const query = new URLSearchParams();
  if (task.course_id) query.set("course_id", task.course_id);
  if (task.conversation_id) query.set("conversation_id", task.conversation_id);
  query.set("task_id", task.id);

  return {
    id: task.id,
    kind: "agent_task",
    courseId: task.course_id,
    conversationId: task.conversation_id,
    title: task.task_goal || "学习任务",
    goal: task.task_goal || "",
    status: task.status || "queued",
    riskLevel: task.risk_level || "low",
    stage: planJson.decision_summary || "",
    targetUrl: `/assistant?${query.toString()}`,
    createdAt: task.created_at,
    updatedAt: task.updated_at,
    lastEventAt: task.last_event_at,
    artifactCount: artifacts.length,
    citationCount: citations.length,
  };
}
```

在 `window.ZhixueStatic = { ... }` 导出区域补充：

```js
broadcastMascotTask,
normalizeMascotAgentTask,
```

---

### 17.2 修改 assistant.html：创建任务后通知桌宠

文件：

```text
frontend/public/stitch-pages/assistant.html
```

找到：

```js
async function sendDynamicAgentMessage(userInput) {
  const conversationId = await ensureAgentConversation();
  const accepted = await api.sendAgentConversationMessage(conversationId, userInput);
  const wrapper = appendDynamicAgentTaskCard(accepted.task);
  void watchDynamicAgentTask(wrapper);
  api.toast("目标已交给 MiMo Supervisor，Agent 正在后台自动执行。", "success");
}
```

修改为：

```js
async function sendDynamicAgentMessage(userInput) {
  const conversationId = await ensureAgentConversation();
  const accepted = await api.sendAgentConversationMessage(conversationId, userInput);

  if (api.normalizeMascotAgentTask && api.broadcastMascotTask) {
    const mascotTask = api.normalizeMascotAgentTask(accepted.task);
    if (mascotTask) api.broadcastMascotTask(mascotTask);
  }

  const wrapper = appendDynamicAgentTaskCard(accepted.task);
  void watchDynamicAgentTask(wrapper);
  api.toast("目标已交给 MiMo Supervisor，网页学习伙伴会提醒你生成进度。", "success");
}
```

在 `watchDynamicAgentTask` 的 SSE 回调里同步更新桌宠：

```js
onEvent: async (eventType, data) => {
  if (eventType !== "heartbeat") {
    wrapper.__agentEvents.push({ type: eventType, data });
  }

  const task = await refreshDynamicAgentTaskCard(wrapper);

  if (api.normalizeMascotAgentTask && api.broadcastMascotTask && task) {
    const mascotTask = api.normalizeMascotAgentTask(task);
    if (mascotTask) {
      const progressByEvent = {
        queued: 8,
        planning: 16,
        plan_created: 24,
        tool_started: 42,
        tool_completed: 58,
        observation: 66,
        replanned: 72,
        reviewed: 84,
        memory_reflected: 92,
        completed: 100,
        failed: 100,
      };
      mascotTask.progress = progressByEvent[eventType] || mascotTask.progress;
      mascotTask.stage = data?.message || data?.summary || mascotTask.stage;
      api.broadcastMascotTask(mascotTask);
    }
  }

  if (eventType === "completed" && !wrapper.__answerRendered) {
    wrapper.__answerRendered = true;
    appendAiMessage({
      answer: data.final_answer,
      citations: data.citations || task.plan_json?.citations || [],
      provider: "xiaomi_mimo",
      model: "mimo-v2.5",
      agent_run_id: task.id,
    });
  }
}
```

---

## 18. 与 V2 多模态 media_jobs 对接

如果 V2 已实现：

```text
media_jobs
media_assets
generate_educational_image
generate_lesson_video
generate_interactive_courseware
```

建议每个多模态 Job 在进度变化时发布同样的 BroadcastChannel 消息：

```js
api.broadcastMascotTask({
  id: job.id,
  kind: "media_job",
  courseId: job.course_id,
  title: job.title || "多模态资源生成",
  status: job.status,
  progress: job.progress,
  stage: job.stage,
  targetUrl: `/assistant?media_job_id=${job.id}`,
});
```

后端 `media_jobs` 的状态建议统一成：

```text
pending
running
succeeded
failed
cancelled
```

---

## 19. 资产同步脚本

文件：

```text
scripts/sync_ip_pet_assets.ps1
```

代码：

```powershell
param(
  [string]$SourceRoot = "docs/ip-assets/hyperframes-pet-preview/assets/pets",
  [string]$TargetRoot = "frontend/public/pets"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $SourceRoot)) {
  Write-Host "Source pet asset folder not found: $SourceRoot" -ForegroundColor Yellow
  Write-Host "Skip pet asset sync. GlobalMascot will fallback to stickers."
  exit 0
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

$mascots = @("zhizhi", "lulu", "diandian")
$states = @("idle", "remind", "focus", "done")

foreach ($mascot in $mascots) {
  $sourceMascotDir = Join-Path $SourceRoot $mascot
  $targetMascotDir = Join-Path $TargetRoot $mascot

  New-Item -ItemType Directory -Force -Path $targetMascotDir | Out-Null

  foreach ($state in $states) {
    $source = Join-Path $sourceMascotDir "$state.png"
    $target = Join-Path $targetMascotDir "$state.png"

    if (Test-Path $source) {
      Copy-Item $source $target -Force
      Write-Host "Copied $source -> $target"
    } else {
      Write-Host "Missing $source, fallback sticker will be used." -ForegroundColor Yellow
    }
  }
}

Write-Host "IP pet assets synced."
```
