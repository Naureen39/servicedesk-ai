import * as RadixAccordion from "@radix-ui/react-accordion";
import { cn } from "../../lib/cn";

export const Accordion = RadixAccordion.Root;
export const AccordionItem = ({ className, ...props }: RadixAccordion.AccordionItemProps) => (
  <RadixAccordion.Item className={cn("border-b border-slate-200", className)} {...props} />
);

export function AccordionTrigger({ children, className, ...props }: RadixAccordion.AccordionTriggerProps) {
  return (
    <RadixAccordion.Header>
      <RadixAccordion.Trigger
        className={cn(
          "group flex w-full items-center justify-between py-4 text-left text-base font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded",
          className,
        )}
        {...props}
      >
        {children}
        <ChevronIcon />
      </RadixAccordion.Trigger>
    </RadixAccordion.Header>
  );
}

export const AccordionContent = ({ className, ...props }: RadixAccordion.AccordionContentProps) => (
  <RadixAccordion.Content
    className={cn(
      "overflow-hidden text-slate-600 data-[state=open]:animate-[accordion-down_200ms_ease-out] data-[state=closed]:animate-[accordion-up_200ms_ease-out]",
      className,
    )}
    {...props}
  />
);

function ChevronIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="shrink-0 text-slate-500 transition-transform duration-200 group-data-[state=open]:rotate-180">
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
