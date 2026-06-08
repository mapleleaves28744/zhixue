/** Reactor 流式渲染类型定义 */

/** SSE 事件类型 */
export type ReactorEventType =
  | "card_start"    // 新卡片开始
  | "card_update"   // 卡片内容更新
  | "card_end"      // 卡片完成
  | "delta"         // 增量文本
  | "done"          // 全部完成
  | "error"         // 错误

/** 单张卡片状态 */
export interface ReactorCard {
  id: string
  type: string           // card 类型: "text" | "quiz" | "resource" | "wiki"
  title: string
  content: string        // 累积内容（每次 update 替换）
  status: "streaming" | "complete" | "error"
  metadata?: Record<string, unknown>
}

/** SSE 事件载荷 */
export interface ReactorEvent {
  event: ReactorEventType
  data: {
    card_id?: string
    card_type?: string
    title?: string
    content?: string
    message?: string
    [key: string]: unknown
  }
}

/** Reactor 容器配置 */
export interface ReactorConfig {
  /** SSE 连接 URL */
  url: string
  /** 请求头（如 Authorization） */
  headers?: Record<string, string>
  /** 最大卡片数 */
  maxCards?: number
  /** 是否自动重连 */
  autoReconnect?: boolean
}
