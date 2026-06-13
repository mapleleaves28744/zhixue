(function () {
  const STICKER_SCENES = {
    empty: "05_sleepy_idle",
    thinking: "02_thinking",
    searching: "08_searching",
    success: "12_completed",
    updated: "09_updated",
    reminder: "07_reminder",
    unsure: "11_unsure",
    greeting: "01_happy_greeting",
    encouraging: "06_encouraging",
  };

  const PAGE_MASCOT_MAP = {
    "/": null,
    "/home": "zhizhi",
    "/courses": null,
    "/knowledge": "zhizhi",
    "/assistant": "zhizhi",
    "/practice": "diandian",
    "/dashboard": "lulu",
    "/path-profile": "lulu",
  };

  const DEFAULT_REVEAL_SELECTORS = [
    "main > section",
    "main > .grid",
    "main > .glass-shell",
    "main .glass-card",
    "main .glass-panel",
    "[data-reveal]",
  ];

  const skeletonRegistry = new WeakMap();
  let revealObserver = null;
  let revealMutationObserver = null;

  function ensureToastHost() {
    let host = document.getElementById("zhixue-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "zhixue-toast-host";
      host.className = "zhixue-toast-host";
      document.body.appendChild(host);
    }
    return host;
  }

  function getPagePath() {
    try {
      if (window.parent && window.parent !== window && window.parent.location) {
        return window.parent.location.pathname;
      }
    } catch {
      // ignore cross-origin
    }
    return window.location.pathname.replace(/\/stitch-pages\/[^/]+\.html$/, "") || "/";
  }

  function getPageMascot() {
    const path = getPagePath();
    if (PAGE_MASCOT_MAP[path] !== undefined) {
      return PAGE_MASCOT_MAP[path];
    }
    const page = document.body.dataset.zhixueMascot;
    return page || null;
  }

  function stickerUrl(mascot, scene) {
    const file = STICKER_SCENES[scene] || scene;
    if (!mascot) {
      return `/stickers/zhizhi/${file}.png`;
    }
    return `/stickers/${mascot}/${file}.png`;
  }

  function showSkeleton(container, options) {
    if (!container) {
      return;
    }
    const opts = options || {};
    const count = opts.lines || 3;
    const wrapper = document.createElement("div");
    wrapper.className = "zhixue-skeleton-wrap";
    wrapper.setAttribute("data-zhixue-skeleton", "true");
    wrapper.innerHTML = Array.from({ length: count })
      .map((_, index) => {
        const width = index === count - 1 ? "60%" : "100%";
        return `<div class="zhixue-skeleton" style="height:${opts.height || 14}px;width:${width};margin-bottom:10px;"></div>`;
      })
      .join("");
    skeletonRegistry.set(container, container.innerHTML);
    container.innerHTML = "";
    container.appendChild(wrapper);
  }

  function hideSkeleton(container) {
    if (!container) {
      return;
    }
    const original = skeletonRegistry.get(container);
    if (original !== undefined) {
      container.innerHTML = original;
      skeletonRegistry.delete(container);
      return;
    }
    const node = container.querySelector("[data-zhixue-skeleton]");
    if (node) {
      node.remove();
    }
  }

  function emptyState(options) {
    const opts = options || {};
    const mascot = opts.mascot || getPageMascot() || "zhizhi";
    const scene = opts.scene || "empty";
    const title = opts.title || "暂无内容";
    const description = opts.description || "";
    const actionLabel = opts.actionLabel || "";
    const actionHref = opts.actionHref || "";
    const actionOnClick = opts.actionOnClick;

    const root = document.createElement("div");
    root.className = "zhixue-empty-state glass-card";
    if (opts.compact) {
      root.classList.add("zhixue-empty-state--compact");
    }
    root.innerHTML = `
      <img class="zhixue-empty-state__img" src="${stickerUrl(mascot, scene)}" alt="${title}" loading="lazy"/>
      <div class="zhixue-empty-state__title">${title}</div>
      ${description ? `<p class="zhixue-empty-state__desc">${description}</p>` : ""}
      ${actionLabel ? `<button type="button" class="glass-button-primary px-6 py-3 font-label-md">${actionLabel}</button>` : ""}
    `;
    if (actionLabel) {
      const button = root.querySelector("button");
      if (typeof actionOnClick === "function") {
        button.addEventListener("click", actionOnClick);
      } else if (actionHref) {
        button.addEventListener("click", () => {
          if (window.parent && window.parent !== window) {
            window.parent.location.href = actionHref;
          } else {
            window.location.href = actionHref;
          }
        });
      }
    }
    return root;
  }

  function emptyStateHtml(options) {
    return emptyState(options).outerHTML;
  }

  function renderEmptyState(container, options) {
    if (!container) {
      return null;
    }
    const node = emptyState(options);
    container.innerHTML = "";
    container.appendChild(node);
    return node;
  }

  function toast(message, variant) {
    if (window.ZhixueStatic && typeof window.ZhixueStatic.toast === "function") {
      const mapped = variant === "warning" ? "info" : variant || "info";
      window.ZhixueStatic.toast(message, mapped);
      return;
    }
    const host = ensureToastHost();
    const node = document.createElement("div");
    node.className = `zhixue-toast zhixue-toast--${variant || "info"}`;
    node.textContent = message;
    host.appendChild(node);
    window.setTimeout(() => node.remove(), 3200);
  }

  function isElementNode(node) {
    return Boolean(node && node.nodeType === Node.ELEMENT_NODE);
  }

  function collectRevealTargets(selector) {
    const selectors = selector ? [selector] : DEFAULT_REVEAL_SELECTORS;
    const targets = new Set();
    selectors.forEach((item) => {
      document.querySelectorAll(item).forEach((node) => {
        if (!isElementNode(node)) {
          return;
        }
        if (node.closest(".zhixue-auth-modal, .zhixue-modal, [aria-modal='true']")) {
          return;
        }
        targets.add(node);
      });
    });
    return Array.from(targets);
  }

  function scrollReveal(selector) {
    const targets = collectRevealTargets(selector).filter((el) => !el.classList.contains("is-visible"));
    if (!targets.length) {
      return;
    }
    targets.forEach((el) => {
      el.classList.add("reveal-on-scroll");
    });
    if (!("IntersectionObserver" in window)) {
      targets.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    if (!revealObserver) {
      revealObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              revealObserver.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
      );
    }
    targets.forEach((el) => {
      if (isElementNode(el)) {
        revealObserver.observe(el);
      }
    });
  }

  function initScrollReveal() {
    scrollReveal();
  }

  function mascotBadge(mascot, label) {
    const root = document.createElement("span");
    root.className = "mascot-badge";
    root.innerHTML = `<img src="${stickerUrl(mascot, "greeting")}" alt=""/><span>${label}</span>`;
    return root;
  }

  function thinkingIndicator(mascot) {
    const root = document.createElement("div");
    root.className = "ai-thinking-indicator";
    root.innerHTML = `
      <img src="${stickerUrl(mascot || getPageMascot() || "zhizhi", "thinking")}" alt="思考中"/>
      <span class="text-sm text-on-surface-variant font-label-md">正在思考…</span>
    `;
    return root;
  }

  function sourceDisclaimer(text) {
    const root = document.createElement("div");
    root.className = "zhixue-source-disclaimer";
    root.innerHTML = `<span class="material-symbols-outlined text-base">info</span><span>${text || "AI 推断内容，建议核对资料。"}</span>`;
    return root;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildMarkdownTable(block) {
    const lines = block.trim().split(/\r?\n/).filter((line) => line.trim());
    if (!lines.length) return "";

    const parseCells = (line) =>
      line
        .split("|")
        .slice(1, -1)
        .map((cell) => escapeHtml(cell.trim()));

    const header = parseCells(lines[0]);
    let bodyLines = lines.slice(1);
    if (bodyLines[0] && /^\|[\s\-:|]+\|$/.test(bodyLines[0].trim())) {
      bodyLines = bodyLines.slice(1);
    }

    const headHtml = header
      .map((cell) => `<th class="px-3 py-2 text-left text-xs font-bold text-on-surface-variant border-b border-outline/20">${cell}</th>`)
      .join("");
    const bodyHtml = bodyLines
      .map((line) => {
        const cells = parseCells(line);
        return `<tr>${cells.map((cell) => `<td class="px-3 py-2 text-sm text-on-surface border-b border-outline/10 align-top">${cell}</td>`).join("")}</tr>`;
      })
      .join("");

    return `<div class="overflow-x-auto my-3"><table class="zhixue-md-table w-full min-w-[320px] border-collapse rounded-xl overflow-hidden bg-white/40"><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
  }

  function renderMarkdown(content) {
    const tables = [];
    const withTableTokens = String(content || "").replace(/(?:^\|[^\n]+\|\r?\n?)+/gm, (block) => {
      const token = `__ZHIXUE_TABLE_${tables.length}__`;
      tables.push(buildMarkdownTable(block));
      return `\n${token}\n`;
    });

    let html = escapeHtml(withTableTokens)
      .replace(/^#### (.*)$/gm, '<h4 class="font-bold text-sm text-on-surface mt-4 mb-2">$1</h4>')
      .replace(/^### (.*)$/gm, '<h4 class="font-bold text-primary mt-4 mb-2">$1</h4>')
      .replace(/^## (.*)$/gm, '<h3 class="font-headline-sm text-headline-sm text-on-surface mt-5 mb-2">$1</h3>')
      .replace(/^# (.*)$/gm, '<h2 class="font-headline-md text-headline-md text-on-surface mt-2 mb-3">$1</h2>')
      .replace(/^---$/gm, '<hr class="my-4 border-0 border-t border-outline/20" />')
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, '<code class="rounded bg-surface-container-high px-1 py-0.5 text-xs">$1</code>')
      .replace(/^\d+\.\s+(.*)$/gm, '<li class="ml-1 list-decimal text-sm text-on-surface-variant">$1</li>')
      .replace(/^- (.*)$/gm, '<li class="ml-1 list-disc text-sm text-on-surface-variant">$1</li>')
      .replace(/(<li class="ml-1 list-decimal[^"]*"[^>]*>[\s\S]*?<\/li>(?:\n|<br\/>)*)+/g, (block) => `<ol class="my-2 space-y-1 pl-5">${block}</ol>`)
      .replace(/(<li class="ml-1 list-disc[^"]*"[^>]*>[\s\S]*?<\/li>(?:\n|<br\/>)*)+/g, (block) => `<ul class="my-2 space-y-1 pl-5">${block}</ul>`)
      .replace(/\n/g, "<br/>");

    tables.forEach((tableHtml, index) => {
      html = html.replace(`__ZHIXUE_TABLE_${index}__`, tableHtml);
    });

    return html;
  }

  function initPage() {
    initScrollReveal();
    const mascot = getPageMascot();
    if (mascot) {
      document.body.dataset.zhixueMascot = mascot;
    }
  }

  window.ZhixueUI = {
    STICKER_SCENES,
    PAGE_MASCOT_MAP,
    DEFAULT_REVEAL_SELECTORS,
    emptyState,
    emptyStateHtml,
    renderEmptyState,
    getPageMascot,
    getPagePath,
    hideSkeleton,
    mascotBadge,
    initScrollReveal,
    scrollReveal,
    showSkeleton,
    sourceDisclaimer,
    renderMarkdown,
    stickerUrl,
    thinkingIndicator,
    toast,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPage, { once: true });
  } else {
    initPage();
  }
})();
