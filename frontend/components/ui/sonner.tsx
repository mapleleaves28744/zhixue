"use client"

import { Toaster as Sonner } from "sonner"

export function Toaster() {
  return (
    <Sonner
      toastOptions={{
        classNames: {
          toast: "border border-white/70 bg-[#fcf9f8]/95 text-[#1c1b1b] shadow-glass backdrop-blur-3xl",
          description: "text-[#524434]",
          actionButton: "bg-primary text-white",
          cancelButton: "bg-white/60 text-[#524434]"
        }
      }}
    />
  )
}
