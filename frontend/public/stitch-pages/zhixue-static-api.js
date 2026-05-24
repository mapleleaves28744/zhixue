(function () {
  const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
  const ACCESS_TOKEN_KEY = "access_token";

  function getApiBaseUrl() {
    return window.localStorage.getItem("zhixue_api_base") || DEFAULT_API_BASE_URL;
  }

  function getToken() {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
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
    generateResource,
    getMe,
    getCourseIdFromUrl,
    getParentSearchParams,
    getToken,
    listCourses,
    listResources,
    listWikiPages,
    navigate,
    request,
    resolveCourseId,
    saveResourceToWiki,
    toast,
  };
})();
