import { Suspense } from "react"
import { AssistantPageClient } from "@/components/assistant/AssistantPageClient"

export default function AssistantPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-outline">加载中…</div>}>
      <AssistantPageClient />
    </Suspense>
  )
}
