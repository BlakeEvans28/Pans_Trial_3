# Testing and Balance

Pan's Trial includes both automated regression testing and headless balance analysis.

## Main Regression Suite

The primary checked-in test file is:

```text
tests/test_rules.py
```

It covers a mix of:

- core rule behavior
- phase transitions
- request resolution
- multiplayer flows
- room-server behavior
- UI smoke checks
- layout regressions

Run it with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rules.py
```

The web-build environment can also run the same suite:

```powershell
.\.venv-web\Scripts\python.exe -m pytest tests\test_rules.py
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

- `tests/test_rules.py`
- `balance_testing.py`
- `Balancing_Testing_01_Report.md`
- `FINAL_Balancing_Testing_01.xlsx`
