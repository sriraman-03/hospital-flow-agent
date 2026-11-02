import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; confirmLabel?: string; destructive?: boolean;
  /** When set, a text box is shown. `required` blocks confirmation until filled. */
  reason?: { label: string; required?: boolean; minLength?: number };
  pending?: boolean; onConfirm: (reason: string) => void;
}

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", destructive, reason, pending, onConfirm }: Props) {
  const [text, setText] = useState("");
  const invalid = !!reason?.required && text.trim().length < (reason.minLength ?? 1);
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setText(""); onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>{title}</DialogTitle>{description && <DialogDescription>{description}</DialogDescription>}</DialogHeader>
        {reason && (
          <div className="grid gap-1.5">
            <Label htmlFor="confirm-reason">{reason.label}{reason.required ? " *" : " (optional)"}</Label>
            <Textarea id="confirm-reason" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} />
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant={destructive ? "destructive" : "default"} disabled={pending || invalid} onClick={() => { onConfirm(text.trim()); setText(""); }}>
            {pending ? "Working…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
