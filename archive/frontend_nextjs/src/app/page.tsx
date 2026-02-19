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
import { TrendingUp, TrendingDown, Zap, Activity, Play } from "lucide-react";
import { toast } from "sonner";
import { strategyApi, poolApi, type StrategyInfo, type Signal, type PoolStock } from "@/lib/api";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function Dashboard() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [signals, setSignals] = useState<Record<string, Signal[]>>({});
  const [ztPool, setZtPool] = useState<PoolStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [stRes, poolRes] = await Promise.all([
          strategyApi.list(),
          poolApi.get("ztgc", today()).catch(() => ({ data: [] as PoolStock[] })),
        ]);
        setStrategies(stRes.data);
        setZtPool(poolRes.data.slice(0, 10));
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
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  const totalSignals = Object.values(signals).flat().length;

  return (
    <div className="space-y-6">
      {/* 标题栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">仪表盘</h1>
          <p className="text-muted-foreground">{today()} 市场概览</p>
        </div>
        <Button onClick={handleRunAll} disabled={running}>
          <Play className="mr-2 h-4 w-4" />
          {running ? "执行中..." : "运行全部策略"}
        </Button>
      </div>

      {/* 统计卡片 */}
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
            <div className="h-2 w-2 rounded-full bg-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">运行中</div>
            <p className="text-xs text-muted-foreground">后端服务正常</p>
          </CardContent>
        </Card>
      </div>

      {/* 内容区 */}
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
