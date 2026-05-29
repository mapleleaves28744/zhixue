(function () {
  const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
  const ACCESS_TOKEN_KEY = "access_token";
  const REFRESH_TOKEN_KEY = "refresh_token";
  const AUTH_USER_KEY = "auth_user";
  const AUTH_ROLE_KEY = "auth_role";

  function getApiBaseUrl() {
    const queryBase = getParentSearchParams().get("api_base") || new URLSearchParams(window.location.search).get("api_base");
    if (queryBase) {
      return queryBase;
    }
    return window.localStorage.getItem("zhixue_api_base") || DEFAULT_API_BASE_URL;
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

  function logout() {
    clearAuthSession();
    navigate("/login");
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
        navigate(`/login?redirect=${encodeURIComponent(getParentSearchParams().toString() ? `${window.parent.location.pathname}?${getParentSearchParams()}` : "/courses")}`);
      }
      throw new Error(detailText || (payload && payload.message) || "请求失败，请稍后重试");
    }
    return payload.data;
  }

  function toast(message, type = "info") {
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

  async function listMaterials(courseId, params = {}) {
    const query = new URLSearchParams({
      course_id: courseId,
      page: String(params.page || 1),
      page_size: String(params.pageSize || 20),
    });
    return request(`/materials?${query}`);
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

  async function resolveCourseId() {
    const courseId = getCourseIdFromUrl();
    if (courseId) {
      return courseId;
    }
    const page = await listCourses({ pageSize: 1 });
    const firstCourse = page.items && page.items[0];
    if (!firstCourse) {
      throw new Error("请先创建课程，再继续操作");
    }
    return firstCourse.id;
  }

  window.ZhixueStatic = {
    formatDate,
    formatSize,
    chatWithTutor,
    streamTutorChat,
    createCourse,
    createWikiPage,
    generateResource,
    getCourse,
    getMe,
    getMastery,
    getCourseIdFromUrl,
    getParentSearchParams,
    getToken,
    logout,
    listCourses,
    listAgentRuns,
    listDiagnosisReports,
    listLearningRecords,
    listMaterials,
    listMistakes,
    listQuizzes,
    listRecommendations,
    listResources,
    listWikiPages,
    navigate,
    request,
    resolveCourseId,
    refreshRecommendations,
    saveResourceToWiki,
    saveTutorAnswerToWiki,
    submitTutorFeedback,
    toast,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountLogoutButton, { once: true });
  } else {
    mountLogoutButton();
  }
})();
