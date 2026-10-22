<script setup lang="ts">
import DOMPurify from "dompurify";
import { marked } from "marked";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { reposApi } from "@/api/repos";
import type { ChapterDetail, ChapterFile, RepoSource } from "@/api/repoTypes";
import { chapterQuizApi } from "@/api/chapterQuiz";
import type { ChapterQuizLatest } from "@/api/chapterQuizTypes";
import { chapterStatusApi } from "@/api/review";
import AiPanel from "@/components/AiPanel.vue";
import ChapterQuizPanel from "@/components/ChapterQuizPanel.vue";

type TabKey = "concept" | "breakdown" | "code" | "quiz" | "review";

const route = useRoute();

const chapter = ref<ChapterDetail | null>(null);
const repos = ref<RepoSource[]>([]);
const content = ref("");
const loading = ref(true);
const generating = ref(false);
const error = ref("");

const tab = ref<TabKey>("concept");
const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "concept", label: "概念" },
  { key: "breakdown", label: "拆解" },
  { key: "code", label: "代码" },
  { key: "quiz", label: "测验" },
  { key: "review", label: "复习" },
];

const files = ref<ChapterFile[]>([]);
const filesLoading = ref(false);
const filesError = ref("");
const activeFile = ref("");
const chapterStatus = ref("todo");
const statusSaving = ref(false);
const latestQuiz = ref<ChapterQuizLatest | null>(null);
const latestLoading = ref(false);

const statuses = [
  { key: "todo", label: "未开始" },
  { key: "learning", label: "学习中" },
  { key: "review", label: "需复习" },
  { key: "mastered", label: "已掌握" },
];

const currentRepo = computed(
  () => repos.value.find((repo) => repo.chapters.some((item) => item.id === chapter.value?.id)) ?? null,
);

const activeContent = computed(
  () => files.value.find((file) => file.path === activeFile.value)?.content ?? "",
);
const codeLines = computed(() => activeContent.value.split("\n"));

const currentIndex = computed(
  () => currentRepo.value?.chapters.findIndex((item) => item.id === chapter.value?.id) ?? -1,
);
const prevChapter = computed(() =>
  currentIndex.value > 0 ? currentRepo.value?.chapters[currentIndex.value - 1] ?? null : null,
);
const nextChapter = computed(() => {
  const chapters = currentRepo.value?.chapters ?? [];
  return currentIndex.value >= 0 && currentIndex.value < chapters.length - 1
    ? chapters[currentIndex.value + 1]
    : null;
});

async function setStatus(status: string): Promise<void> {
  if (!chapter.value || statusSaving.value || chapterStatus.value === status) return;
  statusSaving.value = true;
  try {
    const result = await chapterStatusApi.set(chapter.value.id, status);
    chapterStatus.value = result.status;
  } finally {
    statusSaving.value = false;
  }
}

const html = computed(() => {
  if (!content.value) return "";
  try {
    return DOMPurify.sanitize(marked.parse(content.value) as string);
  } catch {
    return DOMPurify.sanitize(content.value);
  }
});

function selectTab(next: TabKey): void {
  tab.value = next;
  if (next === "code") void loadFiles();
  if (next === "review") void loadLatest();
}

async function loadLatest(): Promise<void> {
  if (!chapter.value) return;
  latestLoading.value = true;
  try {
    latestQuiz.value = await chapterQuizApi.latest(chapter.value.id);
  } catch {
    latestQuiz.value = null;
  } finally {
    latestLoading.value = false;
  }
}

async function onQuizSubmitted(): Promise<void> {
  await loadLatest();
  if (chapter.value) {
    try {
      chapterStatus.value = (await chapterStatusApi.get(chapter.value.id)).status;
    } catch {
      // 状态刷新失败不阻塞结果展示
    }
  }
}

async function loadFiles(): Promise<void> {
  if (!chapter.value || filesLoading.value || files.value.length) return;
  filesLoading.value = true;
  filesError.value = "";
  try {
    const data = await reposApi.chapterFiles(chapter.value.id);
    files.value = data.files;
    activeFile.value = data.files[0]?.path ?? "";
  } catch (err) {
    filesError.value = err instanceof Error ? err.message : "仓库文件读取失败";
  } finally {
    filesLoading.value = false;
  }
}

function openFile(path: string): void {
  activeFile.value = path;
  void selectTab("code");
}

