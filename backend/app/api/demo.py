"""Public demo plan (no auth, no LLM cost)."""

from fastapi import APIRouter

router = APIRouter(tags=["demo"])

DEMO_PLAN = {
    "goal": "三个月掌握 FastAPI 后端开发（示例）",
    "level": "beginner",
    "daily_minutes": 45,
    "total_days": 90,
    "phases": [
        {
            "seq": 1,
            "title": "环境搭建与 Python 基础语法",
            "days": 20,
            "focus": "装好环境，能写出带输入输出和条件循环的小脚本",
            "knowledge_points": ["安装与虚拟环境", "变量与类型", "条件与循环", "函数"],
            "tasks": [
                {"title": "安装 Python 3.12 + VS Code，跑通 hello.py", "type": "coding", "duration_min": 45},
                {"title": "写一个成绩等级判断程序（if/elif/else）", "type": "coding", "duration_min": 45},
                {"title": "用函数封装一个命令行小工具", "type": "coding", "duration_min": 45},
            ],
        },
        {
            "seq": 2,
            "title": "FastAPI 路由与 Pydantic 模型",
            "days": 24,
            "focus": "能独立写 CRUD 接口，并用 /docs 自测",
            "knowledge_points": ["路由与路径参数", "请求/响应模型", "错误处理", "依赖注入"],
            "tasks": [
                {"title": "搭最小 FastAPI 项目并访问 /docs", "type": "coding", "duration_min": 45},
                {"title": "实现 items 的增删改查接口", "type": "coding", "duration_min": 45},
                {"title": "用 Pydantic 做请求校验并返回 422", "type": "coding", "duration_min": 45},
            ],
        },
        {
            "seq": 3,
            "title": "数据库、鉴权与测试",
            "days": 24,
            "focus": "接 SQLite/PostgreSQL，做注册登录与自动化测试",
            "knowledge_points": ["SQLAlchemy 2.x", "JWT 鉴权", "密码哈希", "pytest"],
            "tasks": [
                {"title": "用 SQLAlchemy 定义 User/Item 模型", "type": "coding", "duration_min": 45},
                {"title": "实现注册/登录与 JWT 校验", "type": "coding", "duration_min": 45},
                {"title": "给接口写 5 个 pytest 用例", "type": "coding", "duration_min": 45},
            ],
        },
        {
            "seq": 4,
            "title": "综合项目与部署",
            "days": 22,
            "focus": "完成一个可演示的小服务并部署上线",
            "knowledge_points": ["项目分层", "Docker", "环境变量", "部署"],
            "tasks": [
                {"title": "把一个完整小服务拆成 routers/services/models", "type": "coding", "duration_min": 45},
                {"title": "写 Dockerfile 并本地构建运行", "type": "coding", "duration_min": 45},
                {"title": "写 README + 架构图 + 复盘", "type": "writing", "duration_min": 45},
            ],
        },
    ],
}


@router.get("/demo/plan")
async def demo_plan() -> dict:
    return DEMO_PLAN
