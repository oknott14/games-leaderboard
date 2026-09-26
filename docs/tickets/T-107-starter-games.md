# T-107 · Starter game configs verified against real shares

| | |
|---|---|
| **Workstream** | A — Parsing & game configs ([plan](../plan/01-parsing.md)) |
| **Depends on** | [T-102](T-102-load-games.md), [T-104](T-104-rounds-extraction.md), [T-105](T-105-derived-values.md) |
| **Blocks** | [T-801](T-801-e2e-test.md) |
| **Size** | S (≤ 1 day) |
| **Needs** | Input or action from the project owner |

## Files

- `games/maptap.yaml`
- `games/timeguessr.yaml`
- `games/krillion.yaml`
- `tests/conftest.py` (`SAMPLES` only)
- `tests/test_games.py`

Edit only these files. Anything else needs a coordinated change (see [working rules](../plan/README.md#working-rules)).

## Read first

- [01-parsing.md](../plan/01-parsing.md) §5.6, §9

## Scope

- **Get real share text from the project owner** for MapTap and TimeGuessr: 2–3 samples each, copied from Slack. Krillion's sample and scoring are already in hand: `01-parsing.md` §5.6.
- Write or adjust the three YAML files. Krillion's config in §5.6 has been checked against the sample in both raw-emoji and `:shortcode:` form.
- Krillion is fully specified (7 rounds, tiles 🫧10 🐟30 🦑60 🏮85 🌟100, higher is better). Once the adapter exists, capture one real Krillion message through Slack and confirm the tile shortcodes. `check_sum` warnings flag any that are missing from the `map`.
- Replace `SAMPLES` in `tests/conftest.py` with the real texts. This is a contract-file change, so keep it a small separate commit and tag the other workstreams in review.
- `test_games.py`: every file in `games/` loads, and each real sample parses to the expected score, rounds and values.

## Acceptance criteria

- [ ] Every enabled game parses all its real samples correctly.
- [ ] Krillion `#72` sample gives score 505, puzzle `72` and rounds `(85, 100, 30, 85, 85, 60, 60)` in both raw-emoji and `:shortcode:` form, with no `check_sum` warning.
- [ ] `uv run pytest` passes; committed and pushed to `master`
