'use client';

import { useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { KnowledgeView } from '@/components/knowledge/KnowledgeView';
import { KnowledgePanel } from '@/components/knowledge/KnowledgePanel';
import { AnalysisView, type WorkspaceDoc } from '@/components/analysis/AnalysisView';
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel';
import type { ChatCitation } from '@/lib/api';
import type { ChatMessage } from '@/components/knowledge/ChatArea';

export default function Home() {
  const [mode, setMode] = useState<'knowledge' | 'analysis'>('knowledge');
  const [citations, setCitations] = useState<ChatCitation[]>([]);
  const [caseKey, setCaseKey] = useState(0);
  const [loadedConversation, setLoadedConversation] = useState<{ id: string; messages: ChatMessage[] } | null>(null);

  // Analysis state
  const [workspaces, setWorkspaces] = useState<WorkspaceDoc[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [analysisCitations, setAnalysisCitations] = useState<ChatCitation[]>([]);

  const handleNewCase = () => {
    setMode('knowledge');
    setCitations([]);
    setWorkspaces([]);
    setActiveWorkspaceId(null);
    setAnalysisCitations([]);
    setLoadedConversation(null);
    localStorage.removeItem('dj_active_conversation_id');
    localStorage.removeItem('dj_active_messages');
    setCaseKey(k => k + 1);
  };

  const handleLoadConversation = (conversationId: string, messages: ChatMessage[]) => {
    setMode('knowledge');
    setCitations([]);
    setLoadedConversation({ id: conversationId, messages });
    localStorage.setItem('dj_active_conversation_id', conversationId);
    localStorage.setItem('dj_active_messages', JSON.stringify(messages));
    setCaseKey(k => k + 1);
  };

  return (
    <div className="flex h-screen bg-white font-sans text-slate-900 overflow-hidden selection:bg-navy-200 selection:text-navy-900">
      <Sidebar currentMode={mode} setMode={setMode} onNewCase={handleNewCase} />
      
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        <Header currentMode={mode} onLoadConversation={handleLoadConversation} />

        <div className="flex-1 flex min-h-0">
          {mode === 'knowledge' ? (
            <>
              <KnowledgeView
                key={caseKey}
                onCitationsUpdate={setCitations}
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
    </div>
  );
}
