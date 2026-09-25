import * as RadixTooltip from "@radix-ui/react-tooltip";

export const TooltipProvider = RadixTooltip.Provider;

export function Tooltip({ label, children }: { label: string; children: React.ReactElement }) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          className="z-50 rounded-md bg-navy px-2.5 py-1.5 text-xs font-medium text-white shadow-md"
          sideOffset={6}
        >
          {label}
          <RadixTooltip.Arrow className="fill-navy" />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
