# 观潮 (Tide-Watcher) 架构文档

> 版本：v0.3.1 | 更新日期：2026-02-20

---

## 一、系统总览

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js 16 前端                        │
│  Dashboard │ 股池监控 │ 策略中心 │ 个股查询 │ 市场情绪    │
│            (port 3000)                                   │
└──────────────────────┬──────────────────────────────────┘
                       │  REST API (JSON)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI 后端                            │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │ API 层  │→│ 引擎层    │→│ 数据层    │→│ 存储层   │  │
│  │ routes  │  │ timing   │  │ zhitu    │  │ sqlite  │  │
│  │         │  │ guard    │  │ cache    │  │ models  │  │
│  │         │  │ risk     │  │ limiter  │  │ sync    │  │
│  └─────────┘  └──────────┘  └──────────┘  └─────────┘  │
│            (port 8000)                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ ZhituAPI │ │  SQLite  │ │ chinese  │
    │ (远程)   │ │ (本地DB) │ │ calendar │
    └──────────┘ └──────────┘ └──────────┘
```

---

## 二、后端分层架构

### 2.1 API 层 (`app/api/`)

| 文件 | 前缀 | 职责 |
|------|------|------|
| `routes_stock.py` | `/api/stocks` | 股票实时行情、K线、公司信息、技术指标 |
| `routes_pool.py` | `/api/pools` | 股池、择时、结算日历、风险查询、全局状态 |
| `routes_strategy.py` | `/api/strategies` | 策略列表、执行、信号查询 |

**关键端点：**
- `GET /api/pools/global-status` — 全局状态（日期/假期/择时/风险股列表），前端全页面同步入口
- `GET /api/pools/timing/today` — 今日择时信号（含休市检测）
- `GET /api/pools/timing/calendar` — 结算日历（期货/期权交割日+倒计时）
- `GET /api/pools/risk/check/{code}` — 单股财务风险查询

### 2.2 引擎层 (`app/engine/`)

#### 择时漏斗 (`timing.py`)
```
输入: 日期 d
  │
  ├── 是否交易日？ ──否──→ GREY/INACTIVE（灰色休市态）
  │                         附带: holiday_name, next_open_date
  ├── Level 1: 绝对禁区 (3/15~4/30) ──→ RED/FORCE_EMPTY
  ├── Level 2: 风险预警 (3/5~3/14 + 12月) ──→ YELLOW or RED
  ├── Level 3: 结算周博弈 ──→ 战术信号
  └── 无特殊信号 ──→ GREEN/NORMAL
```

信号优先级：L1 > L2 > L3 > 正常

#### 盘面守卫 (`guard.py`)
- 仅在 L3 `PROBE_ENTRY`（试探建仓）信号时激活
- 基于实时盘面数据（涨跌比、跌停数、情绪温度）二次确认
- 可拦截（→ OBSERVE）或降级（→ 轻仓试探）

#### 财务排雷 (`finance_risk.py`)
- 全市场 5190 只股票季度扫描
- 规则：ST/退市标记 + 营收不达标 + 连续亏损
- 结果写入 `financial_risk` 表
- 查询接口使用 `startswith` 兼容代码格式差异

#### 动态日历 (`calendar.py`)
- 基于 `chinese_calendar` 库判断交易日
- 期货交割日 = 每月第三个周五（遇假前移）
- 期权结算日 = 每月第四个周三（遇假前移）

### 2.3 数据层 (`app/data/`)

| 文件 | 职责 |
|------|------|
| `source_zhitu.py` | ZhituAPI 适配器（3000次/分钟） |
| `rate_limiter.py` | 令牌桶频率控制 |
| `cache.py` | 内存缓存（TTL 机制） |
| `kline_service.py` | K线查询：SQLite优先 → API兜底 |
| `kline_updater.py` | 日K线增量更新器 |

**数据流向：**
```
前端请求 → API层 → kline_service → SQLite(1578万行日K)
                                  ↘ ZhituAPI(仅本地无数据时)
