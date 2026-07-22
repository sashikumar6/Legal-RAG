import { BookOpenText, Landmark, Scale } from 'lucide-react';
import type { ChatCitation } from '@/lib/api';

interface PanelProps {
  citations?: ChatCitation[];
}

const sourceIcon = {
  federal: Landmark,
  cfr: BookOpenText,
  case_law: Scale,
  document: BookOpenText,
};

export function KnowledgePanel({ citations = [] }: PanelProps) {
  return (
    <aside className="hidden w-80 shrink-0 overflow-y-auto border-l border-slate-200 bg-[#f5f6f2] p-6 xl:flex xl:flex-col">
      <div className="mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Referenced sources</p>
        <p className="mt-2 font-serif text-2xl text-emerald-950">{citations.length || '—'}</p>
        <p className="text-xs text-slate-500">{citations.length ? 'sources supporting this response' : 'sources appear after research completes'}</p>
      </div>

      {citations.length > 0 ? (
        <div className="space-y-5">
          {citations.map((citation, index) => {
            const Icon = sourceIcon[citation.source_type as keyof typeof sourceIcon] || BookOpenText;
            const title = citation.canonical_citation || citation.heading || 'Retrieved source';
            return (
              <article key={`${citation.document_id}-${index}`} className="border-b border-slate-200 pb-5 last:border-b-0">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-800">
                  <Icon size={13} />
                  {citation.source_type.replace('_', ' ')}
                </div>
                <h3 className="text-sm font-semibold leading-5 text-slate-800">{title}</h3>
                <p className="mt-2 border-l-2 border-emerald-900/20 pl-3 text-xs leading-5 text-slate-500">
                  “{citation.text.length > 200 ? `${citation.text.slice(0, 200)}…` : citation.text}”
                </p>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="space-y-5 border-t border-slate-200 pt-5 text-sm leading-6 text-slate-600">
          <p>Each response is grounded in the isolated source selected for your question.</p>
          <ul className="space-y-3 text-xs text-slate-500">
            <li className="flex gap-2"><Landmark size={15} className="mt-0.5 text-emerald-800" /> U.S. Code statutes</li>
            <li className="flex gap-2"><BookOpenText size={15} className="mt-0.5 text-emerald-800" /> Federal regulations</li>
            <li className="flex gap-2"><Scale size={15} className="mt-0.5 text-emerald-800" /> Federal precedent</li>
          </ul>
        </div>
      )}
    </aside>
  );
}
