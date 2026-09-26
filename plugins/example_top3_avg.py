"""Example plugin: a custom aggregator.

Every .py file in plugins/ is imported when the bot starts. Registering a component makes it
usable in boards.yaml and in ad-hoc chat commands, exactly like the built-ins:

    boards:
      top3: { window: month, aggregate: top3_avg }          # uses k's default (3)
      top5: { window: month, aggregate: { top3_avg: 5 } }   # shorthand: fills the first param (k)

    @leaderboard maptap top3_avg month

There are three kinds of component (import the decorators from `leaderboard.boards`):
  @window("name")      (anchor: date, params) -> WindowResult       which results count
  @aggregator("name")  (entries: list[Entry], ctx: AggContext) -> float | None
  @board_type("name")  (ctx: BoardContext) -> list[Standing]         the whole computation

Names must be lowercase slugs and can't clash with a game, value, board or built-in name.
The built-ins in src/leaderboard/boards/ are written the same way and make good references.
(The built-in `top_k_avg` does what this example does; this one exists to show the pattern.)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from leaderboard.boards import AggContext, Entry, aggregator


class Params(BaseModel):
    """Parameters are a Pydantic model; boards.yaml values are validated against it."""

    model_config = ConfigDict(extra="forbid")  # reject misspelled parameters

    k: int = Field(default=3, ge=1)


@aggregator(
    "top3_avg",
    params=Params,
    description="Average of each player's k best results (default 3)",
    # unit="pts",              # optional suffix when values are shown
    # higher_is_better=True,   # optional: force the ranking direction (e.g. count, stddev)
)
def top3_avg(entries: list[Entry], ctx: AggContext) -> float | None:
    """`entries` are one player's results in the window, oldest first.

    `ctx.higher_is_better` says which direction is "better" for this value, `ctx.anchor` is the
    board's date, and `ctx.params` is the validated Params. Return None to leave the player off
    the board.
    """
    params = ctx.params if isinstance(ctx.params, Params) else Params()
    best = sorted((e.value for e in entries), reverse=ctx.higher_is_better)[: params.k]
    return sum(best) / len(best) if best else None
