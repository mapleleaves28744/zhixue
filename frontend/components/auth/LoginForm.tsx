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

export function LoginForm() {
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

  return (
    <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">账号</span>
        <Input autoComplete="username" onChange={(event) => setUsername(event.target.value)} placeholder="student_demo" value={username} />
      </label>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">密码</span>
        <PasswordInput id="password" onChange={setPassword} placeholder="请输入密码" value={password} />
      </label>

      {error ? (
        <div className="rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]">
          {error}
        </div>
      ) : null}

      <Button disabled={submitting} size="lg" type="submit" variant="accent">
        {submitting ? "登录中" : "登录"}
      </Button>

      <p className="text-center text-sm text-[#524434]">
        还没有账号？
        <Link className="ml-2 font-bold text-primary hover:underline" href="/register">
          创建学生账号
        </Link>
      </p>
    </form>
  )
}
