import type { ChatMessage } from '@/components/knowledge/ChatArea';
import type { ChatCitation, HistoryResultItem } from './api';

const HISTORY_PREFIX = 'dj_conversation_history';
const MAX_STORED_CONVERSATIONS = 30;

export interface ConversationSnapshot extends HistoryResultItem {
  messages: ChatMessage[];
  citations: ChatCitation[];
}

function storageKey(scope: string): string {
  return `${HISTORY_PREFIX}:${scope}`;
}

export function readConversationSnapshots(scope: string): ConversationSnapshot[] {
  if (typeof window === 'undefined') return [];

  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey(scope)) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is ConversationSnapshot => (
        typeof item?.conversation_id === 'string'
        && typeof item?.updated_at === 'string'
        && Array.isArray(item?.messages)
      ))
      .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  } catch {
    return [];
  }
}

export function saveConversationSnapshot(scope: string, snapshot: ConversationSnapshot): void {
  if (typeof window === 'undefined') return;

  const existing = readConversationSnapshots(scope).filter(
    (item) => item.conversation_id !== snapshot.conversation_id,
  );
  const next = [snapshot, ...existing].slice(0, MAX_STORED_CONVERSATIONS);

  try {
    localStorage.setItem(storageKey(scope), JSON.stringify(next));
  } catch {
    // Keep a smaller cache when the browser's storage quota is nearly full.
    try {
      localStorage.setItem(storageKey(scope), JSON.stringify(next.slice(0, 10)));
    } catch {
      // History persistence is best-effort and must never interrupt chat.
    }
  }
}

export function getConversationSnapshot(
  scope: string,
  conversationId: string,
): ConversationSnapshot | undefined {
  return readConversationSnapshots(scope).find(
    (item) => item.conversation_id === conversationId,
  );
}

export function mergeConversationSummaries(
  primary: HistoryResultItem[],
  cached: ConversationSnapshot[],
): HistoryResultItem[] {
  const byId = new Map<string, HistoryResultItem>();
  [...cached, ...primary].forEach((item) => byId.set(item.conversation_id, {
    conversation_id: item.conversation_id,
    title: item.title,
    mode: item.mode,
    updated_at: item.updated_at,
  }));
  return Array.from(byId.values()).sort(
    (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
  );
}
