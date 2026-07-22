import { getOrCreateLocalSessionId } from './session';
import { supabase } from './supabaseClient';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface ChatCitation {
  document_id: string;
  canonical_citation: string;
  source_type: string;
  title_number?: number;
  section_number?: string;
  heading?: string;
  text: string;
  relevance_score: number;
}

export interface ChatResponse {
  answer: string;
  mode: string;
  confidence: string;
  confidence_score?: number;
  citations: ChatCitation[];
  session_id: string;
  conversation_id: string | null;
  clarification_needed?: boolean;
  clarification_question?: string | null;
}

export type ResearchStage =
  | 'preparing'
  | 'routing'
  | 'planning'
  | 'retrieving'
  | 'retrieved'
  | 'generating'
  | 'verifying'
  | 'fallback'
  | 'complete';

export interface ResearchStatus {
  stage: ResearchStage;
  label: string;
  detail?: string;
}

export interface ChatStreamHandlers {
  onStatus?: (status: ResearchStatus) => void;
  onToken?: (text: string) => void;
  onComplete?: (response: ChatResponse) => void;
}

export interface UploadResponse {
  upload_id: string;
  file_name: string;
  file_type: string;
  status: string;
  chunk_count: number;
  message: string;
}

export interface HistoryResultItem {
  conversation_id: string;
  title: string | null;
  mode: string | null;
  updated_at: string;
}

export interface HistorySearchResponse {
  query: string;
  results: HistoryResultItem[];
}

export interface ConversationListResponse {
  results: HistoryResultItem[];
  next_offset: number | null;
}

export interface HistoryMessageItem {
  role: string;
  content: string;
  mode: string | null;
  confidence: string | null;
  citations: ChatCitation[];
  created_at: string;
}

export interface ConversationDetailResponse {
  conversation_id: string;
  title: string | null;
  mode: string | null;
  messages: HistoryMessageItem[];
}

export const LegalAI = {
  chat: async (
    query: string,
    mode: 'federal' | 'document' | 'auto' = 'auto',
    upload_id?: string,
    conversation_id?: string | null,
  ): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(await authHeaders()),
      },
      body: JSON.stringify({
        query,
        mode,
        upload_id,
        session_id: getOrCreateLocalSessionId(),
        conversation_id: conversation_id || undefined,
      }),
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Chat API Error: ${res.statusText} - ${error}`);
    }

    return res.json();
  },

  chatStream: async (
    query: string,
    mode: 'federal' | 'document' | 'auto' = 'auto',
    upload_id?: string,
    conversation_id?: string | null,
    handlers: ChatStreamHandlers = {},
  ): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(await authHeaders()),
      },
      body: JSON.stringify({
        query,
        mode,
        upload_id,
        session_id: getOrCreateLocalSessionId(),
        conversation_id: conversation_id || undefined,
      }),
    });

    if (!res.ok || !res.body) {
      const error = await res.text();
      throw new Error(`Streaming chat API error: ${res.statusText} - ${error}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let completed: ChatResponse | null = null;

    const dispatch = (rawEvent: string) => {
      const lines = rawEvent.split('\n');
      const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message';
      const dataLine = lines.find((line) => line.startsWith('data:'));
      if (!dataLine) return;
      const data = JSON.parse(dataLine.slice(5).trim());
      if (event === 'status') handlers.onStatus?.(data as ResearchStatus);
      if (event === 'token') handlers.onToken?.(data.text || '');
      if (event === 'error') throw new Error(data.message || 'Streaming request failed');
      if (event === 'complete') {
        completed = data as ChatResponse;
        handlers.onComplete?.(completed);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';
      events.filter(Boolean).forEach(dispatch);
      if (done) break;
    }

    if (!completed) throw new Error('The stream ended before a final response was received.');
    return completed;
  },

  upload: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Upload API Error: ${res.statusText} - ${error}`);
    }

    return res.json();
  },

  searchHistory: async (query: string): Promise<HistorySearchResponse> => {
    const res = await fetch(`${API_BASE_URL}/history/search?q=${encodeURIComponent(query)}`, {
      headers: await authHeaders(),
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`History search error: ${res.statusText} - ${error}`);
    }

    return res.json();
  },

  listHistory: async (limit = 30, offset = 0): Promise<ConversationListResponse> => {
    const res = await fetch(`${API_BASE_URL}/history/conversations?limit=${limit}&offset=${offset}`, {
      headers: await authHeaders(),
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`List history error: ${res.statusText} - ${error}`);
    }

    return res.json();
  },

  getConversation: async (conversationId: string): Promise<ConversationDetailResponse> => {
    const res = await fetch(`${API_BASE_URL}/history/conversations/${conversationId}`, {
      headers: await authHeaders(),
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Get conversation error: ${res.statusText} - ${error}`);
    }

    return res.json();
  },
};
