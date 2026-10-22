<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { reviewApi } from "@/api/review";
import type { MasteryDashboard, ReviewQueueItem } from "@/api/reviewTypes";
import { statsApi } from "@/api/stats";
import type { LearningStats } from "@/api/statsTypes";

type TabKey = "queue" | "mastery";

const tab = ref<TabKey>("queue");
const queue = ref<ReviewQueueItem[]>([]);
const mastery = ref<MasteryDashboard | null>(null);
const stats = ref<LearningStats | null>(null);
const loading = ref(true);
const error = ref("");
const completing = ref("");

const summary = computed(() => mastery.value?.summary);
const statusLabel: Record<string, string> = {
  new: "未测",
  learning: "学习中",
  review: "需复习",
  mastered: "已掌握",
};

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [queueData, masteryData, statsData] = await Promise.all([
      reviewApi.queue(),
      reviewApi.mastery(),
      statsApi.get(),
    ]);
    queue.value = queueData.items;
    mastery.value = masteryData;
    stats.value = statsData;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "复习数据加载失败";
  } finally {
    loading.value = false;
  }
}

async function complete(item: ReviewQueueItem, result: "again" | "hard" | "good"): Promise<void> {
  if (completing.value) return;
  completing.value = item.id;
  try {
    await reviewApi.complete(item.id, result);
    queue.value = queue.value.filter((entry) => entry.id !== item.id);
    mastery.value = await reviewApi.mastery();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "记录失败";
  } finally {
    completing.value = "";
  }
}

function formatDue(value: string | null): string {
  if (!value) return "未安排";
  const date = new Date(value);
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
}

function heatLevel(count: number): number {
  if (count <= 0) return 0;
  if (count >= 3) return 3;
  return count;
}

function barHeight(minutes: number): number {
  const max = Math.max((stats.value?.week.target ?? 480) / 7, 60);
  return Math.max(4, Math.round((minutes / max) * 64));
}

function weekday(date: string): string {
  const day = new Date(date).getUTCDay();
  return ["一", "二", "三", "四", "五", "六", "日"][day === 0 ? 6 : day - 1];
}

onMounted(load);
</script>

