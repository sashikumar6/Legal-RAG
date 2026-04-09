import { FileText, MoreVertical } from 'lucide-react';
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
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-slate-900">Active Workspaces</h3>
        <button className="text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors">
          View All Documents
        </button>
      </div>

      <div className="space-y-4">
        {workspaces.map((doc) => (
          <div 
            key={doc.id} 
            onClick={() => onSelect(doc.id)}
            className={`flex items-center justify-between p-4 bg-white border rounded-xl shadow-sm border-l-4 cursor-pointer transition-colors ${doc.border} ${activeWorkspaceId === doc.id ? 'border-slate-400 bg-slate-50' : 'border-slate-200'}`}
          >
            <div className="flex items-center space-x-4">
              <div className={`p-3 rounded-lg ${doc.iconColor}`}>
                <FileText size={20} />
              </div>
              <div>
                <h4 className="font-bold text-slate-900 text-sm mb-0.5">{doc.name}</h4>
                <div className="flex space-x-3 text-xs font-medium text-slate-500">
                  <span>Size: {doc.size}</span>
                  <span>Added: {doc.added}</span>
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <span className={`text-[10px] font-bold px-2 py-1 uppercase rounded tracking-wider ${doc.color} ${doc.status === 'PROCESSING' ? 'flex items-center space-x-1' : ''}`}>
                {doc.status === 'PROCESSING' && <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse mr-1.5 inline-block"></span>}
                {doc.status}
              </span>
              <button 
                className="text-slate-400 hover:text-slate-600"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
