"use client";

import { useState } from "react";
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
import { Search, TrendingUp, TrendingDown, Building2, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { ErrorMessage } from "@/components/error-message";
import { KlineChart } from "@/components/kline-chart";
import { stockApi, poolApi, type RealtimeQuote, type KlineBar, type RiskCheckResult } from "@/lib/api";
import { formatAmount, formatPct, directionClass } from "@/lib/format";

export default function StocksPage() {
  const [code, setCode] = useState("");
  const [quote, setQuote] = useState<RealtimeQuote | null>(null);
  const [kline, setKline] = useState<KlineBar[]>([]);
  const [companyInfo, setCompanyInfo] = useState<Record<string, unknown> | null>(null);
  const [sectors, setSectors] = useState<{ sector_code: string; sector_name: string }[]>([]);
  const [riskInfo, setRiskInfo] = useState<RiskCheckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch() {
    if (!code.trim()) return;
    setLoading(true);
    setError("");
    setQuote(null);
    setKline([]);
    setCompanyInfo(null);
    setSectors([]);
    setRiskInfo(null);

    try {
      const [quoteRes, klineRes, companyRes, sectorsRes, riskRes] = await Promise.all([
        stockApi.realtime(code.trim()),
        stockApi.klineLatest(code.trim(), "d", 20),
        stockApi.company(code.trim(), "gsjj").catch(() => ({ data: null })),
        poolApi.stockSectors(code.trim()).catch(() => ({ data: [] })),
        poolApi.riskCheck(code.trim()).catch(() => null),
      ]);
      setQuote(quoteRes.data);
      setKline(klineRes.data);
      if (companyRes.data) setCompanyInfo(companyRes.data);
      setSectors(sectorsRes.data || []);
      if (riskRes && riskRes.has_risk) setRiskInfo(riskRes);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "查询失败";
      setError(msg);
      toast.error("查询失败", { description: msg });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">个股查询</h1>
        <p className="text-muted-foreground">输入股票代码查看实时行情、K线和公司信息</p>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3">
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="输入股票代码，如 000001 或 600519"
          className="w-72 rounded-md border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <Button onClick={handleSearch} disabled={loading}>
          <Search className="mr-2 h-4 w-4" />
          {loading ? "查询中..." : "查询"}
        </Button>
      </div>

      {/* 财务风险警告 */}
      {riskInfo && riskInfo.has_risk && (
        <div className="rounded-lg border-2 border-red-500 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-500">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="text-lg font-bold">ST / 退市风险警告</span>
          </div>
          <p className="mt-2 text-sm text-red-400">{riskInfo.reason}</p>
          {riskInfo.scan_date && (
            <p className="mt-1 text-xs text-muted-foreground">扫描日期: {riskInfo.scan_date}</p>
          )}
        </div>
      )}

      {error && <ErrorMessage message={error} onRetry={handleSearch} />}

      {loading && (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      )}

      {quote && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* 实时行情 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {quote.pc >= 0 ? (
                  <TrendingUp className="h-5 w-5 text-red-500" />
                ) : (
                  <TrendingDown className="h-5 w-5 text-green-500" />
                )}
                实时行情
                <span className="text-sm font-normal text-muted-foreground">{quote.t}</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-baseline gap-4">
                <span
                  className={`text-4xl font-bold ${
                    quote.pc >= 0 ? "text-red-500" : "text-green-500"
                  }`}
                >
                  {quote.p.toFixed(2)}
                </span>
                <span
                  className={`text-lg font-medium ${
                    quote.pc >= 0 ? "text-red-500" : "text-green-500"
                  }`}
                >
                  {quote.pc >= 0 ? "+" : ""}
                  {quote.pc.toFixed(2)}%
                </span>
                <span
                  className={`text-sm ${
                    quote.ud >= 0 ? "text-red-500" : "text-green-500"
                  }`}
                >
                  {quote.ud >= 0 ? "+" : ""}
                  {quote.ud.toFixed(2)}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">开盘</span>
                  <p className="font-medium">{quote.o.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">最高</span>
                  <p className="font-medium text-red-500">{quote.h.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">最低</span>
                  <p className="font-medium text-green-500">{quote.l.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">昨收</span>
                  <p className="font-medium">{quote.yc.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">成交额</span>
                  <p className="font-medium">{formatAmount(quote.cje)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">换手率</span>
                  <p className="font-medium">{quote.hs.toFixed(2)}%</p>
                </div>
                <div>
                  <span className="text-muted-foreground">市盈率</span>
                  <p className="font-medium">{quote.pe.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">市净率</span>
                  <p className="font-medium">{quote.sjl.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">总市值</span>
                  <p className="font-medium">{formatAmount(quote.sz)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">量比</span>
                  <p className="font-medium">{quote.lb.toFixed(2)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">振幅</span>
                  <p className="font-medium">{quote.zf.toFixed(2)}%</p>
                </div>
                <div>
                  <span className="text-muted-foreground">流通市值</span>
                  <p className="font-medium">{formatAmount(quote.lt)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 公司信息 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                公司简介
              </CardTitle>
            </CardHeader>
            <CardContent>
              {companyInfo ? (
                <div className="space-y-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">公司名称：</span>
                    <span className="font-medium">{String(companyInfo.name ?? "-")}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">上市日期：</span>
                    <span>{String(companyInfo.ldate ?? "-")}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">行业：</span>
                    <span>{String(companyInfo.instype ?? "-")}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">概念板块：</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {String(companyInfo.idea ?? "")
                        .split(",")
                        .filter(Boolean)
                        .slice(0, 10)
                        .map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                    </div>
                  </div>
                  {!!companyInfo.desc && (
                    <div>
                      <span className="text-muted-foreground">简介：</span>
                      <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-muted-foreground">
                        {String(companyInfo.desc)}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <p className="py-8 text-center text-muted-foreground">暂无公司信息</p>
              )}
            </CardContent>
          </Card>

          {/* 所属板块 */}
          {sectors.length > 0 && (
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  所属板块
                  <Badge variant="outline">{sectors.length} 个</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {sectors.map((s) => (
                    <Badge key={s.sector_code} variant="secondary" className="text-xs">
                      {s.sector_name}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* K线蜡烛图 + 成交量 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                K线走势
                <Badge variant="outline">{kline.length} 日</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {kline.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">暂无K线数据</p>
              ) : (
                <KlineChart
                  data={kline.map((bar) => {
                    const raw = bar as unknown as Record<string, unknown>;
                    return {
                      d: String(raw.d || raw.t || ""),
                      o: Number(raw.o || 0),
                      h: Number(raw.h || 0),
                      l: Number(raw.l || 0),
                      c: Number(raw.c || 0),
                      v: Number(raw.v || 0),
                    };
                  })}
                  height={360}
                />
              )}
            </CardContent>
          </Card>

          {/* K线数据表 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-sm">K线明细</CardTitle>
            </CardHeader>
            <CardContent>
              {kline.length > 0 && (
                <div className="max-h-[300px] overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>日期</TableHead>
                        <TableHead className="text-right">开盘</TableHead>
                        <TableHead className="text-right">最高</TableHead>
                        <TableHead className="text-right">最低</TableHead>
                        <TableHead className="text-right">收盘</TableHead>
                        <TableHead className="text-right">涨跌%</TableHead>
                        <TableHead className="text-right">成交量</TableHead>
                        <TableHead className="text-right">成交额</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[...kline].reverse().map((bar, idx) => {
                        const raw = bar as unknown as Record<string, unknown>;
                        const d = String(raw.d || raw.t || "");
                        const o = Number(raw.o || 0);
                        const h = Number(raw.h || 0);
                        const l = Number(raw.l || 0);
                        const c = Number(raw.c || 0);
                        const v = Number(raw.v || 0);
                        const a = Number(raw.a || 0);
                        const pc = Number(raw.yc || raw.pc || 0);
                        const zf = Number(raw.zf || raw.change_pct || 0);
                        const change = zf !== 0 ? zf : (pc ? ((c - pc) / pc) * 100 : 0);
                        return (
                          <TableRow key={d || idx}>
                            <TableCell className="text-xs">{d.slice(0, 10)}</TableCell>
                            <TableCell className="text-right">{o.toFixed(2)}</TableCell>
                            <TableCell className="text-right text-red-500">{h.toFixed(2)}</TableCell>
                            <TableCell className="text-right text-green-500">{l.toFixed(2)}</TableCell>
                            <TableCell className={`text-right font-medium ${directionClass(change)}`}>
                              {c.toFixed(2)}
                            </TableCell>
                            <TableCell className={`text-right ${directionClass(change)}`}>
                              {formatPct(change)}
                            </TableCell>
                            <TableCell className="text-right text-xs">
                              {(v / 10000).toFixed(0)}万手
                            </TableCell>
                            <TableCell className="text-right text-xs">{formatAmount(a)}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
