"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { getWikiGraph } from "@/services/wikiService"

interface GraphNode {
  id: string
  title: string
  summary: string | null
  current_version: number
}

interface GraphLink {
  id: string
  source_page_id: string
  target_page_id: string
  relation_type: string
}

const relationLabels: Record<string, { label: string; color: string }> = {
  related: { label: "相关", color: "bg-primary/10 text-primary" },
  prerequisite: { label: "前置", color: "bg-secondary/10 text-secondary" },
  extends: { label: "扩展", color: "bg-tertiary/10 text-tertiary" },
}

export default function WikiGraphPage() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [links, setLinks] = useState<GraphLink[]>([])
  const [loading, setLoading] = useState(true)

  const courseId = "00000000-0000-0000-0000-000000000001"

  useEffect(() => {
    loadGraph()
  }, [])

  const loadGraph = async () => {
    try {
      setLoading(true)
      const data = await getWikiGraph(courseId)
      setNodes(data.nodes)
      setLinks(data.links)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  // Group links by source
  const linksBySource = new Map<string, GraphLink[]>()
  for (const link of links) {
    const arr = linksBySource.get(link.source_page_id) || []
    arr.push(link)
    linksBySource.set(link.source_page_id, arr)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-on-surface-variant">
        <span className="material-symbols-outlined text-[24px] animate-spin mr-2">
          sync
        </span>
        <span className="font-body-md">加载知识图谱...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <Link
            href="/student/wiki"
            className="text-on-surface-variant hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined">arrow_back</span>
          </Link>
          <h1 className="font-headline-md text-headline-md text-on-surface">
            知识图谱
          </h1>
        </div>
        <p className="font-body-md text-body-md text-on-surface-variant">
          {nodes.length} 个知识点 · {links.length} 条关系
        </p>
      </div>

      {nodes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <span className="material-symbols-outlined text-6xl text-outline/30 mb-4">
            hub
          </span>
          <p className="font-headline-sm text-on-surface-variant mb-2">
            暂无知识图谱数据
          </p>
          <p className="font-body-md text-on-surface-variant/60">
            请先从资料生成 Wiki 页面
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {nodes.map((node) => {
            const nodeLinks = linksBySource.get(node.id) || []
            const incomingLinks = links.filter(
              (l) => l.target_page_id === node.id
            )

            return (
              <div
                key={node.id}
                className="glass-card p-5 flex flex-col gap-3"
              >
                {/* Node header */}
                <Link
                  href={`/student/wiki/${node.id}`}
                  className="font-headline-sm text-headline-sm text-on-surface hover:text-primary transition-colors"
                >
                  {node.title}
                </Link>
                {node.summary && (
                  <p className="font-body-md text-sm text-on-surface-variant line-clamp-2">
                    {node.summary}
                  </p>
                )}

                {/* Outgoing links */}
                {nodeLinks.length > 0 && (
                  <div className="pt-2 border-t border-outline-variant/20">
                    <p className="font-label-sm text-label-sm text-on-surface-variant mb-2">
                      指向 ({nodeLinks.length})
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {nodeLinks.map((link) => {
                        const target = nodeMap.get(link.target_page_id)
                        const meta = relationLabels[link.relation_type] || {
                          label: link.relation_type,
                          color: "bg-surface-container text-on-surface-variant",
                        }
                        return (
                          <Link
                            key={link.id}
                            href={`/student/wiki/${link.target_page_id}`}
                            className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-container-low/60 hover:bg-surface-container transition-colors"
                          >
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-label-sm ${meta.color}`}
                            >
                              {meta.label}
                            </span>
                            <span className="font-body-md text-xs text-on-surface truncate max-w-[120px]">
                              {target?.title || "未知"}
                            </span>
                          </Link>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Incoming links */}
                {incomingLinks.length > 0 && (
                  <div className="pt-2 border-t border-outline-variant/20">
                    <p className="font-label-sm text-label-sm text-on-surface-variant mb-2">
                      被引用 ({incomingLinks.length})
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {incomingLinks.map((link) => {
                        const source = nodeMap.get(link.source_page_id)
                        const meta = relationLabels[link.relation_type] || {
                          label: link.relation_type,
                          color: "bg-surface-container text-on-surface-variant",
                        }
                        return (
                          <Link
                            key={link.id}
                            href={`/student/wiki/${link.source_page_id}`}
                            className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-surface-container-low/60 hover:bg-surface-container transition-colors"
                          >
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-label-sm ${meta.color}`}
                            >
                              {meta.label}
                            </span>
                            <span className="font-body-md text-xs text-on-surface truncate max-w-[120px]">
                              {source?.title || "未知"}
                            </span>
                          </Link>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* No links */}
                {nodeLinks.length === 0 && incomingLinks.length === 0 && (
                  <p className="font-body-md text-xs text-on-surface-variant/40 pt-2 border-t border-outline-variant/20">
                    暂无关联关系
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
