/** Unwrap Supervisor JSON envelopes so Markdown can render correctly. */
export function normalizeAgentAnswer(raw: string): string {
  const text = (raw || "").trim()
  if (!text) return ""

  const candidates = [text, stripCodeFence(text)]
  for (const candidate of candidates) {
    if (!candidate.startsWith("{") || !candidate.includes("final_answer")) {
      continue
    }
    try {
      const data = JSON.parse(candidate) as Record<string, unknown>
      const inner = data.final_answer ?? data.answer
      if (typeof inner === "string" && inner.trim()) {
        return inner.trim()
      }
    } catch {
      /* keep trying */
    }
  }

  return text
}

function stripCodeFence(text: string): string {
  const trimmed = text.trim()
  if (!trimmed.startsWith("```")) return trimmed
  return trimmed
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/, "")
    .trim()
}
