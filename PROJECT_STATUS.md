# 观潮 (Tide-Watcher) 项目状态文档

> 最后更新：2026-02-20  
> 版本：v0.3

---

## 一、系统概述

Tide-Watcher 是一个 A 股个人选股辅助决策系统，核心能力：
- **择时引擎**：三级优先级漏斗 + 盘面守卫二次确认
- **财务排雷**：全市场 5190 只股票自动扫描，标记 ST/退市风险
- **数据引擎**：ZhituAPI 数据源 + SQLite 本地缓存 + 自动调度
- **可视化**：Next.js 16 暗色主题多页面看板（shadcn/ui + Lightweight Charts）

---

## 二、择时逻辑（三级漏斗）

### Level 1：绝对禁区（最高优先级）
- **时间段**：每年 3月15日 ~ 4月30日
- **动作**：🔴 强制红灯 → 绝对空仓
- **原因**：年报/一季报密集披露期，财报暴雷高发
- **规则**：严禁任何建仓操作，无论其他信号如何

### Level 2：风险预警区（次高优先级）
- **2A 风险前置跑路期**：3月5日 ~ 3月14日
  - 🟡 黄灯 → 清仓离场
  - 为 L1 绝对禁区前的缓冲撤退窗口
- **2B 资金面枯竭期**：12月全月
  - 🔴 红灯 → 建议休息
  - 年末资金回笼压力大，机构调仓密集
- **约束**：仅允许离场预警，严禁建仓

### Level 3：常规结算周博弈（安全时段战术执行）

#### 双周期定义
| 周期 | 名称 | 交割/结算日 | 计算规则 |
|------|------|-----------|---------|
| A | 期货周 | 每月第3个周五 | `_nth_weekday_of_month(year, month, 4, 3)` |
| B | 期权周 | 每月第4个周三 | `_nth_weekday_of_month(year, month, 2, 4)` |

> 若交割/结算日遇非交易日，自动回退到前一个交易日

#### 战术节奏
1. **前置撤退（结算周前的周五 14:30）**：🟡 减仓/离场
2. **战术执行日（结算周的周二 14:30）**：🟢 观察回落，试探建仓
3. **结算日观察（周三/周五 15:00后）**：🟡 结算完成，观察情绪切换

#### 盘面守卫（L3 二次确认）
当 L3 发出 `PROBE_ENTRY` 信号时，通过实时盘面数据二次确认：

| 检查项 | 阈值 | 触发动作 |
|--------|------|---------|
| 指数跌幅 | > 3% | 🔴 拦截 → 禁止建仓 |
| 跌停数 | > 200 只 | 🔴 拦截 → 禁止建仓 |
| 涨跌比 | 跌 > 涨×3 | 🔴 拦截 → 禁止建仓 |
| 炸板率 | > 50% | 🟡 降级 → 极轻仓（≤1成） |
| 跌停数 | > 50 只 | 🟡 降级 → 极轻仓（≤1成） |

**失败安全**：API 请求失败时默认最严格拦截（禁止建仓）

#### 优先级覆盖
```
L1 触发 → 屏蔽 L2 和 L3
L2 触发 → 屏蔽 L3
L3 触发 → 需通过盘面守卫确认
```

---

## 三、财务排雷

### 扫描规则

| 规则 | 条件 | 适用板块 |
|------|------|---------|
| **低营收** | 营收 < 3亿 且 年度亏损 | 主板（000x/001x/60x） |
| **低营收** | 营收 < 1亿 | 创业板(300x)/科创板(688x)/北交所(4xx/8xx) |
| **连续亏损** | 连续 ≥3年 净利润为负 | 所有板块 |
| **极端风险** | 低营收 + 连续3年亏损 | `is_extreme_risk = True` |

### 数据现状（2026-02-20 扫描）
- **总扫描**：5190 只股票
- **总标记**：~697 只（`financial_risk` 表）
- **极端风险**：269 只（`is_extreme_risk = 1`）
- **存储位置**：`backend/tide_watcher.db` → `financial_risk` 表