async function load(): Promise<void> {
  const current = ++loadSeq;
  loading.value = true;
  error.value = "";
  generating.value = false;
  content.value = "";
  tab.value = "concept";
  files.value = [];
  filesError.value = "";
  activeFile.value = "";
  chapterStatus.value = "todo";
  latestQuiz.value = null;
  try {
    const data = await reposApi.chapter(String(route.params.chapterId));
    if (current !== loadSeq) return;
    chapter.value = data;
    try {
      const progress = await chapterStatusApi.get(data.id);
      if (current === loadSeq) chapterStatus.value = progress.status;
    } catch {
      // 状态读取失败时保持未开始
    }
    if (data.content_md) {
      content.value = data.content_md;
    } else {
      generating.value = true;
      const result = await reposApi.generateContent(data.id);
      if (current !== loadSeq) return;
      content.value = result.content_md;
    }
    try {
      const list = await reposApi.list(data.plan_id);
      if (current === loadSeq) repos.value = list;
    } catch {
      if (current === loadSeq) repos.value = [];
    }
  } catch (err) {
    if (current === loadSeq) {
      error.value = err instanceof Error ? err.message : "章节加载失败";
    }
  } finally {
    if (current === loadSeq) {
      loading.value = false;
      generating.value = false;
    }
  }
}

let loadSeq = 0;

watch(
  () => [route.params.planId, route.params.chapterId],
  () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    void load();
  },
);

onMounted(load);
</script>

