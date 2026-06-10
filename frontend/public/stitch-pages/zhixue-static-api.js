(function () {
  const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
  const ACCESS_TOKEN_KEY = "access_token";
  const REFRESH_TOKEN_KEY = "refresh_token";
  const AUTH_USER_KEY = "auth_user";
  const AUTH_ROLE_KEY = "auth_role";

  function getApiBaseUrl() {
    const queryBase = getParentSearchParams().get("api_base") || new URLSearchParams(window.location.search).get("api_base");
    if (queryBase) {
      window.localStorage.setItem("zhixue_api_base", queryBase);
      return queryBase;
    }
    const stored = window.localStorage.getItem("zhixue_api_base");
    const host = window.location.hostname;
    if (stored) {
      const pointsToLocal = stored.includes("localhost") || stored.includes("127.0.0.1");
      if (!(host !== "localhost" && host !== "127.0.0.1" && pointsToLocal)) {
        return stored;
      }
      window.localStorage.removeItem("zhixue_api_base");
    }
    if (host && host !== "localhost" && host !== "127.0.0.1") {
      return `${window.location.origin}/api/v1`;
    }
    return DEFAULT_API_BASE_URL;
  }

  function getToken() {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  function deleteCookie(name) {
    document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
  }

  function clearAuthSession() {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    window.localStorage.removeItem(AUTH_USER_KEY);
    window.localStorage.removeItem(AUTH_ROLE_KEY);
    deleteCookie(ACCESS_TOKEN_KEY);
    deleteCookie(AUTH_ROLE_KEY);
  }

  function getParentSearchParams() {
    try {
      if (window.parent && window.parent.location) {
        return new URLSearchParams(window.parent.location.search);
      }
    } catch {
      // Cross-origin parent access is not expected locally, but keep iframe pages resilient.
    }
    return new URLSearchParams(window.location.search);
  }

  function navigate(path) {
    if (window.parent && window.parent !== window) {
      window.parent.location.href = path;
      return;
    }
    window.location.href = path;
  }

  function getCurrentRouteForRedirect() {
    try {
      if (window.parent && window.parent.location) {
        return `${window.parent.location.pathname}${window.parent.location.search || ""}`;
      }
    } catch {
      // Keep iframe pages resilient if parent access is unavailable.
    }
    return `${window.location.pathname}${window.location.search || ""}`;
  }

  function logout() {
    clearAuthSession();
    navigate("/?auth=login");
  }

  function mountLogoutButton() {
    const sideNav = document.querySelector("nav.fixed.h-screen");
    if (!sideNav || document.getElementById("zhixue-static-logout")) {
      return;
    }
    const button = document.createElement("button");
    button.id = "zhixue-static-logout";
    button.type = "button";
    button.title = "退出登录";
    button.className = "mt-auto flex items-center justify-center w-12 h-12 text-outline hover:text-[#93000a] transition-all duration-200 scale-95 active:scale-90 rounded-2xl group hover:bg-[#ffdad6]/70";
    button.innerHTML = '<span class="material-symbols-outlined group-hover:scale-110 transition-transform">logout</span>';
    button.addEventListener("click", logout);
    sideNav.appendChild(button);
  }

  function getCourseIdFromUrl() {
    return getParentSearchParams().get("course_id") || new URLSearchParams(window.location.search).get("course_id");
  }

  function normalizeErrorDetail(detail) {
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }
          if (item && typeof item === "object" && "msg" in item) {
            return String(item.msg);
          }
          return null;
        })
        .filter(Boolean)
        .join("；");
    }
    return null;
  }

  async function request(path, options = {}) {
    const token = getToken();
    if (!token) {
      throw new Error("请先登录后再操作");
    }

    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (!(options.body instanceof FormData) && options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...options,
      headers,
      body: options.body instanceof FormData || options.body === undefined ? options.body : JSON.stringify(options.body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || payload.code !== 0) {
      const detailText = normalizeErrorDetail(payload && payload.detail);
      if (response.status === 401) {
        clearAuthSession();
        navigate(`/?auth=login&redirect=${encodeURIComponent(getCurrentRouteForRedirect() || "/courses")}`);
      }
      throw new Error(detailText || (payload && payload.message) || "请求失败，请稍后重试");
    }
    return payload.data;
  }

  function toast(message, type = "info") {
    if (window.ZhixueUI && typeof window.ZhixueUI.toast === "function" && !toast.__usingSharedUi) {
      try {
        toast.__usingSharedUi = true;
        window.ZhixueUI.toast(message, type);
        return;
      } finally {
        toast.__usingSharedUi = false;
      }
    }
    let node = document.getElementById("zhixue-static-toast");
    if (!node) {
      node = document.createElement("div");
      node.id = "zhixue-static-toast";
      node.className = "fixed right-6 top-6 z-[999] max-w-sm rounded-2xl border px-5 py-4 text-sm font-bold shadow-2xl backdrop-blur-xl transition-all";
      document.body.appendChild(node);
    }
    const variants = {
      error: "bg-[#ffdad6]/95 text-[#93000a] border-[#ffb4ab]",
      success: "bg-[#ffddb5]/95 text-[#2a1800] border-[#f9a826]",
      info: "bg-white/90 text-[#524434] border-white",
    };
    node.className = `fixed right-6 top-6 z-[999] max-w-sm rounded-2xl border px-5 py-4 text-sm font-bold shadow-2xl backdrop-blur-xl transition-all ${variants[type] || variants.info}`;
    node.textContent = message;
    window.clearTimeout(node.__zhixueTimer);
    node.__zhixueTimer = window.setTimeout(() => {
      node.remove();
    }, 3200);
  }

  function formatSize(bytes) {
    if (!Number.isFinite(bytes)) {
      return "0 KB";
    }
    if (bytes < 1024 * 1024) {
      return `${Math.max(bytes / 1024, 0.1).toFixed(1)} KB`;
    }
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }

  function formatDate(value) {
    if (!value) {
      return "刚刚";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "刚刚";
    }
    return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  }

  async function listCourses(params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 20),
      status: params.status || "active",
    });
    return request(`/courses?${query}`);
  }

  async function createCourse(payload) {
    return request("/courses", {
      method: "POST",
      body: payload,
    });
  }

  async function updateCourse(courseId, payload) {
    return request(`/courses/${courseId}`, {
      method: "PUT",
      body: payload,
    });
  }

  async function getCourse(courseId) {
    return request(`/courses/${courseId}`);
  }

  async function getMe() {
    return request("/users/me");
  }

  async function listWikiPages(courseId, params = {}) {
    const query = new URLSearchParams({
      course_id: courseId,
      page: String(params.page || 1),
      page_size: String(params.pageSize || 20),
      status: params.status || "active",
    });
    return request(`/wiki/pages?${query}`);
  }

  async function getWikiGraph(courseId, params = {}) {
    const query = new URLSearchParams({
      course_id: courseId,
      view: params.view || "merged",
    });
    return request(`/wiki/graph?${query}`);
  }

  async function getWikiPage(pageId) {
    return request(`/wiki/pages/${pageId}`);
  }

  async function listWikiVersions(pageId) {
    return request(`/wiki/pages/${pageId}/versions`);
  }

  async function listMaterials(courseId, params = {}) {
    const query = new URLSearchParams({
      course_id: courseId,
      page: String(params.page || 1),
      page_size: String(params.pageSize || 20),
    });
    return request(`/materials?${query}`);
  }

  function materialDownloadUrl(materialId) {
    return `${getApiBaseUrl()}/materials/${materialId}/download`;
  }

  async function getMaterialParsedText(materialId) {
    return request(`/materials/${materialId}/parsed-text`);
  }

  async function listMaterialChunks(materialId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 20),
    });
    return request(`/materials/${materialId}/chunks?${query}`);
  }

  async function createWikiPage(payload) {
    return request("/wiki/pages", {
      method: "POST",
      body: payload,
    });
  }

  async function generateResource(payload) {
    return request("/resources/generate", {
      method: "POST",
      body: payload,
    });
  }

  async function getResource(resourceId) {
    return request(`/resources/${resourceId}`);
  }

  async function listResources(courseId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
      status: params.status || "active",
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    if (params.resourceType) {
      query.set("resource_type", params.resourceType);
    }
    return request(`/resources?${query}`);
  }

  async function saveResourceToWiki(resourceId, payload = {}) {
    return request(`/resources/${resourceId}/save-to-wiki`, {
      method: "POST",
      body: payload,
    });
  }

  async function listRecommendations(courseId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
      status: params.status || "pending",
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    return request(`/recommendations?${query}`);
  }

  async function listQuizzes(courseId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    return request(`/quizzes?${query}`);
  }

  async function listMistakes(courseId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    if (params.status !== undefined) {
      query.set("status", params.status);
    }
    return request(`/quizzes/mistakes?${query}`);
  }

  async function listDiagnosisReports(courseId, params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    return request(`/diagnosis/reports?${query}`);
  }

  async function getMastery(courseId) {
    const query = new URLSearchParams();
    if (courseId) {
      query.set("course_id", courseId);
    }
    return request(`/diagnosis/mastery?${query}`);
  }

  async function listLearningRecords(courseId, params = {}) {
    const query = new URLSearchParams({
      limit: String(params.limit || 10),
    });
    if (courseId) {
      query.set("course_id", courseId);
    }
    if (params.eventType) {
      query.set("event_type", params.eventType);
    }
    return request(`/learning-records?${query}`);
  }

  async function trackLearningEvents(events) {
    try {
      if (!Array.isArray(events) || !events.length) {
        return { recorded: 0 };
      }
      return await request("/learning-records/events/batch", {
        method: "POST",
        body: {
          events: events.map((event) => ({
            ...event,
            event_source: event.event_source || "stitch_frontend",
            event_payload: event.event_payload || {},
          })),
        },
      });
    } catch {
      return { recorded: 0, ignored: true };
    }
  }

  async function trackLearningEvent(event) {
    return trackLearningEvents([event]);
  }

  async function transcribeAudio(payload) {
    return request("/audio/transcribe", {
      method: "POST",
      body: payload,
    });
  }

  async function synthesizeSpeech(payload) {
    return request("/audio/synthesize", {
      method: "POST",
      body: payload,
    });
  }

  async function listAgentRuns(params = {}) {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      page_size: String(params.pageSize || 10),
    });
    if (params.taskType) {
      query.set("task_type", params.taskType);
    }
    if (params.status) {
      query.set("status", params.status);
    }
    return request(`/agents/runs?${query}`);
  }

  async function createAgentTask(payload) {
    return request("/agent-tasks/create", {
      method: "POST",
      body: payload,
    });
  }

  async function getAgentTask(taskId) {
    return request(`/agent-tasks/${taskId}`);
  }

  async function getAgentTaskSteps(taskId) {
    return request(`/agent-tasks/${taskId}/steps`);
  }

  async function confirmAgentTask(taskId) {
    return request(`/agent-tasks/${taskId}/confirm`, { method: "POST" });
  }

  async function runAgentTask(taskId) {
    return request(`/agent-tasks/${taskId}/run`, { method: "POST" });
  }

  async function cancelAgentTask(taskId) {
    return request(`/agent-tasks/${taskId}/cancel`, { method: "POST" });
  }

  async function createAgentConversation(payload) {
    return request("/agent/conversations", {
      method: "POST",
      body: payload,
    });
  }

  async function listAgentConversations() {
    return request("/agent/conversations");
  }

  async function listAgentConversationMessages(conversationId) {
    return request(`/agent/conversations/${conversationId}/messages`);
  }

  async function sendAgentConversationMessage(conversationId, content) {
    return request(`/agent/conversations/${conversationId}/messages`, {
      method: "POST",
      body: { content },
    });
  }

  async function getDynamicAgentTask(taskId) {
    return request(`/agent/tasks/${taskId}`);
  }

  async function resumeDynamicAgentTask(taskId, approved = true) {
    return request(`/agent/tasks/${taskId}/resume`, {
      method: "POST",
      body: { approved },
    });
  }

  async function cancelDynamicAgentTask(taskId) {
    return request(`/agent/tasks/${taskId}/cancel`, { method: "POST" });
  }

  async function requeueDynamicAgentTask(taskId) {
    return request(`/agent/tasks/${taskId}/requeue`, { method: "POST" });
  }

  async function ingestProfileDialogue(payload) {
    return request("/student/profile/dialogue-ingest", {
      method: "POST",
      body: payload,
    });
  }

  async function streamDynamicAgentTaskEvents(taskId, handlers = {}) {
    const token = getToken();
    if (!token) {
      throw new Error("请先登录后再操作");
    }
    const response = await fetch(`${getApiBaseUrl()}/agent/tasks/${taskId}/events`, {
      headers: {
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(normalizeErrorDetail(payload && payload.detail) || (payload && payload.message) || "Agent 事件流连接失败");
    }
    if (!response.body) {
      throw new Error("浏览器不支持 Agent 实时事件流");
    }

    handlers.onOpen?.();
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    function consumeEvent(rawEvent) {
      const lines = rawEvent.split("\n").map((line) => line.trimEnd());
      const eventName = (lines.find((line) => line.startsWith("event:")) || "event: message").slice(6).trim();
      const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart());
      if (!dataLines.length) {
        return;
      }
      const eventData = JSON.parse(dataLines.join("\n"));
      handlers.onEvent?.(eventName, eventData);
    }

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const eventText of events) {
        if (eventText.trim()) {
          consumeEvent(eventText);
        }
      }
      if (done) {
        break;
      }
    }
    if (buffer.trim()) {
      consumeEvent(buffer);
    }
    handlers.onClose?.();
  }

  async function refreshRecommendations(courseId) {
    const query = new URLSearchParams({ course_id: courseId });
    return request(`/recommendations/refresh?${query}`, { method: "POST" });
  }

  async function chatWithTutor(payload) {
    return request("/tutor/chat", {
      method: "POST",
      body: payload,
    });
  }

  async function streamTutorChat(payload, handlers = {}) {
    const token = getToken();
    if (!token) {
      throw new Error("请先登录后再操作");
    }

    const response = await fetch(`${getApiBaseUrl()}/tutor/chat`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ...payload, stream: true }),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      const detailText = normalizeErrorDetail(errorPayload && errorPayload.detail);
      throw new Error(detailText || (errorPayload && errorPayload.message) || "AI Tutor 请求失败");
    }
    if (!response.body) {
      const data = await chatWithTutor(payload);
      if (data.answer) {
        handlers.onDelta?.(data.answer);
      }
      handlers.onDone?.(data);
      return data;
    }

    handlers.onOpen?.();
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalPayload = null;

    function consumeEvent(rawEvent) {
      const lines = rawEvent.split("\n").map((line) => line.trimEnd());
      const eventName = (lines.find((line) => line.startsWith("event:")) || "event: message").slice(6).trim();
      const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart());
      if (!dataLines.length) {
        return;
      }
      const dataText = dataLines.join("\n");
      const eventData = JSON.parse(dataText);
      if (eventName === "delta") {
        handlers.onDelta?.(eventData.content || "");
      } else if (eventName === "done") {
        finalPayload = eventData;
        handlers.onDone?.(eventData);
      } else if (eventName === "progress") {
        handlers.onProgress?.(eventData);
      } else if (eventName === "error") {
        throw new Error(eventData.message || "AI Tutor 请求失败");
      }
    }

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const eventText of events) {
        if (eventText.trim()) {
          consumeEvent(eventText);
        }
      }
      if (done) {
        break;
      }
    }
    if (buffer.trim()) {
      consumeEvent(buffer);
    }
    return finalPayload;
  }

  async function saveTutorAnswerToWiki(messageId, payload) {
    return request(`/tutor/messages/${messageId}/save-to-wiki`, {
      method: "POST",
      body: payload,
    });
  }

  async function submitTutorFeedback(messageId, payload) {
    return request(`/tutor/messages/${messageId}/feedback`, {
      method: "POST",
      body: payload,
    });
  }

  const CURRENT_COURSE_KEY = "zhixue_current_course_id";

  async function pickCourseIdWithMostWiki(courses) {
    let bestCourse = courses[0];
    let bestWikiCount = -1;
    for (const course of courses) {
      try {
        const wikiPage = await listWikiPages(course.id, { pageSize: 1 });
        const wikiCount = Number(wikiPage.total ?? (wikiPage.items || []).length) || 0;
        if (wikiCount > bestWikiCount) {
          bestWikiCount = wikiCount;
          bestCourse = course;
        }
      } catch {
        // Keep scanning other courses when one course lookup fails.
      }
    }
    return bestCourse.id;
  }

  async function resolveCourseId() {
    const page = await listCourses({ pageSize: 50, status: "active" });
    const courses = page.items || [];
    if (!courses.length) {
      throw new Error("请先创建课程，再继续操作");
    }

    const urlCourseId = getCourseIdFromUrl();
    if (urlCourseId && courses.some((course) => course.id === urlCourseId)) {
      window.localStorage.setItem(CURRENT_COURSE_KEY, urlCourseId);
      return urlCourseId;
    }

    const storedCourseId = window.localStorage.getItem(CURRENT_COURSE_KEY);
    if (storedCourseId && courses.some((course) => course.id === storedCourseId)) {
      return storedCourseId;
    }

    const bestCourseId = await pickCourseIdWithMostWiki(courses);
    window.localStorage.setItem(CURRENT_COURSE_KEY, bestCourseId);
    return bestCourseId;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function getMediaAsset(assetId) {
    return request(`/media-assets/${assetId}`);
  }

  function mediaAssetFileUrl(assetId) {
    const base = getApiBaseUrl().replace(/\/$/, "");
    const url = `${base}/media-assets/${assetId}/file`;
    const token = getToken();
    if (!token) {
      return url;
    }
    return `${url}?access_token=${encodeURIComponent(token)}`;
  }

  function renderArtifactCard(artifact) {
    const type = artifact.subtype || artifact.type;
    const title = artifact.title || "学习产物";
    if (artifact.type === "media_job") {
      return `
        <div class="rounded-3xl border border-[#f3d7ad] bg-white/80 p-5 shadow-sm">
          <div class="text-sm text-[#8a5a00] font-bold">视频生成任务</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${escapeHtml(title)}</div>
          <div class="mt-3 h-2 rounded-full bg-[#f5e4c8] overflow-hidden">
            <div class="h-full bg-[#8a5a00]" style="width:${Number(artifact.progress || 0)}%"></div>
          </div>
          <div class="mt-2 text-xs text-[#7c6b58]">${escapeHtml(artifact.stage || artifact.status || "queued")}</div>
        </div>`;
    }
    if (artifact.type === "media_review") {
      const passed = artifact.passed === true;
      const risk = artifact.risk_level || "unknown";
      const tone = passed ? "border-green-200 bg-green-50/80" : risk === "high" ? "border-red-200 bg-red-50/80" : "border-amber-200 bg-amber-50/80";
      return `
        <div class="rounded-3xl border ${tone} p-5 shadow-sm">
          <div class="text-sm font-bold text-[#8a5a00]">多模态安全审核</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${passed ? "通过" : "需关注"} · 风险 ${escapeHtml(risk)}</div>
          <div class="mt-2 text-xs text-[#7c6b58]">asset ${escapeHtml(artifact.asset_id || "-")}</div>
        </div>`;
    }
    if (artifact.type === "media_asset" && type === "image") {
      const url = mediaAssetFileUrl(artifact.asset_id);
      return `
        <div class="rounded-3xl border border-[#f3d7ad] bg-white/80 p-5 shadow-sm">
          <div class="text-sm text-[#8a5a00] font-bold">教学插图</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${escapeHtml(title)}</div>
          <img class="mt-4 w-full rounded-2xl border border-[#f5e4c8]" src="${url}" alt="${escapeHtml(title)}" />
        </div>`;
    }
    if (artifact.type === "media_asset" && (type === "courseware" || type === "storyboard" || artifact.mime_type === "text/html")) {
      const url = mediaAssetFileUrl(artifact.asset_id);
      return `
        <div class="rounded-3xl border border-[#f3d7ad] bg-white/80 p-5 shadow-sm">
          <div class="text-sm text-[#8a5a00] font-bold">${type === "storyboard" ? "讲解分镜" : "互动课件"}</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${escapeHtml(title)}</div>
          <iframe class="mt-4 w-full h-[520px] rounded-2xl border border-[#f5e4c8] bg-white" src="${url}" sandbox="allow-scripts"></iframe>
        </div>`;
    }
    if (artifact.type === "media_asset" && (type === "audio" || String(artifact.mime_type || "").startsWith("audio/"))) {
      const url = mediaAssetFileUrl(artifact.asset_id);
      return `
        <div class="rounded-3xl border border-[#f3d7ad] bg-white/80 p-5 shadow-sm">
          <div class="text-sm text-[#8a5a00] font-bold">语音讲解</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${escapeHtml(title)}</div>
          <audio class="mt-4 w-full" src="${url}" controls preload="metadata"></audio>
        </div>`;
    }
    if (artifact.type === "media_asset" && (type === "video" || String(artifact.mime_type || "").startsWith("video/"))) {
      const url = mediaAssetFileUrl(artifact.asset_id);
      return `
        <div class="rounded-3xl border border-[#f3d7ad] bg-white/80 p-5 shadow-sm">
          <div class="text-sm text-[#8a5a00] font-bold">讲解视频</div>
          <div class="mt-1 text-lg font-black text-[#2b2118]">${escapeHtml(title)}</div>
          <video class="mt-4 w-full rounded-2xl border border-[#f5e4c8] bg-black" src="${url}" controls preload="metadata"></video>
        </div>`;
    }
    return `<pre class="rounded-2xl bg-white/80 p-4 text-xs overflow-auto">${escapeHtml(JSON.stringify(artifact, null, 2))}</pre>`;
  }

  function getPageMascot() {
    if (window.ZhixueUI && typeof window.ZhixueUI.getPageMascot === "function") {
      return window.ZhixueUI.getPageMascot();
    }
    return null;
  }

  window.ZhixueStatic = {
    formatDate,
    formatSize,
    chatWithTutor,
    cancelAgentTask,
    cancelDynamicAgentTask,
    requeueDynamicAgentTask,
    confirmAgentTask,
    streamTutorChat,
    streamDynamicAgentTaskEvents,
    createAgentConversation,
    createAgentTask,
    createCourse,
    createWikiPage,
    generateResource,
    getResource,
    getCourse,
    getAgentTask,
    getAgentTaskSteps,
    getDynamicAgentTask,
    getMediaAsset,
    getPageMascot,
    getWikiPage,
    getWikiGraph,
    mediaAssetFileUrl,
    renderArtifactCard,
    getMe,
    ingestProfileDialogue,
    getMastery,
    getCourseIdFromUrl,
    getParentSearchParams,
    getToken,
    logout,
    listCourses,
    listAgentRuns,
    listAgentConversations,
    listAgentConversationMessages,
    listDiagnosisReports,
    listLearningRecords,
    listMaterials,
    listMaterialChunks,
    getMaterialParsedText,
    materialDownloadUrl,
    listMistakes,
    listQuizzes,
    listRecommendations,
    listResources,
    listWikiVersions,
    listWikiPages,
    navigate,
    request,
    resolveCourseId,
    refreshRecommendations,
    resumeDynamicAgentTask,
    runAgentTask,
    sendAgentConversationMessage,
    saveResourceToWiki,
    saveTutorAnswerToWiki,
    submitTutorFeedback,
    toast,
    trackLearningEvent,
    trackLearningEvents,
    transcribeAudio,
    synthesizeSpeech,
    updateCourse,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountLogoutButton, { once: true });
  } else {
    mountLogoutButton();
  }
})();
