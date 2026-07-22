'use client';

import { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { KnowledgeView } from '@/components/knowledge/KnowledgeView';
import { KnowledgePanel } from '@/components/knowledge/KnowledgePanel';
import { AnalysisView, type WorkspaceDoc } from '@/components/analysis/AnalysisView';
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel';
import { LegalAI, type ChatCitation, type HistoryResultItem } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import {
  getConversationSnapshot,
  mergeConversationSummaries,
  readConversationSnapshots,
  saveConversationSnapshot,
  type ConversationSnapshot,
} from '@/lib/history';
import type { ChatMessage } from '@/components/knowledge/ChatArea';

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [mode, setMode] = useState<'knowledge' | 'analysis'>('knowledge');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [citations, setCitations] = useState<ChatCitation[]>([]);
  const [caseKey, setCaseKey] = useState(0);
  const [loadedConversation, setLoadedConversation] = useState<{ id: string; messages: ChatMessage[] } | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryResultItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);

  // Analysis state
  const [workspaces, setWorkspaces] = useState<WorkspaceDoc[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [analysisCitations, setAnalysisCitations] = useState<ChatCitation[]>([]);
  const historyScope = user?.id || 'anonymous';

  useEffect(() => {
    setActiveConversationId(localStorage.getItem('dj_active_conversation_id'));
  }, []);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;
    const cached = readConversationSnapshots(historyScope);
    setHistoryLoading(true);
    setHistoryError(null);

    if (!user) {
      setHistory(mergeConversationSummaries([], cached));
      setHistoryLoading(false);
      return;
    }

    LegalAI.listHistory()
      .then((response) => {
        if (!cancelled) setHistory(mergeConversationSummaries(response.results, cached));
      })
      .catch(() => {
        if (cancelled) return;
        setHistory(mergeConversationSummaries([], cached));
        if (cached.length === 0) setHistoryError('Saved case history is temporarily unavailable.');
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, historyRefreshToken, historyScope, user]);

  const handleNewCase = () => {
    setMode('knowledge');
    setCitations([]);
    setWorkspaces([]);
    setActiveWorkspaceId(null);
    setAnalysisCitations([]);
    setLoadedConversation(null);
    setActiveConversationId(null);
    localStorage.removeItem('dj_active_conversation_id');
    localStorage.removeItem('dj_active_messages');
    setCaseKey(k => k + 1);
  };

  const handleLoadConversation = (
    conversationId: string,
    messages: ChatMessage[],
    restoredCitations: ChatCitation[] = [],
  ) => {
    setMode('knowledge');
    setCitations(restoredCitations);
    setLoadedConversation({ id: conversationId, messages });
    setActiveConversationId(conversationId);
    localStorage.setItem('dj_active_conversation_id', conversationId);
    localStorage.setItem('dj_active_messages', JSON.stringify(messages));
    setCaseKey(k => k + 1);
  };

  const handleConversationUpdated = (conversation: ConversationSnapshot) => {
    saveConversationSnapshot(historyScope, conversation);
    setActiveConversationId(conversation.conversation_id);
    setHistory((previous) => mergeConversationSummaries(
      [conversation, ...previous],
      readConversationSnapshots(historyScope),
    ));
    if (user) setHistoryRefreshToken((token) => token + 1);
  };

  const handleSelectConversation = async (conversationId: string) => {
    if (conversationId === activeConversationId) return;
    setHistoryError(null);

    const cached = getConversationSnapshot(historyScope, conversationId);
    if (cached) {
      handleLoadConversation(conversationId, cached.messages, cached.citations);
      return;
    }

    if (!user) {
      setHistoryError('This local case is no longer available in this browser.');
      return;
    }

    try {
      const detail = await LegalAI.getConversation(conversationId);
      const messages: ChatMessage[] = detail.messages.map((message) => ({
        role: message.role as 'user' | 'assistant',
        content: message.content,
        timestamp: new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }));
      const restoredCitations = [...detail.messages]
        .reverse()
        .find((message) => message.role === 'assistant' && message.citations.length > 0)
        ?.citations || [];
      const snapshot: ConversationSnapshot = {
        conversation_id: detail.conversation_id,
        title: detail.title,
        mode: detail.mode,
        updated_at: history.find((item) => item.conversation_id === conversationId)?.updated_at || new Date().toISOString(),
        messages,
        citations: restoredCitations,
      };
      saveConversationSnapshot(historyScope, snapshot);
      handleLoadConversation(conversationId, messages, restoredCitations);
    } catch {
      setHistoryError('That saved case could not be opened. Please try again.');
    }
  };

  return (
    <div className="flex h-screen bg-white font-sans text-slate-900 overflow-hidden selection:bg-navy-200 selection:text-navy-900">
      <Sidebar
        currentMode={mode}
        setMode={setMode}
        onNewCase={handleNewCase}
        onOpenSettings={() => setSettingsOpen(true)}
        history={history}
        historyLoading={historyLoading}
        historyError={historyError}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
      />
      
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        <Header
          currentMode={mode}
          onModeChange={setMode}
          onLoadConversation={handleLoadConversation}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        <div className="flex-1 flex min-h-0">
          {mode === 'knowledge' ? (
            <>
              <KnowledgeView
                key={caseKey}
                onCitationsUpdate={setCitations}
                onConversationUpdated={handleConversationUpdated}
                initialConversationId={loadedConversation?.id}
                initialMessages={loadedConversation?.messages}
              />
              <KnowledgePanel citations={citations} />
            </>
          ) : (
            <>
              <AnalysisView 
                workspaces={workspaces}
                setWorkspaces={setWorkspaces}
                activeWorkspaceId={activeWorkspaceId}
                setActiveWorkspaceId={setActiveWorkspaceId}
                onCitationsUpdate={setAnalysisCitations}
              />
              <AnalysisPanel 
                workspaces={workspaces}
                setWorkspaces={setWorkspaces}
                activeWorkspaceId={activeWorkspaceId}
                citations={analysisCitations}
              />
            </>
          )}
        </div>
      </div>

      {settingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 p-5" role="dialog" aria-modal="true" aria-labelledby="settings-title">
          <div className="w-full max-w-md border border-slate-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-800">Workspace</p>
                <h2 id="settings-title" className="mt-1 font-serif text-2xl text-emerald-950">Research settings</h2>
              </div>
              <button onClick={() => setSettingsOpen(false)} className="text-sm text-slate-500 hover:text-slate-900">Close</button>
            </div>
            <p className="mt-5 text-sm leading-6 text-slate-600">Conversation history stays in this browser unless you sign in. Clearing it only removes the local active session.</p>
            <button
              onClick={() => { handleNewCase(); setSettingsOpen(false); }}
              className="mt-6 w-full border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-emerald-900 hover:text-emerald-950"
            >
              Clear local research session
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
