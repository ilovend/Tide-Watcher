"""放量突破策略。

选股逻辑：
从强势股池中筛选量比 > 2 的股票（放量信号），
并且涨幅在 5%~9.5% 之间（强势但未涨停，仍有介入空间），
标记是否创新高。
"""

from app.engine.registry import strategy


@strategy(
    name="放量突破",
    schedule="14:30",
    description="筛选强势股池中量比>2且涨幅5%~9.5%的放量股",
    tags=["放量", "强势", "短线"],
)
async def volume_breakout(ctx):
    pool = await ctx.get_pool("强势股池")

    for stock in pool:
        lb = stock.get("lb", 0)         # 量比
        zf = stock.get("zf", 0)         # 涨幅 (%)
        nh = stock.get("nh", 0)         # 是否新高 (0/1)
        zs = stock.get("zs", 0)         # 涨速 (%)

        # 放量条件：量比 > 2
        if lb < 2:
            continue

        # 涨幅区间：5% ~ 9.5%（强势但未封板）
        if not (5 <= zf <= 9.5):
            continue

        # 评分逻辑
        score = 0.0
        score += min(lb * 8, 40)                  # 量比贡献最多40分
        score += min((zf - 5) / 4.5 * 30, 30)    # 涨幅越高越好，最多30分
        score += 20 if nh == 1 else 0              # 新高加分
        score += min(zs * 2, 10)                   # 涨速加分
        score = max(0, min(100, score))

        ctx.add_signal(
            code=stock["dm"],
            name=stock.get("mc", ""),
            score=round(score, 1),
            reason=f"量比{lb:.1f} 涨幅{zf:.1f}% {'创新高' if nh else ''} 涨速{zs:.1f}%",
            price=stock.get("p", 0),
            limit_price=stock.get("ztp", 0),
            volume_ratio=lb,
        )

    ctx.results.sort(key=lambda x: x["score"], reverse=True)
    return ctx.results
