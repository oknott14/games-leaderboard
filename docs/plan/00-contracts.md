# Workstream 0 — Contracts & Scaffold

## 1. Goal

Create the project skeleton and every **shared type and signature** as real Python code, with stub
bodies. After this PR merges, workstreams A–E and G can build in parallel against these stubs,
using the test fakes defined here, without waiting on each other.

This doc is the source of truth for the interfaces. **The code stubs must match it exactly.**
Changing anything here follows the contract-change rule in [README.md](README.md#working-rules).

## 2. Owns

- `pyproject.toml`, `uv.lock`, `.gitignore`, `src/leaderboard/__init__.py`, `src/leaderboard/__main__.py` (stub)
- `src/leaderboard/ports.py` (complete — no logic to fill in)
- `src/leaderboard/models.py` (complete)
- **Schema and stubs** in `config.py`, `parser.py`, `boards/core.py`, `boards/config.py`,
  `boards/registry.py`, `boards/engine.py`, `boards/__init__.py`, `commands.py`, `formatting.py`,
  `service.py`, `db.py`, `settings.py`, `adapters/slack.py`, `scheduler.py`, `cli.py`. After merge,
  the **function bodies** in each file belong to the workstream noted next to each section below.
- `tests/conftest.py` (fakes and fixtures) and `tests/test_contracts.py` (smoke tests: importable,
  dataclasses constructible, schemas validate the example YAML)

**Must not:** implement logic owned by other workstreams. Stubs raise `NotImplementedError`.

## 3. Depends on

Nothing.

## 4. Provides

Everything below.

---

## 5. Contracts

Module paths are relative to `src/leaderboard/`. Every module starts with `from __future__ import annotations`.

### 5.1 `ports.py` — chat platform abstraction *(complete in WS0)*

```python
@dataclass(frozen=True)
class ChatMessage:
    platform: str                 # "slack"
    channel_id: str
    message_id: str               # unique within channel (Slack: ts)
    user_id: str
    text: str                     # normalised plain text (adapter's job)
    posted_at: datetime           # tz-aware UTC
    thread_id: str | None = None

class ChatHandler(Protocol):      # implemented by LeaderboardService (B)
    def on_message(self, msg: ChatMessage) -> None: ...          # new OR edited → upsert
    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None: ...
    def on_command(self, text: str) -> str: ...                  # text after mention/command → reply

class ChatPort(Protocol):         # implemented by SlackPort (E), FakePort (tests)
    platform: str
    def fetch_history(self, channel_id: str, oldest: datetime) -> Iterator[ChatMessage]: ...
    def post(self, channel_id: str, text: str, thread_id: str | None = None) -> None: ...
    def display_name(self, user_id: str) -> str: ...             # never raises; falls back to user_id
    def run(self, handler: ChatHandler) -> None: ...             # blocks; dispatches events to handler
```

### 5.2 `config.py` — game config schema *(schema: WS0 · logic: A)*

All models use `model_config = ConfigDict(extra="forbid")`.

```python
Flag = Literal["IGNORECASE", "DOTALL", "MULTILINE"]
Reducer = Literal["sum", "avg", "max", "min"]
DuplicatePolicy = Literal["first", "best", "last"]

class NumberSpec(BaseModel):
    type: Literal["int", "float"] = "int"
    map: dict[str, float] = {}           # raw capture → value, applied before conversion

class ScoreSpec(NumberSpec):
    pattern: str | None = None           # must contain (?P<value>…)
    from_rounds: Reducer | None = None   # exactly one of pattern / from_rounds

class RoundsSpec(NumberSpec):
    block: str                           # must contain (?P<block>…)
    item: str                            # findall inside the block; 1 group or whole match
    check_sum: bool = False              # warn if sum(rounds) != posted score (needs score.pattern)

class PuzzleSpec(BaseModel):
    pattern: str                         # must contain (?P<value>…)

class ValueSpec(BaseModel):
    from_rounds: Reducer
    higher_is_better: bool | None = None # None → game default

class GameConfig(BaseModel):
    name: str                            # slug ^[a-z0-9_]+$ ; defaults to file stem
    display_name: str | None = None
    aliases: list[str] = []
    enabled: bool = True
    flags: list[Flag] = []
    detect: str | None = None            # required unless `parser` is set
    score: ScoreSpec | None = None       # required unless `parser` is set
    rounds: RoundsSpec | None = None
    puzzle: PuzzleSpec | None = None
    parser: str | None = None            # "module:function" plugin parser (see 5.3)
    higher_is_better: bool = True
    duplicates: DuplicatePolicy = "first"
    values: dict[str, ValueSpec] = {}    # extra values; "score" is implicit and reserved

    # --- methods (bodies: A) ---
    @property
    def label(self) -> str: ...                          # display_name or name
    def value_names(self) -> list[str]: ...              # ["score", *values]
    def value(self, name: str, score: float, rounds: tuple[float, ...]) -> float | None: ...
    def higher_is_better_for(self, value_name: str) -> bool: ...

def load_games(directory: Path) -> dict[str, GameConfig]: ...   # body: A
```

### 5.3 `parser.py` *(types: WS0 · logic: A)*

```python
@dataclass(frozen=True)
class ParsedResult:
    game: str
    score: float
    rounds: tuple[float, ...] = ()
    puzzle: str | None = None

# Plugin parser signature referenced by GameConfig.parser. The framework sets `game`
# on the returned value (dataclasses.replace), so plugins may pass any placeholder.
PluginParser = Callable[[str], ParsedResult | None]

def parse_message(text: str, games: Iterable[GameConfig]) -> list[ParsedResult]: ...  # body: A
```

### 5.4 `models.py` — ORM *(complete in WS0)*

SQLAlchemy 2.0 typed declarative. All datetimes are **naive UTC**.

```python
class Base(DeclarativeBase): ...

class Message(Base):             # __tablename__ = "messages"
    id: int (PK)
    platform: str; channel_id: str; message_id: str     # UniqueConstraint(platform, channel_id, message_id)
    user_id: str (indexed)
    text: str
    posted_at: datetime (indexed)
    thread_id: str | None
    edited_at: datetime | None
    results: list[GameResult]    # relationship, cascade="all, delete-orphan"

class GameResult(Base):          # __tablename__ = "game_results"
    id: int (PK)
    message_pk: int              # FK messages.id ON DELETE CASCADE
    game: str (indexed)
    platform: str; user_id: str
    score: float
    puzzle: str | None
    played_on: date (indexed)    # local-timezone date of posted_at
    posted_at: datetime          # copied from message
    rounds: list[GameRound]      # relationship, cascade, order_by round_no
    # UniqueConstraint(message_pk, game)

class GameRound(Base):           # __tablename__ = "game_rounds"
    result_pk: int               # FK game_results.id ON DELETE CASCADE, part of PK
    round_no: int                # 1-based, part of PK
    value: float
```

### 5.5 `boards/core.py` — engine types *(types: WS0 · function bodies: C2)*

```python
PlayerKey = tuple[str, str]              # (platform, user_id)

@dataclass(frozen=True)
class ResultRow:                         # what the service loads from the DB for the engine
    player: PlayerKey
    game: str
    played_on: date
    posted_at: datetime                  # naive UTC
    score: float
    rounds: tuple[float, ...]

@dataclass(frozen=True)
class DateRange:
    start: date | None                   # None = beginning of time
    end: date                            # inclusive

@dataclass(frozen=True)
class Entry:                             # one player's value on one day, after dedupe
    player: PlayerKey
    played_on: date
    posted_at: datetime
    value: float

@dataclass(frozen=True)
class Standing:
    player: PlayerKey
    value: float
    entries: int                         # results that contributed
    rank: int                            # competition ranking (1, 1, 3)
    detail: str | None = None            # extra context, e.g. "+120 vs last week"

@dataclass(frozen=True)
class WindowResult:
    range: DateRange                     # rows to load
    select: Callable[[list[Entry]], list[Entry]] | None = None   # optional per-player trim (last_n)

@dataclass(frozen=True)
class AggContext:
    higher_is_better: bool
    anchor: date
    params: BaseModel | None

@dataclass
class BoardContext:
    game: GameConfig
    board: BoardConfig
    value_name: str
    higher_is_better: bool               # resolved: board → value → game
    anchor: date
    range: DateRange
    entries: list[Entry]                 # deduped, valued, window-selected; sorted by played_on
    params: BaseModel | None             # board type params
    aggregate: Callable[[list[Entry]], float | None]    # board's aggregator, bound
    fetch: Callable[[DateRange], list[Entry]]           # same pipeline for another range

def dedupe_daily(rows: list[ResultRow], policy: DuplicatePolicy, higher_is_better: bool) -> list[ResultRow]: ...
def rank(scored: list[tuple[PlayerKey, float, int, str | None]], higher_is_better: bool) -> list[Standing]: ...
```

### 5.6 `boards/registry.py` + `boards/__init__.py` — plugin API *(decorators & dicts: complete in WS0 · `load_builtins` / `load_plugins` / `validate_params`: C3)*

The decorators are about 20 lines, so WS0 implements them fully. That lets C1 and C2 register
components and test them without waiting for C3. A duplicate name raises `ValueError`.

```python
WindowFn     = Callable[[date, BaseModel | None], WindowResult]
AggregatorFn = Callable[[list[Entry], AggContext], float | None]
BoardTypeFn  = Callable[[BoardContext], list[Standing]]

@dataclass(frozen=True)
class Registered:
    name: str
    fn: Callable
    params: type[BaseModel] | None
    description: str
    unit: str | None                     # display suffix, e.g. "days"
    higher_is_better: bool | None        # forced direction (count → True, stddev → False)

def window(name: str, *, params: type[BaseModel] | None = None, description: str = "") -> Callable: ...
def aggregator(name: str, *, params: type[BaseModel] | None = None, description: str = "",
               unit: str | None = None, higher_is_better: bool | None = None) -> Callable: ...
def board_type(name: str, *, params: type[BaseModel] | None = None, description: str = "",
               unit: str | None = None) -> Callable: ...

WINDOWS: dict[str, Registered]; AGGREGATORS: dict[str, Registered]; BOARD_TYPES: dict[str, Registered]

def load_builtins() -> None: ...                         # imports windows/aggregators/types modules
def load_plugins(directory: Path) -> list[str]: ...      # imports *.py, returns registered names
def validate_params(reg: Registered, raw: dict[str, Any]) -> BaseModel | None: ...
```

`boards/__init__.py` re-exports: `window`, `aggregator`, `board_type`, `Entry`, `Standing`,
`BoardContext`, `AggContext`, `WindowResult`, `DateRange`. That's the whole plugin API.

### 5.7 `boards/config.py` — `boards.yaml` schema *(schema: WS0 · loader & validation: C3)*

```python
class ComponentRef(BaseModel):
    name: str
    params: dict[str, Any] = {}
    # YAML accepts: "avg" | {last_n: 5} (single-key → name + {"n": 5} via the component's
    # first param field) | {name: top_k_avg, k: 3}. A before-validator normalises these.

class BoardConfig(BaseModel):
    name: str
    title: str | None = None
    type: ComponentRef = ComponentRef(name="ranked")
    value: str = "score"
    window: ComponentRef = ComponentRef(name="week")
    aggregate: ComponentRef = ComponentRef(name="sum")
    min_entries: int = 1
    higher_is_better: bool | None = None
    games: list[str] | None = None       # None = every game that has `value`
    limit: int = 10

AnchorName = Literal["today", "yesterday", "last_week", "last_month"]

class ScheduleEntry(BaseModel):
    cron: str                            # 5-field crontab
    boards: list[str]
    anchor: AnchorName = "today"

class BoardsFile(BaseModel):
    defaults: dict[str, Any] = {}        # merged into every board before validation
    boards: dict[str, BoardConfig] = {}
    schedule: list[ScheduleEntry] = []

def load_boards(path: Path, games: Mapping[str, GameConfig]) -> BoardsFile: ...   # body: C3
```

### 5.8 `boards/engine.py` *(body: C2)*

```python
@dataclass(frozen=True)
class GameBoardResult:
    game: GameConfig
    standings: list[Standing]

@dataclass(frozen=True)
class BoardResult:
    board: BoardConfig
    anchor: date
    range: DateRange
    unit: str | None
    sections: list[GameBoardResult]      # one per applicable game, in games-dict order

def board_applies(board: BoardConfig, game: GameConfig) -> bool: ...
def board_range(board: BoardConfig, anchor: date) -> DateRange: ...     # the window's range, for headers
def board_unit(board: BoardConfig) -> str | None: ...                   # board type unit, else aggregator unit
def run_board(board: BoardConfig, game: GameConfig, anchor: date,
              load_rows: Callable[[DateRange], list[ResultRow]]) -> list[Standing]: ...
```

The service (B) supplies `load_rows`. The engine never touches the DB.

### 5.9 `commands.py` *(body: D)*

```python
# Constants (complete in WS0). The C3 collision check uses them too.
ANCHOR_WORDS: frozenset[str] = frozenset({"today", "yesterday", "lastweek", "lastmonth"})
RESERVED_WORDS: frozenset[str] = frozenset({"help", "games", "boards"})

@dataclass(frozen=True)
class Query:
    board: BoardConfig                   # saved or ad hoc
    games: list[str] | None              # None = all applicable
    anchor: date

@dataclass(frozen=True)
class InfoRequest:
    topic: Literal["help", "games", "boards"]

@dataclass(frozen=True)
class CommandError:
    message: str
    suggestions: list[str] = field(default_factory=list)

def parse_command(text: str, *, today: date, games: Mapping[str, GameConfig],
                  boards: Mapping[str, BoardConfig]) -> Query | InfoRequest | CommandError: ...
def resolve_anchor(token: str, today: date) -> date | None: ...   # also used by the scheduler (F)
```

### 5.10 `formatting.py` *(body: D)*

```python
NameFor = Callable[[str, str], str]      # (platform, user_id) → display name

def fmt_value(value: float, unit: str | None = None) -> str: ...
def format_board(result: BoardResult, name_for: NameFor) -> str: ...
def format_info(topic: str, games: Mapping[str, GameConfig], boards: Mapping[str, BoardConfig]) -> str: ...
def format_error(err: CommandError) -> str: ...
```

### 5.11 `db.py` + `service.py` *(bodies: B)*

```python
def make_session_factory(url: str) -> sessionmaker[Session]: ...

class LeaderboardService:                # satisfies ChatHandler
    def __init__(self, sessions: sessionmaker[Session], games: Mapping[str, GameConfig],
                 boards: BoardsFile, tz: ZoneInfo, channel_ids: frozenset[str],
                 name_for: NameFor, *, store_non_game: bool = True,
                 today: Callable[[], date] | None = None) -> None: ...
    def on_message(self, msg: ChatMessage) -> None: ...
    def on_message_deleted(self, platform: str, channel_id: str, message_id: str) -> None: ...
    def on_command(self, text: str) -> str: ...
    def run_query(self, query: Query) -> BoardResult: ...
    def backfill(self, port: ChatPort, *, since: datetime | None = None, default_days: int = 90) -> int: ...
    def reparse(self) -> int: ...
    def latest_posted_at(self, platform: str, channel_id: str) -> datetime | None: ...
```

### 5.12 `adapters/slack.py` *(body: E)*

```python
def normalize_text(text: str) -> str: ...

class SlackPort:                         # satisfies ChatPort; platform = "slack"
    def __init__(self, bot_token: str, app_token: str, *, proxy: str | None = None,
                 ssl_context: ssl.SSLContext | None = None) -> None: ...
```

### 5.13 `settings.py`, `scheduler.py`, `cli.py` *(bodies: F)*

```python
@dataclass(frozen=True)
class Settings:
    slack_bot_token: str; slack_app_token: str
    channel_ids: frozenset[str]
    timezone: ZoneInfo
    database_url: str = "sqlite:///data/leaderboard.db"
    games_dir: Path = Path("games"); boards_file: Path = Path("boards.yaml"); plugins_dir: Path = Path("plugins")
    backfill_days: int = 90
    store_non_game_messages: bool = True
    https_proxy: str | None = None; ssl_cert_file: Path | None = None
    log_level: str = "INFO"
    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings: ...

def start_scheduler(schedule: list[ScheduleEntry], service: LeaderboardService, port: ChatPort,
                    channel_ids: frozenset[str], tz: ZoneInfo) -> BackgroundScheduler | None: ...
def run_schedule_entry(entry: ScheduleEntry, service: LeaderboardService, port: ChatPort,
                       channel_ids: frozenset[str], today: date) -> None: ...

def main(argv: list[str] | None = None) -> int: ...
```

---

## 6. Test fakes (`tests/conftest.py`)

Every workstream tests against these. They are part of the contract.

| Fixture / helper | Provides |
|---|---|
| `SAMPLES: dict[str, str]` | Share texts keyed like `"maptap_basic"`, `"timeguessr_basic"`, `"krillion_basic"` (the real sample: `"Krillion #72 🦐\n505\n\n🏮🌟🐟🏮🏮🦑🦑"`), `"krillion_slack"` (the same with `:shortcodes:`), `"two_games_one_message"`, `"not_a_game"`, and `"maptap_slack_raw"` (with `<url\|label>` link markup). Replace them with real texts once workstream A gets them. |
| `sample_games()` | `dict[str, GameConfig]` for MapTap, TimeGuessr and Krillion, built in code (matching `games/*.yaml`). |
| `make_rows(spec)` | Builds `list[ResultRow]` from a compact spec, e.g. `[("alice", "2026-09-22", 862), ("bob", "2026-09-22", 900, (90, 95))]`. |
| `make_board(**kw)` | `BoardConfig` with defaults, for engine and command tests. |
| `FakePort` | In-memory `ChatPort`: `history` list, `posted` list, `names` dict, `run()` is a no-op. |
| `sessions` | `sessionmaker` over a temporary SQLite file with `Base.metadata.create_all`. Doesn't depend on `db.py`, so B isn't a blocker. |
| `fixed_today` | `date(2026, 9, 24)` (a Thursday), used as the `today` for every date-sensitive test. |

## 7. Tasks

- [ ] `pyproject.toml` (deps: `slack-bolt`, `sqlalchemy>=2`, `pydantic>=2`, `pyyaml`, `apscheduler>=3.10,<4`, `tzdata`; dev: `pytest`; script `leaderboard = "leaderboard.cli:main"`), `uv lock`, `.gitignore`
- [ ] `ports.py`, `models.py` (complete)
- [ ] Every other module with the signatures above; bodies `raise NotImplementedError`
- [ ] Pydantic schemas in `config.py` and `boards/config.py` (fields and simple validators only; cross-file validation belongs to A and C3)
- [ ] `tests/conftest.py` fakes
- [ ] `tests/test_contracts.py`: all modules import; the example YAML in `01-parsing.md` and `03-boards-engine.md` validates against the schemas; `create_all` works on the temporary DB
- [ ] Add owner names to the status table in `README.md`

## 8. Acceptance criteria

- [ ] `uv sync && uv run pytest` passes on a clean checkout.
- [ ] Every signature in this doc exists in code with the same names, parameters and types.
- [ ] Reviewed by at least one owner from A, B, C and D before merge.

## 9. Out of scope

Any real logic. Every stub raises `NotImplementedError`.

## 10. Open questions

- None yet. Add them here.
