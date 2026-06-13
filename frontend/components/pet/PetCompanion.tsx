"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { usePathname } from "next/navigation"
import { getToken } from "@/lib/auth"
import {
  getPetFeed,
  getPetPreferences,
  markAllPetNotificationsRead,
  markPetNotificationRead,
  updatePetPreferences,
} from "@/services/petService"
import type { PetNotification, PetPreference } from "@/types/pet"

const POSITION_KEY = "zhixue_pet_position"
const HIDDEN_ROUTES = new Set(["/", "/login", "/register"])
const PET_SIZE = 96
const EDGE_GAP = 14

type Position = { x: number; y: number }

function defaultPosition(): Position {
  return {
    x: Math.max(EDGE_GAP, window.innerWidth - PET_SIZE - 28),
    y: Math.max(EDGE_GAP, window.innerHeight - PET_SIZE - 28),
  }
}

function clampPosition(position: Position): Position {
  return {
    x: Math.min(Math.max(EDGE_GAP, position.x), Math.max(EDGE_GAP, window.innerWidth - PET_SIZE - EDGE_GAP)),
    y: Math.min(Math.max(EDGE_GAP, position.y), Math.max(EDGE_GAP, window.innerHeight - PET_SIZE - EDGE_GAP)),
  }
}

function loadPosition(): Position {
  try {
    const value = localStorage.getItem(POSITION_KEY)
    return value ? clampPosition(JSON.parse(value) as Position) : defaultPosition()
  } catch {
    return defaultPosition()
  }
}

function activeConversationMatches(notification: PetNotification, pathname: string): boolean {
  if (pathname !== "/assistant" || notification.source_type !== "agent_task") return false
  const url = new URL(notification.action_url, window.location.origin)
  const courseId = url.searchParams.get("course_id")
  const conversationId = url.searchParams.get("conversation_id")
  if (!courseId || !conversationId) return false
  return localStorage.getItem(`zhixue_agent_conversation_id_${courseId}`) === conversationId
}

