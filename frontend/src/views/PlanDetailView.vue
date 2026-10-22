<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { plansApi } from "@/api/plans";
import type { RepoSource } from "@/api/repoTypes";
import { reposApi } from "@/api/repos";
import { tasksApi } from "@/api/tasks";
import type { PlanDetail, TaskItem } from "@/api/types";
import { useSSE } from "@/composables/useSSE";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const sse = useSSE();

const plan = ref<PlanDetail | null>(null);
const loading = ref(true);
const error = ref("");
const actionError = ref("");

const repos = ref<RepoSource[]>([]);
const repoUrl = ref("");
const repoError = ref("");
const repoProfile = ref<RepoProfile | null>(null);

interface RepoProfile {
  language?: string;
  framework?: string;
  summary?: string;
  entrypoints?: string[];
  module_map?: string[];
  reading_order?: string[];
}

const taskCount = computed(
  () => plan.value?.phases.reduce((sum, phase) => sum + phase.tasks.length, 0) ?? 0,
);
const totalMinutes = computed(
  () =>
    plan.value?.phases.reduce(
      (sum, phase) => sum + phase.tasks.reduce((inner, task) => inner + task.duration_min, 0),
      0,
    ) ?? 0,
);
const totalHours = computed(() => (totalMinutes.value / 60).toFixed(1));
const totalDays = computed(
  () => plan.value?.phases.reduce((sum, phase) => sum + phase.days, 0) ?? 0,
);
const completedCount = computed(
  () =>
    plan.value?.phases.reduce(
      (sum, phase) => sum + phase.tasks.filter((task) => task.status === "done").length,
      0,
    ) ?? 0,
);
const progressPercent = computed(() =>
  taskCount.value ? Math.round((completedCount.value / taskCount.value) * 100) : 0,
);
const toggling = ref<Record<string, boolean>>({});
const statusLabel = computed(() => planStatus(plan.value?.status));
const levelLabel = computed(
  () =>
    ({ beginner: "入门", intermediate: "中级", advanced: "高级" } as Record<string, string>)[
      plan.value?.level ?? ""
    ] ?? plan.value?.level ?? "",
);

function planStatus(status?: string): string {
  return (
    ({ generating: "生成中", ready: "计划已生成", failed: "生成失败" } as Record<string, string>)[
      status ?? ""
    ] ?? status ?? ""
  );
}

function taskType(type: string): string {
  return (
    ({ reading: "阅读", coding: "编码", quiz: "测验", review: "复习", writing: "写作" } as Record<
      string,
      string
    >)[type] ?? type
  );
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  actionError.value = "";
  try {
    plan.value = await plansApi.detail(String(route.params.id));
  } catch (err) {
    error.value = err instanceof Error ? err.message : "计划加载失败";
  } finally {
    loading.value = false;
  }
}

async function toggleTask(task: TaskItem): Promise<void> {
  if (toggling.value[task.id]) return;
  const previous = task.status;
  const next: "todo" | "done" = task.status === "done" ? "todo" : "done";
  toggling.value = { ...toggling.value, [task.id]: true };
  task.status = next;
  try {
    const result = await tasksApi.updateStatus(task.id, next);
    const phase = plan.value?.phases.find((item) => item.tasks.some((t) => t.id === task.id));
    if (phase) phase.status = result.phase_status;
  } catch (err) {
    task.status = previous;
    actionError.value = err instanceof Error ? err.message : "更新失败";
  } finally {
    const copy = { ...toggling.value };
    delete copy[task.id];
    toggling.value = copy;
  }
}

async function openGuide(task: TaskItem): Promise<void> {
  await router.push({
    name: "task-guide",
    params: { planId: plan.value?.id ?? route.params.id, taskId: task.id },
  });
}

async function loadRepos(): Promise<void> {
  try {
    repos.value = await reposApi.list(String(route.params.id));
  } catch {
    repos.value = [];
  }
}

async function removePlan(): Promise<void> {
  if (!plan.value) return;
  if (!window.confirm(`删除计划「${plan.value.goal_title}」？阶段、任务、仓库章节和测验记录都会一起删除。`)) {
    return;
  }
  try {
    await plansApi.remove(plan.value.id);
    await router.push("/plans");
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : "删除失败";
  }
}

async function importRepo(): Promise<void> {
  repoError.value = "";
  repoProfile.value = null;
  if (!repoUrl.value.trim()) {
    repoError.value = "请粘贴仓库地址";
    return;
  }
  try {
    await sse.stream(
      `/api/plans/${route.params.id}/repos/stream`,
      { url: repoUrl.value.trim() },
      {
        profile: (data) => {
          repoProfile.value = (data as { profile?: RepoProfile }).profile ?? null;
        },
        done: () => {
          void loadRepos();
        },
        error: (data) => {
          repoError.value = (data as { message?: string }).message ?? "仓库分析失败";
        },
      },
    );
  } catch (err) {
    repoError.value = err instanceof Error ? err.message : "仓库分析失败";
  }
}

function chapterLink(chapterId: string) {
  return { name: "chapter", params: { planId: route.params.id, chapterId } };
}

