import type { ReactNode } from "react"

import { RequireRole } from "@/components/auth/RequireRole"
import { AppShell } from "@/components/layout/AppShell"
import { studentNavItems } from "@/components/layout/StudentSidebar"

export default function StudentLayout({ children }: { children: ReactNode }) {
  return (
    <RequireRole role="student">
      <AppShell navItems={studentNavItems} title="学生学习空间">
        {children}
      </AppShell>
    </RequireRole>
  )
}