### 两步扫描流程
```
Step 1: 基础扫描（/hs/gs/cwzb 财务指标）
  → 浮动阈值筛选 → ~697 只标记

Step 2: 深度扫描（/hs/fin/income 利润表）
  → 仅对已标记股票 → 补齐3年利润 → 269 只 is_extreme_risk
```

### 字段映射（ZhituAPI cwzb 接口）
| 字段 | 含义 | 注意 |
|------|------|------|
| `kflr` | 扣非净利润（元） | 绝对值 |
| `zyyw` | 主营业务收入（元） | 绝对值（非 `zysr`，那是增长率） |
| `date` | 报告期 | 如 2024-12-31 |
| `"--"` | 无数据 | 视为 None，不误标 |

---

## 四、数据架构

### 数据库（SQLite）
- **文件**：`backend/tide_watcher.db`（~2.1 GB）
- **表结构**（5层10张表）：

| 层 | 表名 | 行数 | 说明 |
|----|------|------|------|
| 基础 | `stocks` | ~5190 | 股票列表 |
| 基础 | `daily_kline` | 1578万 | 日K线（含 pre_close/change_pct） |
| 盘面 | `limit_up_pool` | 按日 | 涨停股池 |
| 盘面 | `broken_board_pool` | 按日 | 炸板股池 |
| 盘面 | `strong_pool` | 按日 | 强势股池 |
| 情绪 | `emotion_snapshot` | 按日 | 情绪快照（自动计算） |
| 板块 | `sector` | 2218 | 板块定义 |
| 板块 | `stock_sector` | 20.6万 | 股票-板块关联 |
| 风控 | `financial_risk` | ~697 | 财务风险标记 |
| 策略 | `strategy_signals` | 动态 | 策略产生的信号 |

### ZhituAPI 接口桥接

**Base URL**: `https://api.zhituapi.com`  
**认证**: 查询参数 `token={ZHITU_TOKEN}`  
**频率限制**:
- 通用：3000 次/分（滑动窗口 RateLimiter）
- realall：额外 1 次/分（SingleCallLimiter）
- 财务扫描：并发信号量 10 + 批次延时 0.5s

**核心接口**:
| 接口 | 路径 | 用途 |
|------|------|------|
| 全市场行情 | `/hs/public/realall` | 涨跌统计、指数跌幅 |
| 单股行情 | `/hs/real/ssjy/{code}` | 实时行情 |
| 历史K线 | `/hs/history/{code}/{level}/{adjust}` | K线数据 |
| 股池 | `/hs/pool/{type}/{date}` | 涨停/跌停/强势/炸板/次新 |
| 财务指标 | `/hs/gs/cwzb/{code}` | 净利润、营收等 |
| 利润表 | `/hs/fin/income/{code}` | 完整历史利润表 |
| 公司信息 | `/hs/gs/gsjj/{code}` | 公司简介、板块 |

### 调度器任务（APScheduler）
| 时间 | 任务 | 函数 |
|------|------|------|
| 14:30 | 择时流水线 | `run_timing_pipeline()` |
| 15:30 | 股池同步 + 情绪计算 | `sync_all_pools()` |
| 16:00 | K线增量更新 | `update_all_stocks()` |
| 16:30 | 股票列表同步 | `sync_stock_list()` |
| 季度(1/4/7/10月15日) | 财务排雷 | `scan_all_stocks()` |

---

## 五、前端架构（Next.js 16）

**启动**: `cd frontend && pnpm dev`
**技术栈**: Next.js 16 + React 19 + TailwindCSS 4 + shadcn/ui + Lightweight Charts + Sonner Toast

### 页面功能分布

