"use client"

import { cn } from "@/lib/utils"
import type { ButtonHTMLAttributes, ReactNode } from "react"

type LiquidGlassButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  size?: "sm" | "lg"
}

export function LiquidGlassButton({
  children,
  className,
  size = "sm",
  type = "button",
  ...props
}: LiquidGlassButtonProps) {
  return (
    <button
      className={cn(
        "liquid-glass rounded-full text-foreground transition-transform hover:scale-[1.03] cursor-pointer",
        size === "sm" && "px-6 py-2.5 text-sm",
        size === "lg" && "px-14 py-5 text-base",
        className
      )}
      type={type}
      {...props}
    >
      <span className="relative z-10">{children}</span>
    </button>
  )
}
