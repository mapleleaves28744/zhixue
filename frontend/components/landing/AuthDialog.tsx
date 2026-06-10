"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useState } from "react"

import { LoginForm } from "@/components/auth/LoginForm"
import { RegisterForm } from "@/components/auth/RegisterForm"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog"
import { landingFontVariables } from "@/lib/landingFonts"

type AuthMode = "login" | "register"

type AuthDialogProps = {
  open: boolean
  mode: AuthMode
  onOpenChange: (open: boolean) => void
  onModeChange: (mode: AuthMode) => void
}

export function AuthDialog({ open, mode, onOpenChange, onModeChange }: AuthDialogProps) {
  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent
        className={`landing-auth-dialog ${landingFontVariables} max-w-[440px] gap-0 p-0 sm:max-w-[440px]`}
        closeClassName="landing-auth-close"
      >
        <div aria-hidden="true" className="landing-auth-accent" />

        <div className="space-y-7 px-8 pb-9 pt-8">
          <DialogHeader className="landing-auth-header pr-10 text-left">
            <p className="landing-auth-eyebrow">Zhixue Account</p>
            <DialogTitle className="landing-auth-title font-normal">
              {mode === "login" ? "登录智学工坊" : "注册智学工坊"}
            </DialogTitle>
            <DialogDescription className="landing-auth-desc">
              {mode === "login" ? (
                <>
                  进入课程空间，
                  <br />
                  上传资料、生成 Wiki，继续你的学习。
                </>
              ) : (
                <>
                  创建学生账号，
                  <br />
                  开启个性化学习之旅。
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="landing-auth-tabs" role="tablist">
            {(["login", "register"] as AuthMode[]).map((tab) => (
              <button
                key={tab}
                aria-selected={mode === tab}
                className="landing-auth-tab"
                data-active={mode === tab ? "true" : "false"}
                onClick={() => onModeChange(tab)}
                role="tab"
                type="button"
              >
                {tab === "login" ? "登录" : "注册"}
              </button>
            ))}
          </div>

          {mode === "login" ? (
            <LoginForm onSwitchToRegister={() => onModeChange("register")} variant="landing" />
          ) : (
            <RegisterForm
              onRegisterSuccess={() => onModeChange("login")}
              onSwitchToLogin={() => onModeChange("login")}
              variant="landing"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function AuthDialogController({
  authOpen,
  authMode,
  setAuthOpen,
  setAuthMode
}: {
  authOpen: boolean
  authMode: AuthMode
  setAuthOpen: (open: boolean) => void
  setAuthMode: (mode: AuthMode) => void
}) {
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const auth = searchParams.get("auth")
    if (auth === "login" || auth === "register") {
      setAuthMode(auth)
      setAuthOpen(true)
    }
  }, [searchParams, setAuthMode, setAuthOpen])

  const handleOpenChange = useCallback(
    (open: boolean) => {
      setAuthOpen(open)
      if (!open && searchParams.get("auth")) {
        router.replace("/")
      }
    },
    [router, searchParams, setAuthOpen]
  )

  return (
    <AuthDialog mode={authMode} onModeChange={setAuthMode} onOpenChange={handleOpenChange} open={authOpen} />
  )
}

export function AuthDialogProvider({
  authOpen,
  authMode,
  setAuthOpen,
  setAuthMode
}: {
  authOpen: boolean
  authMode: AuthMode
  setAuthOpen: (open: boolean) => void
  setAuthMode: (mode: AuthMode) => void
}) {
  return (
    <Suspense fallback={null}>
      <AuthDialogController
        authMode={authMode}
        authOpen={authOpen}
        setAuthMode={setAuthMode}
        setAuthOpen={setAuthOpen}
      />
    </Suspense>
  )
}

export type { AuthMode }
