"""涨停板连板策略。

选股逻辑：
从涨停股池中筛选连板数 >= 2 的股票，
按连板数降序排列，优先关注高位连板标的。
封板资金 > 5000万 作为资金面过滤条件。
"""

from app.engine.registry import strategy


@strategy(
    name="涨停板连板",
    schedule="14:50",
    description="筛选连板>=2且封板资金>5000万的涨停股",
    tags=["涨停", "连板", "短线"],
)
async def limit_up_board(ctx):
    pool = await ctx.get_pool("涨停股池")

    for stock in pool:
        lbc = stock.get("lbc", 0)       # 连板数
        zj = stock.get("zj", 0)         # 封板资金（元）
        zbc = stock.get("zbc", 0)       # 炸板次数

        # 核心筛选条件
        if lbc < 2:
            continue
        if zj < 50_000_000:
            continue

        # 评分逻辑：连板数权重60% + 封板资金权重30% + 炸板惩罚10%
        score = min(lbc * 20, 60)
        score += min(zj / 100_000_000 * 30, 30)
        score -= min(zbc * 5, 10)
        score = max(0, min(100, score))

        ctx.add_signal(
            code=stock["dm"],
            name=stock.get("mc", ""),
            score=round(score, 1),
            reason=f"{stock.get('tj', '')} 连板{lbc} 封板资金{zj/1e8:.1f}亿 炸板{zbc}次",
            price=stock.get("p", 0),
            turnover=stock.get("hs", 0),
            first_limit_time=stock.get("fbt", ""),
            last_limit_time=stock.get("lbt", ""),
        )

    # 按评分降序排列
    ctx.results.sort(key=lambda x: x["score"], reverse=True)
    return ctx.results
