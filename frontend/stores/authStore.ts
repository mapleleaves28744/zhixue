"use client"

import { useSyncExternalStore } from "react"

import { clearAuthSession, getStoredUser, getToken, setAuthSession } from "@/lib/auth"
import type { User } from "@/types/auth"

interface AuthSnapshot {
  token: string | null
  user: User | null
  hydrated: boolean
}

interface AuthStore extends AuthSnapshot {
  isAuthenticated: boolean
  hydrate: () => void
  login: (token: string, refreshToken: string, user: User) => void
  logout: () => void
}

let snapshot: AuthSnapshot = {
  token: null,
  user: null,
  hydrated: false
}

const listeners = new Set<() => void>()
const serverSnapshot: AuthSnapshot = {
  token: null,
  user: null,
  hydrated: false
}

function emit() {
  listeners.forEach((listener) => listener())
}

function setSnapshot(next: AuthSnapshot) {
  snapshot = next
  emit()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): AuthSnapshot {
  return snapshot
}

function getServerSnapshot(): AuthSnapshot {
  return serverSnapshot
}

export function authStoreActions() {
  return {
    hydrate() {
      setSnapshot({
        token: getToken(),
        user: getStoredUser(),
        hydrated: true
      })
    },
    login(token: string, refreshToken: string, user: User) {
      setAuthSession(token, refreshToken, user)
      setSnapshot({
        token,
        user,
        hydrated: true
      })
    },
    logout() {
      clearAuthSession()
      setSnapshot({
        token: null,
        user: null,
        hydrated: true
      })
    }
  }
}

export function useAuthStore(): AuthStore {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  const actions = authStoreActions()
  return {
    ...state,
    isAuthenticated: Boolean(state.token && state.user),
    ...actions
  }
}