<template>
  <div class="app-shell">
    <aside class="rail">
      <router-link class="rail-logo" to="/" title="学径">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
      </router-link>
      <router-link class="rail-btn is-active" :to="`/plans/${chapter?.plan_id ?? ''}`" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </router-link>
      <span class="rail-spacer"></span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">仓库章节</span>
          <span class="chip" style="height:20px;font-size:10.5px">{{ currentRepo?.chapters.length ?? 0 }} 章</span>
        </div>
        <div class="side-title" style="margin-top:8px">{{ currentRepo?.repo_full_name ?? "仓库" }}</div>
        <div class="side-meta">
          <span class="chip">{{ currentRepo?.ref ?? "main" }}</span>
        </div>
      </div>

      <div class="side-section">
        <div class="side-section-head"><span>章节</span><span>{{ currentRepo?.chapters.length ?? 0 }}</span></div>
        <div class="tree">
          <router-link
            v-for="item in currentRepo?.chapters ?? []"
            :key="item.id"
            class="tree-item"
            :class="{ 'is-active': item.id === chapter?.id }"
            :to="{ name: 'chapter', params: { planId: chapter?.plan_id, chapterId: item.id } }"
          >
            <span class="tree-seq">{{ String(item.seq).padStart(2, "0") }}</span>
            <span>{{ item.title }}</span>
          </router-link>
        </div>
      </div>

      <span class="rail-spacer" style="flex:none"></span>
      <router-link class="btn btn-sm" style="width:100%" :to="`/plans/${chapter?.plan_id ?? ''}`">返回计划</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <router-link :to="`/plans/${chapter?.plan_id ?? ''}`" style="color:var(--muted)">学习计划</router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <router-link
            :to="{ path: `/plans/${chapter?.plan_id ?? ''}`, hash: '#repos' }"
            style="color:var(--muted)"
          >
            仓库章节
          </router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ chapter?.title ?? "加载中…" }}</b>
        </div>
        <div class="topbar-actions">
          <router-link class="btn btn-sm btn-ghost" :to="`/plans/${chapter?.plan_id ?? ''}`">返回计划</router-link>
        </div>
      </div>

      <div class="content" v-reveal>
        <div v-if="loading" class="empty">正在读取章节…</div>

        <div v-else-if="error" class="card card-pad">
          <div class="eyebrow">加载失败</div>
          <p class="lead" style="margin:10px 0 16px">{{ error }}</p>
          <button class="btn" @click="load">重试</button>
          <router-link class="btn btn-ghost" :to="`/plans/${chapter?.plan_id ?? ''}`">返回计划</router-link>
        </div>

        <template v-else-if="chapter">
          <div class="eyebrow" style="margin-bottom:8px">REPO CHAPTER · 第 {{ String(chapter.seq).padStart(2, "0") }} 章</div>
          <h1 class="page-title" style="max-width:22em">{{ chapter.title }}</h1>
          <p class="lead" style="margin:12px 0 0;max-width:42em">{{ chapter.purpose }}</p>

          <div class="phase-chips" style="margin-top:14px">
            <span v-for="concept in chapter.concepts" :key="concept" class="chip">{{ concept }}</span>
          </div>

          <div class="repo-chips" style="margin:16px 0 8px">
            <span v-for="file in chapter.files" :key="file" class="repo-chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v5h5"/><path d="M6 3h8l5 5v13H6z"/></svg>
              {{ file }}
            </span>
          </div>

          <div class="chapter-tabs">
            <button
              v-for="item in tabs"
              :key="item.key"
              class="chapter-tab"
              :class="{ 'is-active': tab === item.key }"
              type="button"
              @click="selectTab(item.key)"
            >
              {{ item.label }}
            </button>
          </div>

          <template v-if="tab === 'concept'">
            <div v-if="generating" class="inset" style="padding:12px 14px;margin:16px 0;font-size:13px;color:var(--muted)">
              正在根据这几个文件生成讲解，大约需要 5–10 秒…
            </div>
            <article v-if="html" class="md-body" v-html="html" />
          </template>

          <div v-else-if="tab === 'breakdown'" class="tab-panel">
            <section class="card card-pad">
              <div class="eyebrow" style="margin-bottom:10px">阅读顺序</div>
              <ol class="file-steps">
                <li v-for="(file, index) in chapter.files" :key="file">
                  <button class="file-step" type="button" @click="openFile(file)">
                    <span class="file-index">{{ String(index + 1).padStart(2, "0") }}</span>
                    <span class="mono">{{ file }}</span>
                    <span class="tiny muted">打开代码</span>
                  </button>
                </li>
              </ol>
            </section>
            <section class="card card-pad" style="margin-top:14px">
              <div class="eyebrow" style="margin-bottom:10px">本章要讲清的概念</div>
              <div class="phase-chips">
                <span v-for="concept in chapter.concepts" :key="concept" class="chip">{{ concept }}</span>
              </div>
            </section>
          </div>

          <div v-else-if="tab === 'code'" class="tab-panel">
            <div v-if="filesLoading" class="empty" style="padding:40px 0">正在读取仓库文件…</div>
            <div v-else-if="filesError" class="card card-pad">{{ filesError }}</div>
            <div v-else-if="files.length" class="code-shell">
              <div class="code-filebar">
                <button
                  v-for="file in files"
                  :key="file.path"
                  class="code-file"
                  :class="{ 'is-active': file.path === activeFile }"
                  type="button"
                  @click="activeFile = file.path"
                >
                  {{ file.path }}
                </button>
              </div>
              <div class="code-view">
                <div v-for="(line, index) in codeLines" :key="index" class="code-line">
                  <span class="code-ln">{{ index + 1 }}</span>
                  <span class="code-text">{{ line || " " }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty" style="padding:40px 0">这一章没有可读取的文件。</div>
          </div>

          <div v-else-if="tab === 'quiz'" class="tab-panel">
            <ChapterQuizPanel :chapter-id="chapter.id" @submitted="onQuizSubmitted" />
          </div>

          <div v-else-if="tab === 'review'" class="tab-panel">
            <section class="card card-pad">
              <div class="eyebrow" style="margin-bottom:8px">复习</div>

              <div v-if="latestLoading" class="small muted" style="padding:12px 0">正在读取上次测验…</div>
              <template v-else-if="latestQuiz?.score !== null && latestQuiz?.score !== undefined">
                <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px">
                  <span style="font-family:var(--font-display);font-size:32px">{{ latestQuiz.score }}</span>
                  <span class="small muted">上次章节测验得分</span>
                  <button class="btn btn-sm" style="margin-left:auto" @click="tab = 'quiz'">再测一次</button>
                </div>
                <div v-if="latestQuiz.results.filter((item) => item.score < 70).length" class="small" style="line-height:1.8">
                  <b>需要回看：</b>
                  <ul style="margin:6px 0 0;padding-left:18px;color:var(--muted)">
                    <li v-for="item in latestQuiz.results.filter((entry) => entry.score < 70)" :key="item.quiz_id">
                      {{ item.question }}（{{ item.score }} 分）
                    </li>
                  </ul>
                </div>
                <p v-else class="small muted" style="margin:0">上次没有低分题，过一遍概念就可以。</p>
              </template>
              <template v-else>
                <p class="small muted" style="margin:0 0 12px;line-height:1.8">
                  还没测过这一章。先做一次章节测验，回来这里会显示薄弱题。
                </p>
                <button class="btn btn-sm btn-primary" @click="tab = 'quiz'">去章节测验</button>
              </template>

              <div class="phase-chips" style="margin-top:16px">
                <span v-for="concept in chapter.concepts" :key="concept" class="chip">{{ concept }}</span>
              </div>
            </section>
          </div>

          <div class="reader-bar">
            <div class="reader-status">
              <button
                v-for="item in statuses"
                :key="item.key"
                type="button"
                :class="{ 'is-active': chapterStatus === item.key }"
                :disabled="statusSaving"
                @click="setStatus(item.key)"
              >
                {{ item.label }}
              </button>
            </div>
            <div class="reader-nav">
              <router-link
                v-if="prevChapter"
                :to="{ name: 'chapter', params: { planId: chapter.plan_id, chapterId: prevChapter.id } }"
              >
                上一节
              </router-link>
              <span class="tiny muted">{{ currentIndex + 1 }} / {{ currentRepo?.chapters.length ?? 0 }}</span>
              <router-link
                v-if="nextChapter"
                :to="{ name: 'chapter', params: { planId: chapter.plan_id, chapterId: nextChapter.id } }"
              >
                下一节
              </router-link>
            </div>
          </div>
        </template>
      </div>
    </main>

    <AiPanel
      scope="chapter"
      :context-id="chapter?.id ?? ''"
      :suggestions="['这章先看哪个文件？', '用一句话解释核心概念', '给一个最小可运行例子', '这里最容易踩的坑是什么？']"
    />
  </div>
</template>

<style scoped>
.chapter-tabs {
  display: flex;
  gap: 2px;
  margin: 22px 0 0;
  border-bottom: 1px solid var(--line);
}

.chapter-tab {
  position: relative;
  padding: 9px 14px;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
}

.chapter-tab:hover {
  color: var(--ink);
}

.chapter-tab.is-active {
  color: var(--blue);
  font-weight: 600;
}

.chapter-tab.is-active::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: -1px;
  height: 2px;
  background: var(--blue);
}

