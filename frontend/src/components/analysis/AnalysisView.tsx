import { useState, useCallback, Dispatch, SetStateAction } from 'react';
import { Dropzone } from './Dropzone';
import { WorkspaceList } from './WorkspaceList';
import { LegalAI, type ChatCitation, type ResearchStatus } from '@/lib/api';
import { ChatArea, type ChatMessage } from '../knowledge/ChatArea';
import { InputBox } from '../knowledge/InputBox';

export interface WorkspaceDoc {
  id: string;
  name: string;
  size: string;
  added: string;
  status: 'PROCESSING' | 'ANALYZED' | 'ERROR';
  color: string;
  iconColor: string;
  border: string;
}

interface Props {
  workspaces: WorkspaceDoc[];
  setWorkspaces: Dispatch<SetStateAction<WorkspaceDoc[]>>;
  activeWorkspaceId: string | null;
  setActiveWorkspaceId: Dispatch<SetStateAction<string | null>>;
  onCitationsUpdate: Dispatch<SetStateAction<ChatCitation[]>>;
}

export function AnalysisView({ workspaces, setWorkspaces, activeWorkspaceId, setActiveWorkspaceId, onCitationsUpdate }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [researchSteps, setResearchSteps] = useState<ResearchStatus[]>([]);

  const handleFileUpload = useCallback(async (file: File) => {
    const docId = `temp-${Date.now()}`;
    const newDoc: WorkspaceDoc = {
      id: docId,
      name: file.name,
      size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
      added: 'Just now',
      status: 'PROCESSING',
      color: 'bg-slate-100 text-slate-600',
      iconColor: 'text-slate-500 bg-slate-100',
      border: 'border-l-slate-300'
    };
    
    setWorkspaces(prev => [newDoc, ...prev]);

    try {
      const result = await LegalAI.upload(file);
      
      setWorkspaces(prev => prev.map(w => w.id === docId ? {
        ...w,
        id: result.upload_id || docId,
        status: 'ANALYZED',
        color: 'bg-[#f4f6f2] text-emerald-900',
        iconColor: 'text-emerald-900 bg-[#f4f6f2]',
        border: 'border-l-emerald-900'
      } : w));
      
      if (result.upload_id) {
        setActiveWorkspaceId(result.upload_id);
      }
    } catch (e: any) {
      setWorkspaces(prev => prev.map(w => w.id === docId ? {
        ...w,
        status: 'ERROR',
        color: 'bg-red-100 text-red-800',
        iconColor: 'text-red-600 bg-red-50',
        border: 'border-l-red-600'
      } : w));
    }
  }, [setWorkspaces, setActiveWorkspaceId]);

  const handleSend = async (text: string) => {
    if (!activeWorkspaceId) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: ChatMessage = { role: 'user', content: text, timestamp };
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', timestamp, isStreaming: true };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsThinking(true);
    setResearchSteps([]);
    onCitationsUpdate([]);

    try {
      const resp = await LegalAI.chatStream(text, 'document', activeWorkspaceId, undefined, {
        onStatus: (status) => setResearchSteps(previous => [...previous, status]),
        onToken: (token) => setMessages(previous => previous.map((message, index) => (
          index === previous.length - 1 ? { ...message, content: message.content + token } : message
        ))),
      });
      setMessages(previous => previous.map((message, index) => (
        index === previous.length - 1
          ? { ...message, content: resp.answer || 'I could not find an answer in the document.', isStreaming: false }
          : message
      )));
      
      if (resp.citations) {
        onCitationsUpdate(resp.citations);
      }
    } catch (e: any) {
      const detail = e instanceof Error ? e.message : 'Unknown network error';
      setMessages(previous => previous.map((message, index) => (
        index === previous.length - 1 ? { ...message, content: `**Research interrupted.** ${detail}`, isStreaming: false } : message
      )));
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden bg-[#fafaf8]">
      {!activeWorkspaceId ? (
        <div className="flex-1 overflow-y-auto px-5 py-12 md:px-12 lg:px-16">
          <div className="mx-auto max-w-4xl w-full space-y-10">
            <div className="max-w-2xl">
              <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-800">Analysis mode</p>
              <h1 className="font-serif text-4xl leading-tight tracking-tight text-emerald-950 md:text-5xl">Analyze discovery documents with grounded evidence.</h1>
              <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">Upload a document for risk assessment, entity extraction, and cross-reference analysis — answers are grounded only in that file.</p>
            </div>

            <Dropzone onUpload={handleFileUpload} />

            <WorkspaceList workspaces={workspaces} activeWorkspaceId={activeWorkspaceId} onSelect={setActiveWorkspaceId} />
          </div>
        </div>
      ) : (
        <div className="flex h-full flex-1 flex-col overflow-hidden">
          <div className="z-10 flex items-center justify-between border-b border-slate-200 bg-[#fafaf8] p-4 shadow-sm">
            <div className="flex items-center space-x-3">
              <span className="font-serif text-lg text-emerald-950">Document Chat: {workspaces.find(w => w.id === activeWorkspaceId)?.name}</span>
            </div>
            <button onClick={() => setActiveWorkspaceId(null)} className="text-sm font-semibold text-slate-500 transition hover:text-emerald-950">
              Back to Overview
            </button>
          </div>

          <ChatArea messages={messages} researchSteps={researchSteps} isResearching={isThinking} />

          <InputBox onSend={handleSend} disabled={isThinking} />
        </div>
      )}
    </div>
  );
}
