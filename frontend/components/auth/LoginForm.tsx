"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { FormEvent, useState } from "react"
import { toast } from "sonner"

import { PasswordInput } from "@/components/auth/PasswordInput"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getDefaultRouteByRole } from "@/lib/auth"
import { login as loginRequest } from "@/services/authService"
import { useAuthStore } from "@/stores/authStore"
import { cn } from "@/lib/utils"

type LoginFormProps = {
  variant?: "light" | "dark" | "landing"
  onSwitchToRegister?: () => void
}

export function LoginForm({ variant = "light", onSwitchToRegister }: LoginFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const auth = useAuthStore()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (!username.trim() || !password) {
      setError("请输入账号和密码")
      return
    }

    try {
      setSubmitting(true)
      const token = await loginRequest({ username: username.trim(), password })
      auth.login(token.access_token, token.refresh_token, token.user)
      toast.success("登录成功")
      const redirect = searchParams.get("redirect")
      router.replace(redirect && redirect.startsWith("/") ? redirect : getDefaultRouteByRole(token.user.role))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "登录失败，请稍后重试")
    } finally {
      setSubmitting(false)
    }
  }

  const labelClass =
    variant === "landing"
      ? "text-sm font-medium tracking-[0.04em] text-muted-foreground"
      : variant === "dark"
        ? "text-sm font-medium text-muted-foreground"
        : "text-sm font-bold text-[#524434]"
  const footerClass =
    variant === "landing"
      ? "text-center text-sm leading-[1.85] tracking-[0.02em] text-muted-foreground"
      : variant === "dark"
        ? "text-center text-sm text-muted-foreground"
        : "text-center text-sm text-[#524434]"
  const errorClass =
    variant === "dark"
      ? "rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-200"
      : "rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]"
  const inputClass =
    variant === "landing"
      ? "landing-auth-input"
      : variant === "dark"
        ? "border-white/15 bg-white/5 text-foreground placeholder:text-muted-foreground focus:border-white/30 focus:bg-white/10"
        : undefined

  return (
    <form className={cn("flex flex-col", variant === "landing" ? "gap-6" : "gap-5")} onSubmit={handleSubmit}>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>账号</span>
        <Input
          autoComplete="username"
          className={inputClass}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="student_demo"
          value={username}
        />
      </label>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>密码</span>
        <PasswordInput
          id="password"
          inputClassName={inputClass}
          onChange={setPassword}
          placeholder="请输入密码"
          value={password}
        />
      </label>

      {error ? <div className={errorClass}>{error}</div> : null}

      <Button
        className={cn(
          variant === "landing" && "landing-auth-submit w-full border-0 text-base",
          variant === "dark" && "bg-foreground text-background hover:bg-foreground/90"
        )}
        disabled={submitting}
        size="lg"
        type="submit"
        variant={variant === "landing" ? "default" : variant === "dark" ? "default" : "accent"}
      >
        {submitting ? "登录中…" : "登录"}
      </Button>

      <p className={footerClass}>
        还没有账号？
        {onSwitchToRegister ? (
          <button
            className={cn(
              "ml-1.5 font-semibold transition-colors hover:underline",
              variant === "landing" ? "text-primary" : "text-foreground"
            )}
            onClick={onSwitchToRegister}
            type="button"
          >
            创建学生账号
          </button>
        ) : (
          <Link className="ml-2 font-bold text-primary hover:underline" href="/register">
            创建学生账号
          </Link>
        )}
      </p>
    </form>
  )
}
