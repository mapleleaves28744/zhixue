/**
 * Obsidian 式 D3 力导向知识图谱（zhixue-force-graph.js）
 * 依赖：window.d3（v7+）
 */
(function () {
  function masteryTier(score, confidence) {
    const s = Math.max(0, Math.min(1, Number(score) || 0));
    if (Number(confidence) < 0.4) {
      return { label: "待验证", color: "#64748b", min: 0 };
    }
    if (s >= 0.75) {
      return { label: "已掌握", color: "#16a34a", min: 0.75 };
    }
    if (s >= 0.45) {
      return { label: "熟练", color: "#2563eb", min: 0.45 };
    }
    if (s >= 0.2) {
      return { label: "学习中", color: "#ea580c", min: 0.2 };
    }
    return { label: "薄弱", color: "#dc2626", min: 0 };
  }

  function masteryColor(score) {
    return masteryTier(score).color;
  }

  function masteryRadius(score, compact) {
    const s = Math.max(0, Math.min(1, Number(score) || 0));
    const minR = compact ? 8 : 12;
    const maxR = compact ? 20 : 30;
    return minR + (maxR - minR) * Math.pow(s, 0.85);
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  function truncateLabel(text, maxLen) {
    const value = String(text || "未命名").trim() || "未命名";
    return value.length > maxLen ? `${value.slice(0, maxLen)}…` : value;
  }

  function measureWidth(container, fallbackWidth) {
    const rect = container.getBoundingClientRect();
    return Math.max(rect.width || 0, container.clientWidth || 0, container.offsetWidth || 0, fallbackWidth, 280);
  }

  function seedNodePositions(nodes, width, height) {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.34;
    nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1);
      node.x = cx + Math.cos(angle) * radius + (Math.random() - 0.5) * 24;
      node.y = cy + Math.sin(angle) * radius + (Math.random() - 0.5) * 24;
    });
  }

  function normalizeGraph(raw) {
    const nodes = (raw.nodes || []).map((n) => ({
      id: String(n.id),
      title: n.title || n.name || "未命名",
      summary: n.summary || "",
      mastery_score: Number(n.mastery_score || 0.5),
      mastery_confidence: Number(n.mastery_confidence || 0.2),
      scope: n.scope || "personal",
      page_type: n.page_type || "wiki",
      knowledge_id: n.knowledge_id || null,
      current_version: n.current_version || 0,
    }));
    const bidirectional = new Set(["similar", "confused_with", "related"]);
    const links = (raw.links || []).map((l) => {
      const relationType = l.relation_type || "related";
      const direction = l.direction || (bidirectional.has(relationType) ? "both" : "forward");
      return {
        id: String(l.id || `${l.source}-${l.target}`),
        source: String(l.source || l.source_page_id),
        target: String(l.target || l.target_page_id),
        relation_type: relationType,
        line_style: l.line_style || (l.scope === "public" ? "dashed" : "solid"),
        scope: l.scope || "personal",
        direction,
      };
    });
    return { nodes, links };
  }

  function mountGraph(container, options) {
    const opts = options || {};
    const graph = normalizeGraph(opts.graph || {});
    const compact = Boolean(opts.compact);
    const height = opts.height || (compact ? 260 : 480);
    const onNodeClick = typeof opts.onNodeClick === "function" ? opts.onNodeClick : null;
    const onNodeHover = typeof opts.onNodeHover === "function" ? opts.onNodeHover : null;
    const fallbackWidth = compact ? 480 : 640;

    container.innerHTML = "";
    container.style.position = "relative";
    container.style.width = "100%";
    container.style.minHeight = `${height}px`;
    container.style.overflow = "hidden";

    if (!graph.nodes.length) {
      container.innerHTML = `<div class="flex items-center justify-center h-full text-xs text-on-surface-variant py-10">暂无图谱节点</div>`;
      return { destroy() { container.innerHTML = ""; } };
    }

    let width = measureWidth(container, fallbackWidth);
    const svg = window.d3
      .select(container)
      .append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .attr("class", "zhixue-force-graph-svg");

    const defs = svg.append("defs");
    defs
      .append("marker")
      .attr("id", "zhixue-arrow-end")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "#835400");
    defs
      .append("marker")
      .attr("id", "zhixue-arrow-start")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 2)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M8,-4L0,0L8,4")
      .attr("fill", "#835400");

    const root = svg.append("g");
    const zoom = window.d3
      .zoom()
      .scaleExtent(compact ? [0.6, 2.5] : [0.35, 3])
      .on("zoom", (event) => root.attr("transform", event.transform));
    svg.call(zoom);

    const labelMaxLen = compact ? 8 : 14;
    const nodes = graph.nodes.map((n) => ({ ...n }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links = graph.links
      .filter((l) => nodeById.has(l.source) && nodeById.has(l.target))
      .map((l) => ({ ...l }));

    seedNodePositions(nodes, width, height);

    const simulation = window.d3
      .forceSimulation(nodes)
      .force(
        "link",
        window.d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(compact ? 72 : 110)
          .strength(0.65),
      )
      .force("charge", window.d3.forceManyBody().strength(compact ? -180 : -420))
      .force("center", window.d3.forceCenter(width / 2, height / 2))
      .force("collide", window.d3.forceCollide((d) => masteryRadius(d.mastery_score, compact) + (compact ? 6 : 10)))
      .force("x", window.d3.forceX(width / 2).strength(0.04))
      .force("y", window.d3.forceY(height / 2).strength(0.04));

    const link = root
      .append("g")
      .attr("stroke-opacity", 0.75)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => (d.line_style === "dashed" ? "#b8a88a" : "#835400"))
      .attr("stroke-width", compact ? 1.2 : 1.8)
      .attr("stroke-dasharray", (d) => (d.line_style === "dashed" ? "4 4" : null))
      .attr("marker-end", (d) => (d.direction === "forward" || d.direction === "both" ? "url(#zhixue-arrow-end)" : null))
      .attr("marker-start", (d) => (d.direction === "both" ? "url(#zhixue-arrow-start)" : null));

    const tooltip = document.createElement("div");
    tooltip.className = "zhixue-graph-tooltip pointer-events-none absolute z-20 max-w-[220px] rounded-lg border border-primary/15 bg-white/95 px-3 py-2 text-[11px] text-on-surface shadow-lg opacity-0 transition-opacity duration-150";
    tooltip.style.left = "0";
    tooltip.style.top = "0";
    container.appendChild(tooltip);

    function showTooltip(event, node) {
      const masteryPct = Math.round((Number(node.mastery_score) || 0) * 100);
      const tier = masteryTier(node.mastery_score, node.mastery_confidence);
      tooltip.innerHTML = `
        <p class="font-bold text-on-surface leading-snug">${escapeHtml(node.title)}</p>
        <p class="text-on-surface-variant mt-1">
          <span style="color:${tier.color};font-weight:700">${tier.label}</span>
          · 掌握度 ${masteryPct}%
        </p>`;
      tooltip.style.opacity = "1";
      moveTooltip(event);
      if (onNodeHover) onNodeHover(node);
    }

    function moveTooltip(event) {
      const bounds = container.getBoundingClientRect();
      const offsetX = Math.min(Math.max(event.clientX - bounds.left + 12, 8), bounds.width - 180);
      const offsetY = Math.min(Math.max(event.clientY - bounds.top + 12, 8), bounds.height - 64);
      tooltip.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    }

    function hideTooltip() {
      tooltip.style.opacity = "0";
      if (onNodeHover) onNodeHover(null);
    }

    const nodeGroup = root
      .append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "zhixue-graph-node")
      .attr("cursor", "pointer")
      .call(
        window.d3
          .drag()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.25).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            if (!opts.pinNodes) {
              d.fx = null;
              d.fy = null;
            }
          }),
      );

    nodeGroup
      .append("circle")
      .attr("r", (d) => masteryRadius(d.mastery_score, compact))
      .attr("fill", (d) => masteryColor(d.mastery_score))
      .attr("stroke", (d) => (d.scope === "public_neighbor" ? "#cbd5e1" : "#ffffff"))
      .attr("stroke-width", (d) => {
        const r = masteryRadius(d.mastery_score, compact);
        return compact ? Math.max(1.5, r * 0.12) : Math.max(2, r * 0.1);
      })
      .attr("opacity", (d) => (d.scope === "public_neighbor" ? 0.88 : 1));

    nodeGroup
      .append("text")
      .text((d) => truncateLabel(d.title, labelMaxLen))
      .attr("text-anchor", compact ? "middle" : "start")
      .attr("x", (d) => (compact ? 0 : masteryRadius(d.mastery_score, compact) + 6))
      .attr("y", (d) => (compact ? masteryRadius(d.mastery_score, compact) + 14 : 4))
      .attr("font-size", compact ? 9 : 11)
      .attr("fill", "#3b3228")
      .attr("pointer-events", "none");

    nodeGroup
      .on("click", (_, d) => {
        if (onNodeClick) onNodeClick(d);
      })
      .on("mouseenter", (event, d) => showTooltip(event, d))
      .on("mousemove", (event) => moveTooltip(event))
      .on("mouseleave", hideTooltip);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      nodeGroup.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);
    });

    function updateDimensions(nextWidth) {
      const measured = Math.max(nextWidth || measureWidth(container, fallbackWidth), 280);
      if (Math.abs(measured - width) < 2) return;
      width = measured;
      svg.attr("viewBox", [0, 0, width, height]);
      simulation.force("center", window.d3.forceCenter(width / 2, height / 2));
      simulation.force("x", window.d3.forceX(width / 2).strength(0.04));
      simulation.alpha(0.35).restart();
    }

    let resizeObserver = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        updateDimensions(entry.contentRect.width);
      });
      resizeObserver.observe(container);
    }

    if (opts.legend !== false && !compact) {
      const legend = document.createElement("div");
      legend.className = "absolute bottom-3 left-3 flex flex-wrap gap-2 text-[10px] text-on-surface-variant bg-white/80 rounded-lg px-2 py-1 border border-primary/10";
      legend.innerHTML = `
        <span><i style="display:inline-block;width:14px;height:14px;border-radius:50%;background:#16a34a;border:2px solid #fff"></i> 已掌握 ≥75%</span>
        <span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#2563eb;border:2px solid #fff"></i> 熟练 45–75%</span>
        <span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#ea580c;border:2px solid #fff"></i> 学习中 20–45%</span>
        <span><i style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#dc2626;border:2px solid #fff"></i> 薄弱 &lt;20%</span>
        <span class="opacity-80">圆越大 = 越熟练</span>
        <span>→ 先修/后继</span>
        <span>↔ 相似/易混</span>
        <span style="border-bottom:1px dashed #b8a88a">公有邻居</span>`;
      container.appendChild(legend);
    }

    simulation.alpha(1).restart();

    return {
      destroy() {
        simulation.stop();
        if (resizeObserver) resizeObserver.disconnect();
        container.innerHTML = "";
      },
      escapeHtml,
      relayout() {
        updateDimensions();
      },
    };
  }

  function render(container, options) {
    if (!container || !window.d3) {
      console.warn("ZhixueForceGraph: container or d3 missing");
      return { destroy() {} };
    }

    let instance = null;
    let cancelled = false;

    const start = () => {
      if (cancelled) return;
      instance = mountGraph(container, options);
    };

    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => requestAnimationFrame(start));
    } else {
      start();
    }

    return {
      destroy() {
        cancelled = true;
        if (instance?.destroy) instance.destroy();
        else container.innerHTML = "";
      },
      relayout() {
        instance?.relayout?.();
      },
      escapeHtml,
    };
  }

  window.ZhixueForceGraph = {
    render,
    masteryColor,
    masteryRadius,
    masteryTier,
    normalizeGraph,
    escapeHtml,
    truncateLabel,
  };
})();