.tab-panel {
  margin-top: 20px;
}

.file-steps {
  list-style: none;
  margin: 0;
  padding: 0;
}

.file-step {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 8px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  font: inherit;
  font-size: 13.5px;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}

.file-step:hover {
  background: var(--paper-2);
}

.file-index {
  flex: none;
  width: 24px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--faint);
}

.code-shell {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  overflow: hidden;
}

.code-filebar {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  padding: 6px 6px 0;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2);
}

.code-file {
  white-space: nowrap;
  padding: 7px 12px;
  border: 0;
  border-radius: 7px 7px 0 0;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--muted);
  cursor: pointer;
}

.code-file.is-active {
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-bottom-color: var(--surface);
}

.code-view {
  overflow: auto;
  padding: 12px 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.75;
}

.code-line {
  display: flex;
  min-width: max-content;
}

.code-ln {
  flex: none;
  width: 46px;
  padding-right: 14px;
  text-align: right;
  color: var(--faint);
  user-select: none;
}

.code-text {
  white-space: pre;
  color: var(--ink-2);
  padding-right: 18px;
}

.reader-bar {
  position: sticky;
  bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 28px 0 10px;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--paper);
  box-shadow: 0 8px 30px rgba(20, 28, 40, 0.06);
}

.reader-status {
  display: flex;
  gap: 3px;
}

.reader-status button {
  padding: 6px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}

.reader-status button.is-active {
  background: var(--blue-soft);
  color: var(--blue);
  font-weight: 600;
}

.reader-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.reader-nav a {
  color: var(--blue);
  text-decoration: none;
}

.reader-nav a:hover {
  text-decoration: underline;
}

.md-body {
  max-width: 780px;
  margin-top: 24px;
  font-size: 15.5px;
  line-height: 1.95;
  color: var(--ink-2);
}

.md-body :deep(h1),
.md-body :deep(h2) {
  font-family: var(--font-display);
  font-weight: 600;
  color: var(--ink);
  line-height: 1.35;
}

.md-body :deep(h1) {
  font-size: 28px;
  margin: 28px 0 12px;
}

.md-body :deep(h2) {
  font-size: 22px;
  margin: 30px 0 10px;
}

.md-body :deep(h3) {
  font-size: 17px;
  margin: 22px 0 8px;
  color: var(--ink);
}

.md-body :deep(p) {
  margin: 0 0 14px;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  padding-left: 22px;
  margin: 0 0 14px;
}

.md-body :deep(li) {
  margin: 4px 0;
}

.md-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 5px;
  padding: 1px 5px;
  color: var(--ink);
}

.md-body :deep(pre) {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 14px 16px;
  overflow: auto;
  margin: 0 0 16px;
}

.md-body :deep(pre code) {
  background: transparent;
  border: 0;
  padding: 0;
}

.md-body :deep(blockquote) {
  border-left: 2px solid var(--blue);
  background: var(--blue-soft);
  border-radius: 0 10px 10px 0;
  padding: 10px 14px;
  margin: 0 0 14px;
}

.md-body :deep(strong) {
  color: var(--ink);
}
</style>