| 页面 | 文件 | 功能 |
|------|------|------|
| **观潮看板** | `src/app/page.tsx` | 三级择时红绿灯 HUD（红/黄/绿渐变）+ 结算日倒计时 + 盘面守卫状态 + 策略信号 + 涨停TOP10 |
| **股池监控** | `src/app/pools/page.tsx` | 5种股池Tab（涨停/跌停/强势/炸板/次新）+ 日期选择 |
| **策略中心** | `src/app/strategies/page.tsx` | 策略列表 + 一键执行 + 信号历史表 |
| **个股查询** | `src/app/stocks/page.tsx` | 实时行情 + K线图(Lightweight Charts) + 财务排雷深度面板(风险指标明细) + Toast预警 |
| **市场情绪** | `src/app/emotion/page.tsx` | 5阶段指标卡 + 情绪走势表 |

### 综合操作建议矩阵

| 择时信号 | 财务状态 | 建议 |
|---------|---------|------|
| L1 红灯 | 任何 | 🚫 禁买 |
| L2 黄灯 | 任何 | 🚨 清仓离场 |
| L3 绿灯 | 极端风险 | 🚫 禁买（环境+个股双雷） |
| L3 绿灯 | 普通风险 | ⚠️ 谨慎 |
| L3 绿灯 | 安全 | ✅ 可试探建仓 |
| 正常 | 安全 | ✅ 正常交易 |

---

## 六、后端目录结构

```
backend/
├── app/
│   ├── api/                → REST 接口层
│   │   ├── routes_stock.py     → 股票查询 API
│   │   ├── routes_pool.py      → 股池/择时/风控 API
│   │   └── routes_strategy.py  → 策略执行 API
│   ├── data/               → 数据采集层
│   │   ├── source_zhitu.py     → ZhituAPI 适配器
│   │   ├── source_base.py      → DataSource 基类
│   │   ├── rate_limiter.py     → 频率控制器
│   │   ├── cache.py            → 内存缓存
│   │   └── kline_updater.py    → K线增量更新
│   ├── store/              → 数据存储层
│   │   ├── models.py           → ORM 模型（10张表）
│   │   ├── database.py         → SQLite 连接
│   │   └── sync.py             → 定时同步任务
│   ├── engine/             → 策略引擎层
│   │   ├── calendar.py         → 动态交易日历
│   │   ├── timing.py           → 三级择时漏斗
│   │   ├── guard.py            → 盘面守卫
│   │   ├── bridge.py           → 数据桥接（API→守卫）
│   │   ├── finance_risk.py     → 财务排雷扫描器
│   │   ├── context.py          → 策略执行上下文
│   │   ├── registry.py         → 策略注册表
│   │   ├── runner.py           → 策略执行器
│   │   └── scheduler.py        → APScheduler 调度
│   └── strategies/         → 策略定义层（待编写）
├── scripts/                → 工具脚本
├── tide_watcher.db         → SQLite 数据库（~2.1GB）
└── requirements.txt        → Python 依赖

frontend/
├── src/
│   ├── app/                → Next.js 页面（5个路由）
│   ├── components/         → 通用组件（sidebar/kline-chart/ui/）
│   └── lib/                → API 客户端 + 格式化工具
├── package.json            → pnpm 依赖（670 packages）
└── .env.local              → NEXT_PUBLIC_API_URL
```

---

## 七、依赖清单

### 后端（Python）
```
fastapi, uvicorn, httpx, tenacity, pydantic-settings, python-dotenv,
sqlalchemy, aiosqlite, apscheduler, pandas, chinesecalendar
```

### 前端（Node.js / pnpm）
```
next@16, react@19, tailwindcss@4, shadcn/ui, lightweight-charts,
lucide-react, sonner, radix-ui, class-variance-authority
```

---

## 八、待办事项

- [ ] 编写选股策略（`strategies/` 目录）
- [ ] 连续亏损规则可进一步用 `/hs/fin/income` 深度扫描全市场（目前仅对已标记股扫描）
- [ ] 交易日盘中实测择时+守卫完整流程
- [ ] 清理 `scripts/` 目录中的临时调试脚本
- [ ] 前端情绪页面增加 Plotly/Recharts 评分走势图
- [ ] 个股查询页面增加择时+排雷综合操作建议矩阵
