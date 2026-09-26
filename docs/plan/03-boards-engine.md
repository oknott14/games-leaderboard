# Workstream C — Boards Engine

## 1. Goal

Make **any leaderboard** possible. A board is a composition of four pluggable parts (value, window,
aggregator, board type). Boards are defined in `boards.yaml`, built ad hoc from chat commands, or
extended with Python plugins that register through the same decorators as the built-ins.

The engine is **pure**: it receives rows from a `load_rows` callback and returns standings. It
never touches the database, Slack or text formatting.

This workstream is split into three sub-workstreams that can run in parallel:

| Sub | Scope | Files |
|---|---|---|
| **C1** | Built-in windows and aggregators | `boards/windows.py`, `boards/aggregators.py`, `tests/test_windows.py`, `tests/test_aggregators.py` |
| **C2** | Dedupe, ranking, board types, engine | `boards/core.py` (function bodies), `boards/types.py`, `boards/engine.py`, `tests/test_core.py`, `tests/test_board_types.py`, `tests/test_engine.py` |
| **C3** | Plugin loading, `boards.yaml` loader and validation, example plugin | `boards/registry.py` (`load_builtins`, `load_plugins`, `validate_params`), `boards/config.py` (loader), `boards.yaml`, `plugins/example_top3_avg.py`, `tests/test_registry.py`, `tests/test_boards_config.py` |

C2's tests register small stand-in windows and aggregators with the decorators (complete in WS0),
so C2 doesn't wait on C1.

## 2. Owns

The files in the table above. **Must not edit:** the contract types in `boards/core.py` (their
fields), the decorator code in `registry.py` (WS0), or game config logic (A).

## 3. Depends on

[Contracts](00-contracts.md) §5.2 (`GameConfig.value`, `higher_is_better_for`, `duplicates`), §5.5
core types, §5.6 registry, §5.7 board schema, §5.8 engine signatures, §5.9 `ANCHOR_WORDS` and
`RESERVED_WORDS`, and §6 fakes (`make_rows`, `make_board`, `sample_games`, `fixed_today`).

## 4. Provides

- `run_board`, `board_applies`, `board_range`, `board_unit`, used by B.
- `load_boards`, `load_builtins`, `load_plugins`, used by F.
- The registries `WINDOWS`, `AGGREGATORS` and `BOARD_TYPES`, used by D for ad-hoc commands and `boards` help.
- The public plugin API in `leaderboard.boards`.

---

## 5. Design

### 5.1 The model

| Part | Question | Where it's defined |
|---|---|---|
| **Value** | Which number from each result? | Game YAML (`score` + `values`), workstream A |
| **Window** | Which results are in scope, relative to an anchor date? | `@window` |
| **Aggregator** | How are one player's values combined into one number? | `@aggregator` |
| **Board type** | The whole computation | `@board_type` |

How the requested boards map onto these parts:

| Board | Composition |
|---|---|
| Best average score | `ranked` · `score` · `month` · `avg` · `min_entries: 5` |
| Best top score | `ranked` · `score` · `all` · `best` |
| Best recent score | `ranked` · `score` · `week` · `latest`, or "recent form": `last_n: 5` · `avg` |
| Best round by person | `ranked` · `best_round` · `week` · `best` |
| Most daily wins | `daily_wins` · `score` · `month` |

### 5.2 C1 — Built-in windows

Signature: `(anchor: date, params) -> WindowResult`. Every range **ends at the anchor**
(inclusive), so "this week" means Monday to today, and anchoring at last Sunday gives the full
previous week.

| Name | Params | Range | `select` |
|---|---|---|---|
| `day` | — | `[anchor, anchor]` | — |
| `week` | — | `[Monday of anchor's week, anchor]` | — |
| `month` | — | `[1st of anchor's month, anchor]` | — |
| `year` | — | `[Jan 1, anchor]` | — |
| `all` | — | `[None, anchor]` | — |
| `rolling_days` | `n: int ≥ 1` | `[anchor − (n−1), anchor]` | — |
| `last_n` | `n: int ≥ 1` | `[None, anchor]` | keeps each player's latest `n` entries |

### 5.3 C1 — Built-in aggregators

Signature: `(entries: list[Entry], ctx: AggContext) -> float | None`. Entries arrive sorted by
`played_on`. `ctx.higher_is_better` is the **value's** direction. Return `None` for "no value",
which drops the player.

| Name | Result | Forced ranking direction | Unit |
|---|---|---|---|
| `sum` | Σ values | — | — |
| `avg` | mean | — | — |
| `median` | median | — | — |
| `best` | max if higher is better, else min | — | — |
| `worst` | the opposite of `best` | — | — |
| `max` / `min` | raw max / min | — | — |
| `latest` / `first` | value of the last / first entry | — | — |
| `count` | number of entries | higher | `games` |
| `stddev` | population std dev (`None` if fewer than 2 entries) | **lower** (consistency) | — |
| `streak` | consecutive played days ending at the most recent played day, counted only if that day is the anchor or the day before; otherwise 0 | higher | `days` |
| `top_k_avg` | mean of the best `k` values (`k: int ≥ 1`) | — | — |

