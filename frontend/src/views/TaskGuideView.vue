<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { tasksApi } from "@/api/tasks";
import type { TaskDetail, TaskGuide } from "@/api/types";
import AiPanel from "@/components/AiPanel.vue";

const route = useRoute();
const router = useRouter();

const task = ref<TaskDetail | null>(null);
const guide = ref<TaskGuide | null>(null);
const loading = ref(true);
const generating = ref(false);
const saving = ref(false);
const error = ref("");
const actionError = ref("");

const typeLabel: Record<string, string> = {
  reading: "阅读",
  coding: "编码",
  quiz: "测验",
  review: "复习",
  writing: "写作",
};

function taskType(type: string): string {
  return typeLabel[type] ?? type;
}

function searchUrl(query: string): string {
  return `https://www.bing.com/search?q=${encodeURIComponent(query)}`;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  guide.value = null;
  try {
    const detail = await tasksApi.detail(String(route.params.taskId));
    task.value = detail;
    if (detail.guide) {
      guide.value = detail.guide;
    } else {
      generating.value = true;
      guide.value = await tasksApi.guide(detail.id);
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "学习建议加载失败";
  } finally {
    loading.value = false;
    generating.value = false;
  }
}

async function toggleDone(): Promise<void> {
  if (!task.value || saving.value) return;
  const next: "todo" | "done" = task.value.status === "done" ? "todo" : "done";
  saving.value = true;
  try {
    await tasksApi.updateStatus(task.value.id, next);
    task.value.status = next;
    const sibling = task.value.phase_tasks.find((item) => item.id === task.value?.id);
    if (sibling) sibling.status = next;
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : "更新失败";
  } finally {
    saving.value = false;
  }
}

function goTask(taskId: string): void {
  void router.push({ name: "task-guide", params: { planId: route.params.planId, taskId } });
}

watch(
  () => route.params.taskId,
  () => {
    window.scrollTo({ top: 0 });
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
      <router-link class="rail-btn is-active" :to="`/plans/${task?.plan_id ?? route.params.planId}`" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </router-link>
      <span class="rail-spacer"></span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">怎么学</span>
          <span class="chip" style="height:20px;font-size:10.5px">任务</span>
        </div>
        <div class="side-title" style="margin-top:8px">{{ task?.phase_title ?? "加载中…" }}</div>
        <div class="side-meta">
          <span class="chip">{{ task ? `${task.duration_min} 分钟` : "—" }}</span>
          <span class="chip">{{ task ? taskType(task.type) : "—" }}</span>
        </div>
      </div>

      <div class="side-section">
        <div class="side-section-head"><span>本阶段任务</span><span>{{ task?.phase_tasks.length ?? 0 }}</span></div>
        <div class="tree">
          <button
            v-for="(item, index) in task?.phase_tasks ?? []"
            :key="item.id"
            class="tree-item task-link"
            :class="{ 'is-active': item.id === task?.id }"
            type="button"
            @click="goTask(item.id)"
          >
            <span class="tree-seq">{{ item.status === "done" ? "✓" : String(index + 1).padStart(2, "0") }}</span>
            <span>{{ item.title }}</span>
          </button>
        </div>
      </div>

      <span class="rail-spacer" style="flex:none"></span>
      <router-link class="btn btn-sm" style="width:100%" :to="`/plans/${task?.plan_id ?? route.params.planId}`">返回计划</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <router-link :to="`/plans/${task?.plan_id ?? route.params.planId}`" style="color:var(--muted)">学习计划</router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <span>{{ task?.phase_title ?? "阶段" }}</span>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ task?.title ?? "加载中…" }}</b>
        </div>
        <div class="topbar-actions">
          <router-link class="btn btn-sm btn-ghost" :to="`/plans/${task?.plan_id ?? route.params.planId}`">返回计划</router-link>
        </div>
      </div>

      <div class="content" v-reveal>
        <div v-if="loading" class="empty">正在准备学习建议…</div>

        <div v-else-if="error && !task" class="card card-pad">
          <div class="eyebrow">加载失败</div>
          <p class="lead" style="margin:10px 0 16px">{{ error }}</p>
          <button class="btn" @click="load">重试</button>
          <router-link class="btn btn-ghost" :to="`/plans/${route.params.planId}`">返回计划</router-link>
        </div>

        <template v-else-if="task">
          <div class="eyebrow" style="margin-bottom:8px">TASK GUIDE · 怎么学</div>
          <h1 class="page-title" style="max-width:22em">{{ task.title }}</h1>

          <div class="page-sub" style="margin-top:14px">
            <span class="chip">{{ taskType(task.type) }}</span>
            <span class="chip">{{ task.duration_min }} 分钟</span>
            <span class="chip" :class="task.status === 'done' ? 'is-green' : ''">{{ task.status === "done" ? "已完成" : "待办" }}</span>
            <span class="chip">第 {{ task.day_offset + 1 }} 天</span>
          </div>

          <div v-if="task.acceptance" class="inset" style="margin:16px 0;padding:12px 14px;font-size:13px;color:var(--ink-2);line-height:1.75">
            <b style="font-size:11px;color:var(--muted);letter-spacing:.06em">验收标准</b>
            <div style="margin-top:4px">{{ task.acceptance }}</div>
          </div>

          <div v-if="generating" class="empty" style="padding:30px 0">正在生成学习步骤与资料…</div>
          <div v-else-if="error" class="small" style="color:var(--rose);display:flex;gap:10px;align-items:center">
            {{ error }}
            <button class="btn btn-sm btn-ghost" @click="load">重试</button>
          </div>

          <div v-else-if="guide" class="guide-body">
            <section>
              <h3>怎么学</h3>
              <ol class="guide-steps">
                <li v-for="step in guide.steps" :key="step">{{ step }}</li>
              </ol>
            </section>

            <section v-if="guide.concepts?.length">
              <h3>核心概念</h3>
              <div class="concept-grid">
                <div v-for="concept in guide.concepts" :key="concept.name" class="concept">
                  <div class="concept-name">{{ concept.name }}</div>
                  <p class="concept-text">{{ concept.explanation }}</p>
                </div>
              </div>
            </section>

            <section v-if="guide.code_examples?.length">
              <h3>最小代码</h3>
              <div v-for="example in guide.code_examples" :key="example.title" class="code-card">
                <div class="code-head">
                  <b>{{ example.title }}</b>
                  <span class="tiny muted">{{ example.language }}</span>
                </div>
                <div class="code-body">
                  <div v-for="(line, index) in example.code.split('\n')" :key="index" class="code-line">
                    <span class="code-ln">{{ index + 1 }}</span>
                    <span class="code-text">{{ line || " " }}</span>
                  </div>
                </div>
                <div v-if="example.note" class="tiny muted" style="padding:8px 12px">{{ example.note }}</div>
              </div>
            </section>

            <section>
              <h3>学习资料</h3>
              <a
                v-for="material in guide.materials"
                :key="material.title"
                class="guide-link"
                :href="material.url || searchUrl(material.title)"
                target="_blank"
                rel="noopener noreferrer"
              >
                <span>{{ material.title }}</span>
                <span class="tiny muted">{{ material.url ? material.kind : "搜索" }}</span>
              </a>
              <div class="guide-queries">
                <a
                  v-for="query in guide.search_queries"
                  :key="query"
                  class="chip"
                  :href="searchUrl(query)"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ query }}
                </a>
              </div>
            </section>

            <section>
              <h3>自测</h3>
              <ul class="guide-list">
                <li v-for="item in guide.self_check" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section v-if="guide.pitfalls.length">
              <h3>常见坑</h3>
              <ul class="guide-list">
                <li v-for="pitfall in guide.pitfalls" :key="pitfall">{{ pitfall }}</li>
              </ul>
            </section>

            <p class="tiny muted" style="margin:0 0 14px">资料由 AI 推荐，链接可能失效；优先看官方文档。</p>

            <div style="display:flex;gap:10px;align-items:center">
              <button class="btn btn-primary" :disabled="saving" @click="toggleDone">
                {{ saving ? "保存中…" : task.status === "done" ? "标记为待办" : "标记完成" }}
              </button>
              <router-link class="btn btn-ghost" :to="`/plans/${task.plan_id}`">返回计划</router-link>
            </div>
            <div v-if="actionError" class="small" style="color:var(--rose);margin-top:10px">{{ actionError }}</div>
          </div>
        </template>
      </div>
    </main>

    <AiPanel
      scope="task"
      :context-id="task?.id ?? ''"
      :suggestions="['这一步具体怎么做？', '给我一个最小代码例子', '为什么要这样验证？', '我卡在报错上，怎么排查？']"
    />
  </div>
