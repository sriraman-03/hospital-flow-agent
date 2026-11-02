import * as React from "react";
import { cn } from "@/lib/utils";

const field = "flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn(field, className)} {...p} />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(field, "h-auto min-h-[72px] py-2", className)} {...p} />
));
Textarea.displayName = "Textarea";

/** Styled native select: fully accessible and keyboard friendly. */
export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, ref) => (
  <select ref={ref} className={cn(field, "pr-8", className)} {...p}>{children}</select>
));
Select.displayName = "Select";
