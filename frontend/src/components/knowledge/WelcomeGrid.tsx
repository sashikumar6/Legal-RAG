import { BookOpen, Clock, FileSearch, Landmark, Scale, Shield } from 'lucide-react';

export function WelcomeGrid({ onSelect }: { onSelect: (query: string) => void }) {
  const prompts = [
    { icon: Clock, label: 'Immigration', text: 'What are the rules regarding deportation and asylum under Title 8?' },
    { icon: Scale, label: 'Bankruptcy', text: 'How does Chapter 11 bankruptcy protect corporate debtors under Title 11?' },
    { icon: Shield, label: 'Criminal law', text: 'What are the federal penalties for wire fraud under Title 18?' },
    { icon: Landmark, label: 'Labor', text: 'Explain federal overtime and minimum-wage requirements under Title 29.' },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#fafaf8] px-5 py-12 md:px-12 lg:px-16">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 max-w-2xl">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-800">Knowledge mode</p>
          <h1 className="font-serif text-4xl leading-tight tracking-tight text-emerald-950 md:text-5xl">Research federal law with visible evidence.</h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">Ask a question about statutes, regulations, or precedent. The research trace shows each step before the cited response is finalized.</p>
        </div>

        <div className="mb-10 grid gap-px border border-slate-200 bg-slate-200 sm:grid-cols-2" aria-label="Research mode guide">
          <div className="bg-white p-4">
            <div className="flex items-center gap-2 text-emerald-900">
              <BookOpen size={16} />
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em]">Knowledge Mode</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">Use for general legal Q&amp;A about federal statutes, regulations, and court precedent.</p>
          </div>
          <div className="bg-[#f4f6f2] p-4">
            <div className="flex items-center gap-2 text-emerald-900">
              <FileSearch size={16} />
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em]">Analysis Mode</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">Use to upload and analyze a case document, with answers grounded in that file.</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {prompts.map(({ icon: Icon, label, text }) => (
            <button
              key={label}
              onClick={() => onSelect(text)}
              className="group border border-slate-200 bg-white p-5 text-left transition hover:border-emerald-900/35 hover:bg-[#f4f6f2]"
            >
              <Icon size={18} className="mb-5 text-emerald-800" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-400">{label}</p>
              <p className="mt-2 font-serif text-lg leading-6 text-slate-800 group-hover:text-emerald-950">{text}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