<template>
  <div class="app-shell">
    <aside class="rail">
      <router-link class="rail-logo" to="/" title="学径">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
      </router-link>
      <router-link class="rail-btn" to="/plans" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </router-link>
      <router-link class="rail-btn is-active" to="/review" title="复习队列">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
      </router-link>
      <span class="rail-spacer"></span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">复习与掌握</span>
        </div>
        <div class="side-title" style="margin-top:8px">今天该复习什么</div>
        <div class="side-meta">
          <span class="chip">待复习 {{ queue.length }}</span>
          <span v-if="summary" class="chip">平均 {{ summary.average }} 分</span>
        </div>
      </div>

      <div class="side-section">
        <div class="tree">
          <button class="tree-item" :class="{ 'is-active': tab === 'queue' }" type="button" @click="tab = 'queue'">
            <span class="tree-seq">01</span>
            <span>复习队列</span>
            <span class="tiny muted">{{ queue.length }}</span>
          </button>
          <button class="tree-item" :class="{ 'is-active': tab === 'mastery' }" type="button" @click="tab = 'mastery'">
            <span class="tree-seq">02</span>
            <span>掌握度</span>
            <span class="tiny muted">{{ summary?.total ?? 0 }}</span>
          </button>
        </div>
      </div>

      <span class="rail-spacer" style="flex:none"></span>
      <router-link class="btn btn-sm" style="width:100%" to="/plans">返回计划</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <router-link to="/plans" style="color:var(--muted)">学习计划</router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ tab === "queue" ? "复习队列" : "掌握度看板" }}</b>
        </div>
        <div class="topbar-actions">
          <button class="btn btn-sm btn-ghost" @click="load">刷新</button>
        </div>
      </div>

      <div class="content" v-reveal>
        <div v-if="stats" class="stats-grid">
          <section class="card card-pad">
            <div class="stats-head">
              <span class="eyebrow">连续学习</span>
              <span class="chip is-green">{{ stats.streak }} 天</span>
            </div>
            <div class="heatmap">
              <span
                v-for="day in stats.days"
                :key="day.date"
                class="heat-cell"
                :class="`level-${heatLevel(day.count)}`"
                :title="`${day.date} · ${day.minutes} 分钟`"
              ></span>
            </div>
          </section>

          <section class="card card-pad">
            <div class="stats-head">
              <span class="eyebrow">本周投入</span>
              <span class="tiny muted">{{ (stats.week.minutes / 60).toFixed(1) }}h / {{ (stats.week.target / 60).toFixed(1) }}h</span>
            </div>
            <div class="weekly">
              <div v-for="day in stats.week.days" :key="day.date" class="week-col">
                <div class="week-track">
                  <div class="week-fill" :style="{ height: `${barHeight(day.minutes)}px` }"></div>
                </div>
                <span class="tiny muted">{{ weekday(day.date) }}</span>
              </div>
            </div>
            <p class="tiny muted" style="margin:8px 0 0">
              {{ (stats.week.minutes / 60).toFixed(1) }}h 投入 · 目标 {{ (stats.week.target / 60).toFixed(1) }}h
            </p>
          </section>

          <section class="card card-pad">
            <div class="eyebrow">复习策略</div>
            <p class="small muted" style="margin:8px 0 0;line-height:1.8">
              间隔序列 {{ stats.review_strategy.intervals.join(" / ") }} 天；连续答对
              {{ stats.review_strategy.mastered_streak }} 次进入「已掌握」，不再高频出现。
            </p>
          </section>
        </div>

        <div v-if="loading" class="empty">正在读取复习数据…</div>
        <div v-else-if="error" class="card card-pad">
          <div class="eyebrow">加载失败</div>
          <p class="lead" style="margin:10px 0 16px">{{ error }}</p>
          <button class="btn" @click="load">重试</button>
        </div>

        <template v-else-if="tab === 'queue'">
          <div class="eyebrow" style="margin-bottom:8px">REVIEW QUEUE · 今日复习</div>
          <h1 class="page-title">按遗忘曲线复习</h1>
          <p class="lead" style="margin:10px 0 0;max-width:40em">
            间隔 1 → 3 → 7 → 15 → 30 天；连续答对 3 次标记「已掌握」，不再高频出现。
          </p>

          <div v-if="queue.length" style="margin-top:24px;display:grid;gap:10px">
            <div v-for="item in queue" :key="item.id" class="card card-pad">
              <div style="display:flex;justify-content:space-between;gap:14px;align-items:flex-start">
                <div>
                  <div style="font-weight:600;font-size:15px">{{ item.kp_name }}</div>
                  <div class="tiny muted" style="margin-top:4px">
                    {{ item.phase_title }} · {{ item.overdue ? "已到期" : "待复习" }} · 下次 {{ formatDue(item.due_at) }}
                  </div>
                </div>
                <span class="chip" :class="item.mastery_status === 'mastered' ? 'is-green' : item.mastery_status === 'review' ? 'is-rose' : ''">
                  {{ statusLabel[item.mastery_status] ?? item.mastery_status }}
                </span>
              </div>

              <div class="review-progress">
                <div class="review-bar"><i :style="{ width: `${item.mastery_score}%` }"></i></div>
                <span class="tiny muted">{{ item.mastery_score }} 分</span>
              </div>

              <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
                <button class="btn btn-sm" :disabled="!!completing" @click="complete(item, 'again')">忘了</button>
                <button class="btn btn-sm" :disabled="!!completing" @click="complete(item, 'hard')">有点难</button>
                <button class="btn btn-sm btn-primary" :disabled="!!completing" @click="complete(item, 'good')">记住了</button>
              </div>
            </div>
          </div>

          <div v-else class="card card-pad" style="margin-top:24px">
            <div class="eyebrow">队列为空</div>
            <p class="small muted" style="margin:8px 0 14px">
              做完阶段测验后，薄弱知识点会进入复习队列。
            </p>
            <router-link class="btn btn-sm" to="/plans">去学习计划</router-link>
          </div>
        </template>

        <template v-else>
          <div class="eyebrow" style="margin-bottom:8px">MASTERY · 掌握度</div>
          <h1 class="page-title">哪些会了，哪些还虚</h1>

          <div v-if="summary" class="stats-row" style="margin-top:20px">
            <div class="stat card"><b>{{ summary.average }}</b><span>平均分</span></div>
            <div class="stat card"><b>{{ summary.mastered }}</b><span>已掌握</span></div>
            <div class="stat card"><b>{{ summary.learning }}</b><span>学习中</span></div>
            <div class="stat card"><b>{{ summary.review }}</b><span>需复习</span></div>
          </div>

          <div v-if="mastery?.items.length" style="margin-top:24px;display:grid;gap:8px">
            <div v-for="item in mastery.items" :key="item.kp_id" class="card" style="padding:12px 16px">
              <div style="display:flex;justify-content:space-between;gap:14px;align-items:baseline">
                <div>
                  <div style="font-weight:600;font-size:14px">{{ item.kp_name }}</div>
                  <div class="tiny muted" style="margin-top:3px">{{ item.phase_title }} · 测过 {{ item.attempts }} 次</div>
                </div>
                <span class="chip">{{ item.score }} 分 · {{ statusLabel[item.status] ?? item.status }}</span>
              </div>
              <div class="review-progress" style="margin-top:8px">
                <div class="review-bar"><i :style="{ width: `${item.score}%` }"></i></div>
              </div>
            </div>
          </div>

          <div v-else class="card card-pad" style="margin-top:24px">
            <div class="eyebrow">还没有掌握度数据</div>
            <p class="small muted" style="margin:8px 0 14px">先做一次阶段测验，系统会按知识点更新掌握度。</p>
            <router-link class="btn btn-sm" to="/plans">去学习计划</router-link>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.tree-item {
  width: 100%;
  border: 0;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.review-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.review-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.review-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--blue);
}

.stats-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr 0.9fr;
  gap: 12px;
  margin-bottom: 22px;
}

.stats-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.heatmap {
  display: grid;
  grid-template-rows: repeat(7, 10px);
  grid-auto-flow: column;
  grid-auto-columns: 10px;
  gap: 3px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.heat-cell {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: var(--paper-2);
}

.heat-cell.level-1 {
  background: #cdd8f2;
}

.heat-cell.level-2 {
  background: #8aa4e3;
}

.heat-cell.level-3 {
  background: var(--blue);
}

.weekly {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  margin-top: 4px;
}

.week-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.week-track {
  width: 100%;
  height: 64px;
  display: flex;
  align-items: flex-end;
  border-radius: 4px;
  background: var(--paper-2);
  overflow: hidden;
}

.week-fill {
  width: 100%;
  min-height: 4px;
  border-radius: 4px;
  background: var(--blue);
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
