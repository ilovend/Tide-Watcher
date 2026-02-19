"""
策略模板 —— 复制此文件并重命名即可创建新策略。

使用方法：
1. 复制此文件到 strategies/ 目录，如 my_strategy.py
2. 修改 @strategy 装饰器中的 name 和 schedule
3. 在函数体内编写你的选股逻辑
4. 重启服务器，策略自动注册生效

可用的 ctx 方法：
- ctx.get_pool("涨停股池")           → 获取股池数据
- ctx.get_realtime("000001")         → 获取单只实时行情
- ctx.get_realtime_all()             → 获取全市场实时行情
- ctx.get_kline("000001", "d")       → 获取日K线
- ctx.get_company("000001", "gsjj")  → 获取公司简介
- ctx.get_finance("000001.SZ", "income")  → 获取利润表
- ctx.get_indicator("000001", "macd")     → 获取MACD指标
- ctx.get_fund_flow("000001")             → 获取资金流向
- ctx.add_signal(code, name, score, reason)  → 添加选股信号
"""

from app.engine.registry import strategy


@strategy(
    name="我的策略",            # 改成你的策略名称
    schedule="14:50",            # 每日执行时间（HH:MM），留空则仅手动触发
    description="策略描述",      # 简要说明策略逻辑
    tags=["自定义"],             # 标签，用于分类
)
async def my_strategy(ctx):
    # ===== 第1步：获取数据 =====
    pool = await ctx.get_pool("涨停股池")

    # ===== 第2步：筛选条件 =====
    for stock in pool:
        # 示例条件：连板数 >= 2
        if stock.get("lbc", 0) >= 2:

            # ===== 第3步：添加信号 =====
            ctx.add_signal(
                code=stock["dm"],
                name=stock.get("mc", ""),
                score=stock.get("lbc", 0) * 30,
                reason=f"连板{stock.get('lbc')}天",
            )

    return ctx.results
