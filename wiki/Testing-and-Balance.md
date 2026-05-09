# Testing and Balance

Pan's Trial includes both automated regression testing and headless balance analysis. This page carries the evidence section of the written report into the wiki and links it back to the runnable project files.

## Main Regression Suite

The primary checked-in test file is:

```text
tests/test_rules.py
```

The current checkout collects `118` tests from this file. They cover a mix of:

- core rule behavior
- phase transitions
- request resolution
- multiplayer flows
- room-server behavior
- UI smoke checks
- layout regressions
- browser bridge behavior
- rematch, leave, and reconnect-adjacent room flows

Run it with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rules.py
```

The web-build environment can also run the same suite:

```powershell
.\.venv-web\Scripts\python.exe -m pytest tests\test_rules.py
```

If you only need to confirm the current collected count:

```powershell
.\.venv-web\Scripts\python.exe -m pytest tests\test_rules.py --collect-only -q
```

## Foundation Verification

For a quick non-UI sanity check of imports and basic setup:

```powershell
python verify_foundation.py
```

This verifies that the engine, UI package, and basic setup flow still initialize correctly.

## Headless Balance Study

The project includes a headless match simulator:

```text
balance_testing.py
```

Run the default study:

```powershell
python balance_testing.py
```

Run a custom-size study and save the results to a folder:

```powershell
python balance_testing.py --games 200 --output-dir .\balance_runs
```

By default, the study writes:

- `Balancing_Testing_01.xlsx`
- `Balancing_Testing_01_Report.md`

The written report cites a 100-game AI-vs-AI study:

| Metric | Result |
| --- | --- |
| Games simulated | 100 |
| Player 1 wins | 52 |
| Player 2 wins | 48 |
| Experienced profile | 51/67 wins, 76.12% |
| Amateur profile | 48/67 wins, 71.64% |
| Beginner profile | 1/66 wins, 1.52% |
| Average actions per game | 235.83 |
| Average final damage, Player 1 | 19.22 |
| Average final damage, Player 2 | 19.24 |
| Request uses | Plane Shift 124, Steal Life 88, Ignore Us 49, Restructure 49 |
| Appeasing Pan skips | 0 |

The main interpretation is that neither seat dominates and stronger AI profiles outperform weaker profiles. That supports the publication claim that Pan's Trial is tactical rather than only random.

## What the Balance Study Measures

The simulation is meant to answer questions like:

- Is there an obvious starting-seat advantage?
- Do stronger agents beat weaker ones consistently?
- How often is Appeasing Pan skipped after hands run out?
- Are request types showing up in a healthy mix?
- Are the final damage totals roughly close between seats?

## Why the Balance Harness Matters

Because the simulator runs on the same live engine rules as the playable game, it helps turn balance discussion into measurable evidence instead of guesswork.

That makes it useful for:

- rule tuning
- fairness checks
- AI evaluation
- documenting design decisions

## Recommended Testing Habit

When changing gameplay behavior:

1. Update or add engine-level tests.
2. Run `tests/test_rules.py`.
3. If the change affects fairness, run at least a small balance study.
4. Rebuild the browser package if the change affects web behavior or assets.

## Related Files

- [`tests/test_rules.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/tests/test_rules.py)
- [`balance_testing.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/balance_testing.py)
- [`Balancing_Testing_01_Report.md`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/Balancing_Testing_01_Report.md)
- [`FINAL_Balancing_Testing_01.xlsx`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/FINAL_Balancing_Testing_01.xlsx)
- [Publication Case](Publication-Case)
