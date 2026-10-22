import { api } from "./request";

export interface ChatSource {
  title: string;
  url: string;
  snippet?: string;
}

export interface ChatHistoryItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  created_at: string;
}

export interface AnnotationItem {
  id: string;
  content: string;
  created_at: string;
}

export const chatApi = {
  history: (scope: "chapter" | "task", contextId: string) =>
    api.get<{ items: ChatHistoryItem[] }>(
      `/api/chat/history?scope=${scope}&context_id=${encodeURIComponent(contextId)}`,
    ),
  annotations: (scope: "chapter" | "task", contextId: string) =>
    api.get<{ items: AnnotationItem[] }>(
      `/api/annotations?scope=${scope}&context_id=${encodeURIComponent(contextId)}`,
    ),
  saveAnnotation: (scope: "chapter" | "task", contextId: string, content: string) =>
    api.post<{ id: string; created_at: string }>("/api/annotations", {
      scope,
      context_id: contextId,
      content,
    }),
};
