---
id: eval-readme-status
title: Make the README's status say what has been run
track: eval
milestone: v1
priority: core
needs: none
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "README.md"
done_when:
  - "the README no longer says that no language model has been run, and says that the exploratory runs have no result file"
  - "the README says which sensor channels the bolt task has and that the evaluator does not hand them to a policy yet"
  - "tools/check.sh"
---
## Why
The README says no learned or language model has been evaluated and that force feedback is not here. Since then the bolt task gained its sensor channels (`sim-obs-channels`), and a contributor has driven the arm on the bolt task with language models in exploratory runs. A reader who arrives from outside should find the same status the people working on it would give.

## What
- The status line names the exploratory language-model runs and says they are not results: no result file, not in the table.
- The sentence on freezing the hypotheses says what is frozen against: the runs of the experiment, not every run of a model.
- "Not here yet" separates what exists (sensor channels on the bolt task) from what does not (a policy receiving them, cameras, real hardware).
- No number is quoted for the exploratory runs. Numbers enter the README from result files.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-27, spartacosan: done. Three statements changed in the README. The exploratory runs are described without figures because none of them has a result file; `paper/hypotheses.md` still says it is frozen before any model result exists and belongs to `paper-prereg`, which should record these runs when it freezes.