export function PetCompanion() {
  const pathname = usePathname()
  const [position, setPosition] = useState<Position | null>(null)
  const [items, setItems] = useState<PetNotification[]>([])
  const [preference, setPreference] = useState<PetPreference | null>(null)
  const [open, setOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [bubble, setBubble] = useState<PetNotification | null>(null)
  const [dragging, setDragging] = useState(false)
  const dragOffset = useRef<Position>({ x: 0, y: 0 })
  const moved = useRef(false)
  const previousUnread = useRef<Set<string>>(new Set())

  const visible = Boolean(getToken()) && !HIDDEN_ROUTES.has(pathname)

  const dismissBubble = useCallback(async () => {
    const current = bubble
    setBubble(null)
    if (!current) return
    await markPetNotificationRead(current.id).catch(() => undefined)
    setItems((all) => all.map((item) => (item.id === current.id ? { ...item, is_read: true } : item)))
  }, [bubble])

  const refresh = useCallback(async () => {
    if (!visible) return
    try {
      const feed = await getPetFeed()
      const unread = feed.items.filter((item) => !item.is_read)
      const active = unread.filter((item) => activeConversationMatches(item, pathname))
      if (active.length) {
        await Promise.all(active.map((item) => markPetNotificationRead(item.id).catch(() => undefined)))
      }
      const activeIds = new Set(active.map((item) => item.id))
      const normalized = feed.items.map((item) => (activeIds.has(item.id) ? { ...item, is_read: true } : item))
      const nextUnread = normalized.filter((item) => !item.is_read)
      const newlyUnread = nextUnread.find((item) => !previousUnread.current.has(item.id))
      previousUnread.current = new Set(nextUnread.map((item) => item.id))
      setItems(normalized)
      if (newlyUnread && !open) setBubble(newlyUnread)
    } catch {
      // The pet stays quiet when the backend is unavailable.
    }
  }, [open, pathname, visible])

  useEffect(() => {
    if (!visible) return
    setPosition(loadPosition())
    void refresh()
    void getPetPreferences().then(setPreference).catch(() => undefined)
    const timer = window.setInterval(() => void refresh(), 30_000)
    const onFocus = () => void refresh()
    window.addEventListener("focus", onFocus)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("focus", onFocus)
    }
  }, [refresh, visible])

  useEffect(() => {
    const onResize = () => {
      setPosition((current) => {
        if (!current) return current
        const next = clampPosition(current)
        localStorage.setItem(POSITION_KEY, JSON.stringify(next))
        return next
      })
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  useEffect(() => {
    if (!dragging) return
    const onMove = (event: PointerEvent) => {
      moved.current = true
      setPosition(clampPosition({ x: event.clientX - dragOffset.current.x, y: event.clientY - dragOffset.current.y }))
    }
    const onUp = () => {
      setDragging(false)
      setPosition((current) => {
        if (!current) return current
        localStorage.setItem(POSITION_KEY, JSON.stringify(current))
        return current
      })
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp, { once: true })
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [dragging])

  if (!visible || !position) return null

  const unreadCount = items.filter((item) => !item.is_read).length
  const panelOnLeft = position.x > window.innerWidth / 2
  const panelBelow = position.y < 420
  const mascot = bubble ? "/stickers/zhizhi/07_reminder.png" : "/stickers/zhizhi/05_sleepy_idle.png"

  const openNotification = async (item: PetNotification) => {
    if (!item.is_read) await markPetNotificationRead(item.id).catch(() => undefined)
    window.location.href = item.action_url
  }

  const savePreference = async (patch: Partial<PetPreference>) => {
    const updated = await updatePetPreferences(patch)
    setPreference(updated)
  }

  return (
    <div className="fixed z-[1000]" style={{ left: position.x, top: position.y }}>
      {bubble && !open && (
        <div
          className={`absolute w-64 rounded-2xl border border-white/80 bg-white/95 p-3 shadow-xl backdrop-blur-xl ${
            panelOnLeft ? "right-12" : "left-12"
          } ${
            panelBelow ? "top-[82px]" : "bottom-[82px]"
          }`}
        >
          <button className="absolute right-2 top-1 text-sm text-gray-400" onClick={() => void dismissBubble()}>×</button>
          <button className="w-full pr-4 text-left" onClick={() => void openNotification(bubble)}>
            <strong className="block text-sm text-gray-800">{bubble.title}</strong>
            <span className="mt-1 block text-xs leading-5 text-gray-500">{bubble.reason || "点击查看详情"}</span>
          </button>
        </div>
      )}

      {open && (
        <section
          className={`absolute w-[min(360px,calc(100vw-28px))] rounded-3xl border border-white/80 bg-white/95 p-4 shadow-2xl backdrop-blur-2xl ${
            panelOnLeft ? "right-0" : "left-0"
          } ${
            panelBelow ? "top-20" : "bottom-20"
          }`}
        >
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="font-bold text-gray-800">知知提醒箱</h2>
              <p className="text-xs text-gray-500">{unreadCount} 条未读提醒</p>
            </div>
            <div className="flex gap-2 text-xs">
              <button onClick={() => setSettingsOpen((value) => !value)} className="rounded-lg bg-amber-50 px-2 py-1 text-amber-800">设置</button>
              <button
                onClick={() => void markAllPetNotificationsRead().then(() => setItems((all) => all.map((item) => ({ ...item, is_read: true }))))}
                className="rounded-lg bg-gray-100 px-2 py-1 text-gray-600"
              >
                全部已读
              </button>
            </div>
          </div>

          {settingsOpen && preference && (
            <div className="mb-3 space-y-2 rounded-2xl bg-amber-50/70 p-3 text-xs text-gray-700">
              <label className="flex items-center justify-between">
                学习催促
                <input
                  type="checkbox"
                  checked={preference.study_reminders_enabled}
                  onChange={(event) => void savePreference({ study_reminders_enabled: event.target.checked })}
                />
              </label>
              <label className="flex items-center justify-between">
                提醒间隔
                <select
                  value={preference.interval_hours}
                  onChange={(event) => void savePreference({ interval_hours: Number(event.target.value) as 1 | 2 | 4 })}
                  className="rounded-lg border bg-white px-2 py-1"
                >
                  <option value={1}>1 小时</option>
                  <option value={2}>2 小时</option>
                  <option value={4}>4 小时</option>
                </select>
              </label>
              <div className="flex items-center justify-between gap-2">
                <span>免打扰</span>
                <input type="time" value={preference.quiet_start.slice(0, 5)} onChange={(e) => void savePreference({ quiet_start: e.target.value })} />
                <span>至</span>
                <input type="time" value={preference.quiet_end.slice(0, 5)} onChange={(e) => void savePreference({ quiet_end: e.target.value })} />
              </div>
            </div>
          )}

          <div className="max-h-[360px] space-y-2 overflow-y-auto">
            {!items.length && <p className="py-8 text-center text-sm text-gray-500">暂无提醒，知知先安静陪着你。</p>}
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => void openNotification(item)}
                className={`w-full rounded-2xl border p-3 text-left transition hover:-translate-y-0.5 ${
                  item.is_read ? "border-gray-100 bg-gray-50/70 opacity-70" : "border-amber-100 bg-amber-50/80"
                }`}
              >
                <strong className="block text-sm text-gray-800">{item.title}</strong>
                <span className="mt-1 block text-xs leading-5 text-gray-500">{item.reason || "点击查看详情"}</span>
                <span className="mt-2 block text-[11px] font-semibold text-amber-800">查看详情 →</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <button
        aria-label="知知桌宠"
        onPointerDown={(event) => {
          moved.current = false
          dragOffset.current = { x: event.clientX - position.x, y: event.clientY - position.y }
          setDragging(true)
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onClick={() => {
          if (moved.current) return
          setOpen((value) => !value)
          setBubble(null)
        }}
        className={`relative h-24 w-24 cursor-grab select-none rounded-full focus:outline-none active:cursor-grabbing ${
          dragging ? "" : "motion-safe:animate-[pet-float_3s_ease-in-out_infinite]"
        }`}
      >
        <img src={mascot} draggable={false} alt="知知" className="h-full w-full object-contain drop-shadow-xl" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-6 min-w-6 items-center justify-center rounded-full border-2 border-white bg-red-500 px-1 text-xs font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      <span className="sr-only">prefers-reduced-motion</span>
    </div>
  )
}
