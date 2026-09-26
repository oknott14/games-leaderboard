# Workstream D — Commands & Formatting

## 1. Goal

Turn what people type (`@leaderboard weekly maptap`, `/leaderboard maptap avg month`) into a
`Query`, and turn board results into readable chat text. The same parser serves @mentions, the
slash command, the CLI `show` command and the scheduler.

## 2. Owns

- `src/leaderboard/commands.py`: `parse_command` and `resolve_anchor` bodies. The constants are WS0's.
- `src/leaderboard/formatting.py`
- `tests/test_commands.py`, `tests/test_formatting.py`

**Must not edit:** the engine or registries (C), or the service (B).

## 3. Depends on

[Contracts](00-contracts.md):
- §5.2 `GameConfig` (name, aliases, `value_names`, label)
- §5.5 and §5.8 `Standing`, `BoardResult`
- §5.6 registries: read `WINDOWS`, `AGGREGATORS` and `BOARD_TYPES` for names, descriptions and
  params models. In tests, register stand-ins with the WS0 decorators.
- §5.7 `BoardConfig` and `ComponentRef`
- §5.9 and §5.10 this workstream's signatures
- §6 fakes (`sample_games`, `make_board`, `fixed_today`)

## 4. Provides

`parse_command`, `resolve_anchor`, `format_board`, `format_info`, `format_error` and `fmt_value`,
used by B and F.

---

## 5. Design

### 5.1 Grammar

The input is the text after the mention or slash command. It's lower-cased and split on
whitespace. **Tokens can come in any order.** Each token is classified by which namespace it's
in. The C3 loader guarantees the namespaces never collide.

| Token kind | Examples | Effect |
|---|---|---|
| reserved | `help`, `games`, `boards` | returns `InfoRequest(topic)` (must be the only token) |
| anchor | `today`, `yesterday`, `lastweek`, `lastmonth`, `2026-09-20` | sets the anchor |
| board | `daily`, `weekly`, `average`, `wins`, … | selects a saved board |
| game | `maptap`, `map`, `tg`, `TimeGuessr` | adds to the game filter (id, alias or display name) |
| value | `score`, `best_round` | ad hoc: which value |
| aggregator | `avg`, `best`, `streak`, `top_k_avg` | ad hoc: aggregator |
| window | `week`, `month`, `all`, `last_n` | ad hoc: window |
| `name=value` | `last_n=10`, `top_k_avg=3`, `k=3` | param for the named component, or for the single ad-hoc component with that param field |
| shortcuts | `today` or `yesterday` alone gives `daily`; `lastweek` alone gives `weekly` | see rule 4 |

**Resolution rules:**
1. An empty input or `help` gives `InfoRequest("help")`.
2. A **saved board** token plus anchors or games gives `Query(board, games or None, anchor)`.
   Mixing a saved board with ad-hoc tokens (value, aggregator or window) gives a `CommandError`
   ("use either a saved board or ad-hoc parts").
3. **Ad hoc:** any value, aggregator or window token builds
   `BoardConfig(name="adhoc", type=ranked, value=value or "score", window=window or "week", aggregate=aggregator or "best")`.
   The title is auto-generated, e.g. `"MapTap · avg · month"`. Params are validated with
   `validate_params`, and a validation error becomes a `CommandError`.
4. **Shortcuts:** if there are only anchor and/or game tokens and no board or ad-hoc part:
   `lastweek` alone gives the `weekly` board; `lastmonth` alone gives the `average` board; any
   other anchor or no anchor gives the `daily` board. If the shortcut board doesn't exist in
   `boards.yaml`, return a `CommandError`.
5. The default anchor is `today`.
6. An **unknown token** gives `CommandError(f"I didn't understand `{tok}`", suggestions)`, where
   the suggestions come from `difflib.get_close_matches` over all known tokens (n=3, cutoff 0.6).

**`resolve_anchor(token, today)`:**

| Token | Resolves to |
|---|---|
| `today` | `today` |
| `yesterday` | `today − 1` |
| `lastweek` / `last_week` | the Sunday of the previous week |
| `lastmonth` / `last_month` | the last day of the previous month |
| `YYYY-MM-DD` | that date |
| anything else | `None` |

