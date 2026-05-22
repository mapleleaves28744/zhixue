import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      className={cn(
        "flex h-11 w-full rounded-2xl border border-border/70 bg-white/55 px-4 py-3 text-base text-foreground outline-none transition placeholder:text-[#857462] focus:border-primary focus:bg-white/80 disabled:cursor-not-allowed disabled:opacity-60",
        className
      )}
      ref={ref}
      type={type}
      {...props}
    />
  )
)
Input.displayName = "Input"

export { Input }
