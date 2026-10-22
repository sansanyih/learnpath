<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { chapterQuizApi } from "@/api/chapterQuiz";
import type { ChapterQuiz, ChapterQuizResult } from "@/api/chapterQuizTypes";

const props = defineProps<{ chapterId: string }>();
const emit = defineEmits<{ submitted: [score: number] }>();

const quiz = ref<ChapterQuiz | null>(null);
const answers = ref<Record<string, string>>({});
const result = ref<ChapterQuizResult | null>(null);
const loading = ref(true);
const submitting = ref(false);
const error = ref("");

const answered = computed(
  () => Object.values(answers.value).filter((value) => value.trim().length > 0).length,
);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    quiz.value = await chapterQuizApi.create(props.chapterId);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "章节测验生成失败";
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  if (!quiz.value || submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    result.value = await chapterQuizApi.submit(
      props.chapterId,
      quiz.value.questions.map((question) => ({
        quiz_id: question.id,
        answer: answers.value[question.id] ?? "",
      })),
    );
    emit("submitted", result.value.score);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "提交失败";
  } finally {
    submitting.value = false;
  }
}

function retry(): void {
  answers.value = {};
  result.value = null;
  void load();
}

onMounted(load);
</script>

<template>
  <div class="chapter-quiz">
    <div v-if="loading" class="empty" style="padding:30px 0">正在根据本章内容出题…</div>
    <div v-else-if="error" class="card card-pad">
      <div class="eyebrow">出错了</div>
      <p class="small" style="margin:8px 0 12px;color:var(--muted)">{{ error }}</p>
      <button class="btn btn-sm" @click="load">重试</button>
    </div>

    <template v-else-if="result">
      <div class="quiz-result-head">
        <div class="quiz-score card"><b>{{ result.score }}</b><span>本章得分</span></div>
        <div>
          <div class="eyebrow">CHAPTER QUIZ · 结果</div>
          <p class="small muted" style="margin:6px 0 0">
            已写回章节状态：{{ result.status === "mastered" ? "已掌握" : result.status === "review" ? "需复习" : "学习中" }}
          </p>
          <button class="btn btn-sm" style="margin-top:10px" @click="retry">再测一次</button>
        </div>
      </div>

      <div v-for="(item, index) in result.results" :key="item.quiz_id" class="card card-pad" style="margin-top:10px">
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
          <b style="font-size:13.5px">{{ index + 1 }}. {{ item.question }}</b>
          <span class="chip" :class="item.score >= 85 ? 'is-green' : item.score >= 60 ? '' : 'is-rose'">{{ item.score }}</span>
        </div>
        <p class="small muted" style="margin:6px 0 0">{{ item.feedback }}</p>
        <details class="small" style="margin-top:6px">
          <summary style="cursor:pointer;color:var(--muted)">参考答案</summary>
          <p style="margin:6px 0 0">{{ item.reference }}</p>
        </details>
      </div>
    </template>

    <template v-else-if="quiz">
      <div class="eyebrow" style="margin-bottom:6px">CHAPTER QUIZ · 3 选择 + 2 简答</div>
      <p class="small muted" style="margin:0 0 14px">根据本章讲解和文件出题，提交后自动评分并更新章节状态。</p>

      <div v-for="(question, index) in quiz.questions" :key="question.id" class="card card-pad" style="margin-bottom:10px">
        <div class="eyebrow" style="margin-bottom:6px">
          {{ String(index + 1).padStart(2, "0") }} · {{ question.type === "choice" ? "选择题" : "简答题" }}
        </div>
        <div style="font-size:14px;line-height:1.75">{{ question.question }}</div>

        <div v-if="question.type === 'choice'" class="chapter-options">
          <label
            v-for="(option, optionIndex) in question.options"
            :key="optionIndex"
            class="chapter-option"
            :class="{ 'is-selected': answers[question.id] === 'ABCD'[optionIndex] }"
          >
            <input v-model="answers[question.id]" type="radio" :name="question.id" :value="'ABCD'[optionIndex]" />
            <span class="chapter-letter">{{ "ABCD"[optionIndex] }}</span>
            <span>{{ option }}</span>
          </label>
        </div>

        <textarea
          v-else
          v-model="answers[question.id]"
          rows="3"
          placeholder="用自己的话写：结论 + 为什么 + 一个例子"
          style="margin-top:8px"
        ></textarea>
      </div>

      <div style="display:flex;gap:10px;align-items:center;margin-top:14px">
        <button class="btn btn-primary" :disabled="submitting" @click="submit">
          {{ submitting ? "评分中…" : "提交测验" }}
        </button>
        <span class="tiny muted">已答 {{ answered }} / {{ quiz.questions.length }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.quiz-result-head {
  display: flex;
  gap: 18px;
  align-items: center;
  margin-bottom: 8px;
}

.quiz-score {
  flex: none;
  width: 104px;
  height: 104px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 3px;
}

.quiz-score b {
  font-family: var(--font-display);
  font-size: 34px;
  line-height: 1;
}

.quiz-score span {
  font-size: 10px;
  color: var(--muted);
}

.chapter-options {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.chapter-option {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 9px 11px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  font-size: 13px;
  cursor: pointer;
}

.chapter-option.is-selected {
  border-color: var(--blue);
  background: var(--blue-soft);
}

.chapter-option input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.chapter-letter {
  flex: none;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}

.chapter-option.is-selected .chapter-letter {
  border-color: var(--blue);
  color: var(--blue);
  font-weight: 700;
}

textarea {
  width: 100%;
  resize: vertical;
  font: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 9px 11px;
}
</style>
