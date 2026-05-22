import { redirect } from "next/navigation"

type LoginPageProps = {
  searchParams?: {
    redirect?: string
  }
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const target = searchParams?.redirect
    ? `/?auth=login&redirect=${encodeURIComponent(searchParams.redirect)}`
    : "/?auth=login"

  redirect(target)
}
