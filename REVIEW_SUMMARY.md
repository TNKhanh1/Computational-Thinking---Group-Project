# Testing Plan & Testing_System Review — Summary

**Branch:** `testing-system/paper-alignment` · **Commit:** `bcac08d` · **PR:** https://github.com/TNKhanh1/Computational-Thinking---Group-Project/pull/6
**Baseline (`group03-smartschedule-baseline/`) was not modified.**

## What was done
Checked every formula and threshold in `Testing_Plan/Testing_Plan.md` and `Testing_System/` against the full text of the papers in `Testing_Plan/`. Then fixed both the plan and the code wherever they disagreed with the source.

## Fixes
1. **Harness couldn't run.** The code imported `schedule_testing_system`, but the folder is named `Testing_System`. Imports were renamed.
2. **P2.3 Social Jetlag** now follows Smarr & Schirmer:
   - Only study blocks count as activity; class events just mark a day as a class day.
   - Days are calendar days, and each day type uses one pooled circular median.
   - SJL = class-day phase − non-class-day phase.
   - The old sign was inverted, so morning classes were labelled "delay". Regime 3 went from 600 min (delay) to 75 min (advance).
3. **P3.2 Corne.** The `10:3:1` weights were made up: Schaerf §4.2 p. 25 gives only a descending order of importance. The three counts are now kept as a vector and compared in that order.
4. **P2.2 Albulescu.**
   - Only `cognitive_load == 3` blocks are checked. The `FLOW` and `≥90 min` triggers had no source.
   - A class or other fixed event right after a heavy block no longer counts as a break.
5. **Removed** the "heavy block ≤60 min before bedtime" rule. Its threshold has no source.
6. **P4.2 / P4.1.**
   - Removed the made-up "first 5 blocks" fallback.
   - The time-shift metric (Δt) now uses both start and end times, as in Cowling & Johansson.
   - `DONE` blocks are no longer put through the delay simulation.
7. **G2.** Pinned slots are now subtracted from both the numerator and the denominator of ρ.
8. **Regime checks rewritten.**
   - Regime 2's old check always passed.
   - Regime 4 now also requires no unjustified last-10h crowding.
   - Regime 6 is now checked separately at each disruption level.
9. **Citations corrected.** The plan now marks which numbers come from papers and which are project parameters, and has a revision log at the top.

## Results
- `pytest Testing_System/tests`: 31 passed.
- Full suite on seeds 42/101/7/13, run directly and over HTTP: all pass.

## Finding (not fixed: it's in the baseline)
In Regime 2 the input has room for every task (EDF places 100%). Even so, **SCORED_GREEDY (95–98%) and WSPT (~86–87%) drop tasks that have deadlines**.
