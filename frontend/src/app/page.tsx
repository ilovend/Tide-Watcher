"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  TrendingUp,
  Play,
  Zap,
  Activity,
  Shield,
  ShieldAlert,
  ShieldOff,
  Calendar,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import {
  strategyApi,
  poolApi,
  type StrategyInfo,
  type Signal,
  type PoolStock,
  type TimingSignal,
  type SettlementCalendar,
} from "@/lib/api";

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ==================== 择时 HUD 配色 ====================

const LIGHT_CONFIG: Record<string, {
  bg: string; border: string; text: string; glow: string;
  icon: typeof Shield; label: string;
}> = {
  "红灯": {
    bg: "bg-red-950/60",
    border: "border-red-500/50",
    text: "text-red-400",
    glow: "shadow-red-500/20 shadow-lg",
    icon: ShieldOff,
    label: "危险",
  },
  "黄灯": {
    bg: "bg-amber-950/40",
    border: "border-amber-500/40",
    text: "text-amber-400",
    glow: "shadow-amber-500/15 shadow-lg",
    icon: ShieldAlert,
    label: "警戒",
  },
  "绿灯": {
    bg: "bg-emerald-950/30",
    border: "border-emerald-500/30",
    text: "text-emerald-400",
    glow: "shadow-emerald-500/10 shadow-lg",
    icon: Shield,
    label: "安全",
  },
};

function getLightConfig(light: string) {
  return LIGHT_CONFIG[light] || LIGHT_CONFIG["绿灯"];
}