</template>

<style scoped>
.task-link {
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  cursor: pointer;
}

.task-link:hover {
  background: var(--paper-2);
}

.guide-body {
  max-width: 760px;
  margin-top: 8px;
}

.guide-body section {
  margin-bottom: 24px;
}

.guide-body h3 {
  font-size: 11.5px;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin: 0 0 8px;
}

.guide-steps {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink-2);
}

.guide-steps li {
  margin-bottom: 10px;
}

.concept-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.concept {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--surface);
}

.concept-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.concept-text {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: var(--muted);
}

.code-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 12px;
  background: var(--surface);
}

.code-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  padding: 9px 12px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-2);
  font-size: 13px;
}

.code-body {
  padding: 10px 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.75;
  overflow: auto;
}

.code-line {
  display: flex;
  min-width: max-content;
}

.code-ln {
  flex: none;
  width: 42px;
  padding-right: 12px;
  text-align: right;
  color: var(--faint);
  user-select: none;
}

.code-text {
  white-space: pre;
  padding-right: 16px;
  color: var(--ink-2);
}

@media (max-width: 760px) {
  .concept-grid {
    grid-template-columns: 1fr;
  }
}

.guide-list {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink-2);
}

.guide-list li {
  margin-bottom: 6px;
}

.guide-link {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 6px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  font-size: 13.5px;
  color: var(--ink);
  text-decoration: none;
}

.guide-link:hover {
  border-color: var(--blue);
}

.guide-queries {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.guide-queries .chip {
  text-decoration: none;
}
</style>
