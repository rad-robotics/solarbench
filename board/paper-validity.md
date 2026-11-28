---
id: paper-validity
title: Say what a score licenses, and cite what each design choice rests on
track: paper
milestone: v1
priority: stretch
needs: none
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "paper/outline.md"
done_when:
  - "paper/outline.md has a paragraph stating what a SolarBench result lets a reader claim and what it does not"
  - "section 2 of paper/outline.md names, for each check listed under contribution 4 and each choice in the experimental design, the published work it follows, with a link"
---
## Why
A review of 445 language-model benchmarks found that what they measure, their tasks and their scoring often do not support the claims made from them [P] https://arxiv.org/abs/2511.04703 . Most of what that literature recommends is already in this repository; the paper should say so, with citations, and say where it stops.

## What
- One paragraph: a SolarBench score is evidence about contact skill on these tasks, for this body, in simulation, against these specifications. It is not evidence of real-world performance until `open-real-arm` reports.
- Cite, each against the choice it supports:
  - Success as a written specification, scored by a signed margin: SPECOLA [P] https://arxiv.org/abs/2610.35730 (also add to `docs/field.md` through `field-watch`)
  - Reporting practice: number of runs, initial conditions, failure modes [P] https://arxiv.org/abs/2409.09491
  - Intervals and episode counts: https://arxiv.org/abs/2108.13264 ; STEP and N-SCORE (see `eval-power`)
  - Two physics engines: Erez, Tassa and Todorov, ICRA 2015 https://doi.org/10.1109/ICRA.2015.7139807
  - Missions broken into elemental tests: NIST and ASTM E54.09 https://www.nist.gov/node/1118501
  - Audits of the benchmark itself: SWE-bench Verified https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
