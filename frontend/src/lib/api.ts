export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface ChatCitation {
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
}

export interface UploadResponse {
  upload_id: string;
  file_name: string;
  file_type: string;
  status: string;
  chunk_count: number;
  message: string;
}

export const LegalAI = {
  chat: async (query: string, mode: 'federal' | 'document' | 'auto' = 'auto', upload_id?: string): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, mode, upload_id }),
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`Chat API Error: ${res.statusText} - ${error}`);
    }

    return res.json();
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
  }
};
