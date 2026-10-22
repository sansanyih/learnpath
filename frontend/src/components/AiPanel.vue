<script setup lang="ts">
import DOMPurify from "dompurify";
import { marked } from "marked";
import { computed, nextTick, onUnmounted, ref, watch } from "vue";

import { chatApi } from "@/api/chat";
import type { AnnotationItem } from "@/api/chat";
import { useSSE } from "@/composables/useSSE";

interface Source {
  title: string;
  url: string;
  snippet?: string;
}

interface ChatItem {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: boolean;
}

const props = defineProps<{
  scope: "chapter" | "task";
  contextId: string;
  suggestions?: string[];
}>();

const sse = useSSE();
const open = ref(true);
const input = ref("");
const messages = ref<ChatItem[]>([]);
const annotations = ref<AnnotationItem[]>([]);
const annotationSaved = ref<Record<number, boolean>>({});
const showAnnotations = ref(false);
const toolStatus = ref("");
const errorText = ref("");
const listRef = ref<HTMLElement | null>(null);

const defaultSuggestions = [
  "这节先看哪个文件？",
  "用一句话解释核心概念",
  "给我一个最小可运行例子",
  "这里最容易踩的坑是什么？",
];
const prompts = computed(() => props.suggestions?.length ? props.suggestions : defaultSuggestions);

function render(content: string): string {
  try {
    return DOMPurify.sanitize(marked.parse(content) as string);
  } catch {
    return DOMPurify.sanitize(content);
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
}

async function loadHistory(): Promise<void> {
  if (!props.contextId) return;
  try {
    const [history, notes] = await Promise.all([
      chatApi.history(props.scope, props.contextId),
      chatApi.annotations(props.scope, props.contextId),
    ]);
    messages.value = history.items.map((item) => ({
      role: item.role,
      content: item.content,
      sources: item.sources,
    }));
    annotations.value = notes.items;
    await scrollToBottom();
  } catch {
    // 历史加载失败不阻塞提问
  }
}

async function saveAnnotation(item: ChatItem, index: number): Promise<void> {
  if (!props.contextId || annotationSaved.value[index]) return;
  try {
    await chatApi.saveAnnotation(props.scope, props.contextId, item.content);
    annotationSaved.value = { ...annotationSaved.value, [index]: true };
    const notes = await chatApi.annotations(props.scope, props.contextId);
    annotations.value = notes.items;
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : "保存批注失败";
  }
}

watch(
  () => [props.scope, props.contextId],
  () => {
    void loadHistory();
  },
  { immediate: true },
);

watch(
  open,
  (value) => {
    document.body.classList.toggle("ai-panel-open", value);
  },
  { immediate: true },
);

onUnmounted(() => {
  document.body.classList.remove("ai-panel-open");
});

async function ask(raw?: string): Promise<void> {
  const question = (raw ?? input.value).trim();
  if (!question || sse.streaming.value || !props.contextId) return;

  const history = messages.value.slice(-6).map((item) => ({ role: item.role, content: item.content }));
  messages.value.push({ role: "user", content: question });
  input.value = "";
  errorText.value = "";
  toolStatus.value = "正在思考…";
  await scrollToBottom();

  try {
    await sse.stream(
      "/api/chat/stream",
      { scope: props.scope, context_id: props.contextId, question, history },
      {
        status: () => {
          toolStatus.value = "正在思考…";
        },
        tool_call: (data) => {
          const name = (data as { name?: string }).name;
          toolStatus.value = name === "search_web" ? "正在搜索资料…" : "正在打开网页…";
        },
        tool_result: (data) => {
          const payload = data as { ok?: boolean; summary?: string };
          toolStatus.value = payload.ok === false ? `工具失败：${payload.summary ?? ""}` : payload.summary ?? "";
        },
        answer: (data) => {
          const payload = data as { content?: string; sources?: Source[] };
          messages.value.push({
            role: "assistant",
            content: payload.content ?? "",
            sources: payload.sources ?? [],
          });
          void scrollToBottom();
        },
        done: () => {
          toolStatus.value = "";
        },
        error: (data) => {
          errorText.value = (data as { message?: string }).message ?? "回答失败";
          toolStatus.value = "";
        },
      },
    );
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : "回答失败";
    toolStatus.value = "";
  }
}
</script>

<template>
  <Teleport to="body">
    <button v-if="!open" class="ai-fab" type="button" @click="open = true">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/></svg>
      问 AI
    </button>

    <aside v-if="open" class="ai-panel">
      <div class="ai-head">
        <div>
          <div class="eyebrow">AI 助手 · Agent</div>
          <div class="ai-title">{{ scope === "chapter" ? "就这一章提问" : "就这个任务提问" }}</div>
        </div>
        <button class="btn btn-sm btn-ghost" type="button" @click="open = false">关闭</button>
      </div>

      <div ref="listRef" class="ai-list">
        <div v-if="!messages.length && !toolStatus" class="ai-empty">
          <p>可以让我联网查官方文档、解释这段代码、给最小例子。</p>
          <div class="ai-suggestions">
            <button v-for="item in prompts" :key="item" class="chip" type="button" @click="ask(item)">{{ item }}</button>
          </div>
        </div>

        <div v-for="(item, index) in messages" :key="index" class="ai-msg" :class="`is-${item.role}`">
          <div class="ai-role">{{ item.role === "user" ? "你" : "AI" }}</div>
          <div v-if="item.role === 'assistant'" class="ai-content markdown" v-html="render(item.content)" />
          <div v-else class="ai-content">{{ item.content }}</div>
          <div v-if="item.sources?.length" class="ai-sources">
            <a
              v-for="source in item.sources"
              :key="source.url"
              :href="source.url"
              target="_blank"
              rel="noopener noreferrer"
              class="ai-source"
            >
              {{ source.title || source.url }}
            </a>
          </div>
          <button
            v-if="item.role === 'assistant'"
            class="ai-note"
            type="button"
            @click="saveAnnotation(item, index)"
          >
            {{ annotationSaved[index] ? "已存批注" : "存为批注" }}
          </button>
        </div>

        <div v-if="toolStatus" class="ai-thinking">
          <span class="ai-dot"></span>{{ toolStatus }}
        </div>
        <div v-if="errorText" class="ai-error">{{ errorText }}</div>
      </div>

      <div v-if="annotations.length" class="ai-notes">
        <button class="ai-notes-toggle" type="button" @click="showAnnotations = !showAnnotations">
          我的批注 · {{ annotations.length }} {{ showAnnotations ? "▾" : "▸" }}
        </button>
        <div v-if="showAnnotations" class="ai-notes-list">
          <p v-for="note in annotations" :key="note.id">{{ note.content }}</p>
        </div>
      </div>

      <div class="ai-input">
        <textarea
          v-model="input"
          rows="2"
          placeholder="问这一章：这段代码为什么这么写？"
          @keydown.enter.exact.prevent="ask()"
        ></textarea>
        <button class="btn btn-sm btn-primary" type="button" :disabled="sse.streaming.value || !input.trim()" @click="ask()">
          {{ sse.streaming.value ? "回答中…" : "发送" }}
        </button>
      </div>
    </aside>
  </Teleport>
</template>

<style scoped>
.ai-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 80;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid var(--ink);
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 10px 30px rgba(20, 28, 40, 0.22);
}

