<script setup lang="ts">
import { onMounted, ref } from "vue";

import { demoApi } from "@/api/demo";
import type { DemoPlan } from "@/api/demoTypes";

const plan = ref<DemoPlan | null>(null);
const loading = ref(true);
const error = ref("");

async function load(): Promise<void> {
  loading.value = true;
  try {
    plan.value = await demoApi.plan();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "示例加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="demo-page">
    <header class="demo-nav">
      <router-link class="brand" to="/">学径 LearnPath</router-link>
      <div class="demo-actions">
        <router-link class="btn btn-sm btn-ghost" to="/plans">自己生成一份</router-link>
        <router-link class="btn btn-sm btn-primary" to="/login">登录 / 注册</router-link>
      </div>
    </header>

    <main class="demo-main">
      <div v-if="loading" class="empty">正在加载示例计划…</div>
      <div v-else-if="error" class="card card-pad">{{ error }}</div>

      <template v-else-if="plan">
        <div class="eyebrow" style="margin-bottom:8px">DEMO · 免登录示例</div>
        <h1 class="page-title">{{ plan.goal }}</h1>
        <div class="page-sub" style="margin-top:12px">
          <span class="chip">{{ plan.level === "beginner" ? "入门" : plan.level }}</span>
          <span class="chip">每天 {{ plan.daily_minutes }} 分钟</span>
          <span class="chip">计划周期 {{ plan.total_days }} 天</span>
          <span class="chip">预生成，不消耗 token</span>
        </div>

        <p class="lead" style="margin:18px 0 0;max-width:44em">
          这是预生成的示例骨架，用来感受「阶段 → 知识点 → 每日任务」的结构。登录后可以生成自己的计划，并解锁章节、测验、复习队列和 AI 助手。
        </p>

        <div v-for="phase in plan.phases" :key="phase.seq" class="phase" style="margin-top:22px">
          <div class="phase-rail">
            <div class="phase-dot">{{ String(phase.seq).padStart(2, "0") }}</div>
            <div class="phase-line"></div>
          </div>
          <div class="phase-body">
            <div class="phase-head">
              <h3>{{ phase.title }}</h3>
              <span class="phase-meta">{{ phase.days }} 天</span>
            </div>
            <p class="small ink-2" style="margin:8px 0 0">{{ phase.focus }}</p>
            <div class="phase-chips">
              <span v-for="concept in phase.knowledge_points" :key="concept" class="chip">{{ concept }}</span>
            </div>
            <div class="card phase-card">
              <div class="task-list">
                <div v-for="task in phase.tasks" :key="task.title" class="task">
                  <span class="task-check"></span>
                  <div>
                    <div class="task-title">{{ task.title }}</div>
                    <div class="task-type">{{ task.type === "coding" ? "编码" : task.type === "writing" ? "写作" : task.type }} · {{ task.duration_min }} 分钟</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style="display:flex;gap:10px;margin:30px 0 10px">
          <router-link class="btn btn-primary" to="/login">登录后生成我的计划</router-link>
          <router-link class="btn btn-ghost" to="/plans">直接生成一份</router-link>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.demo-page {
  min-height: 100vh;
  background: var(--paper);
}

.demo-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  max-width: 980px;
  margin: 0 auto;
  padding: 20px 0;
}

.brand {
  font-family: var(--font-display);
  font-size: 19px;
  color: var(--ink);
  text-decoration: none;
}

.demo-actions {
  display: flex;
  gap: 8px;
}

.demo-main {
  max-width: 980px;
  margin: 0 auto;
  padding: 10px 0 60px;
}

.demo-main .page-title {
  max-width: 20em;
}
</style>
