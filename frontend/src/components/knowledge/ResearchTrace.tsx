import { Check, LoaderCircle, Search, Sparkles, ShieldCheck } from 'lucide-react';
import type { ResearchStatus } from '@/lib/api';

const stageIcon = {
  preparing: LoaderCircle,
  routing: Search,
  planning: Search,
  retrieving: Search,
  retrieved: Check,
  generating: Sparkles,
  verifying: ShieldCheck,
  fallback: Sparkles,
  complete: Check,
};

interface ResearchTraceProps {
  steps: ResearchStatus[];
  isResearching: boolean;
}

export function ResearchTrace({ steps, isResearching }: ResearchTraceProps) {
  if (!isResearching && steps.length === 0) return null;

  return (
    <section className="my-7 rounded-md border border-emerald-950/15 bg-[#f4f6f2] px-5 py-4" aria-live="polite">
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-950/65">
        <span className={`h-2 w-2 rounded-full ${isResearching ? 'animate-pulse bg-emerald-800' : 'bg-emerald-700'}`} />
        Research trace
      </div>
      <ol className="space-y-2">
        {steps.map((step, index) => {
          const Icon = stageIcon[step.stage];
          const isLatest = index === steps.length - 1 && isResearching;
          return (
            <li key={`${step.stage}-${index}`} className="flex items-start gap-3 text-sm text-slate-700">
              <Icon size={15} className={`mt-0.5 shrink-0 ${isLatest ? 'animate-spin text-emerald-900' : 'text-emerald-700'}`} />
              <div>
                <p className="font-medium text-slate-800">{step.label}</p>
                {step.detail && <p className="mt-0.5 text-xs text-slate-500">{step.detail}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
