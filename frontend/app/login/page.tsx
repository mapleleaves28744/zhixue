import { redirect } from "next/navigation"

type LoginPageProps = {
  searchParams?: Promise<{
    redirect?: string
  }>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams
  const target = params?.redirect
    ? `/?auth=login&redirect=${encodeURIComponent(params.redirect)}`
    : "/?auth=login"

  redirect(target)
}
