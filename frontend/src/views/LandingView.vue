<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

onMounted(() => document.documentElement.classList.add("snap-landing"));
onUnmounted(() => document.documentElement.classList.remove("snap-landing"));

const goal = ref("");
const dailyMinutes = ref(45);
const customMinutes = ref(45);
const timeOpen = ref(false);
const presets = [15, 25, 45, 60, 90];

function pick(minutes: number): void {
  dailyMinutes.value = minutes;
  customMinutes.value = minutes;
  timeOpen.value = false;
}

function applyCustom(): void {
  const value = Math.min(120, Math.max(15, Math.round(Number(customMinutes.value) || 45)));
  dailyMinutes.value = value;
  customMinutes.value = value;
  timeOpen.value = false;
}

function start(): void {
  const query: Record<string, string> = { daily: String(dailyMinutes.value) };
  if (goal.value.trim()) query.goal = goal.value.trim();
  router.push({ name: "plans", query });
}
</script>

<template>
  <div class="landing">
    <div class="screen hero-screen">
    <nav class="nav">
      <router-link class="brand" to="/">
        <span class="brand-mark">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
        </span>
        <span>
          <span class="brand-name">学径</span>
          <span class="brand-sub">LEARN PATH</span>
        </span>
      </router-link>
      <div class="nav-links">
        <a href="#">功能</a>
        <a href="#">计划示例</a>
        <a href="#">复习机制</a>
        <a href="#">GitHub 学习</a>
      </div>
      <div class="nav-actions">
        <router-link class="btn btn-ghost" to="/login">登录</router-link>
        <router-link class="btn btn-primary" to="/plans">
          游客体验
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </router-link>
      </div>
    </nav>

    <header class="hero">
      <div>
        <div class="hero-eyebrow">
          <span class="dash"></span>
          <span class="eyebrow">AI LEARNING PLANNER · 动态计划 × 代码走读</span>
        </div>
        <h1 v-reveal="{ y: 0 }">
          <span class="line"><span class="line-inner">任何学习目标，</span></span>
          <span class="line"><span class="line-inner">拆成<em>每天的一小步</em>。</span></span>
        </h1>
        <p class="lead" v-reveal="{ delay: 80 }">
          说清目标、截止时间、每天能投入多少——可以是 FastAPI、前端面试，也可以是读懂一个开源仓库。AI 先给出阶段骨架，再逐阶段细化成每日任务；分数会回写计划，薄弱处自动加练。
        </p>

        <div class="hero-try" v-reveal="{ delay: 140 }">
          <input v-model="goal" type="text" placeholder="例如：三个月掌握 FastAPI 后端开发" aria-label="学习目标" />
          <div class="time-picker" :class="{ 'is-open': timeOpen }">
            <button class="time-select" type="button" aria-label="每天可投入时长" @click="timeOpen = !timeOpen">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
              每天 {{ dailyMinutes }} 分钟
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
            </button>
            <div class="time-menu">
              <div class="time-menu-head">每天可投入</div>
              <button
                v-for="preset in presets"
                :key="preset"
                class="time-opt"
                :class="{ 'is-active': dailyMinutes === preset }"
                type="button"
                @click="pick(preset)"
              >
                <span>{{ preset }} 分钟</span>
                <span class="hint">{{ preset === 15 ? "碎片" : preset === 25 ? "轻量" : preset === 45 ? "默认" : preset === 60 ? "整块" : "深度" }}</span>
              </button>
              <div class="time-menu-rule"></div>
              <div class="time-custom">
                <span>自定义</span>
                <input v-model.number="customMinutes" aria-label="自定义分钟数" @keyup.enter="applyCustom" />
                <span class="unit">分钟</span>
              </div>
              <div class="time-range">15 – 120 分钟，按你的节奏来</div>
            </div>
          </div>
          <button class="btn btn-primary" type="button" @click="start">
            生成骨架
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
        <div class="hero-alt" v-reveal="{ delay: 180 }">已有账号？<router-link to="/login">用邮箱登录</router-link>，保存进度与测验记录</div>

        <div class="guest-note" v-reveal="{ delay: 220 }">
          <span class="chip is-blue">生成示例计划</span>
          <span class="chip">阅读 1 个章节</span>
          <span class="chip">试 1 次 AI 追问</span>
          <span class="hint">游客数据只存在当前浏览器；登录后可保存进度、测验与复习计划。</span>
        </div>
      </div>

      <aside class="plan-preview" v-reveal="{ delay: 120, y: 28 }">
        <div class="pp-head">
          <div>
            <div class="pp-title">三个月掌握 FastAPI 后端开发</div>
            <div class="pp-sub">示例计划 · 12 周 · 每天 45 分钟 · 已投入 32h</div>
          </div>
          <div class="pp-ring">
            <svg width="74" height="74" viewBox="0 0 74 74">
              <circle cx="37" cy="37" r="30" fill="none" stroke="#e7e0d2" stroke-width="6"/>
              <circle class="ring-progress" cx="37" cy="37" r="30" fill="none" stroke="#2b4fbf" stroke-width="6" stroke-linecap="round"/>
            </svg>
            <span>42%</span>
          </div>
        </div>

        <div class="pp-weeks">
          <span class="pp-week is-done">W1</span>
          <span class="pp-week is-done">W2</span>
          <span class="pp-week is-done">W3</span>
          <span class="pp-week is-now">W4</span>
          <span class="pp-week">W5</span>
          <span class="pp-week">W6</span>
        </div>

        <div class="pp-list">
          <div class="pp-row"><span class="pp-seq">01</span><span>环境与路由骨架</span><span class="chip is-green">8/8</span></div>
          <div class="pp-row"><span class="pp-seq">02</span><span>Pydantic 校验与响应模型</span><span class="chip is-green">6/6</span></div>
          <div class="pp-row"><span class="pp-seq">03</span><span><b>异步数据库与事务</b></span><span class="chip is-blue">3/7</span></div>
          <div class="pp-row"><span class="pp-seq">04</span><span>鉴权与依赖注入</span><span class="chip">未开始</span></div>
        </div>

        <div class="pp-today">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
          今日 · <b>事务与回滚</b> · 25 分钟 · 附 1 道判分题
        </div>
      </aside>
    </header>
    </div>

    <section class="samples screen">
      <div class="samples-head" v-reveal="{ y: 20 }">
        <div>
          <div class="eyebrow">REAL EXAMPLES</div>
          <h2 class="display h2">先看三份真实的计划</h2>
        </div>
        <span class="muted">不是示意图，点开就是示例内容</span>
      </div>
      <div class="sample-bento">
        <router-link class="sample-card is-featured" to="/plans" v-reveal="{ delay: 60 }">
          <div class="sample-top"><span class="chip is-blue">GOAL</span><span class="mono">12 周 · 每天 45 分钟 · 已学 32h</span></div>
          <h3>三个月掌握 FastAPI 后端开发</h3>
          <p>从路由、校验、异步事务到鉴权与部署，每个阶段都有可验收的交付物。</p>
          <div class="sample-mini">
            <div class="mini-row"><span class="seq">01</span><span>环境与路由骨架</span><div class="bar"><i class="done" style="width:100%"></i></div><b>8/8</b></div>
            <div class="mini-row"><span class="seq">02</span><span>请求校验与响应模型</span><div class="bar"><i class="done" style="width:100%"></i></div><b>6/6</b></div>
            <div class="mini-row"><span class="seq">03</span><span>异步数据库与事务</span><div class="bar"><i style="width:43%"></i></div><b>3/7</b></div>
            <div class="mini-row"><span class="seq">04</span><span>鉴权与依赖注入</span><div class="bar"><i style="width:0%"></i></div><b>0/9</b></div>
          </div>
          <div class="sample-foot">
            <span class="open">打开示例
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </span>
            <span class="mono meta">48 知识点 · 5 阶段</span>
          </div>
        </router-link>

        <div class="sample-stack">
          <router-link class="sample-card tint-amber" to="/plans" v-reveal="{ delay: 140 }">
            <div class="sample-top"><span class="chip is-amber">GOAL</span><span class="mono">6 周 · 每周 10H</span></div>
            <h3>六周补齐前端面试：Vue 与工程化</h3>
            <p>按面试频率排期，先自己答、再对照评分；答错的点自动安排复习。</p>
            <div class="sample-foot">
              <span class="open">打开示例
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </span>
              <span class="mono meta">30 知识点 · 18 测验</span>
            </div>
          </router-link>
          <router-link class="sample-card tint-green" to="/plans" v-reveal="{ delay: 220 }">
            <div class="sample-top"><span class="chip is-green">REPO</span><span class="mono">9 章 · 60 文件</span></div>
            <h3>读懂 fastapi：从入口到依赖注入</h3>
            <p>以仓库里的真实文件为线索，每章给出代码走读任务与检查题。</p>
            <div class="sample-foot">
              <span class="open">打开示例
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </span>
              <span class="mono meta">18 个走读任务</span>
            </div>
          </router-link>
        </div>
      </div>
    </section>

    <div class="screen combined-screen">
    <section class="why">
      <div class="why-left" v-reveal="{ y: 20 }">
        <div class="eyebrow">WHY LEARNPATH</div>
        <h2>不是又一份<br />看起来很美、<br />然后吃灰的计划。</h2>
        <p>大多数 AI 计划在生成那一刻就结束了。这里多做了一步：每一道题的分数都会回到计划里，决定明天到底学什么。</p>
      </div>
      <div class="why-list">
        <div class="why-item" v-reveal>
          <span class="why-num">01</span>
          <div>
            <h3>骨架先行，再逐段细化</h3>
            <p>先让模型只输出「阶段名 + 天数 + 知识点」的短骨架并做校验，再按阶段单独细化。避免一次性生成超长计划，越往后质量越崩。</p>
          </div>
        </div>
        <div class="why-item" v-reveal>
          <span class="why-num">02</span>
          <div>
            <h3>贴着 GitHub 仓库学</h3>
            <p>粘贴仓库链接，自动读目录与关键文件，切成学习章节：先讲清这段代码解决什么问题，再给代码走读任务与检查题，不是泛泛的知识点。</p>
          </div>
        </div>
        <div class="why-item" v-reveal>
          <span class="why-num">03</span>
          <div>
            <h3>分数回写计划</h3>
            <p>掌握度按「正确率 × 新鲜度」衰减。低于阈值的知识点会自动加练、降难度；稳定通过的阶段直接跳过，复习间隔随理解程度拉长。</p>
          </div>
        </div>
      </div>
    </section>

    <section class="steps">
      <div class="steps-head" v-reveal="{ y: 20 }">
        <h2 class="display h2">从一句目标，到每天具体做什么</h2>
        <span class="eyebrow">ONE LOOP, FOUR MOVES</span>
      </div>
      <div class="steps-row">
        <div class="step" v-reveal>
          <span class="mono">STEP 01</span>
          <h4>说清目标</h4>
          <p>目标、截止时间、每天可投入、当前水平，可选补一个 GitHub 仓库。</p>
        </div>
        <div class="step" v-reveal>
          <span class="mono">STEP 02</span>
          <h4>生成与拆解</h4>
          <p>骨架 → 校验 → 逐阶段细化 → 落到每日任务与验收标准。</p>
        </div>
        <div class="step" v-reveal>
          <span class="mono">STEP 03</span>
          <h4>读、写、测</h4>
          <p>章节阅读支持批注与 AI 追问，测验按评分维度给分并解释扣分点。</p>
        </div>
        <div class="step" v-reveal>
          <span class="mono">STEP 04</span>
          <h4>回写与重排</h4>
          <p>得分进入掌握度模型，触发跳过 / 复习 / 加练，复习队列按间隔重复生成。</p>
        </div>
      </div>
    </section>
    </div>

    <div class="screen end-screen">
    <section class="final-cta" v-reveal>
      <span class="eyebrow">START SMALL, STAY CONSISTENT</span>
      <h2>从今天的一小步开始。</h2>
      <p>每天 15 分钟还是 1 小时，你定。先把第一周排出来，剩下的交给每天的反馈。</p>
      <router-link class="btn-pill" to="/plans">
        生成我的计划
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </router-link>
      <span class="final-note">免注册可试用 · 不需要信用卡 · 随时导出</span>
    </section>

    <footer class="site-footer">
      <router-link class="brand" to="/">
        <span class="brand-mark">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-2 1.5-3.5 4-4l6-1.5c2.5-.6 4-2 4-4"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/></svg>
        </span>
        <span>
          <span class="brand-name">学径</span>
          <span class="brand-sub">LEARN PATH</span>
        </span>
      </router-link>
      <p>把目标拆成每天的一小步。</p>
      <div class="links">
        <a href="#">反馈</a>
        <router-link to="/login">登录</router-link>
        <a href="#">GitHub</a>
      </div>
    </footer>
    </div>
  </div>
</template>