Both spellings are accepted so the scheduler's `AnchorName` values work too. Because every window
range ends at the anchor, "last week" plus the `week` window gives the full Mon–Sun of last week.

### 5.2 Formatting

**`fmt_value(v, unit)`:**
- An integer-valued float shows with thousands separators (`38532` → `38,532`). Other values show
  with one decimal (`4.25` → `4.3`).
- Unit `±` always shows a sign (`+120`, `-3.5`).
- Other units are appended: `5 days`, `12 games`, `3 wins`.

**`format_board(result, name_for)`:**

```
*Weekly total* — Sep 15–21
*MapTap*
🥇 Alice — 4,321 · 5 games
🥈 Bob — 4,100 · 5 games
🥉 Cara — 4,100 · 4 games      ← tie shares a rank; the next is 4.
4. Dan — 3,900 · 5 games

*TimeGuessr*
🥇 …
```
- The header is `*{title or board name}* — {range}`:
  - day: `Tue Sep 23`
  - within one month: `Sep 15–21`
  - across months: `Aug 28 – Sep 3`
  - `start=None`: `all time to Sep 24`
- A section per game, showing the first `board.limit` standings.
- Ranks 1, 2 and 3 get 🥇🥈🥉 (tied ranks get the same medal); `4.` onward after that.
- `· N games` is shown when `entries > 1`, and `· {detail}` when a detail is set.
- If there are no sections at all, the reply is `*{title}* — {range}\n_No results yet._`.
- `name_for(platform, user_id)` gives each player's display name.

**`format_info`:**
- `help`: the grammar, with 6–8 examples (taken from the table in §5.1).
- `games`: each game's label, its aliases and its value names.
- `boards`: each saved board's name and title, a one-line composition (`week · sum · score`), then
  the available aggregators, windows and board types with their descriptions and params.

**`format_error`:** the message plus `Did you mean: x, y?` when there are suggestions, plus
`Try \`help\`.`

---

## 6. Tasks

- [ ] Token namespace index built from games, boards and registries (built once per call; the input is small)
- [ ] `resolve_anchor`
- [ ] `parse_command`: reserved words, saved boards, ad hoc, shortcuts, params, errors, suggestions
- [ ] `fmt_value`, date-range formatting, `format_board`
- [ ] `format_info` (help, games, boards) and `format_error`

## 7. Acceptance criteria

`tests/test_commands.py` (with `fixed_today = Thu 2026-09-24`):
- [ ] `""` and `help` give help. `games` and `boards` give an `InfoRequest`. `help maptap` gives an error.
- [ ] `weekly` gives the weekly board, anchored today, for all games
- [ ] `maptap weekly lastweek` and `lastweek weekly maptap` give the same query, anchored Sun 2026-09-20
- [ ] `daily 2026-09-01 tg` resolves the alias to `timeguessr`
- [ ] `maptap avg month` gives an ad-hoc board (ranked, score, month, avg)
- [ ] `maptap best_round best all` gives an ad-hoc board over `best_round`
- [ ] `tg median last_n=10` gives an ad-hoc board with window params `{n: 10}`. `last_n=abc` gives an error.
- [ ] `weekly avg` gives the mixing error
- [ ] `lastweek` alone gives weekly, `yesterday` alone gives daily, `today maptap` gives daily
- [ ] `wekly` gives an error suggesting `weekly`
- [ ] `resolve_anchor`: last week and last month across a month and a year boundary

`tests/test_formatting.py`:
- [ ] `fmt_value`: integers, decimals, `±` and units
- [ ] Range headers: day, same month, across months, all time
- [ ] Medal ties (two 🥇, then `3.`), `limit` truncation, `detail` and entries suffixes
- [ ] The empty result message
- [ ] `format_info("boards")` lists a plugin-registered aggregator

## 8. Out of scope

Slack-specific rendering such as Block Kit (possible later, in the adapter), and per-person stat
cards (follow-up).

## 9. Open questions

- Should the ad-hoc default window be `week` or `month`? It's `week` for now.