```

### 2.4 存储层 (`app/store/`)

**SQLite 数据库** (`tide_watcher.db`, ~2.1GB)

| 表名 | 行数 | 用途 |
|------|------|------|
| `daily_kline` | ~1578万 | 全市场日K线历史 |
| `stock_list` | ~5190 | 股票基础信息 |
| `financial_risk` | ~269 | 财务风险标记 |
| `limit_up_pool` | 动态 | 涨停股池快照 |
| `broken_board_pool` | 动态 | 炸板股池快照 |
| `strong_pool` | 动态 | 强势股池快照 |
| `emotion_snapshot` | 动态 | 情绪指标快照 |
| `strategy_signal` | 动态 | 策略选股信号 |
| `sector_info` | ~500 | 板块信息 |
| `watchlist` | 用户自定义 | 自选股 |

---

## 三、前端架构

### 3.1 技术栈
- **框架**: Next.js 16 (Turbopack) + React 19
- **样式**: TailwindCSS 4 + shadcn/ui 组件库
- **图表**: Lightweight Charts (TradingView)
- **通知**: Sonner Toast
- **图标**: Lucide React

### 3.2 页面路由

```
frontend/src/
├── app/
│   ├── page.tsx           → / (Dashboard 观潮看板)
│   ├── pools/page.tsx     → /pools (股池监控)
│   ├── strategies/page.tsx → /strategies (策略中心)
│   ├── stocks/page.tsx    → /stocks (个股查询)
│   ├── emotion/page.tsx   → /emotion (市场情绪)
│   ├── layout.tsx         → 全局布局 (Sidebar + Sonner)
│   └── globals.css        → 全局样式 (暗色主题)
├── components/
│   ├── sidebar.tsx        → 侧边栏导航
│   ├── kline-chart.tsx    → K线蜡烛图组件
│   ├── error-message.tsx  → 错误提示组件
│   └── ui/                → shadcn/ui 基础组件
└── lib/
    ├── api.ts             → API 客户端 (25+ 端点)
    ├── format.ts          → 金额/百分比格式化
    └── utils.ts           → cn() 工具函数
```

### 3.3 HUD 状态机

```
后端 timing/today API
  │
  ├── light="休市" → 灰色(slate-500) Moon图标 + 呼吸灯
  ├── light="红灯" → 红色(red-500) ShieldOff图标
  ├── light="黄灯" → 琥珀(amber-500) ShieldAlert图标
  └── light="绿灯" → 翠绿(emerald-500) Shield图标
```

### 3.4 风险股视觉层级

| 风险等级 | 排雷面板样式 | Toast 行为 |
|---------|------------|-----------|
| extreme | `border-l-4 border-red-500 bg-gradient-to-r from-red-600/20` + `animate-pulse` | "⚠️ 命中财务红线名单 — 严禁买入" (10秒) |
| high | `border-2 border-amber-500/60 bg-amber-500/10` | "财务风险警告" (10秒) |
| 安全 | 无面板 | 无 |

---

## 四、定时任务调度

| 时间 | 任务 | 函数 |
|------|------|------|
| 14:30 | 择时流水线 | `run_timing_pipeline()` |
| 14:50 | 涨停板连板策略 | `策略: 涨停板连板` |
| 14:30 | 放量突破策略 | `策略: 放量突破` |
| 15:30 | 股池同步 + 情绪计算 | `sync_all_pools()` |
| 16:00 | K线增量更新 | `update_all_stocks()` |
| 16:30 | 股票列表同步 | `sync_stock_list()` |
| 季度(1/4/7/10月15日) | 财务排雷 | `scan_all_stocks()` |

---

## 五、数据源约定

### ZhituAPI
- **Base URL**: `https://api.zhituapi.com`
- **认证**: 查询参数 `token={ZHITU_TOKEN}`（非请求头）
- **频率**: 3000次/分钟（`rate_limiter.py` 控制）
- **特殊限制**: `realall` 接口每分钟最多1次
- **公司信息**: 使用纯代码（如 `000001`）
- **历史数据**: 使用带后缀代码（如 `000001.SZ`）

### 股票代码规范
- **内部统一**: `000001.SZ` 标准格式
- **转换函数**: `normalize_code()` (source_zhitu.py)
- **已知问题**: `financial_risk` 表存储为 `000004.SZ.BJ` 格式，查询用 `startswith` 兼容

---

## 六、环境配置

### 后端 (.env)
```
APP_ENV=development
DATABASE_URL=sqlite:///tide_watcher.db
ZHITU_TOKEN=<your_token>
```

### 前端 (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 启动命令
```bash
# 后端 (port 8000)
cd backend && ./venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端 (port 3000)
cd frontend && pnpm dev
```

---

## 七、已知限制与待办

1. **financial_risk 代码格式**: 表中为 `xxx.SZ.BJ`，应修复为 `xxx.SZ`
2. **情绪页面**: 缺少走势图可视化（仅数据表）
3. **综合建议矩阵**: 个股查询页尚未集成择时+排雷联合判断
4. **选股策略**: 仅有2个模板（涨停板连板、放量突破），需扩充
5. **实盘验证**: 春节后 2/24 首次全流程实盘测试
