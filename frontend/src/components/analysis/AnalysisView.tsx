import { useState, useCallback, Dispatch, SetStateAction } from 'react';
import { Dropzone } from './Dropzone';
import { WorkspaceList } from './WorkspaceList';
import { LegalAI, type ChatCitation } from '@/lib/api';
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

    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);
    onCitationsUpdate([]);

    try {
      const resp = await LegalAI.chat(text, 'document', activeWorkspaceId);
      
      const aiMsg: ChatMessage = { 
        role: 'assistant', 
        content: resp.answer || "I could not find an answer in the document.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      
      setMessages(prev => [...prev, aiMsg]);
      
      if (resp.citations) {
        onCitationsUpdate(resp.citations);
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `**Error:** An exception occurred contacting the backend.\n\`\`\`text\n${e.message}\n\`\`\``, timestamp: new Date().toLocaleTimeString() }]);
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
          
          <ChatArea messages={messages} />
          
          {isThinking && (
            <div className="absolute bottom-28 right-1/2 translate-x-1/2 bg-white px-4 py-2 shadow-lg rounded-full border border-slate-200 flex items-center space-x-2 z-10 animate-fade-in">
              <span className="w-2 h-2 rounded-full bg-slate-900 animate-bounce"></span>
              <span className="w-2 h-2 rounded-full bg-slate-700 animate-bounce" style={{ animationDelay: '0.1s' }}></span>
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: '0.2s' }}></span>
              <span className="text-xs font-semibold text-slate-800 tracking-wider uppercase ml-1">Analyzing...</span>
            </div>
          )}
          
          <InputBox onSend={handleSend} disabled={isThinking} />
        </div>
      )}
    </div>
  );
}
