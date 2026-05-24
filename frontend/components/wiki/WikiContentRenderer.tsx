"use client"

interface WikiContentRendererProps {
  content: string
}

export function WikiContentRenderer({ content }: WikiContentRendererProps) {
  // Simple Markdown-to-HTML renderer for MVP
  const html = renderMarkdown(content)

  return (
    <div
      className="prose prose-wiki max-w-none font-body-md text-body-md text-on-surface leading-relaxed"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function renderMarkdown(md: string): string {
  let html = md
    // Headings
    .replace(/^### (.+)$/gm, '<h3 class="font-headline-sm text-headline-sm mt-6 mb-3 text-on-surface">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="font-headline-md text-headline-md mt-8 mb-4 text-on-surface">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="font-display-lg-mobile text-display-lg-mobile mt-10 mb-5 text-on-surface">$1</h1>')
    // Bold & italic
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Blockquote
    .replace(
      /^> (.+)$/gm,
      '<blockquote class="border-l-4 border-primary/30 pl-4 py-1 my-3 text-on-surface-variant italic bg-primary/5 rounded-r-lg">$1</blockquote>',
    )
    // Unordered list items
    .replace(/^- (.+)$/gm, '<li class="ml-4 mb-1">$1</li>')
    // Ordered list items
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 mb-1 list-decimal">$1</li>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="my-6 border-outline-variant/30" />')
    // Paragraphs (lines not starting with HTML tags)
    .replace(/^(?!<[a-zA-Z])(.+)$/gm, '<p class="mb-3">$1</p>')
    // Wrap adjacent <li> in <ul>
    .replace(/((?:<li[^>]*>.*?<\/li>\s*)+)/g, '<ul class="list-disc mb-4">$1</ul>')

  return html
}
