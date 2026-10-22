<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { quizApi } from "@/api/quiz";
import type { PhaseQuiz, SubmitResult } from "@/api/quizTypes";

const route = useRoute();
const router = useRouter();

const quiz = ref<PhaseQuiz | null>(null);
const answers = ref<Record<string, string>>({});
const loading = ref(true);
const submitting = ref(false);
const acting = ref(false);
const error = ref("");
const actionError = ref("");
const result = ref<SubmitResult | null>(null);

const planId = computed(() => String(route.params.planId));
const answeredCount = computed(
  () => Object.values(answers.value).filter((value) => value.trim().length > 0).length,
);

const actionLabel: Record<string, string> = {
  skip: "可以跳过",
  mastered: "已经掌握",
  continue: "继续下一阶段",
  review: "需要复习",
  remediate: "需要加练",
  remediate_plus: "回到学习状态",
};

const dimLabel: Record<string, string> = {
  technical: "技术正确性",
  principle: "原理与因果",
  coverage: "关键点覆盖",
  structure: "表达与结构",
};

function scoreTone(score: number): string {
  if (score >= 85) return "is-green";
  if (score >= 60) return "is-amber";
  return "is-rose";
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    quiz.value = await quizApi.create(planId.value, String(route.params.phaseId));
  } catch (err) {
    error.value = err instanceof Error ? err.message : "测验加载失败";
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  if (!quiz.value || submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    result.value = await quizApi.submit(
      quiz.value.phase_id,
      quiz.value.questions.map((question) => ({
        quiz_id: question.id,
        answer: answers.value[question.id] ?? "",
      })),
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    error.value = err instanceof Error ? err.message : "提交失败";
  } finally {
    submitting.value = false;
  }
}

async function adopt(): Promise<void> {
  const adjustment = result.value?.adjustment;
  if (!adjustment || acting.value) return;
  acting.value = true;
  try {
    await quizApi.adopt(adjustment.id);
    await router.push({ name: "plan-detail", params: { id: planId.value } });
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : "采纳失败";
    acting.value = false;
  }
}

async function ignore(): Promise<void> {
  const adjustment = result.value?.adjustment;
  if (!adjustment || acting.value) return;
  acting.value = true;
  try {
    await quizApi.ignore(adjustment.id);
    await router.push({ name: "plan-detail", params: { id: planId.value } });
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : "忽略失败";
    acting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="app-shell">
    <aside class="rail">
      <router-link class="rail-logo" to="/" title="学径">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
      </router-link>
      <router-link class="rail-btn is-active" :to="`/plans/${planId}`" title="学习计划">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5"/></svg>
      </router-link>
      <span class="rail-spacer"></span>
    </aside>

    <aside class="sidebar">
      <div>
        <div class="side-kicker">
          <span class="eyebrow">阶段测验</span>
          <span class="chip" style="height:20px;font-size:10.5px">{{ quiz?.questions.length ?? 5 }} 题</span>
        </div>
        <div class="side-title" style="margin-top:8px">{{ quiz?.phase_title ?? "加载中…" }}</div>
        <div class="side-meta">
          <span class="chip">3 选择 + 2 简答</span>
        </div>
      </div>

      <div class="side-section">
        <div class="side-section-head"><span>题目</span><span>{{ answeredCount }}/{{ quiz?.questions.length ?? 0 }}</span></div>
        <div class="tree">
          <div v-for="(question, index) in quiz?.questions ?? []" :key="question.id" class="tree-item">
            <span class="tree-seq">{{ String(index + 1).padStart(2, "0") }}</span>
            <span>{{ question.type === "choice" ? "选择题" : "简答题" }}</span>
            <span class="tiny muted">{{ (answers[question.id] ?? "").trim() ? "已答" : "未答" }}</span>
          </div>
        </div>
      </div>

      <span class="rail-spacer" style="flex:none"></span>
      <router-link class="btn btn-sm" style="width:100%" :to="`/plans/${planId}`">返回计划</router-link>
    </aside>

    <main class="main">
      <div class="topbar">
        <div class="crumbs">
          <router-link :to="`/plans/${planId}`" style="color:var(--muted)">学习计划</router-link>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <span>阶段测验</span>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
          <b>{{ quiz?.phase_title ?? "加载中" }}</b>
        </div>
        <div class="topbar-actions">
          <router-link class="btn btn-sm btn-ghost" :to="`/plans/${planId}`">返回计划</router-link>
        </div>
      </div>

      <div class="content" v-reveal>
        <div v-if="loading" class="empty">正在生成测验…</div>

        <div v-else-if="error" class="card card-pad">
          <div class="eyebrow">出错了</div>
          <p class="lead" style="margin:10px 0 16px">{{ error }}</p>
          <button class="btn" @click="load">重试</button>
          <router-link class="btn btn-ghost" :to="`/plans/${planId}`">返回计划</router-link>
        </div>

        <template v-else-if="result">
          <div class="result-head">
            <div class="result-score card" :class="scoreTone(result.score)">
              <b>{{ result.score }}</b>
              <span>阶段得分</span>
            </div>
            <div>
              <div class="eyebrow" style="margin-bottom:6px">QUIZ RESULT · 测验结果</div>
              <h1 class="page-title" style="font-size:30px">{{ actionLabel[result.adjustment?.action ?? ""] ?? "本阶段完成" }}</h1>
              <p class="small muted" style="margin-top:8px">
                {{ result.adjustment?.message ?? "成绩已记录，掌握度和复习计划已更新。" }}
              </p>
            </div>
          </div>

          <div v-if="result.adjustment" class="adjust card card-pad" style="margin:20px 0">
            <div class="eyebrow" style="margin-bottom:8px">计划调整建议</div>
            <p class="small ink-2" style="margin:0 0 10px">{{ result.adjustment.message }}</p>
            <ul v-if="result.adjustment.tasks.length" class="small" style="margin:0 0 14px;padding-left:18px;color:var(--muted)">
              <li v-for="task in result.adjustment.tasks" :key="task">{{ task }}</li>
            </ul>
            <button class="btn btn-primary" :disabled="acting" @click="adopt">
              {{ acting ? "处理中…" : "采纳调整" }}
            </button>
            <button class="btn btn-ghost" :disabled="acting" @click="ignore">忽略</button>
            <div v-if="actionError" class="small" style="color:var(--rose);margin-top:10px">{{ actionError }}</div>
          </div>

          <div class="dims card card-pad" style="margin:20px 0">
            <div class="eyebrow" style="margin-bottom:12px">评分维度</div>
            <div v-for="(value, key) in result.dims" :key="key" class="dim-row">
              <span>{{ dimLabel[key] ?? key }}</span>
              <div class="dim-bar"><i :style="{ width: `${value}%` }"></i></div>
              <b>{{ value }}</b>
            </div>
          </div>

          <div class="eyebrow" style="margin:26px 0 10px">逐题反馈</div>
          <div v-for="(item, index) in result.results" :key="item.quiz_id" class="card card-pad" style="margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline">
              <div style="font-weight:600;font-size:14px">{{ index + 1 }}. {{ item.question }}</div>
              <span class="chip" :class="item.score >= 85 ? 'is-green' : item.score >= 60 ? '' : 'is-rose'">{{ item.score }}</span>
            </div>
            <p class="small" style="margin:8px 0 0;color:var(--muted)">{{ item.feedback }}</p>
            <details class="small" style="margin-top:8px">
              <summary style="cursor:pointer;color:var(--muted)">查看参考答案</summary>
              <p style="margin:6px 0 0">{{ item.reference }}</p>
            </details>
          </div>
        </template>

        <template v-else-if="quiz">
          <div class="eyebrow" style="margin-bottom:8px">PHASE QUIZ · 阶段测验</div>
          <h1 class="page-title">{{ quiz.phase_title }}</h1>
          <p class="lead" style="margin:10px 0 0;max-width:40em">
            5 道题：3 道选择 + 2 道简答。简答题按「技术正确性 / 原理因果 / 关键点覆盖 / 表达结构」四维评分。
          </p>

          <div style="margin-top:26px">
            <div v-for="(question, index) in quiz.questions" :key="question.id" class="card card-pad" style="margin-bottom:14px">
              <div class="eyebrow" style="margin-bottom:8px">
                {{ String(index + 1).padStart(2, "0") }} · {{ question.type === "choice" ? "选择题" : "简答题" }}
              </div>
              <div class="quiz-question">{{ question.question }}</div>

              <div v-if="question.type === 'choice'" class="quiz-options">
                <label
                  v-for="(option, optionIndex) in question.options"
                  :key="optionIndex"
                  class="quiz-option"
                  :class="{ 'is-selected': answers[question.id] === 'ABCD'[optionIndex] }"
                >
                  <input v-model="answers[question.id]" type="radio" :name="question.id" :value="'ABCD'[optionIndex]" />
                  <span class="quiz-letter">{{ "ABCD"[optionIndex] }}</span>
                  <span>{{ option }}</span>
                </label>
              </div>

              <textarea
                v-else
                v-model="answers[question.id]"
                rows="4"
                placeholder="用自己的话写清楚：结论 + 为什么 + 一个例子"
                style="margin-top:10px"
              ></textarea>
            </div>
          </div>

          <div style="display:flex;align-items:center;gap:12px;margin-top:20px">
            <button class="btn btn-primary" :disabled="submitting" @click="submit">
              {{ submitting ? "评分中…" : "提交测验" }}
            </button>
            <span class="tiny muted">已答 {{ answeredCount }} / {{ quiz.questions.length }} 题</span>
          </div>
          <div v-if="error" class="small" style="color:var(--rose);margin-top:10px">{{ error }}</div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.quiz-question {
  font-size: 15.5px;
  line-height: 1.8;
  color: var(--ink);
}

.quiz-options {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.quiz-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.quiz-option:hover {
  border-color: var(--blue);
}

.quiz-option.is-selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}

.quiz-option input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.quiz-letter {
  flex: none;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
}

.quiz-option.is-selected .quiz-letter {
  border-color: var(--blue);
  color: var(--blue);
  font-weight: 700;
}

.result-head {
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 8px;
}

.result-score {
  flex: none;
  width: 132px;
  height: 132px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 4px;
}

.result-score b {
  font-family: var(--font-display);
  font-size: 44px;
  line-height: 1;
  color: var(--ink);
}

.result-score span {
  font-size: 11px;
  color: var(--muted);
}

.result-score.is-green {
  border-color: color-mix(in srgb, var(--green) 35%, var(--line));
}

.result-score.is-amber {
  border-color: color-mix(in srgb, var(--amber) 35%, var(--line));
}

.result-score.is-rose {
  border-color: color-mix(in srgb, var(--rose) 35%, var(--line));
}

.dim-row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr) 36px;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12.5px;
  color: var(--muted);
}

.dim-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--paper-2);
  overflow: hidden;
}

.dim-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--blue);
}

textarea {
  width: 100%;
  resize: vertical;
  font: inherit;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  line-height: 1.7;
}
</style>
