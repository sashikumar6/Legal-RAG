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

  return (
    <div className="w-80 bg-slate-50 border-l border-slate-200 p-8 flex flex-col space-y-10 overflow-y-auto">
      <h3 className="text-sm font-bold tracking-widest text-slate-400 uppercase">
        Workspace Insights
      </h3>

      {activeDoc ? (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold tracking-widest text-slate-900 uppercase mb-4">Active Document</div>
          <div className="text-sm font-bold text-slate-800 break-words mb-2">{activeDoc.name}</div>
          <div className="text-xs font-semibold text-slate-500 mb-2">Size: {activeDoc.size}</div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 mb-2 mt-4">
            <div className="bg-slate-900 h-1.5 rounded-full" style={{ width: '100%' }}></div>
          </div>
          <p className="text-[10px] text-slate-500 font-medium leading-relaxed">
            Status: <span className="font-bold text-slate-800">{activeDoc.status}</span>
          </p>
        </div>
      ) : (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-bold tracking-widest text-slate-900 uppercase mb-4">Batch Progress</div>
          <div className="flex justify-between text-xs font-semibold text-slate-600 mb-2">
            <span>Overall Status</span>
            <span className="text-slate-900">{workspaces.length > 0 ? 'Analyzed' : 'Empty'}</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 mb-4">
            <div className="bg-slate-900 h-1.5 rounded-full" style={{ width: workspaces.length > 0 ? '100%' : '0%' }}></div>
          </div>
          <p className="text-[10px] text-slate-500 font-medium leading-relaxed">
            <span className="font-bold text-slate-800">{workspaces.length}</span> documents in workspace.
          </p>
        </div>
      )}

      {citations.length > 0 ? (
        <div>
          <h3 className="text-sm font-bold tracking-widest text-slate-400 uppercase mb-4">
            Referenced Sources
          </h3>
          <div className="space-y-6">
            {citations.map((c, i) => (
              <div key={i} className="animate-fade-in group" style={{ animationDelay: `${i * 100}ms` }}>
                <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-bold uppercase tracking-widest mb-2">
                  Document Match
                </span>
                <h4 className="font-bold text-sm text-slate-900 mb-1 flex items-start gap-2">
                  <Bookmark size={14} className="mt-1 flex-shrink-0 text-slate-400" />
                  <span>Page {c.section_number || c.canonical_citation || 'Unknown'} {c.heading ? `- ${c.heading}` : ''}</span>
                </h4>
                <p className="text-xs text-slate-500 font-medium leading-relaxed italic border-l-2 border-slate-300 pl-3 py-1">
                  &quot;{c.text.length > 200 ? c.text.substring(0, 200) + '...' : c.text}&quot;
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Default static insights */}
          <div>
            <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-bold uppercase tracking-widest mb-2">
              Key Entity Detect
            </span>
            <h4 className="font-bold text-sm text-slate-900 mb-1">Henderson, Sarah L.</h4>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              Mentioned in 12 documents. Primary connection: Liability Clause 4.2.
            </p>
          </div>

          <div>
            <span className="inline-block px-2 py-0.5 rounded bg-orange-100 text-orange-800 text-[10px] font-bold uppercase tracking-widest mb-2">
              Risk Alert
            </span>
            <h4 className="font-bold text-sm text-slate-900 mb-1">Inconsistent Dates</h4>
            <p className="text-xs text-slate-500 font-medium leading-relaxed">
              Discrepancy found between Exhibit A and Merger Agreement signature page.
            </p>
          </div>
        </div>
      )}

      <div className="mt-8 space-y-3">
        <button 
          onClick={() => alert('Downloading full audit report...')}
          className="w-full py-3 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-lg text-xs font-bold uppercase tracking-widest transition-colors shadow-sm"
        >
          Download Full Audit
        </button>
        <button 
          onClick={() => setWorkspaces([])}
          className="w-full py-3 bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-lg text-xs font-bold uppercase tracking-widest transition-colors shadow-sm"
        >
          Clear Workspace
        </button>
      </div>
    </div>
  );
}
