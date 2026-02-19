# Tide-Watcher 🌊

> A 股个人选股系统 — 数据驱动的智能选股平台

## 功能概览

| 模块 | 功能 |
|------|------|
| **仪表盘** | 市场概览、策略信号汇总、涨停 TOP10 |
| **股池监控** | 涨停/跌停/强势/炸板/次新 五大股池实时监控 |
| **策略中心** | 策略管理、一键执行、信号历史查询 |
| **个股查询** | 实时行情、公司信息、近 20 日 K 线 |

## 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy / APScheduler / httpx / tenacity
- **前端**: Next.js 16 / React / TailwindCSS / shadcn/ui
- **数据库**: SQLite
- **数据源**: ZhituAPI（包年版）

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv venv
# Windows
venv/Scripts/pip install -r requirements.txt
# Linux/Mac
# venv/bin/pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入你的 ZHITU_TOKEN

venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档。

### 2. 前端

```bash
cd frontend
pnpm install
pnpm dev --port 3000
```

访问 http://localhost:3000 查看界面。

## 项目结构

```
Tide-Watcher/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── api/                 # REST 接口（16 个端点）
│   │   ├── data/                # 数据采集层（适配器+缓存+限流）
│   │   ├── store/               # 数据存储层（ORM 模型）
│   │   ├── engine/              # 策略引擎（注册表+执行器+调度器）
│   │   └── strategies/          # 策略定义（一文件一策略）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js 页面（4 个）
│   │   ├── components/          # UI 组件
│   │   └── lib/api.ts           # 后端 API 客户端
│   └── package.json
└── docs/
    └── zhitu_api_docs.md        # ZhituAPI 接口文档
```

## 添加新策略

复制模板并编辑：

```bash
cp backend/app/strategies/_template.py backend/app/strategies/my_strategy.py
```

策略只需三步：取数据 → 写条件 → 添信号：

```python
@strategy(name="我的策略", schedule="14:50")
async def my_strategy(ctx):
    pool = await ctx.get_pool("涨停股池")
    for stock in pool:
        if stock.get("lbc", 0) >= 2:
            ctx.add_signal(code=stock["dm"], name=stock.get("mc", ""), score=80)
    return ctx.results
```

重启服务器后策略自动注册生效。

## License

MIT
