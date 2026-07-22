import { FileText } from 'lucide-react';
import type { WorkspaceDoc } from './AnalysisView';

interface Props {
  workspaces: WorkspaceDoc[];
  activeWorkspaceId: string | null;
  onSelect: (id: string) => void;
}

export function WorkspaceList({ workspaces, activeWorkspaceId, onSelect }: Props) {
  if (workspaces.length === 0) return null;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-serif text-xl text-emerald-950">Active Workspaces</h3>
        <span className="text-sm font-semibold text-slate-500">{workspaces.length} document{workspaces.length === 1 ? '' : 's'}</span>
      </div>

      <div className="space-y-3">
        {workspaces.map((doc) => (
          <div
            key={doc.id}
            onClick={() => onSelect(doc.id)}
            className={`flex cursor-pointer items-center justify-between border border-l-4 bg-white p-4 transition-colors ${doc.border} ${activeWorkspaceId === doc.id ? 'border-emerald-900/30 bg-[#f4f6f2]' : 'border-slate-200'}`}
          >
            <div className="flex items-center space-x-4">
              <div className={`p-3 ${doc.iconColor}`}>
                <FileText size={20} />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-semibold text-slate-800">{doc.name}</h4>
                <div className="flex space-x-3 text-xs font-medium text-slate-500">
                  <span>Size: {doc.size}</span>
                  <span>Added: {doc.added}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${doc.color} ${doc.status === 'PROCESSING' ? 'flex items-center space-x-1' : ''}`}>
                {doc.status === 'PROCESSING' && <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500"></span>}
                {doc.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
