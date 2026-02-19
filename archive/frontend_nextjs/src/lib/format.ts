/**
 * 数字格式化 + 涨跌色 + 日期工具
 *
 * 全站统一使用，避免各页面重复编写格式化逻辑。
 */

// ==================== 金额/市值格式化 ====================

export function formatAmount(val?: number | null): string {
  if (val == null || val === 0) return "-";
  const abs = Math.abs(val);
  if (abs >= 1e12) return (val / 1e12).toFixed(2) + "万亿";
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return (val / 1e4).toFixed(0) + "万";
  return val.toFixed(0);
}

export function formatVolume(val?: number | null): string {
  if (val == null || val === 0) return "-";
  if (val >= 1e8) return (val / 1e8).toFixed(2) + "亿手";
  if (val >= 1e4) return (val / 1e4).toFixed(0) + "万手";
  return val.toFixed(0) + "手";
}

export function formatPrice(val?: number | null, digits = 2): string {
  if (val == null) return "-";
  return val.toFixed(digits);
}

export function formatPct(val?: number | null, digits = 2): string {
  if (val == null) return "-";
  const sign = val > 0 ? "+" : "";
  return `${sign}${val.toFixed(digits)}%`;
}

// ==================== 涨跌色工具 ====================

export type StockColor = "up" | "down" | "flat";

export function getDirection(val?: number | null): StockColor {
  if (val == null || val === 0) return "flat";
  return val > 0 ? "up" : "down";
}

export function directionClass(val?: number | null): string {
  const d = getDirection(val);
  if (d === "up") return "text-red-500";
  if (d === "down") return "text-green-500";
  return "text-muted-foreground";
}

export function directionBg(val?: number | null): string {
  const d = getDirection(val);
  if (d === "up") return "bg-red-500/10 text-red-500";
  if (d === "down") return "bg-green-500/10 text-green-500";
  return "bg-muted text-muted-foreground";
}

// ==================== 日期工具 ====================

export function formatDate(raw: string): string {
  if (!raw) return "-";
  if (raw.length === 8) return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6)}`;
  return raw.slice(0, 10);
}

export function toCompactDate(raw: string): string {
  return raw.replace(/-/g, "").slice(0, 8);
}

export function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function isWeekday(date: Date = new Date()): boolean {
  const day = date.getDay();
  return day !== 0 && day !== 6;
}
