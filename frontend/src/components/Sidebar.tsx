import Link from 'next/link';
import { BookOpen, FileSearch, Plus, Settings, HelpCircle, MessageSquare } from 'lucide-react';
import type { HistoryResultItem } from '@/lib/api';

interface SidebarProps {
  currentMode: 'knowledge' | 'analysis';
  setMode: (mode: 'knowledge' | 'analysis') => void;
  onNewCase: () => void;
  onOpenSettings: () => void;
  history: HistoryResultItem[];
  historyLoading: boolean;
  historyError: string | null;
  activeConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
}

type HistoryGroup = 'Today' | 'Previous 7 Days' | 'Older';

function groupHistory(history: HistoryResultItem[]): Array<[HistoryGroup, HistoryResultItem[]]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekAgo = today - (7 * 24 * 60 * 60 * 1000);
  const groups: Record<HistoryGroup, HistoryResultItem[]> = {
    Today: [],
    'Previous 7 Days': [],
    Older: [],
  };

  history.forEach((conversation) => {
    const updated = Date.parse(conversation.updated_at);
    const group: HistoryGroup = updated >= today
      ? 'Today'
      : updated >= weekAgo
        ? 'Previous 7 Days'
        : 'Older';
    groups[group].push(conversation);
  });

  return (Object.entries(groups) as Array<[HistoryGroup, HistoryResultItem[]]>).filter(
    ([, conversations]) => conversations.length > 0,
  );
}

export function Sidebar({
  currentMode,
  setMode,
  onNewCase,
  onOpenSettings,
  history = [],
  historyLoading,
  historyError,
  activeConversationId,
  onSelectConversation,
}: SidebarProps) {
  const groupedHistory = groupHistory(history);

  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-[#f4f6f2] md:flex">
      {/* App Branding */}
      <div className="p-6">
        <h1 className="font-serif text-xl font-semibold tracking-tight text-emerald-950">The Digital Jurist</h1>
        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Federal research suite</p>
      </div>

      {/* Mode Switcher Label */}
      <div className="px-6 mb-2 mt-4">
        <p className="text-xs font-semibold tracking-widest text-slate-500 uppercase">
          AI Legal Suite
        </p>
      </div>

      {/* Navigation Modules */}
      <nav className="px-4 space-y-2">
        <button
          onClick={() => setMode('knowledge')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
            currentMode === 'knowledge'
              ? 'bg-emerald-950 text-white shadow-sm'
              : 'text-slate-600 hover:bg-white hover:text-emerald-950'
          }`}
        >
          <BookOpen size={18} className={currentMode === 'knowledge' ? 'text-white' : 'text-slate-400'} />
          <span className="tracking-wide">KNOWLEDGE MODE</span>
        </button>

        <button
          onClick={() => setMode('analysis')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
            currentMode === 'analysis'
              ? 'bg-emerald-950 text-white shadow-sm'
              : 'text-slate-600 hover:bg-white hover:text-emerald-950'
          }`}
        >
          <FileSearch size={18} className={currentMode === 'analysis' ? 'text-white' : 'text-slate-400'} />
          <span className="tracking-wide">ANALYSIS MODE</span>
        </button>
      </nav>

      <div className="px-4 pt-5">
        <button
          onClick={onNewCase}
          className="w-full flex items-center justify-center space-x-2 bg-emerald-950 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-900"
        >
          <Plus size={16} />
          <span>New Case</span>
        </button>
      </div>

      <section className="mt-5 min-h-0 flex-1 overflow-y-auto px-3" aria-label="Case history">
        <div className="flex items-center justify-between px-3 pb-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Case History</p>
          {!historyLoading && history.length > 0 && (
            <span className="text-[10px] tabular-nums text-slate-400">{history.length}</span>
          )}
        </div>

        {historyLoading ? (
          <div className="space-y-2 px-2 py-2" aria-label="Loading case history">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-9 animate-pulse rounded bg-slate-200/70" />
            ))}
          </div>
        ) : historyError ? (
          <p className="px-3 py-3 text-xs leading-5 text-amber-700">{historyError}</p>
        ) : groupedHistory.length === 0 ? (
          <div className="px-3 py-4 text-xs leading-5 text-slate-500">
            Your recent research cases will appear here.
          </div>
        ) : (
          <div className="space-y-4 pb-5">
            {groupedHistory.map(([label, conversations]) => (
              <div key={label}>
                <p className="px-3 pb-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <div className="space-y-0.5">
                  {conversations.map((conversation) => {
                    const active = conversation.conversation_id === activeConversationId;
                    return (
                      <button
                        key={conversation.conversation_id}
                        onClick={() => onSelectConversation(conversation.conversation_id)}
                        aria-current={active ? 'page' : undefined}
                        className={`group flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                          active
                            ? 'bg-white font-medium text-emerald-950 shadow-sm'
                            : 'text-slate-600 hover:bg-white/70 hover:text-emerald-950'
                        }`}
                      >
                        <MessageSquare size={14} className={active ? 'text-emerald-800' : 'text-slate-400'} />
                        <span className="min-w-0 flex-1 truncate">{conversation.title || 'Untitled case'}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Bottom Actions */}
      <div className="p-4">
        <div className="pt-4 border-t border-slate-200 flex flex-col space-y-1">
          <button onClick={onOpenSettings} className="flex items-center space-x-3 px-2 py-2 text-sm text-slate-600 transition-colors hover:text-emerald-950">
            <Settings size={18} className="text-slate-400" />
            <span className="font-medium tracking-wide">SETTINGS</span>
          </button>
          <Link href="/support" className="flex items-center space-x-3 px-2 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors">
            <HelpCircle size={18} className="text-slate-400" />
            <span className="font-medium tracking-wide">SUPPORT</span>
          </Link>
        </div>
      </div>
    </aside>
  );
}
