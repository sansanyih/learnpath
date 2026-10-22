<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const mode = ref<"login" | "register">("login");
const email = ref("");
const password = ref("");
const displayName = ref("");
const loading = ref(false);
const error = ref("");

async function submit(): Promise<void> {
  error.value = "";
  if (!email.value || !password.value) {
    error.value = "请填写邮箱和密码";
    return;
  }
  if (mode.value === "register" && password.value.length < 8) {
    error.value = "密码至少 8 位";
    return;
  }

  loading.value = true;
  try {
    if (mode.value === "login") {
      await session.login(email.value, password.value);
    } else {
      await session.register(email.value, password.value, displayName.value);
    }
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/plans";
    await router.push(redirect);
  } catch (err) {
    error.value = err instanceof ApiError ? err.message : "网络异常，请稍后再试";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="auth-shell">
    <aside class="auth-left">
      <router-link class="brand" to="/">
        <span class="brand-mark">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
        </span>
        <span>
          <span class="brand-name">学径</span>
          <span class="brand-sub">LEARN PATH</span>
        </span>
      </router-link>

      <div class="auth-quote" v-reveal="{ y: 24 }">
        <div class="eyebrow">YOUR PLAN, YOUR PROGRESS</div>
        <h1>计划是别人的，<br />进度得是自己的。</h1>
        <p>登录后，目标、任务勾选、测验成绩、批注和复习进度都按账号保存。换一台设备、隔一周回来，都能从上次停下的地方继续。</p>
        <ul class="auth-points">
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            计划与进度跨设备同步，不依赖浏览器缓存
          </li>
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            每次评分与掌握度都留历史，能回看"为什么被调整"
          </li>
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            批注与 AI 对话跟着章节走，不会散在聊天记录里
          </li>
        </ul>
      </div>

      <footer>学径 LearnPath · 个人项目 · 2026</footer>
    </aside>

    <main class="auth-right">
      <div class="auth-card" v-reveal="{ delay: 120, y: 24 }">
        <h2>{{ mode === "login" ? "登录学径" : "创建账号" }}</h2>
        <p class="auth-sub">
          {{ mode === "login" ? "继续你的学习计划，或先以游客身份体验。" : "邮箱 + 密码即可，不需要验证码。" }}
        </p>

        <form @submit.prevent="submit">
          <div v-if="mode === 'register'" class="field">
            <label for="name">怎么称呼你</label>
            <input id="name" v-model="displayName" type="text" placeholder="例如：小林" autocomplete="nickname" />
          </div>

          <div class="field">
            <label for="email">邮箱</label>
            <input id="email" v-model="email" type="email" placeholder="you@example.com" autocomplete="email" />
          </div>

          <div class="field">
            <label for="password">密码</label>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="至少 8 位"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            />
            <span class="hint">至少 8 位；连续 5 次失败会锁定 15 分钟</span>
          </div>

          <p v-if="error" class="contact-error" style="margin:0 0 12px">{{ error }}</p>

          <div class="auth-row">
            <label><input type="checkbox" checked /> 记住我（7 天）</label>
            <a href="#">忘记密码？</a>
          </div>

          <button class="btn btn-primary auth-submit" type="submit" :disabled="loading">
            {{ loading ? "请稍候…" : mode === "login" ? "登录" : "创建并登录" }}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </form>

        <div class="auth-divider">或</div>

        <div class="auth-alt">
          <button class="btn" type="button" disabled style="opacity:.65;cursor:not-allowed">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
            使用 GitHub 登录
            <span class="chip" style="margin-left:6px">即将支持</span>
          </button>
          <router-link class="btn" to="/plans" style="justify-content:center">
            先以游客身份体验
          </router-link>
        </div>

        <p class="auth-foot">
          {{ mode === "login" ? "还没有账号？" : "已经有账号？" }}
          <a href="#" @click.prevent="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === "login" ? "免费创建" : "直接登录" }}
          </a>
        </p>

        <div class="auth-tip">
          <b>游客模式：</b>可以生成一份示例计划并阅读章节，数据只存在当前浏览器；登录时可一键导入为正式计划。测验记录、批注与复习需要账号。
        </div>
      </div>
    </main>
  </div>
</template>
