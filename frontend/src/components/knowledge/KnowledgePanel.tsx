import { CheckCircle2, Bookmark, Scale } from 'lucide-react';
import type { ChatCitation } from '@/lib/api';

interface PanelProps {
  citations?: ChatCitation[];
}

export function KnowledgePanel({ citations = [] }: PanelProps) {
  if (citations.length > 0) {
    return (
      <div className="w-80 bg-slate-50 border-l border-slate-200 p-8 flex flex-col space-y-8 overflow-y-auto">
        <h3 className="text-sm font-bold tracking-widest text-slate-400 uppercase">
          Referenced Sources
        </h3>
        
        <div className="space-y-6">
          {citations.map((c, i) => (
            <div key={i} className="animate-fade-in group" style={{ animationDelay: `${i * 100}ms` }}>
              <span className="inline-block px-2 py-0.5 rounded bg-orange-100 text-orange-800 text-[10px] font-bold uppercase tracking-widest mb-2">
                {c.source_type}
              </span>
              <h4 className="font-bold text-sm text-slate-900 mb-1 flex items-start gap-2">
                <Bookmark size={14} className="mt-1 flex-shrink-0 text-slate-400" />
                <span>{c.canonical_citation} {c.title_number && c.section_number ? `(Title ${c.title_number}, Sec ${c.section_number})` : ''}</span>
              </h4>
              <p className="text-xs text-slate-500 font-medium leading-relaxed italic border-l-2 border-slate-300 pl-3 py-1">
                &quot;{c.text.length > 200 ? c.text.substring(0, 200) + '...' : c.text}&quot;
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-slate-50 border-l border-slate-200 p-8 flex flex-col space-y-10 overflow-y-auto hidden lg:flex">
      <div>
        <h3 className="text-sm font-bold tracking-widest text-slate-400 uppercase mb-4">
          Knowledge Stats
        </h3>
        
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm mb-4">
          <div className="text-3xl font-bold text-slate-900 mb-1">1,240</div>
          <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Precedents Indexed</div>
        </div>
        
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm">
          <div className="text-3xl font-bold text-slate-900 mb-1">42</div>
          <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Active Briefs</div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-bold tracking-widest text-slate-400 uppercase mb-4">
          Curator Guidelines
        </h3>
        <ul className="space-y-4">
          <li className="flex items-start space-x-3 text-sm text-slate-600">
            <CheckCircle2 size={16} className="text-orange-600 flex-shrink-0 mt-0.5" />
            <span>Cite specific case numbers for faster retrieval and deeper analysis.</span>
          </li>
          <li className="flex items-start space-x-3 text-sm text-slate-600">
            <CheckCircle2 size={16} className="text-orange-600 flex-shrink-0 mt-0.5" />
            <span>Use 'Comparison Mode' to see differences between state jurisdictions.</span>
          </li>
          <li className="flex items-start space-x-3 text-sm text-slate-600">
            <CheckCircle2 size={16} className="text-orange-600 flex-shrink-0 mt-0.5" />
            <span>Knowledge Mode data is updated every 24 hours with new court filings.</span>
          </li>
        </ul>
      </div>

      <div className="mt-8 rounded-xl overflow-hidden shadow-sm relative group cursor-pointer border border-slate-800">
        <div className="h-40 bg-slate-900 bg-[url('https://images.unsplash.com/photo-1505664177922-2418fc3c7a0c?q=80&w=400&auto=format&fit=crop')] bg-cover bg-center blend-overlay opacity-80 transition-opacity group-hover:opacity-100"></div>
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 to-transparent flex items-end p-5">
          <div>
            <h4 className="text-white font-bold mb-1">Case Archives</h4>
            <p className="text-slate-300 text-xs font-medium">Browse the digital collection</p>
          </div>
        </div>
      </div>
    </div>
  );
}
