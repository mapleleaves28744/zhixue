"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { FormEvent, useState } from "react"
import { toast } from "sonner"

import { PasswordInput } from "@/components/auth/PasswordInput"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { register } from "@/services/authService"
import { cn } from "@/lib/utils"

type RegisterFormProps = {
  variant?: "light" | "dark" | "landing"
  onSwitchToLogin?: () => void
  onRegisterSuccess?: () => void
}

export function RegisterForm({ variant = "light", onSwitchToLogin, onRegisterSuccess }: RegisterFormProps) {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (username.trim().length < 3) {
      setError("用户名至少需要 3 个字符")
      return
    }
    if (password.length < 6) {
      setError("密码至少需要 6 个字符")
      return
    }
    if (password !== confirmPassword) {
      setError("两次输入的密码不一致")
      return
    }

    try {
      setSubmitting(true)
      await register({
        username: username.trim(),
        email: email.trim() || undefined,
        password,
        role: "student"
      })
      toast.success("注册成功，请登录")
      if (onRegisterSuccess) {
        onRegisterSuccess()
      } else {
        router.replace("/login")
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "注册失败，请稍后重试")
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
    <form className={cn("flex flex-col", variant === "landing" ? "gap-5" : "gap-5")} onSubmit={handleSubmit}>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>用户名</span>
        <Input
          autoComplete="username"
          className={inputClass}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="student_demo"
          value={username}
        />
      </label>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>邮箱</span>
        <Input
          autoComplete="email"
          className={inputClass}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="student@example.com"
          type="email"
          value={email}
        />
      </label>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>密码</span>
        <PasswordInput
          id="register-password"
          inputClassName={inputClass}
          onChange={setPassword}
          placeholder="至少 6 个字符"
          value={password}
        />
      </label>
      <label className="flex flex-col gap-2.5">
        <span className={labelClass}>确认密码</span>
        <PasswordInput
          id="confirm-password"
          inputClassName={inputClass}
          onChange={setConfirmPassword}
          placeholder="再次输入密码"
          value={confirmPassword}
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
        {submitting ? "注册中…" : "注册学生账号"}
      </Button>

      <p className={footerClass}>
        已有账号？
        {onSwitchToLogin ? (
          <button
            className={cn(
              "ml-1.5 font-semibold transition-colors hover:underline",
              variant === "landing" ? "text-primary" : "text-foreground"
            )}
            onClick={onSwitchToLogin}
            type="button"
          >
            返回登录
          </button>
        ) : (
          <Link className="ml-2 font-bold text-primary hover:underline" href="/login">
            返回登录
          </Link>
        )}
      </p>
    </form>
  )
}
