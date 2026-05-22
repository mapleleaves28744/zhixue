import type { ReactNode } from "react"

import { RequireRole } from "@/components/auth/RequireRole"
import { AppShell } from "@/components/layout/AppShell"
import { adminNavItems } from "@/components/layout/AdminSidebar"

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <RequireRole role="admin">
      <AppShell navItems={adminNavItems} title="管理员控制台">
        {children}
      </AppShell>
    </RequireRole>
  )
}
