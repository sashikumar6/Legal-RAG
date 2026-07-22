import type { Dispatch, SetStateAction } from 'react';
import { Bookmark } from 'lucide-react';
import type { WorkspaceDoc } from './AnalysisView';
import type { ChatCitation } from '@/lib/api';

interface Props {
  workspaces: WorkspaceDoc[];
  setWorkspaces: Dispatch<SetStateAction<WorkspaceDoc[]>>;
  activeWorkspaceId: string | null;
  citations: ChatCitation[];
}

export function AnalysisPanel({ workspaces, setWorkspaces, activeWorkspaceId, citations }: Props) {
  const activeDoc = workspaces.find(w => w.id === activeWorkspaceId);

  const downloadAudit = () => {
    const sourceLines = citations.length
      ? citations.map((citation) => `- ${citation.canonical_citation || citation.heading || 'Retrieved source'}`).join('\n')
      : '- No sources were cited in this session.';
    const report = [
      '# Document Research Audit',
      '',
      `Generated: ${new Date().toLocaleString()}`,
      `Active document: ${activeDoc?.name || 'None selected'}`,
      '',
      '## Referenced Sources',
      sourceLines,
    ].join('\n');
    const url = URL.createObjectURL(new Blob([report], { type: 'text/markdown' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'digital-jurist-audit.md';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <aside className="hidden w-80 shrink-0 flex-col overflow-y-auto border-l border-slate-200 bg-[#f5f6f2] p-6 xl:flex">
      <p className="mb-6 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace insights</p>

      {activeDoc ? (
        <div className="border border-slate-200 bg-white p-5">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Active document</p>
          <p className="mb-2 break-words font-serif text-lg text-emerald-950">{activeDoc.name}</p>
          <p className="mb-3 text-xs text-slate-500">Size: {activeDoc.size}</p>
          <div className="mb-2 h-1 w-full bg-slate-100">
            <div className="h-1 bg-emerald-900" style={{ width: '100%' }} />
          </div>
          <p className="text-[11px] text-slate-500">
            Status: <span className="font-semibold text-emerald-950">{activeDoc.status}</span>
          </p>
        </div>
      ) : (
        <div className="border border-slate-200 bg-white p-5">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Batch progress</p>
          <div className="mb-2 flex justify-between text-xs text-slate-600">
            <span>Overall status</span>
            <span className="font-semibold text-emerald-950">{workspaces.length > 0 ? 'Analyzed' : 'Empty'}</span>
          </div>
          <div className="mb-3 h-1 w-full bg-slate-100">
            <div className="h-1 bg-emerald-900" style={{ width: workspaces.length > 0 ? '100%' : '0%' }} />
          </div>
          <p className="text-[11px] text-slate-500">
            <span className="font-semibold text-emerald-950">{workspaces.length}</span> documents in workspace.
          </p>
        </div>
      )}

      {citations.length > 0 ? (
        <div className="mt-8">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Referenced sources</p>
          <div className="space-y-5">
            {citations.map((c, i) => (
              <article key={i} className="border-b border-slate-200 pb-5 last:border-b-0">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-800">
                  <Bookmark size={13} />
                  Document match
                </div>
                <h3 className="text-sm font-semibold leading-5 text-slate-800">
                  Page {c.section_number || c.canonical_citation || 'Unknown'} {c.heading ? `— ${c.heading}` : ''}
                </h3>
                <p className="mt-2 border-l-2 border-emerald-900/20 pl-3 text-xs leading-5 text-slate-500">
                  &quot;{c.text.length > 200 ? `${c.text.slice(0, 200)}…` : c.text}&quot;
                </p>
              </article>
            ))}
          </div>
        </div>
      ) : (
        <p className="mt-8 border-t border-slate-200 pt-5 text-xs leading-5 text-slate-500">
          Upload a document and ask a question to see only evidence actually retrieved from that document.
        </p>
      )}

      <div className="mt-8 space-y-2">
        <button
          onClick={downloadAudit}
          className="w-full bg-emerald-950 py-2.5 text-xs font-semibold uppercase tracking-widest text-white transition hover:bg-emerald-900"
        >
          Download full audit
        </button>
        <button
          onClick={() => setWorkspaces([])}
          className="w-full border border-slate-300 bg-white py-2.5 text-xs font-semibold uppercase tracking-widest text-slate-600 transition hover:border-emerald-900/40 hover:text-emerald-950"
        >
          Clear workspace
        </button>
      </div>
    </aside>
  );
}