export default function Dashboard() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [signals, setSignals] = useState<Record<string, Signal[]>>({});
  const [ztPool, setZtPool] = useState<PoolStock[]>([]);
  const [timing, setTiming] = useState<TimingSignal | null>(null);
  const [calendar, setCalendar] = useState<SettlementCalendar | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [stRes, poolRes, timingRes, calRes] = await Promise.all([
          strategyApi.list(),
          poolApi.get("ztgc", today()).catch(() => ({ data: [] as PoolStock[] })),
          poolApi.timingToday().catch(() => null),
          poolApi.timingCalendar().catch(() => null),
        ]);
        setStrategies(stRes.data);
        setZtPool(poolRes.data.slice(0, 10));
        if (timingRes) setTiming(timingRes);
        if (calRes) setCalendar(calRes);
      } catch (e) {
        console.error("加载失败", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleRunAll() {
    setRunning(true);
    try {
      const res = await strategyApi.runAll();
      setSignals(
        Object.fromEntries(
          Object.entries(res.results).map(([name, r]) => [name, r.signals])
        )
      );
      const totalSignals = Object.values(res.results).reduce((s, r) => s + r.signal_count, 0);
      toast.success("全部策略执行完成", {
        description: `${res.strategy_count} 个策略，共产生 ${totalSignals} 个信号`,
      });
    } catch (e) {
      toast.error("策略执行失败", {
        description: e instanceof Error ? e.message : "未知错误",
      });
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full rounded-xl" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  const totalSignals = Object.values(signals).flat().length;
  const lc = timing ? getLightConfig(timing.light) : getLightConfig("绿灯");
  const LightIcon = lc.icon;

  // 判断是否为守卫拦截/降级场景
  const isGuardBlock = timing?.action === "结算观察" && timing?.reason?.includes("守卫拦截");
  const isGuardDowngrade = timing?.reason?.includes("守卫降级");

  return (
    <div className="space-y-6">
      {/* ==================== 择时 HUD 状态条 ==================== */}
      <div
        className={`relative overflow-hidden rounded-xl border-2 ${lc.border} ${lc.bg} ${lc.glow} p-5 transition-all duration-500`}
      >
        <div className="flex items-start justify-between gap-4">
          {/* 左侧：信号灯 + 状态 */}
          <div className="flex items-center gap-4">
            <div className={`flex h-14 w-14 items-center justify-center rounded-full ${lc.bg} border ${lc.border}`}>
              <LightIcon className={`h-7 w-7 ${lc.text}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-2xl font-bold ${lc.text}`}>
                  {timing?.light || "绿灯"}
                </span>
                {timing && timing.level > 0 && (
                  <Badge variant="outline" className={`${lc.text} border-current text-xs`}>
                    L{timing.level}
                  </Badge>
                )}
                <Badge variant="secondary" className="text-xs">
                  {timing?.action || "正常交易"}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {timing?.reason || "正常交易时段"}
              </p>
            </div>
          </div>

          {/* 右侧：结算日倒计时 */}
          {calendar && (
            <div className="hidden shrink-0 md:flex items-center gap-4">
              <div className="text-right">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  期货交割
                </div>
                <div className={`text-lg font-bold tabular-nums ${
                  calendar.days_to_futures <= 3 ? "text-amber-400" : "text-foreground"
                }`}>
                  {calendar.days_to_futures === 0 ? "今日" : `${calendar.days_to_futures}天`}
                </div>
                <div className="text-xs text-muted-foreground">{calendar.next_futures_day}</div>
              </div>
              <div className="h-10 w-px bg-border" />
              <div className="text-right">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  期权结算
                </div>
                <div className={`text-lg font-bold tabular-nums ${
                  calendar.days_to_options <= 3 ? "text-amber-400" : "text-foreground"
                }`}>
                  {calendar.days_to_options === 0 ? "今日" : `${calendar.days_to_options}天`}
                </div>
                <div className="text-xs text-muted-foreground">{calendar.next_options_day}</div>
              </div>
              {(calendar.is_futures_week || calendar.is_options_week) && (
                <>
                  <div className="h-10 w-px bg-border" />
                  <Badge variant="outline" className="border-amber-500/50 text-amber-400">
                    <AlertTriangle className="mr-1 h-3 w-3" />
                    结算周
                  </Badge>
                </>
              )}
            </div>
          )}
        </div>

        {/* 守卫状态提示 */}
        {(isGuardBlock || isGuardDowngrade) && (
          <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-300">
            <ShieldAlert className="mr-1.5 inline-block h-4 w-4" />
            {isGuardBlock
              ? "盘面守卫拦截：环境安全但盘面过冷，暂停建仓"
              : "盘面守卫降级：情绪偏弱，仅允许极轻仓试探（不超过1成）"
            }
          </div>
        )}

        {/* 细节列表 */}
        {timing?.details && timing.details.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {timing.details.map((d, i) => (
              <span
                key={i}
                className="rounded-full bg-muted/50 px-2.5 py-0.5 text-xs text-muted-foreground"
              >
                {d}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ==================== 标题 + 运行按钮 ==================== */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">观潮看板</h1>
          <p className="text-muted-foreground">{today()} 市场概览</p>
        </div>
        <Button onClick={handleRunAll} disabled={running}>
          <Play className="mr-2 h-4 w-4" />
          {running ? "执行中..." : "运行全部策略"}
        </Button>
      </div>

      {/* ==================== 统计卡片 ==================== */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">已注册策略</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{strategies.length}</div>
            <p className="text-xs text-muted-foreground">
              {strategies.filter((s) => s.enabled).length} 个已启用
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">今日信号</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalSignals}</div>
            <p className="text-xs text-muted-foreground">
              来自 {Object.keys(signals).length} 个策略
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">今日涨停</CardTitle>
            <TrendingUp className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">{ztPool.length}+</div>
            <p className="text-xs text-muted-foreground">涨停股池实时数据</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">系统状态</CardTitle>
            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">运行中</div>
            <p className="text-xs text-muted-foreground">后端服务正常</p>
          </CardContent>
        </Card>
      </div>

      {/* ==================== 内容区 ==================== */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* 策略信号 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              策略信号
            </CardTitle>
          </CardHeader>
          <CardContent>
            {totalSignals === 0 ? (
              <p className="py-8 text-center text-muted-foreground">
                点击右上角「运行全部策略」生成今日信号
              </p>
            ) : (
              <div className="space-y-4">
                {Object.entries(signals).map(([name, sigs]) => (
                  <div key={name}>
                    <h4 className="mb-2 text-sm font-semibold">{name}</h4>
                    <div className="space-y-1">
                      {sigs.slice(0, 5).map((s, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-mono">{s.stock_code}</span>
                            <span>{s.stock_name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary">
                              {s.score.toFixed(0)}分
                            </Badge>
                          </div>
                        </div>
                      ))}
                      {sigs.length > 5 && (
                        <p className="text-center text-xs text-muted-foreground">
                          还有 {sigs.length - 5} 条信号...
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 涨停股池 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-red-500" />
              今日涨停 TOP10
            </CardTitle>
          </CardHeader>
          <CardContent>
            {ztPool.length === 0 ? (
              <p className="py-8 text-center text-muted-foreground">
                暂无数据（非交易时间或接口未响应）
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>代码</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead className="text-right">连板</TableHead>
                    <TableHead className="text-right">封板时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ztPool.map((s) => (
                    <TableRow key={s.dm}>
                      <TableCell className="font-mono">{s.dm}</TableCell>
                      <TableCell>{s.mc}</TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant={
                            (s.lbc ?? 0) >= 3
                              ? "destructive"
                              : (s.lbc ?? 0) >= 2
                                ? "default"
                                : "secondary"
                          }
                        >
                          {s.lbc ?? 0}板
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {s.fbt ?? "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
