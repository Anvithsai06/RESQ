import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

/** Shared surface for dashboard sections — one border weight, one radius. */
export default function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
  bodyClassName = "",
}: PanelProps) {
  return (
    <section className={`flex flex-col rounded-lg border border-slate-800 bg-slate-900/40 shadow-panel ${className}`}>
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-slate-200">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className={`flex-1 p-4 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-full min-h-[80px] items-center justify-center px-4 py-6 text-center">
      <p className="text-sm text-slate-500">{message}</p>
    </div>
  );
}
