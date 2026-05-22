"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { FormEvent, useState } from "react"
import { toast } from "sonner"

import { PasswordInput } from "@/components/auth/PasswordInput"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { register } from "@/services/authService"

export function RegisterForm() {
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
      router.replace("/login")
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "注册失败，请稍后重试")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">用户名</span>
        <Input autoComplete="username" onChange={(event) => setUsername(event.target.value)} placeholder="student_demo" value={username} />
      </label>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">邮箱</span>
        <Input autoComplete="email" onChange={(event) => setEmail(event.target.value)} placeholder="student@example.com" type="email" value={email} />
      </label>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">密码</span>
        <PasswordInput id="register-password" onChange={setPassword} placeholder="至少 6 个字符" value={password} />
      </label>
      <label className="flex flex-col gap-2">
        <span className="text-sm font-bold text-[#524434]">确认密码</span>
        <PasswordInput id="confirm-password" onChange={setConfirmPassword} placeholder="再次输入密码" value={confirmPassword} />
      </label>

      {error ? (
        <div className="rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]">
          {error}
        </div>
      ) : null}

      <Button disabled={submitting} size="lg" type="submit" variant="accent">
        {submitting ? "注册中" : "注册学生账号"}
      </Button>

      <p className="text-center text-sm text-[#524434]">
        已有账号？
        <Link className="ml-2 font-bold text-primary hover:underline" href="/login">
          返回登录
        </Link>
      </p>
    </form>
  )
}
