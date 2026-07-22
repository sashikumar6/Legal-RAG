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
        color: 'bg-orange-100 text-orange-800',
        iconColor: 'text-orange-600 bg-orange-50',
        border: 'border-l-orange-600'
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
    <div className="flex-1 flex flex-col bg-slate-50 relative overflow-hidden">
      {!activeWorkspaceId ? (
        <div className="flex-1 overflow-y-auto px-12 pt-16 pb-8">
          <div className="max-w-4xl mx-auto w-full space-y-12">
            <div>
              <h2 className="text-4xl font-bold tracking-tight text-slate-900 flex items-center space-x-3 mb-2">
                <span className="w-1 h-8 bg-slate-600 inline-block rounded-full mr-2"></span>
                Analysis Mode
              </h2>
              <p className="text-xl text-slate-600 font-medium">Upload your discovery documents for AI-driven risk assessment, entity extraction, and cross-reference analysis.</p>
            </div>

            <Dropzone onUpload={handleFileUpload} />
            
            <WorkspaceList workspaces={workspaces} activeWorkspaceId={activeWorkspaceId} onSelect={setActiveWorkspaceId} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          <div className="p-4 bg-white border-b border-slate-200 shadow-sm flex items-center justify-between z-10">
            <div className="flex items-center space-x-3">
              <span className="font-bold text-slate-800">Document Chat: {workspaces.find(w => w.id === activeWorkspaceId)?.name}</span>
            </div>
            <button onClick={() => setActiveWorkspaceId(null)} className="text-sm font-semibold text-slate-500 hover:text-slate-800">
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