.ai-fab:hover {
  background: var(--blue);
  border-color: var(--blue);
}

.ai-panel {
  position: fixed;
  right: 24px;
  top: 76px;
  bottom: 24px;
  z-index: 80;
  width: min(380px, calc(100vw - 32px));
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--paper);
  box-shadow: 0 24px 80px rgba(20, 28, 40, 0.22);
  overflow: hidden;
}

.ai-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--line);
}

.ai-title {
  margin-top: 4px;
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--ink);
}

.ai-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  background: var(--surface);
}

.ai-empty {
  font-size: 13px;
  line-height: 1.7;
  color: var(--muted);
}

.ai-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.ai-suggestions .chip {
  text-decoration: none;
  cursor: pointer;
}

.ai-msg {
  margin-bottom: 14px;
  font-size: 13.5px;
  line-height: 1.75;
}

.ai-role {
  margin-bottom: 3px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.08em;
  color: var(--faint);
}

.ai-msg.is-user .ai-content {
  padding: 8px 11px;
  border-radius: 9px;
  background: var(--paper-2);
  color: var(--ink);
}

.ai-content :deep(p) {
  margin: 0 0 8px;
}

.ai-content :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 4px;
}

.ai-content :deep(pre) {
  margin: 0 0 8px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--paper-2);
  overflow: auto;
}

.ai-content :deep(pre code) {
  border: 0;
  background: transparent;
  padding: 0;
}

.ai-content :deep(a) {
  color: var(--blue);
}

.ai-content :deep(ul),
.ai-content :deep(ol) {
  padding-left: 18px;
  margin: 0 0 8px;
}

.ai-sources {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.ai-source {
  font-size: 11.5px;
  color: var(--blue);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-source:hover {
  text-decoration: underline;
}

.ai-thinking {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--muted);
}

.ai-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--blue);
  animation: ai-pulse 1s ease-in-out infinite;
}

@keyframes ai-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.ai-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--rose);
}

.ai-input {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--line);
  background: var(--paper);
}

.ai-input textarea {
  flex: 1;
  resize: none;
  font: inherit;
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  color: var(--ink);
}

.ai-note {
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 11px;
  color: var(--muted);
  text-decoration: underline;
  cursor: pointer;
}

.ai-notes {
  max-height: 130px;
  overflow-y: auto;
  padding: 8px 14px;
  border-top: 1px solid var(--line);
  background: var(--paper);
}

.ai-notes-toggle {
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 11.5px;
  color: var(--muted);
  cursor: pointer;
}

.ai-notes-list p {
  margin: 6px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--ink-2);
}

@media (max-width: 640px) {
  .ai-panel {
    right: 12px;
    top: 64px;
    bottom: 12px;
    width: calc(100vw - 24px);
  }
}
</style>

<style>
@media (min-width: 1180px) {
  body.ai-panel-open .main {
    margin-right: 404px;
    transition: margin-right 0.18s ease;
  }
}
</style>
