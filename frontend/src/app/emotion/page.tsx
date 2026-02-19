"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Flame, TrendingUp, TrendingDown, Snowflake, Zap, BarChart3 } from "lucide-react";
import { poolApi, type EmotionSnapshot } from "@/lib/api";

const PHASE_MAP: Record<string, { label: string; color: string; icon: typeof Flame; bg: string }> = {
  ice:     { label: "冰点期", color: "text-blue-400",   icon: Snowflake,    bg: "bg-blue-500/10" },
  retreat: { label: "退潮期", color: "text-green-400",  icon: TrendingDown, bg: "bg-green-500/10" },
  ferment: { label: "发酵期", color: "text-yellow-400", icon: Zap,          bg: "bg-yellow-500/10" },
  boom:    { label: "爆发期", color: "text-orange-400", icon: Flame,        bg: "bg-orange-500/10" },
  frenzy:  { label: "狂热期", color: "text-red-400",    icon: Flame,        bg: "bg-red-500/10" },
};

function getPhaseInfo(phase: string) {
  return PHASE_MAP[phase] || { label: phase || "未知", color: "text-muted-foreground", icon: BarChart3, bg: "bg-muted" };
}

function scoreColor(score: number): string {
  if (score >= 60) return "text-red-500";
  if (score >= 40) return "text-orange-400";
  if (score >= 20) return "text-yellow-400";
  return "text-blue-400";
}

export default function EmotionPage() {
  const [data, setData] = useState<EmotionSnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await poolApi.emotionLatest(60);
        setData(res.data);
      } catch (e) {
        console.error("加载情绪数据失败", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  const latest = data[0];
  const phaseInfo = latest ? getPhaseInfo(latest.phase) : null;
  const PhaseIcon = phaseInfo?.icon || BarChart3;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">市场情绪</h1>
        <p className="text-muted-foreground">基于涨停数据的市场情绪监测与阶段判断</p>
      </div>

      {latest && phaseInfo ? (
        <>
          <div className="grid gap-4 md:grid-cols-5">
            <Card className={phaseInfo.bg}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">当前阶段</CardTitle>
                <PhaseIcon className={`h-5 w-5 ${phaseInfo.color}`} />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${phaseInfo.color}`}>{phaseInfo.label}</div>
                <p className="text-xs text-muted-foreground">{latest.trade_date}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">情绪评分</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${scoreColor(latest.phase_score)}`}>
                  {latest.phase_score.toFixed(0)}
                </div>
                <p className="text-xs text-muted-foreground">满分100</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">涨停数</CardTitle>
                <TrendingUp className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-500">{latest.limit_up_count}</div>
                <p className="text-xs text-muted-foreground">
                  炸板 {latest.broken_board_count} | 炸板率 {latest.broken_rate.toFixed(1)}%
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">最高连板</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{latest.max_streak}</div>
                <p className="text-xs text-muted-foreground">
                  晋级率 {latest.promotion_rate.toFixed(1)}%
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">首板数</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{latest.first_board_count}</div>
                <p className="text-xs text-muted-foreground">
                  涨停总额 {(latest.total_limit_amount / 1e8).toFixed(1)}亿
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                情绪走势
                <Badge variant="outline">{data.length} 天</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-[500px] overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>阶段</TableHead>
                      <TableHead className="text-right">评分</TableHead>
                      <TableHead className="text-right">涨停</TableHead>
                      <TableHead className="text-right">炸板</TableHead>
                      <TableHead className="text-right">炸板率</TableHead>
                      <TableHead className="text-right">连板</TableHead>
                      <TableHead className="text-right">首板</TableHead>
                      <TableHead className="text-right">晋级率</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.map((row) => {
                      const pi = getPhaseInfo(row.phase);
                      return (
                        <TableRow key={row.trade_date}>
                          <TableCell className="text-xs">{row.trade_date}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className={pi.color}>{pi.label}</Badge>
                          </TableCell>
                          <TableCell className={`text-right font-medium ${scoreColor(row.phase_score)}`}>
                            {row.phase_score.toFixed(0)}
                          </TableCell>
                          <TableCell className="text-right font-medium text-red-500">{row.limit_up_count}</TableCell>
                          <TableCell className="text-right">{row.broken_board_count}</TableCell>
                          <TableCell className="text-right">{row.broken_rate.toFixed(1)}%</TableCell>
                          <TableCell className="text-right font-medium">{row.max_streak}</TableCell>
                          <TableCell className="text-right">{row.first_board_count}</TableCell>
                          <TableCell className="text-right">{row.promotion_rate.toFixed(1)}%</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            暂无情绪数据。情绪快照会在每日盘后股池同步时自动计算。
          </CardContent>
        </Card>
      )}
    </div>
  );
}
