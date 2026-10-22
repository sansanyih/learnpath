<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { plansApi } from "@/api/plans";
import { meApi } from "@/api/stats";
import type { PhaseSkeleton, PlanSummary } from "@/api/types";
import { useSSE } from "@/composables/useSSE";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const sse = useSSE();

const goal = ref(typeof route.query.goal === "string" ? route.query.goal : "");
const dailyMinutes = ref(Number(route.query.daily) || 45);
const level = ref("beginner");
const phases = ref<PhaseSkeleton[]>([]);
const plans = ref<PlanSummary[]>([]);
const error = ref("");
const presets = [15, 25, 45, 60, 90];
const levels = [
  { value: "beginner", label: "入门" },
  { value: "intermediate", label: "中级" },
  { value: "advanced", label: "高级" },
];

const displayName = computed(
  () => session.user?.display_name || session.user?.email?.split("@")[0] || "游客",
);

async function generate(): Promise<void> {
  error.value = "";
  phases.value = [];
  try {
    await sse.stream(
      "/api/plans/stream",
      { goal: goal.value.trim() || "三个月掌握 FastAPI 后端开发", daily_minutes: dailyMinutes.value, level: level.value },
      {
        phase_skeleton: (data) => phases.value.push(data as PhaseSkeleton),
        done: (data) => {
          const result = data as { plan_id?: string | null };
          if (result.plan_id) {
            void router.push({ name: "plan-detail", params: { id: result.plan_id } });
          }
        },
        error: (data) => {
          error.value = (data as { message?: string }).message ?? "生成失败";
        },
      },
    );
  } catch (err) {
    error.value = err instanceof Error ? err.message : "生成中断，请稍后重试";
  }
}

function logout(): void {
  session.logout();
  void router.push("/");
}

async function exportAccount(): Promise<void> {
  try {
    const data = await meApi.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "learnpath-export.json";
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "导出失败";
  }
}

async function deleteAccount(): Promise<void> {
  if (!window.confirm("注销账号？7 天内用原密码登录可恢复，之后数据会被清理。")) return;
  try {
    await meApi.deleteAccount();
    session.logout();
    await router.push("/");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "注销失败";
  }
}

async function loadPlans(): Promise<void> {
  if (!session.token) return;
  try {
    plans.value = await plansApi.list();
  } catch {
    plans.value = [];
  }
}

