import { ref } from "vue";

import { getGuestId } from "@/api/guest";
import { API_BASE, getToken } from "@/api/request";

type EventHandler = (data: unknown) => void;

export function useSSE() {
  const streaming = ref(false);
  let controller: AbortController | null = null;

  async function stream(
    path: string,
    body: unknown,
    handlers: Record<string, EventHandler>,
  ): Promise<void> {
    controller?.abort();
    controller = new AbortController();
    streaming.value = true;

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Guest-Id": getGuestId(),
      };
      const token = getToken();
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok) {
        let message = `生成失败（${response.status}）`;
        try {
          const payload = (await response.json()) as { error?: { message?: string } };
          message = payload?.error?.message ?? message;
        } catch {
          // keep the fallback message
        }
        throw new Error(message);
      }
      if (!response.body) {
        throw new Error("连接中断，请重试");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let index = buffer.indexOf("\n\n");
        while (index >= 0) {
          const frame = buffer.slice(0, index);
          buffer = buffer.slice(index + 2);
          dispatch(frame, handlers);
          index = buffer.indexOf("\n\n");
        }
      }
    } finally {
      streaming.value = false;
      controller = null;
    }
  }

  function stop(): void {
    controller?.abort();
    streaming.value = false;
  }

  return { streaming, stream, stop };
}

function dispatch(frame: string, handlers: Record<string, EventHandler>): void {
  if (!frame.trim() || frame.startsWith(":")) return;

  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) return;

  try {
    handlers[event]?.(JSON.parse(dataLines.join("\n")));
  } catch (error) {
    console.error("invalid SSE payload", error);
  }
}
