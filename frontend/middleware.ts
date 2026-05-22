import { NextRequest, NextResponse } from "next/server"

const ACCESS_TOKEN_KEY = "access_token"
const AUTH_ROLE_KEY = "auth_role"

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get(ACCESS_TOKEN_KEY)?.value
  const role = request.cookies.get(AUTH_ROLE_KEY)?.value

  if (!token) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("redirect", pathname)
    return NextResponse.redirect(loginUrl)
  }

  if (pathname.startsWith("/admin") && role === "student") {
    return NextResponse.redirect(new URL("/student/dashboard", request.url))
  }

  if (pathname.startsWith("/student") && role === "admin") {
    return NextResponse.redirect(new URL("/admin/dashboard", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/student/:path*", "/admin/:path*"]
}