onMounted(() => {
  void load();
  void loadRepos();
});
</script>

<template>
  <div class="app-shell">
    <aside class="rail">
      <router-link class="rail-logo" to="/" title="学径">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
      </router-link>
      <router-link class="rail-btn is-active" to="/plans" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </router-link>
      <router-link class="rail-btn" to="/review" title="复习队列">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
      </router-link>
      <button class="rail-btn" title="学习数据" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>
      </button>
      <span class="rail-spacer"></span>
      <span class="avatar" style="margin-bottom:6px">{{ session.user?.email?.slice(0, 1).toUpperCase() ?? "U" }}</span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">学习计划</span>
          <span class="chip" :class="plan?.status === 'ready' ? 'is-green' : 'is-blue'" style="height:20px;font-size:10.5px">{{ statusLabel }}</span>
        </div>
        <div class="side-title" style="margin-top:8px">{{ plan?.goal_title ?? "加载中…" }}</div>
        <div class="side-meta">
          <span class="chip">每天 {{ plan?.daily_minutes ?? 45 }} 分钟</span>
          <span class="chip">{{ plan?.phases.length ?? 0 }} 个阶段</span>
        </div>
      </div>

      <div class="side-section">
        <div class="side-section-head"><span>阶段</span><span>{{ plan?.phases.length ?? 0 }}</span></div>
        <div class="tree">
          <a
            v-for="phase in plan?.phases ?? []"
            :key="phase.id"
            class="tree-item"
            :href="`#phase-${phase.id}`"
          >
            <span class="tree-seq">{{ String(phase.seq).padStart(2, "0") }}</span>
            <span>{{ phase.title }}</span>
            <span class="tiny muted">{{ phase.days }} 天</span>
          </a>
        </div>
      </div>

      <span class="rail-spacer" style="flex:none"></span>
      <router-link class="btn btn-sm btn-primary" style="width:100%" to="/plans">+ 新建计划</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <router-link to="/plans" style="color:var(--muted)">学习计划</router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ plan?.goal_title ?? "计划详情" }}</b>
        </div>
        <div class="topbar-actions">
          <button class="btn btn-sm btn-ghost" @click="load">刷新</button>
          <button class="btn btn-sm btn-ghost" style="color:var(--rose)" @click="removePlan">删除计划</button>
          <router-link class="btn btn-sm" to="/plans">新建计划</router-link>
        </div>
      </div>

      <div class="content" v-reveal>
        <div v-if="loading" class="empty">正在读取计划…</div>

        <div v-else-if="error" class="card card-pad">
          <div class="eyebrow">加载失败</div>
          <p class="lead" style="margin:10px 0 16px">{{ error }}</p>
          <button class="btn" @click="load">重试</button>
          <router-link class="btn btn-ghost" to="/plans">返回计划列表</router-link>
        </div>

        <template v-else-if="plan">
          <div v-if="actionError" class="small" style="color:var(--rose);margin:0 0 12px">{{ actionError }}</div>
          <div class="page-head">
            <div>
              <div class="eyebrow" style="margin-bottom:8px">PLAN · 学习计划</div>
              <h1 class="page-title">{{ plan.goal_title }}</h1>
              <div class="page-sub">
                <span class="chip">{{ levelLabel }}</span>
                <span class="chip">每天 {{ plan.daily_minutes }} 分钟</span>
                <span class="chip">计划周期 {{ totalDays }} 天</span>
                <span v-if="plan.deadline" class="chip">截止 {{ plan.deadline }}</span>
                <span class="chip">创建于 {{ plan.created_at.slice(0, 10) }}</span>
              </div>
              <div style="margin-top:16px;max-width:420px">
                <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:6px">
                  <span>学习进度</span>
                  <span>{{ completedCount }} / {{ taskCount }} · {{ progressPercent }}%</span>
                </div>
                <div class="progress is-green"><i :style="{ width: progressPercent + '%' }"></i></div>
              </div>
            </div>
            <span class="pill" :class="plan.status === 'ready' ? 'is-done' : plan.status === 'failed' ? 'is-todo' : 'is-doing'">{{ statusLabel }}</span>
          </div>

          <div class="stats-row">
            <div class="stat card"><b>{{ plan.phases.length }}</b><span>阶段</span></div>
            <div class="stat card"><b>{{ taskCount }}</b><span>任务</span></div>
            <div class="stat card"><b>{{ totalHours }}h</b><span>预计总时长</span></div>
            <div class="stat card"><b>{{ completedCount }}/{{ taskCount }}</b><span>已完成任务</span></div>
          </div>

          <section id="repos" class="card card-pad" style="margin:0 0 26px">
            <div class="eyebrow" style="margin-bottom:6px">FROM GITHUB · 从仓库学</div>
            <p class="small muted" style="margin:0 0 12px">
              粘贴公开仓库地址，自动拆成学习章节；每章可以生成「代码走读」讲解。
            </p>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
              <input
                v-model="repoUrl"
                placeholder="https://github.com/owner/repo"
                style="flex:1;min-width:260px"
                @keyup.enter="importRepo"
              />
              <button class="btn btn-primary" :disabled="sse.streaming.value" @click="importRepo">
                {{ sse.streaming.value ? "分析中…" : "分析仓库" }}
              </button>
            </div>
            <div v-if="repoError" class="small" style="color:var(--rose);margin-top:8px">{{ repoError }}</div>

            <div v-if="repoProfile" class="inset" style="margin-top:14px;padding:12px 14px">
              <div class="tiny mono" style="color:var(--faint)">REPO PROFILE</div>
              <div class="small ink-2" style="margin-top:4px">{{ repoProfile.summary }}</div>
              <div class="tiny muted" style="margin-top:4px">
                {{ repoProfile.language }} · {{ repoProfile.framework }}
              </div>
            </div>

            <div v-if="repos.length" style="margin-top:16px;display:grid;gap:16px">
              <div v-for="repo in repos" :key="repo.id">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
                  <div style="font-weight:600;font-size:14px">
                    {{ repo.repo_full_name }} <span class="tiny muted">@{{ repo.ref }}</span>
                  </div>
                  <span class="chip">{{ repo.chapters.length }} 章</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px">
                  <router-link
                    v-for="chapter in repo.chapters"
                    :key="chapter.id"
                    :to="chapterLink(chapter.id)"
                    class="card"
                    style="padding:10px 12px;display:block"
                  >
                    <div style="display:flex;gap:8px;align-items:baseline">
                      <span class="mono" style="font-size:10px;color:var(--faint)">{{ String(chapter.seq).padStart(2, "0") }}</span>
                      <span style="font-size:13px;font-weight:600">{{ chapter.title }}</span>
                    </div>
                    <div
                      class="tiny muted"
                      style="margin-top:4px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden"
                    >
                      {{ chapter.purpose }}
                    </div>
                  </router-link>
                </div>
              </div>
            </div>
          </section>

          <div
            v-for="phase in plan.phases"
            :id="`phase-${phase.id}`"
            :key="phase.id"
            class="phase"
          >
            <div class="phase-rail">
              <div class="phase-dot" :class="{ 'is-done': phase.status === 'done', 'is-doing': phase.status === 'doing' }">{{ String(phase.seq).padStart(2, "0") }}</div>
              <div class="phase-line"></div>
            </div>
            <div class="phase-body">
              <div class="phase-head">
                <h3>{{ phase.title }}</h3>
                <span class="pill" :class="phase.status === 'done' ? 'is-done' : phase.status === 'doing' ? 'is-doing' : 'is-todo'">{{ phase.status === "done" ? "已完成" : phase.status === "doing" ? "进行中" : "未开始" }}</span>
                <span class="phase-meta">{{ phase.days }} 天 · {{ phase.knowledge_points.length }} 个知识点 · {{ phase.tasks.length }} 个任务</span>
                <router-link
                  class="btn btn-sm"
                  style="margin-left:auto"
                  :to="{ name: 'quiz', params: { planId: plan.id, phaseId: phase.id } }"
                >
                  阶段测验
                </router-link>
              </div>
              <p class="small ink-2" style="margin:8px 0 0">{{ phase.focus }}</p>
              <div class="phase-chips">
                <span v-for="kp in phase.knowledge_points" :key="kp.id" class="chip" :title="kp.objective">{{ kp.name }}</span>
              </div>

              <div class="card phase-card">
                <div class="task-list">
                  <div
                    v-for="task in phase.tasks"
                    :key="task.id"
                    class="task"
                    :class="{ 'is-done': task.status === 'done' }"
                    style="cursor:pointer"
                    @click="openGuide(task)"
                  >
                    <button
                      class="task-check"
                      type="button"
                      :class="{ 'is-done': task.status === 'done' }"
                      :aria-label="task.status === 'done' ? '标记为待办' : '标记为完成'"
                      @click.stop="toggleTask(task)"
                    >
                      <svg v-if="task.status === 'done'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                    </button>
                    <div>
                      <div class="task-title">{{ task.title }}</div>
                      <div class="task-type">{{ taskType(task.type) }} · {{ task.duration_min }} 分钟 · 第 {{ task.day_offset + 1 }} 天</div>
                      <div v-if="task.acceptance" class="task-accept" :title="task.acceptance">{{ task.acceptance }}</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px">
                      <span class="chip" :class="task.status === 'done' ? 'is-green' : ''">{{ toggling[task.id] ? "保存中…" : task.status === "done" ? "完成" : "待办" }}</span>
                      <button class="btn btn-sm btn-ghost" @click.stop="openGuide(task)">怎么学</button>
                    </div>
                  </div>
                  <div v-if="!phase.tasks.length" class="tiny muted" style="padding:10px 8px">
                    这个阶段的任务没有生成成功，可稍后重新生成。
                  </div>
                </div>
              </div>

              <div v-if="phase.deliverable" class="tiny muted" style="margin-top:10px">
                阶段交付物：{{ phase.deliverable }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.pill {
  white-space: nowrap;
}

.task-title {
  overflow-wrap: anywhere;
}

.task-accept {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.task-check {
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.task-check:hover {
  border-color: var(--blue);
}

.task-check.is-done {
  background: var(--green);
  border-color: var(--green);
  color: #fff;
}
</style>
