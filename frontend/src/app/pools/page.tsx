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
import { Layers, RefreshCw, ShieldAlert } from "lucide-react";
import { poolApi, type PoolStock, type GlobalStatus } from "@/lib/api";

const POOL_TABS = [
  { code: "ztgc", name: "涨停股池", color: "text-red-500" },
  { code: "dtgc", name: "跌停股池", color: "text-green-500" },
  { code: "qsgc", name: "强势股池", color: "text-orange-500" },
  { code: "zbgc", name: "炸板股池", color: "text-yellow-500" },
  { code: "cxgc", name: "次新股池", color: "text-blue-500" },
];

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatAmount(val?: number) {
  if (!val) return "-";
  if (val >= 1e8) return (val / 1e8).toFixed(2) + "亿";
  if (val >= 1e4) return (val / 1e4).toFixed(0) + "万";
  return val.toFixed(0);
}

export default function PoolsPage() {
  const [activeTab, setActiveTab] = useState("ztgc");
  const [data, setData] = useState<PoolStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [date, setDate] = useState("");
  const [globalStatus, setGlobalStatus] = useState<GlobalStatus | null>(null);
  const riskCodeSet = new Set(globalStatus?.risk_codes ?? []);

  function isRiskStock(dm: string): boolean {
    if (!dm) return false;
    return riskCodeSet.has(dm) || [...riskCodeSet].some(rc => rc.startsWith(dm));
  }

  async function loadPool(poolCode: string, d: string) {
    if (!d) return;
    setLoading(true);
    try {
      const res = await poolApi.get(poolCode, d);
      setData(Array.isArray(res.data) ? res.data : []);
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    poolApi.globalStatus().then(gs => {
      setGlobalStatus(gs);
      setDate(gs.date);
    }).catch(() => setDate(today()));
  }, []);

  useEffect(() => {
    loadPool(activeTab, date);
  }, [activeTab, date]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">股池监控</h1>
          <p className="text-muted-foreground">
            实时跟踪涨停、跌停、强势、炸板、次新股池
            {globalStatus && !globalStatus.is_trading_day && (
              <span className="ml-2 text-slate-500">
                ({globalStatus.holiday_name || "非交易日"}
                {globalStatus.next_open_date && ` | ${globalStatus.next_open_date} 开盘`})
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-md border bg-background px-3 py-1.5 text-sm"
          />
          <Button variant="outline" size="sm" onClick={() => loadPool(activeTab, date)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {POOL_TABS.map((tab) => (
            <TabsTrigger key={tab.code} value={tab.code}>
              {tab.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {POOL_TABS.map((tab) => (
          <TabsContent key={tab.code} value={tab.code}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className={`h-5 w-5 ${tab.color}`} />
                  {tab.name}
                  <Badge variant="outline">{data.length} 只</Badge>
                  <span className="text-sm font-normal text-muted-foreground">{date}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="space-y-2">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : data.length === 0 ? (
                  <p className="py-12 text-center text-muted-foreground">
                    暂无数据（非交易日或接口未返回）
                  </p>
                ) : (
                  <div className="max-h-[600px] overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-24">代码</TableHead>
                          <TableHead>名称</TableHead>
                          <TableHead className="text-right">价格</TableHead>
                          <TableHead className="text-right">涨幅%</TableHead>
                          {tab.code === "ztgc" && (
                            <>
                              <TableHead className="text-right">连板</TableHead>
                              <TableHead className="text-right">封板资金</TableHead>
                              <TableHead className="text-right">炸板</TableHead>
                              <TableHead className="text-right">首封时间</TableHead>
                              <TableHead>统计</TableHead>
                            </>
                          )}
                          {tab.code === "qsgc" && (
                            <>
                              <TableHead className="text-right">量比</TableHead>
                              <TableHead className="text-right">涨速%</TableHead>
                              <TableHead className="text-right">新高</TableHead>
                            </>
                          )}
                          {tab.code === "zbgc" && (
                            <>
                              <TableHead className="text-right">炸板次数</TableHead>
                              <TableHead className="text-right">首封时间</TableHead>
                            </>
                          )}
                          {tab.code === "dtgc" && (
                            <>
                              <TableHead className="text-right">连续跌停</TableHead>
                              <TableHead className="text-right">封单资金</TableHead>
                            </>
                          )}
                          <TableHead className="text-right">成交额</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.map((s) => (
                          <TableRow key={s.dm}>
                            <TableCell className={`font-mono text-xs ${isRiskStock(s.dm) ? "text-red-400" : ""}`}>
                              {s.dm}
                              {isRiskStock(s.dm) && (
                                <Badge variant="destructive" className="ml-1 px-1 py-0 text-[10px]">风险</Badge>
                              )}
                            </TableCell>
                            <TableCell className={`font-medium ${isRiskStock(s.dm) ? "text-red-400" : ""}`}>{s.mc}</TableCell>
                            <TableCell className="text-right">{s.p?.toFixed(2) ?? "-"}</TableCell>
                            <TableCell
                              className={`text-right font-medium ${
                                (s.zf ?? 0) > 0 ? "text-red-500" : (s.zf ?? 0) < 0 ? "text-green-500" : ""
                              }`}
                            >
                              {s.zf != null ? `${s.zf > 0 ? "+" : ""}${s.zf.toFixed(2)}%` : "-"}
                            </TableCell>
                            {tab.code === "ztgc" && (
                              <>
                                <TableCell className="text-right">
                                  <Badge
                                    variant={
                                      (s.lbc ?? 0) >= 3 ? "destructive" : (s.lbc ?? 0) >= 2 ? "default" : "secondary"
                                    }
                                  >
                                    {s.lbc ?? 0}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-right">{formatAmount(s.zj)}</TableCell>
                                <TableCell className="text-right">{s.zbc ?? 0}</TableCell>
                                <TableCell className="text-right text-xs">{s.fbt ?? "-"}</TableCell>
                                <TableCell className="text-xs">{s.tj ?? "-"}</TableCell>
                              </>
                            )}
                            {tab.code === "qsgc" && (
                              <>
                                <TableCell className="text-right">{s.lb?.toFixed(1) ?? "-"}</TableCell>
                                <TableCell className="text-right">{s.zs?.toFixed(1) ?? "-"}</TableCell>
                                <TableCell className="text-right">
                                  {s.nh === 1 ? <Badge variant="destructive">新高</Badge> : "-"}
                                </TableCell>
                              </>
                            )}
                            {tab.code === "zbgc" && (
                              <>
                                <TableCell className="text-right">{s.zbc ?? 0}</TableCell>
                                <TableCell className="text-right text-xs">{s.fbt ?? "-"}</TableCell>
                              </>
                            )}
                            {tab.code === "dtgc" && (
                              <>
                                <TableCell className="text-right">{s.lbc ?? 0}</TableCell>
                                <TableCell className="text-right">{formatAmount(s.zj)}</TableCell>
                              </>
                            )}
                            <TableCell className="text-right text-xs">{formatAmount(s.cje)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
