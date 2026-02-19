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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BrainCircuit, Play, History, Clock } from "lucide-react";
import { toast } from "sonner";
import {
  strategyApi,
  type StrategyInfo,
  type Signal,
  type SignalRecord,
} from "@/lib/api";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [runResult, setRunResult] = useState<Record<string, Signal[]>>({});
  const [loading, setLoading] = useState(true);
  const [runningStrategy, setRunningStrategy] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [stRes, sigRes] = await Promise.all([
          strategyApi.list(),
          strategyApi.signals({ limit: 50 }),
        ]);
        setStrategies(stRes.data);
        setSignals(sigRes.data);
      } catch (e) {
        console.error("加载失败", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleRun(name: string) {
    setRunningStrategy(name);
    try {
      const res = await strategyApi.run(name);
      setRunResult((prev) => ({ ...prev, [name]: res.signals }));
      const sigRes = await strategyApi.signals({ limit: 50 });
      setSignals(sigRes.data);
      toast.success(`策略「${name}」执行完成`, {
        description: `产生 ${res.signal_count} 个信号`,
      });
    } catch (e) {
      toast.error(`策略「${name}」执行失败`, {
        description: e instanceof Error ? e.message : "未知错误",
      });
    } finally {
      setRunningStrategy(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">策略中心</h1>
        <p className="text-muted-foreground">管理和执行选股策略，查看历史信号</p>
      </div>

      <Tabs defaultValue="list">
        <TabsList>
          <TabsTrigger value="list">策略列表</TabsTrigger>
          <TabsTrigger value="signals">信号历史</TabsTrigger>
        </TabsList>

        {/* 策略列表 */}
        <TabsContent value="list">
          <div className="grid gap-4 md:grid-cols-2">
            {strategies.map((st) => (
              <Card key={st.name}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BrainCircuit className="h-5 w-5" />
                      {st.name}
                    </div>
                    <Badge variant={st.enabled ? "default" : "secondary"}>
                      {st.enabled ? "已启用" : "已禁用"}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">{st.description}</p>

                  <div className="flex items-center gap-4 text-sm">
                    {st.schedule && (
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Clock className="h-3.5 w-3.5" />
                        每日 {st.schedule}
                      </div>
                    )}
                    <div className="flex gap-1">
                      {st.tags.map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <Button
                      size="sm"
                      onClick={() => handleRun(st.name)}
                      disabled={runningStrategy === st.name}
                    >
                      <Play className="mr-2 h-3.5 w-3.5" />
                      {runningStrategy === st.name ? "执行中..." : "立即执行"}
                    </Button>

                    {runResult[st.name] && (
                      <span className="text-sm text-muted-foreground">
                        产生 {runResult[st.name].length} 条信号
                      </span>
                    )}
                  </div>

                  {/* 执行结果展示 */}
                  {runResult[st.name] && runResult[st.name].length > 0 && (
                    <div className="space-y-1 rounded-md border p-3">
                      <h4 className="text-xs font-semibold text-muted-foreground">最新执行结果</h4>
                      {runResult[st.name].slice(0, 5).map((s, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs">{s.stock_code}</span>
                            <span>{s.stock_name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary">{s.score.toFixed(0)}分</Badge>
                          </div>
                        </div>
                      ))}
                      {runResult[st.name].length > 5 && (
                        <p className="text-center text-xs text-muted-foreground">
                          还有 {runResult[st.name].length - 5} 条...
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* 信号历史 */}
        <TabsContent value="signals">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                历史信号记录
                <Badge variant="outline">{signals.length} 条</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {signals.length === 0 ? (
                <p className="py-12 text-center text-muted-foreground">
                  暂无信号记录，请先执行策略
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>策略</TableHead>
                      <TableHead>代码</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead>日期</TableHead>
                      <TableHead className="text-right">评分</TableHead>
                      <TableHead>理由</TableHead>
                      <TableHead className="text-right">时间</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {signals.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell>
                          <Badge variant="outline">{s.strategy_name}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{s.stock_code}</TableCell>
                        <TableCell>{s.stock_name}</TableCell>
                        <TableCell className="text-xs">{s.signal_date}</TableCell>
                        <TableCell className="text-right">
                          <Badge
                            variant={
                              s.score >= 70 ? "destructive" : s.score >= 40 ? "default" : "secondary"
                            }
                          >
                            {s.score.toFixed(0)}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">
                          {s.reason}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground">
                          {s.created_at ? new Date(s.created_at).toLocaleTimeString("zh-CN") : "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
