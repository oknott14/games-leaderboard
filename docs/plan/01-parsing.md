# Workstream A — Parsing & Game Configs

## 1. Goal

Turn a chat message's text into zero or more game results, using one YAML file per game. It must
handle horizontal and vertical share layouts and per-round scores, and give clear errors for bad
configs. It also ships the `leaderboard parse` tool that people use to write and debug game configs.

## 2. Owns

- `src/leaderboard/config.py`: method bodies, validators and `load_games`. The schema fields belong to WS0.
- `src/leaderboard/parser.py`: the `parse_message` body.
- `games/maptap.yaml`, `games/timeguessr.yaml`, `games/krillion.yaml`
- `src/leaderboard/parse_cli.py`: `parse_main(argv) -> int`, which WS F hooks up as the `parse` subcommand
- `tests/test_config.py`, `tests/test_parser.py`

**Must not edit:** anything else. Link normalisation (`<url|label>`) belongs to the Slack adapter (E).

## 3. Depends on

[Contracts](00-contracts.md) §5.2 `config.py`, §5.3 `parser.py`, and §6 test fakes (`SAMPLES`).

## 4. Provides

- `load_games(dir)` → validated, enabled games. Used by B, D and F.
- `parse_message(text, games)` → `list[ParsedResult]`. Used by B.
- `GameConfig.value(...)`, `value_names()`, `higher_is_better_for()`. Used by C.

---

## 5. Design

### 5.1 Three extraction steps

Every step is a regex run over the **whole message text** with the game's `flags`. That's why
layout needs no special handling.

1. **`detect`** (`re.search`): is this message this game? Use the most distinctive text in the
   share: the site name, `#puzzle`, or a `/50,000` suffix. If it doesn't match, stop; this game
   isn't in the message.
2. **`score`**: the total.
   - `pattern`: a `search` whose `(?P<value>…)` group is converted with `parse_number`.
   - `from_rounds: sum|avg|max|min`: the total is computed from the extracted rounds.
   - With `DOTALL`, `.*?` spans lines, so a total on another line is still matched.
3. **`rounds`** (optional):
   - `block` (a `search`) isolates the text holding the rounds through its `(?P<block>…)` group.
   - `item` runs `findall` **inside the block only**. It uses the single capture group if there
     is one, otherwise the whole match. Each item is converted with `parse_number`.
   - Scoping to the block stops dates, puzzle numbers and totals from being counted as rounds.
   - Optional `check_sum: true` logs a warning when `sum(rounds)` doesn't equal the posted score,
     which catches tiles that were mapped wrongly or not at all.

| Layout | Example | `block` | `item` |
|---|---|---|---|
| Horizontal | `93:trophy: 88:fire: 71 97 85` on the line after the header | `maptap\.gg[^\n]*\n(?P<block>[^\n]+)` | `(\d+)` |
| Vertical | one round per line between the header and the total | `Header[^\n]*\n(?P<block>(?:[^\n]*\n)*?)Total` with `MULTILINE` | `^\s*(\d[\d,]*)` |
| Emoji tiles (Krillion) | `🏮🌟🐟🏮🏮🦑🦑` on the first line after the score | `…\n\s*[\d,]+[ \t]*\n\s*(?P<block>[^\n]+)` | known tiles only, with a `map` of unicode **and** `:shortcode:` → value (see §5.6) |

4. **`puzzle`** (optional): a `search` with a `(?P<value>…)` group, kept as a string.

**Plugin escape hatch:** if `parser: "module:function"` is set, that function
(`PluginParser`, contracts §5.3) is called with the text instead of steps 1–4. The framework sets
`game` on the result. Modules are imported from `PLUGINS_DIR`, which is on `sys.path` (the
plugin loader C3 puts it there). Resolve lazily, on first use.

### 5.2 `parse_number(raw, spec)`

1. `raw.strip()`
2. If the raw value is a key in `spec.map`, return the mapped value.
3. Remove `,`, `_` and spaces, then convert with `int()` or `float()` per `spec.type` (returning a float).
4. On `ValueError`, return `None`.

### 5.3 `parse_message(text, games)`

- For each game in input order:
  - Run `detect`, then the score, rounds and puzzle steps.
  - If the score is `None` after `detect` matched, **log a warning** with the game name and the
    first 80 characters of the text, then skip the game. That's how broken configs get noticed.
- A message can yield results for **several games**; people often paste two or three in one post.
- It's a pure function: no I/O except the warning log.

### 5.4 Values

- `value_names()` returns `["score", *values]`.
- `value(name, score, rounds)`:
  - `score` returns the score.
  - A declared value applies its reducer (`sum`, `avg`, `max`, `min`) to the rounds, or returns
    `None` if there are no rounds.
  - An unknown name raises `KeyError`.