### 5.4 C2 — Dedupe and ranking (`core.py`)

- **`dedupe_daily(rows, policy, higher_is_better)`**: one row per `(player, played_on)`. `first`
  keeps the earliest `posted_at`, `last` keeps the latest, and `best` keeps the best `score` by
  direction, with ties going to the earliest. Dedupe always uses the **score**, so every value
  (e.g. `best_round`) comes from the post that counted.
- **`rank(scored, higher_is_better)`**:
  - `scored` is `(player, value, entries, detail)`.
  - Sort by value in the given direction, then by player for a stable order.
  - Competition ranking: equal values share a rank and the next rank skips, giving 1, 1, 3.

### 5.5 C2 — Board types (`types.py`)

Signature: `(ctx: BoardContext) -> list[Standing]`.

- **`ranked`** (the default): group `ctx.entries` by player, then `ctx.aggregate`. Drop players
  with a `None` result or fewer than `board.min_entries` entries. Then `rank` using
  `ctx.higher_is_better`.
- **`daily_wins`** (unit `wins`):
  - For each day, the players with the best value win. **Ties all win.**
  - Count each player's wins, and keep players with at least `min_entries` days played.
  - Rank higher-is-better. `detail` is `"{days} played"`.
- **`improvement`** (unit `±`):
  - Requires a bounded range. With `start=None` it raises `ValueError("improvement needs a bounded window")`.
  - The previous range is the same length, immediately before the current one.
  - For each player in both periods: `delta = aggregate(current) − aggregate(previous)`, negated
    when lower is better, so a positive number always means improved.
  - Rank higher-is-better. `detail` is `"{prev} → {cur}"`.

### 5.6 C2 — Engine (`engine.py`)

```
run_board(board, game, anchor, load_rows):
  win   = WINDOWS[board.window.name];     wparams = validate_params(win, board.window.params)
  wres  = win.fn(anchor, wparams)
  value_hib = game.higher_is_better_for(board.value)
  agg   = AGGREGATORS[board.aggregate.name]; aparams = validate_params(agg, board.aggregate.params)
  rank_hib = first non-None of (board.higher_is_better, agg.higher_is_better, value_hib)

  entries_for(range):
    rows    = load_rows(range)
    rows    = dedupe_daily(rows, game.duplicates, game.higher_is_better_for("score"))
    entries = [Entry(r.player, r.played_on, r.posted_at, v)
               for r in rows if (v := game.value(board.value, r.score, r.rounds)) is not None]
    sort by (played_on, posted_at);  apply wres.select if set
    return entries

  ctx = BoardContext(game, board, board.value, rank_hib, anchor, wres.range,
                     entries_for(wres.range), type_params,
                     aggregate=lambda es: agg.fn(es, AggContext(value_hib, anchor, aparams)),
                     fetch=entries_for)
  return BOARD_TYPES[board.type.name].fn(ctx)
```

- `board_applies(board, game)`: `board.value in game.value_names()`, and if `board.games` is set,
  `game.name` is in it.
- `board_range(board, anchor)`: the window's `range`.
- `board_unit(board)`: the board type's `unit`, else the aggregator's `unit`, else `None`.
- `run_board` returns **all** standings. Truncating to `board.limit` is formatting's job (D), so
  ranks stay correct.

### 5.7 C3 — Registry loading

- **`load_builtins()`** imports `windows`, `aggregators` and `types`. The import registers them,
  and repeat calls do nothing.
- **`load_plugins(dir)`**:
  - If the directory is missing, it returns `[]`.
  - Otherwise it adds `dir` to `sys.path`, imports each `*.py` in sorted order (skipping names
    starting with `_`) with `importlib`, and returns the names newly registered.
  - An import error is re-raised as `RuntimeError(f"plugin {file}: {exc}")`, so it fails fast
    with the file name.
- **`validate_params(reg, raw)`**:
  - With no params model, it returns `None` and rejects non-empty `raw`.
  - Otherwise it returns `reg.params.model_validate(raw)`.

### 5.8 C3 — `boards.yaml`

```yaml
defaults:
  min_entries: 1
  limit: 10

boards:
  daily:         { title: "Daily results",   window: day,   aggregate: best }
  weekly:        { title: "Weekly total",    window: week,  aggregate: sum }
  average:       { title: "Best average",    window: month, aggregate: avg, min_entries: 5 }
  top_score:     { title: "Top score",       window: all,   aggregate: best }
  recent_form:   { title: "Recent form",     window: { last_n: 5 }, aggregate: avg, min_entries: 3 }
  latest_scores: { title: "Latest score",    window: week,  aggregate: latest }
  streaks:       { title: "Streaks",         window: all,   aggregate: streak }
  consistency:   { title: "Most consistent", window: month, aggregate: stddev, min_entries: 5 }
  wins:          { title: "Daily wins",      type: daily_wins, window: month }
  most_improved: { title: "Most improved",   type: improvement, window: week, aggregate: avg }
  top_round:     { title: "Best round",      value: best_round, window: week, aggregate: best }

schedule:
  - cron: "0 9 * * *"
    boards: [daily]
    anchor: yesterday
  - cron: "0 9 * * MON"
    boards: [weekly, recent_form, wins]
    anchor: last_week
```

