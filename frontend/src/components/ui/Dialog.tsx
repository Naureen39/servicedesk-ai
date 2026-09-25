import * as RadixDialog from "@radix-ui/react-dialog";
import { cn } from "../../lib/cn";

export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

export function DialogContent({ className, children, ...props }: RadixDialog.DialogContentProps) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-50 bg-navy/60" />
      <RadixDialog.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-card)] bg-white p-6 shadow-xl focus-visible:outline-none",
          className,
        )}
        {...props}
      >
        {children}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export const DialogTitle = ({ className, ...props }: RadixDialog.DialogTitleProps) => (
  <RadixDialog.Title className={cn("text-xl font-bold text-navy", className)} {...props} />
);

export const DialogDescription = RadixDialog.Description;