- `higher_is_better_for(name)` returns the value's override if it has one, otherwise the game default.

### 5.5 Validation (Pydantic validators + `load_games`)

- Every pattern compiles with the game's flags. The error names the field and the regex error.
- `score.pattern` and `puzzle.pattern` contain a `value` group, and `rounds.block` contains a `block` group.
- `score` has exactly one of `pattern` or `from_rounds`. `from_rounds` requires `rounds`.
- `values[*].from_rounds` requires `rounds`, and `"score"` isn't allowed as a key in `values`.
- A game has either `parser`, or both `detect` and `score`.
- `name` and value names match `^[a-z0-9_]+$`.
- `load_games`:
  - Reads `*.yaml` and `*.yml` in sorted order, and sets `name` from the file stem when it's missing.
  - Drops games with `enabled: false`.
  - Rejects duplicate names or aliases across files (compared case-insensitively).
  - Every error is raised as `ValueError(f"{path}: {details}")`.

### 5.6 Starter configs

These are written from the share formats we believe each game uses. **They must be confirmed
against real pasted messages** (see Open questions).

```yaml
# games/maptap.yaml
# Share text (Slack stores emoji as :shortcodes:):
#   www.maptap.gg September 24
#   93:trophy: 88:fire: 71 97:trophy: 85
#   Final score: 862
display_name: MapTap
aliases: [map]
flags: [IGNORECASE]
detect: 'maptap\.gg'
score:
  pattern: 'final score:?\s*(?P<value>[\d,]+)'
rounds:
  block: 'maptap\.gg[^\n]*\n(?P<block>[^\n]+)'
  item: '(?<![:\w])(\d+)'   # not digits inside emoji codes like :100:
higher_is_better: true
duplicates: first
values:
  best_round:  { from_rounds: max }
  worst_round: { from_rounds: min }
  round_avg:   { from_rounds: avg }
```

```yaml
# games/timeguessr.yaml
# Share text:  TimeGuessr #512 38,532/50,000   (+ emoji rows per round)
display_name: TimeGuessr
aliases: [tg, timeguesser]
detect: 'TimeGuessr\s+#\d+'
score:  { pattern: 'TimeGuessr\s+#\d+\s+(?P<value>[\d,]+)\s*/\s*50,000' }
puzzle: { pattern: 'TimeGuessr\s+#(?P<value>\d+)' }
higher_is_better: true
duplicates: first
```

```yaml
# games/krillion.yaml   (header line, total on its own line, then one emoji tile per round)
# Share text, as pasted by the project owner:
#   Krillion #72 🦐
#   505
#
#   🏮🌟🐟🏮🏮🦑🦑            ← 85+100+30+85+85+60+60 = 505
# 7 rounds, max 100 per round (700 total), higher is better.
# Tile values: 🫧 bubbles 10 · 🐟 fish 30 · 🦑 squid 60 · 🏮 lantern 85 · 🌟 star 100
# Slack's API `text` may carry the emoji as unicode or as :shortcodes:, so both are mapped.
display_name: Krillion
aliases: [krill]
flags: [IGNORECASE, MULTILINE]
detect: 'Krillion\s+#\d+'
score:  { pattern: 'Krillion\s+#\d+[^\n]*\n\s*(?P<value>[\d,]+)\s*$' }
puzzle: { pattern: 'Krillion\s+#(?P<value>\d+)' }
rounds:
  block: 'Krillion\s+#\d+[^\n]*\n\s*[\d,]+[ \t]*\n\s*(?P<block>[^\n]+)'   # the first line after the score
  item: ':(?:bubbles|fish|squid|izakaya_lantern|lantern|star2):|🫧|🐟|🦑|🏮|🌟'
  map:
    "🫧": 10
    ":bubbles:": 10
    "🐟": 30
    ":fish:": 30
    "🦑": 60
    ":squid:": 60
    "🏮": 85
    ":izakaya_lantern:": 85
    ":lantern:": 85
    "🌟": 100
    ":star2:": 100
  check_sum: true                 # warn if the tiles don't add up to the posted score
higher_is_better: true
duplicates: first
values:
  best_round:  { from_rounds: max }
  worst_round: { from_rounds: min }
  round_avg:   { from_rounds: avg }
```

- The score pattern anchors on the number on the line **directly after** the `Krillion #N` header,
  so the puzzle number `72` and the tile row are never read as the score.
- The rounds block is the first non-blank line after the score (`\s*` skips the blank line when
  there is one). The item regex matches **only known tiles**, so the 🦐 in the header and any
  chatter after the tiles are ignored.
- The header 🦐 is outside the block, so its shortcode (`:shrimp:`) never needs mapping.