async function removePlan(plan: PlanSummary): Promise<void> {
  if (!window.confirm(`删除计划「${plan.goal_title}」？阶段、任务、仓库章节和测验记录都会一起删除。`)) {
    return;
  }
  try {
    await plansApi.remove(plan.id);
    plans.value = plans.value.filter((item) => item.id !== plan.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "删除失败";
  }
}

onMounted(loadPlans);
</script>

<template>
  <div class="app-shell">
    <aside class="rail">
      <router-link class="rail-logo" to="/" title="学径">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
      </router-link>
      <button class="rail-btn is-active" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </button>
      <router-link class="rail-btn" to="/review" title="复习队列">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
      </router-link>
      <button class="rail-btn" title="学习数据" disabled>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>
      </button>
      <span class="rail-spacer"></span>
      <span class="avatar" style="margin-bottom:6px">{{ session.user ? displayName.slice(0, 1).toUpperCase() : "G" }}</span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">学习计划</span>
          <span v-if="!session.token" class="chip is-amber" style="height:20px;font-size:10.5px">游客</span>
        </div>
        <div class="side-title" style="margin-top:8px">
          {{ session.token ? `你好，${displayName}` : "先试一份示例" }}
        </div>
        <div class="side-meta">
          <span class="chip">每天 {{ dailyMinutes }} 分钟</span>
          <span class="chip">{{ phases.length }} 个阶段</span>
        </div>
      </div>

      <div class="side-section">
        <div class="side-section-head"><span>阶段</span><span>{{ phases.length }}</span></div>
        <div class="tree">
          <div
            v-for="(phase, index) in phases"
            :key="phase.id"
            class="tree-item"
            :class="{ 'is-active': index === 0 }"
          >
            <span class="tree-seq">{{ String(phase.seq).padStart(2, "0") }}</span>
            <span>{{ phase.title }}</span>
            <span class="tiny muted">{{ phase.days }} 天</span>
          </div>
          <div v-if="!phases.length" class="tiny muted" style="padding:8px;line-height:1.7">
            生成后，阶段会出现在这里。
          </div>
        </div>
      </div>

      <div class="inset" style="padding:12px;font-size:12px;color:var(--muted);line-height:1.7">
        M4 已完成：AI 助手、复习队列、章节测验、任务「怎么学」。管理台与部署在后续里程碑。
      </div>

      <span class="rail-spacer" style="flex:none"></span>

      <div v-if="session.token" style="display:grid;gap:6px;width:100%">
        <button class="btn btn-sm btn-ghost" type="button" @click="exportAccount">导出数据</button>
        <button class="btn btn-sm btn-ghost" type="button" style="color:var(--rose)" @click="deleteAccount">注销账号</button>
        <button class="btn btn-sm" type="button" @click="logout">退出登录</button>
      </div>
      <router-link v-else class="btn btn-sm btn-primary" style="width:100%" to="/login">登录 / 注册</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <span>学习计划</span>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ phases.length ? "计划骨架" : "新计划" }}</b>
        </div>
        <div class="topbar-actions">
          <router-link v-if="!session.token" class="btn btn-sm" to="/login">登录保存进度</router-link>
          <span v-else class="chip">{{ session.user?.email }}</span>
        </div>
      </div>

      <div class="content" v-reveal>
        <div class="page-head">
          <div>
            <div class="eyebrow" style="margin-bottom:8px">NEW PLAN · 目标拆解</div>
            <h1 class="page-title">从一句话开始</h1>
            <p class="lead" style="margin-top:10px;max-width:36em">
              说出目标与每天能投入的时间，AI 会生成阶段骨架与每日任务；登录后自动保存，刷新不丢。
            </p>
          </div>
        </div>

        <div v-if="!session.token" class="guest-bar" style="margin:0 0 18px;border:1px solid rgba(183,129,29,.22);border-radius:10px">
          <span class="dot"></span>
          游客模式 · 这份骨架不会保存
          <router-link to="/login">登录后保存进度</router-link>
          <router-link to="/demo" style="margin-left:8px">先看示例计划</router-link>
        </div>

        <div class="card card-pad">
          <div class="field" style="margin-bottom:14px">
            <label for="goal">学习目标</label>
            <input id="goal" v-model="goal" type="text" placeholder="例如：三个月掌握 FastAPI 后端开发" />
          </div>

          <div class="field" style="margin-bottom:18px">
            <label>当前水平</label>
            <div class="guest-note" style="margin-top:0">
              <button
                v-for="item in levels"
                :key="item.value"
                class="chip"
                :class="{ 'is-blue': level === item.value }"
                type="button"
                style="cursor:pointer;height:30px;padding:0 12px"
                @click="level = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="field" style="margin-bottom:18px">
            <label>每天可投入</label>
            <div class="guest-note" style="margin-top:0">
              <button
                v-for="preset in presets"
                :key="preset"
                class="chip"
                :class="{ 'is-blue': dailyMinutes === preset }"
                type="button"
                style="cursor:pointer;height:30px;padding:0 12px"
                @click="dailyMinutes = preset"
              >
                {{ preset }} 分钟
              </button>
            </div>
          </div>

          <div style="display:flex;align-items:center;gap:12px">
            <button class="btn btn-primary" type="button" :disabled="sse.streaming.value" @click="generate">
              {{ sse.streaming.value ? "生成中…" : session.token ? "生成学习计划" : "生成示例骨架" }}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
            <button v-if="sse.streaming.value" class="btn btn-ghost" type="button" @click="sse.stop">停止</button>
            <span v-if="error" class="small" style="color:var(--rose)">{{ error }}</span>
          </div>
        </div>

        <div v-if="session.token && plans.length && !phases.length" style="margin-top:22px">
          <div class="eyebrow" style="margin-bottom:10px">MY PLANS · 最近的计划</div>
          <div style="display:grid;gap:8px">
            <div
              v-for="plan in plans"
              :key="plan.id"
              class="card"
              style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;gap:16px"
            >
              <router-link
                :to="{ name: 'plan-detail', params: { id: plan.id } }"
                style="flex:1;min-width:0;color:inherit;text-decoration:none"
              >
                <div style="font-weight:600;font-size:14px">{{ plan.goal_title }}</div>
                <div class="tiny muted">{{ plan.phase_count }} 阶段 · {{ plan.task_count }} 任务 · {{ plan.created_at.slice(0, 10) }}</div>
              </router-link>
              <span class="chip" :class="plan.status === 'ready' ? 'is-green' : 'is-blue'">
                {{ plan.status === "ready" ? "计划已生成" : plan.status === "generating" ? "生成中" : plan.status }}
              </span>
              <button class="btn btn-sm btn-ghost" style="color:var(--rose)" @click="removePlan(plan)">删除</button>
            </div>
          </div>
        </div>

        <div v-if="phases.length" style="margin-top:26px">
          <div class="eyebrow" style="margin-bottom:12px">PHASE SKELETON · {{ phases.length }} 个阶段</div>
          <TransitionGroup name="phase" tag="div">
            <div
              v-for="(phase, index) in phases"
              :key="phase.id"
              class="phase"
            >
            <div class="phase-rail">
              <div class="phase-dot" :class="{ 'is-doing': index === 0 }">{{ String(phase.seq).padStart(2, "0") }}</div>
              <div class="phase-line"></div>
            </div>
            <div class="phase-body">
              <div class="phase-head">
                <h3>{{ phase.title }}</h3>
                <span class="pill" :class="index === 0 ? 'is-doing' : 'is-todo'">{{ index === 0 ? "从这里开始" : "待开始" }}</span>
                <span class="phase-meta">{{ phase.days }} 天 · {{ phase.knowledge_points.length }} 个知识点</span>
              </div>
              <p class="small ink-2" style="margin:8px 0 0">{{ phase.focus }}</p>
              <div class="phase-chips">
                <span v-for="kp in phase.knowledge_points" :key="kp.name" class="chip">{{ kp.name }}</span>
              </div>
              <div class="card phase-card" style="padding:14px 16px">
                <div class="tiny muted" style="margin-bottom:6px">可验证目标</div>
                <div class="small ink-2">
                  {{ phase.knowledge_points.map((kp) => kp.objective).join(" · ") }}
                </div>
              </div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div v-if="!phases.length && !plans.length" class="empty" style="margin-top:26px">
          还没有生成计划。输入目标后点「生成示例骨架」，先看看它长什么样。
        </div>
      </div>
    </main>
  </div>
</template>
