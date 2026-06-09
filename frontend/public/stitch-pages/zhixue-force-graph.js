/**
 * Obsidian 式 D3 力导向知识图谱（zhixue-force-graph.js）
 * 依赖：window.d3（v7+）
 */
(function () {
  function masteryColor(score) {
    const s = Math.max(0, Math.min(1, Number(score) || 0));
    if (s >= 0.75) return "#835400";
    if (s >= 0.45) return "#b8860b";
    if (s >= 0.2) return "#c97b5a";
    return "#9e6b6b";
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

  function normalizeGraph(raw) {
    const nodes = (raw.nodes || []).map((n) => ({
      id: String(n.id),
      title: n.title || n.name || "未命名",
      summary: n.summary || "",
      mastery_score: Number(n.mastery_score || 0),
      scope: n.scope || "personal",
      page_type: n.page_type || "wiki",
      knowledge_id: n.knowledge_id || null,
      current_version: n.current_version || 0,
    }));
    const links = (raw.links || []).map((l) => ({
      id: String(l.id || `${l.source}-${l.target}`),
      source: String(l.source || l.source_page_id),
      target: String(l.target || l.target_page_id),
      relation_type: l.relation_type || "related",
      line_style: l.line_style || (l.scope === "public" ? "dashed" : "solid"),
      scope: l.scope || "personal",
    }));
    return { nodes, links };
  }

  function render(container, options) {
    if (!container || !window.d3) {
      console.warn("ZhixueForceGraph: container or d3 missing");
      return { destroy: function () {} };
    }

    const opts = options || {};
    const graph = normalizeGraph(opts.graph || {});
    const compact = Boolean(opts.compact);
    const height = opts.height || (compact ? 260 : 480);
    const onNodeClick = typeof opts.onNodeClick === "function" ? opts.onNodeClick : null;

    container.innerHTML = "";
    container.style.position = "relative";
    container.style.width = "100%";
    container.style.minHeight = `${height}px`;

    if (!graph.nodes.length) {
      container.innerHTML = `<div class="flex items-center justify-center h-full text-xs text-on-surface-variant py-10">暂无图谱节点</div>`;
      return { destroy: function () { container.innerHTML = ""; } };
    }

    const width = container.clientWidth || 640;
    const svg = window.d3
      .select(container)
      .append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .attr("class", "zhixue-force-graph-svg");

    const root = svg.append("g");
    const zoom = window.d3
      .zoom()
      .scaleExtent(compact ? [0.6, 2.5] : [0.35, 3])
      .on("zoom", (event) => root.attr("transform", event.transform));
    svg.call(zoom);

    const nodeRadius = compact ? 10 : 16;
    const nodes = graph.nodes.map((n) => ({ ...n }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links = graph.links
      .filter((l) => nodeById.has(l.source) && nodeById.has(l.target))
      .map((l) => ({ ...l }));

    const simulation = window.d3
      .forceSimulation(nodes)
      .force(
        "link",
        window.d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(compact ? 56 : 92)
          .strength(0.55),
      )
      .force("charge", window.d3.forceManyBody().strength(compact ? -140 : -320))
      .force("center", window.d3.forceCenter(width / 2, height / 2))
      .force("collide", window.d3.forceCollide(compact ? 18 : 28));

    const link = root
      .append("g")
      .attr("stroke-opacity", 0.75)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => (d.line_style === "dashed" ? "#b8a88a" : "#835400"))
      .attr("stroke-width", compact ? 1.2 : 1.8)
      .attr("stroke-dasharray", (d) => (d.line_style === "dashed" ? "4 4" : null));

    const nodeGroup = root
      .append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
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
      .attr("r", nodeRadius)
      .attr("fill", (d) => masteryColor(d.mastery_score))
      .attr("stroke", (d) => (d.scope === "public_neighbor" ? "#d4c4a8" : "#fff"))
      .attr("stroke-width", compact ? 1.5 : 2.2)
      .attr("opacity", (d) => (d.scope === "public_neighbor" ? 0.82 : 1));

    if (!compact) {
      nodeGroup
        .append("text")
        .text((d) => d.title)
        .attr("x", nodeRadius + 4)
        .attr("y", 4)
        .attr("font-size", 11)
        .attr("fill", "#3b3228")
        .each(function () {
          const self = window.d3.select(this);
          const text = self.text();
          if (text.length > 14) self.text(`${text.slice(0, 14)}…`);
        });
    }

    nodeGroup.on("click", (_, d) => {
      if (onNodeClick) onNodeClick(d);
    });

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      nodeGroup.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    if (opts.legend !== false && !compact) {
      const legend = document.createElement("div");
      legend.className = "absolute bottom-3 left-3 flex flex-wrap gap-2 text-[10px] text-on-surface-variant bg-white/80 rounded-lg px-2 py-1 border border-primary/10";
      legend.innerHTML = `
        <span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#835400"></i> 掌握 ≥75%</span>
        <span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#b8860b"></i> 45–75%</span>
        <span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#c97b5a"></i> 20–45%</span>
        <span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#9e6b6b"></i> &lt;20%</span>
        <span>— 个人边</span>
        <span style="border-bottom:1px dashed #b8a88a">公有邻居</span>`;
      container.appendChild(legend);
    }

    return {
      destroy() {
        simulation.stop();
        container.innerHTML = "";
      },
      escapeHtml,
    };
  }

  window.ZhixueForceGraph = {
    render,
    masteryColor,
    normalizeGraph,
    escapeHtml,
  };
})();