**`check_sum` (new `RoundsSpec` option, default `false`):** when `true` and the game has both a
score pattern and rounds, `parse_message` logs a warning if `sum(rounds) != score`. The result is
still recorded, using the posted score. This catches a tile that was mapped wrongly or not mapped
(for example if Slack sends an unexpected shortcode), without losing data.

### 5.7 `leaderboard parse` CLI

`parse_main(argv)`:
- Takes the text from the positional argument, or from stdin if there isn't one (this makes it easy
  to paste multi-line shares).
- Loads games from `--games-dir` (default `games`), runs `normalize_text` from the Slack adapter
  (imported lazily, and skipped with a note if E isn't merged yet), then runs `parse_message`.
- Prints each result:

```
MapTap        score=862  rounds=[93, 88, 71, 97, 85]  puzzle=-
              best_round=97  worst_round=71  round_avg=86.8
```

- Prints `No game detected.` if there are no results, and exits 0 in both cases.
- `--all-games` also lists games whose `detect` didn't match. That's useful for debugging.

---

## 6. Tasks

- [ ] `parse_number`, plus the schema validators and cross-field checks
- [ ] `load_games` with file-path error prefixes, duplicate detection and `enabled` filtering
- [ ] `parse_message`: detect, score, rounds, puzzle, the warning log, and multi-game messages
- [ ] Plugin parser hook (lazy import and `game` override)
- [ ] `GameConfig.value`, `value_names`, `higher_is_better_for`, `label`
- [ ] The three starter YAML files (Krillion's format is known; see §5.6)
- [ ] `parse_cli.py`
- [ ] Replace `SAMPLES` in `tests/conftest.py` with real share texts once received (a contract-change PR)

## 7. Acceptance criteria

`tests/test_config.py`:
- [ ] Every file in `games/` loads (all three enabled)
- [ ] Rejected with a useful message: a bad regex, a missing `value` or `block` group, both or
      neither of `pattern`/`from_rounds`, `from_rounds` without `rounds`, an unknown key, `score`
      used as a value name, a duplicate alias across two files
- [ ] The error message includes the file path

`tests/test_parser.py`:
- [ ] MapTap sample gives score 862 and rounds (93, 88, 71, 97, 85). The date `24` and the
      total `862` aren't counted as rounds.
- [ ] TimeGuessr `38,532/50,000` gives 38532.0, with puzzle `"512"`
- [ ] Krillion sample gives score 505, puzzle `"72"` and rounds `(85, 100, 30, 85, 85, 60, 60)`,
      in **both** forms: raw unicode emoji (`Krillion #72 🦐 … 🏮🌟🐟…`) and Slack shortcodes
      (`Krillion #72 :shrimp: … :izakaya_lantern::star2::fish:…`). It also works without the blank
      line and with chatter after the tiles. The puzzle number `72` is never read as the score.
- [ ] `check_sum`: a Krillion text whose tiles don't add up to its score logs a warning and still
      records the posted score. A matching text logs nothing.
- [ ] A vertical-layout test game (defined in the test) extracts rounds line by line
- [ ] `from_rounds: sum` total
- [ ] `map` substitution (e.g. `X` becomes 7)
- [ ] Two games in one message give two results
- [ ] A non-game message gives `[]`
- [ ] `detect` matches but the score doesn't: the result is `[]` and a warning is logged (`caplog`)
- [ ] The plugin parser is called, and `game` is overridden
- [ ] Derived values: `best_round`, `round_avg`, and `None` when there are no rounds

## 8. Out of scope

Storage (B), Slack link normalisation (E), leaderboard logic (C).

## 9. Open questions

- **Needed from the project owner:** real share text for MapTap and TimeGuessr (Krillion ✅
  received: see §5.6). Paste the raw text as it appears in Slack (right-click → Copy text),
  ideally 2–3 samples per game, including a bad day and a perfect day.
- ~~Krillion scoring~~ ✅ Answered: 7 rounds, max 100 each, higher is better. Tiles: 🫧 10,
  🐟 30, 🦑 60, 🏮 85, 🌟 100 (see §5.6).
- **Krillion, to check during T-107:**
  - How the shared text arrives through the Slack API: unicode emoji vs `:shortcodes:`, and
    whether the blank line survives. Capture one real message with `leaderboard parse` once the
    adapter exists.
  - The exact shortcode Slack uses for each tile. 🏮 may be `:izakaya_lantern:` or `:lantern:`,
    and both are mapped. `check_sum` warnings will flag any tile that's missed.
  - Is the 🦐 in the header always the same, or does it vary (e.g. with a streak or rank)? It
    doesn't affect parsing, but it could be worth capturing later.
- Does any game post several puzzles per day (e.g. a daily and a bonus)? If so, the unit for
  duplicate handling may need to be `(day, puzzle)` rather than the day.
