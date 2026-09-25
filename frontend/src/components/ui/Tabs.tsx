import * as RadixTabs from "@radix-ui/react-tabs";
import { cn } from "../../lib/cn";

export const Tabs = RadixTabs.Root;

export const TabsList = ({ className, ...props }: RadixTabs.TabsListProps) => (
  <RadixTabs.List className={cn("flex flex-wrap gap-2 border-b border-slate-200", className)} {...props} />
);

export const TabsTrigger = ({ className, ...props }: RadixTabs.TabsTriggerProps) => (
  <RadixTabs.Trigger
    className={cn(
      "px-4 py-2.5 text-sm font-semibold text-slate-600 border-b-2 border-transparent -mb-px transition-colors",
      "hover:text-slate-900 data-[state=active]:text-accent data-[state=active]:border-accent",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-t",
      className,
    )}
    {...props}
  />
);

export const TabsContent = ({ className, ...props }: RadixTabs.TabsContentProps) => (
  <RadixTabs.Content className={cn("pt-6 focus-visible:outline-none", className)} {...props} />
);