**Component shorthand** (normalised by the `ComponentRef` validator in WS0):
- `avg` becomes `{name: avg}`.
- `{last_n: 5}` becomes `{name: last_n, params: {n: 5}}`. A scalar fills the component's
  **first** params field.
- `{top_k_avg: {k: 3}}` or `{name: top_k_avg, k: 3}` becomes `{name: top_k_avg, params: {k: 3}}`.

**`load_boards(path, games)` validation.** Every error is raised as `ValueError("boards.yaml: board '<name>': …")`.
1. Merge `defaults` under each board, and set `name` from the key.
2. `type`, `window` and `aggregate` names exist in the registries, and their params validate.
3. `value` exists in at least one game (or in every game listed in `games`), and listed games exist.
4. Each schedule entry's boards exist, and its cron parses (`CronTrigger.from_crontab`).
5. **Token collisions:** board names, game names and aliases, value names, aggregator names,
   window names, `ANCHOR_WORDS` and `RESERVED_WORDS` must all be distinct (value names may repeat
   across games). Ad-hoc command parsing (D) depends on this.

A missing `boards.yaml` gives an empty `BoardsFile`, with a warning logged.

### 5.9 C3 — Example plugin (`plugins/example_top3_avg.py`)

It's heavily commented, since it doubles as the plugin tutorial:

```python
from pydantic import BaseModel
from leaderboard.boards import aggregator, AggContext, Entry

class Params(BaseModel):
    k: int = 3

@aggregator("top3_avg", params=Params, description="Average of each player's k best results")
def top3_avg(entries: list[Entry], ctx: AggContext) -> float | None:
    best = sorted((e.value for e in entries), reverse=ctx.higher_is_better)[: ctx.params.k]
    return sum(best) / len(best) if best else None
```

The built-in `top_k_avg` does the same thing. The example exists to show the pattern, and it's
registered under a different name so the two can coexist.

---

## 6. Tasks

**C1**
- [ ] The seven windows, each with a params model where needed
- [ ] The thirteen aggregators, with forced directions and units

**C2**
- [ ] `dedupe_daily`, `rank`
- [ ] The `ranked`, `daily_wins` and `improvement` board types
- [ ] `engine.py`: `run_board`, `board_applies`, `board_range`, `board_unit`

**C3**
- [ ] `load_builtins`, `load_plugins`, `validate_params`
- [ ] `load_boards`, with every check in §5.8
- [ ] `boards.yaml` starter file and the example plugin

## 7. Acceptance criteria

**C1:**
- [ ] `week` anchored on a Sunday covers Mon–Sun, and anchored on a Monday covers that single day
- [ ] `month` and `year` start dates are correct. `rolling_days: 7` covers exactly 7 days.
- [ ] `last_n: 2` keeps each player's latest 2 entries independently
- [ ] Each aggregator is correct on a small list
- [ ] `best`/`worst` follow the direction, `stddev` returns `None` for fewer than 2 entries
- [ ] `streak`: a gap resets it, and a streak ending 2 or more days before the anchor is 0

**C2:**
- [ ] `dedupe_daily`: `first`, `best` and `last` each pick the right row, including when rows arrive out of order
- [ ] `rank`: ties give 1, 1, 3, and both directions sort correctly
- [ ] `ranked` applies `min_entries` and drops players whose aggregate is `None`
- [ ] `daily_wins` counts tied winners for each of them
- [ ] `improvement`: positive means better in both directions, a player missing from either period
      is excluded, and an unbounded window raises
- [ ] Engine: `best_round` comes from the post that dedupe chose, a game without the board's value
      doesn't apply, and a board override beats the aggregator's forced direction, which beats the
      value's direction

**C3:**
- [ ] The starter `boards.yaml` loads against `sample_games`
- [ ] A plugin file in `tmp_path` registers and is usable in a board
- [ ] A plugin with a syntax error fails with the file name
- [ ] Registering a duplicate name raises
- [ ] Rejected with a clear message: an unknown window, aggregator, type or value; bad params; a
      schedule referencing an unknown board; a bad cron; each kind of token collision
- [ ] All three shorthand forms normalise correctly

## 8. Out of scope

Chat command parsing and formatting (D), database loading (B), running the schedule (F).

## 9. Open questions

- **For the project owner:** is the starter set of boards and the schedule in §5.8 right? Add,
  remove or rename freely; it's config.
- Should `weekly` be a total (`sum`, which rewards playing every day) or an average (`avg` with
  `min_entries: 4`)? It's `sum` for now.
