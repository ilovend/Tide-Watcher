# 观潮 Tide-Watcher

> A 股个人择时选股系统 — 三级择时漏斗 × 财务排雷 × 量化策略引擎

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=next.js" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?logo=tailwindcss" />
  <img src="https://img.shields.io/badge/SQLite-2.1GB-003B57?logo=sqlite" />
</p>

---

## 核心能力

**择时引擎** — 三级优先级漏斗，自动生成红/黄/绿/灰四色信号灯

| 级别 | 触发条件 | 信号 | 操作 |
|------|---------|------|------|
| L1 绝对禁区 | 3/15~4/30 财报季 | 红灯 | 强制空仓 |
| L2 风险预警 | 3/5~3/14 跑路期 / 12月资金枯竭 | 黄/红灯 | 清仓离场 |
| L3 结算博弈 | 期指交割周 / 期权结算周 | 战术信号 | 撤退/建仓/观察 |
| — | 节假日 / 周末 | 灰灯 | 休市（附下一开盘日） |

**盘面守卫** — L3 建仓信号的二次确认：基于涨跌比、跌停数、情绪温度实时拦截或降级

**财务排雷** — 全市场 5190 只个股季度扫描，标记 ST / 退市风险股，个股查询页实时高亮预警

**量化策略** — 装饰器注册 + APScheduler 定时调度，一个文件一个策略

---

## 页面预览

| 页面 | 功能亮点 |
|------|---------|
| **观潮看板** | 四色择时 HUD + 结算日倒计时 + 盘面守卫状态 + 涨停 TOP10 |
| **股池监控** | 涨停/跌停/强势/炸板/次新 5 种股池 + 风险股 `[风险]` 标签 |
| **策略中心** | 策略列表 + 一键执行 + 信号历史 |
| **个股查询** | K 线蜡烛图 + 财务排雷深度面板 + 严禁买入 Toast |
| **市场情绪** | 5 阶段情绪指标 + 历史走势 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| **后端** | Python 3.11 · FastAPI · SQLAlchemy · APScheduler · httpx · tenacity · chinesecalendar |
| **前端** | Next.js 16 · React 19 · TailwindCSS 4 · shadcn/ui · Lightweight Charts · Sonner |
| **存储** | SQLite（日 K 线 1578 万行 + 10 张业务表） |
| **数据源** | ZhituAPI（包年版，3000 次/分钟） |

---

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt   # Windows
# venv/bin/pip install -r requirements.txt     # Linux/Mac

cp .env.example .env
# 编辑 .env，填入 ZHITU_TOKEN

venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

打开 http://localhost:3000 即可使用。后端 API 文档：http://localhost:8000/docs

---

## 项目结构

```
backend/
├── app/
│   ├── api/           → REST 接口（25+ 端点）
│   ├── data/          → 数据采集（ZhituAPI 适配器 + 缓存 + 限流）
│   ├── store/         → ORM 模型 + SQLite 连接
│   ├── engine/        → 择时漏斗 + 盘面守卫 + 财务排雷 + 策略调度
│   └── strategies/    → 策略定义（一文件一策略）

frontend/
├── src/app/           → 5 个页面路由
├── src/components/    → 侧边栏 + K 线图 + shadcn/ui
└── src/lib/           → API 客户端 + 格式化工具

docs/
├── ARCHITECTURE.md    → 架构设计文档
└── zhitu_api_docs.md  → ZhituAPI 接口文档
```

---

## 添加新策略

```python
# backend/app/strategies/my_strategy.py
from app.engine.registry import strategy

@strategy(name="我的策略", schedule="14:50", description="策略描述")
async def my_strategy(ctx):
    pool = await ctx.get_pool("涨停股池")
    for stock in pool:
        if stock.get("lbc", 0) >= 2:
            ctx.add_signal(code=stock["dm"], name=stock.get("mc", ""), score=80)
    return ctx.results
```

保存文件后重启服务即可自动注册。

---

## 文档

- [架构设计](docs/ARCHITECTURE.md) — 系统总览、分层设计、状态机、定时任务
- [项目状态](PROJECT_STATUS.md) — 功能进度、待办事项、已知问题

## License

MIT
