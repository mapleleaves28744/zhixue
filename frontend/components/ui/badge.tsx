import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva("inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold transition", {
  variants: {
    variant: {
      default: "border-primary/10 bg-[#ffddb5]/35 text-primary",
      secondary: "border-border/60 bg-white/45 text-muted-foreground",
      destructive: "border-[#ffdad6] bg-[#ffdad6]/45 text-[#93000a]",
      outline: "border-border/80 text-[#524434]"
    }
  },
  defaultVariants: {
    variant: "default"
  }
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
