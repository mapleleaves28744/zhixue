const FOOTER_LINKS = {
  产品: ["核心功能", "更新日志", "价格策略"],
  关于: ["关于我们", "服务条款", "隐私政策"],
  联系: ["联系我们", "加入社区"]
}

export function LandingFooter() {
  return (
    <footer className="relative z-10 border-t border-border/30 bg-[#f6f3f2]/65 backdrop-blur-md" id="contact">
      <div className="mx-auto flex w-full max-w-7xl flex-col items-start justify-between space-y-8 px-8 py-16 md:flex-row md:items-center md:space-y-0">
        <div className="max-w-sm space-y-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <span className="material-symbols-outlined text-sm">auto_stories</span>
            </div>
            <span className="font-display text-lg font-bold tracking-tight text-foreground" style={{ fontFamily: "var(--font-display)" }}>
              智学工坊
            </span>
          </div>
          <p className="text-muted-foreground">下一代 AI 原生学习伴侣，致力于用技术服务人类的求知本能。</p>
          <p className="text-xs text-muted-foreground/70">© 2026 智学工坊 Zhixue Gongfang. All rights reserved.</p>
        </div>

        <div className="flex flex-wrap gap-x-12 gap-y-6">
          {Object.entries(FOOTER_LINKS).map(([title, links]) => (
            <div key={title} className="space-y-4">
              <p className="text-sm font-bold text-foreground">{title}</p>
              <div className="flex flex-col gap-2">
                {links.map((link) => (
                  <a
                    key={link}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                    href="#"
                  >
                    {link}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  )
}
