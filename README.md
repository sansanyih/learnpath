# 学径 LearnPath · AI 学习规划师

> **M4 已完成**：AI 助手常驻右栏（Agent：DuckDuckGo / Tavily + 网页读取 + 来源引用 + 对话落库 + 存为批注）、章节测验与章节复习、复习队列、掌握度看板、章节状态条与上一节/下一节。
> **P1 已完成**：登录锁定、token 日配额、账号导出/注销（7 天恢复）、游客示例计划 `/demo`、连续学习/本周投入/复习策略统计。
> 下一步：管理台（M4.5）、部署（M5）。方案见 [`docs/技术方案.md`](docs/技术方案.md)，约定与验收见 [`docs/工程手册.md`](docs/工程手册.md) / [`docs/验收清单.md`](docs/验收清单.md)。

## 目录

```
ai-learning-planner/
├─ backend/                  # FastAPI（登录 / health / mock SSE）
│  ├─ app/
│  └─ tests/
├─ frontend/                 # Vue 3 + TS + Vite + Pinia
│  └─ src/
│     ├─ views/              # 落地页 / 登录 / 计划
│     ├─ composables/        # useSSE
│     ├─ design/base.css     # 设计系统（与视觉稿同源）
│     └─ stores/
├─ docs/
│  ├─ 技术方案.md
│  ├─ 工程手册.md
│  ├─ mockups/               # 高保真静态稿（含管理台）
│  ├─ screenshots/           # M0 运行截图
│  └─ assets/ui/
└─ README.md
```

## 本地启动

```bash
# 后端（终端 1）
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# 前端（终端 2）
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173
```

打开 <http://127.0.0.1:5173>，游客可直接在 `/plans` 点「生成示例骨架」看 SSE 流式渲染；登录/注册走真实 JWT。

## 运行截图

| 落地页 | 登录 | 计划页（mock / 骨架） |
| --- | --- | --- |
| ![落地页](docs/screenshots/m0-landing.png) | ![登录](docs/screenshots/m0-login.png) | ![计划](docs/screenshots/m0-plans.png) |

| 我的计划 | 计划详情（真实 LLM 生成） |
| --- | --- |
| ![计划列表](docs/screenshots/m1-plans.png) | ![计划详情](docs/screenshots/m1-plan-detail.png) |

| 从仓库学（画像 + 章节） | 章节阅读（代码走读讲解） |
| --- | --- |
| ![从仓库学](docs/screenshots/m2-plan-repo.png) | ![章节阅读](docs/screenshots/m2-chapter.png) |

| 章节 tabs + 行号代码块 |
| --- |
| ![章节 tabs](docs/screenshots/m2-chapter-tabs.png) |

| 阶段测验 | 评分结果 + 调整建议 |
| --- | --- |
| ![阶段测验](docs/screenshots/m3-quiz.png) | ![评分结果](docs/screenshots/m3-result.png) |

| 任务勾选与学习进度 | 任务「怎么学」独立页 |
| --- | --- |
| ![计划进度](docs/screenshots/m3-plan.png) | ![怎么学](docs/screenshots/m3-task-page.png) |

| 计划水平选择（默认入门） |
| --- |
| ![水平选择](docs/screenshots/m3-level.png) |

| AI 助手（常驻右栏 + 搜索 + 引用） | 复习队列 |
| --- | --- |
| ![AI 助手](docs/screenshots/m4-panel-persistent.png) | ![复习队列](docs/screenshots/m4-review.png) |

| 章节测验 | 章节复习（薄弱题） |
| --- | --- |
| ![章节测验](docs/screenshots/m4-chapter-quiz.png) | ![章节复习](docs/screenshots/m4-chapter-review.png) |

| 章节状态条 + 上一节/下一节 |
| --- |
| ![章节状态](docs/screenshots/m4-chapter-bar.png) |

## 一句话产品

输入学习目标（可附 GitHub 仓库）→ 生成「阶段骨架 → 每日任务」；测验分数回写掌握度，自动跳过 / 加练 / 重排，并按间隔重复安排复习。

## 关键文档

- 技术方案：`docs/技术方案.md`（账号、管理台、数据模型、接口、部署、简历叙事）
- 工程手册：`docs/工程手册.md`（约定、坑位、里程碑验收）
- 设计稿：`docs/mockups/`，设计 token：`frontend/src/design/base.css` 顶部 `:root`
