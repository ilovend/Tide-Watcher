"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  const friendly = friendlyError(message);

  return (
    <div className="flex items-center gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3">
      <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
      <p className="flex-1 text-sm text-destructive">{friendly}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          重试
        </Button>
      )}
    </div>
  );
}

function friendlyError(msg: string): string {
  if (msg.includes("Failed to fetch") || msg.includes("fetch"))
    return "无法连接后端服务，请确认后端是否启动（端口 8000）";
  if (msg.includes("502") || msg.includes("数据源"))
    return "数据源暂时不可用，请稍后重试";
  if (msg.includes("500"))
    return "服务器内部错误，请查看后端日志";
  if (msg.includes("400") || msg.includes("参数"))
    return "请求参数有误，请检查输入";
  if (msg.includes("404"))
    return "请求的资源不存在";
  return msg;
}
