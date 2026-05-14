# Tutorial 04 — Sprint Mode

autodev ships a BMAD-derived sprint flow that manages a software sprint from
planning through retrospective, with course-correction support mid-sprint.

All sprint artifacts live under `.autodev/sprints/sprint-NNN/` inside your repo.

---

## Commands at a glance

| Command | Purpose |
|---------|---------|
| `autodev sprint-start` | Open a new sprint, generate planning artifacts |
| `autodev sprint-status` | Report health metrics for the current sprint |
| `autodev sprint-retro` | Run a retrospective, produce an action-item list |
| `autodev sprint-correct` | Analyse impact of a proposed mid-sprint change |

---

## Step 1 — Start a sprint

```bash
autodev sprint-start \
  --repo-path /tmp/my-project \
  --product-name "mdlines" \
  --goal "Deliver MVP: line-counter CLI with section breakdown and summary flag" \
  --duration-days 10
```

Expected output:

```
sprint_id=sprint-001 started_at=2024-05-14T14:30:00Z
planning=.autodev/sprints/sprint-001/planning/
implementation=.autodev/sprints/sprint-001/implementation/
```

The sprint directory is created with:

```
.autodev/sprints/sprint-001/
├── planning/
│   ├── sprint_plan.md       ← goal, scope, acceptance criteria
│   ├── epic_breakdown.md    ← epics and user stories
│   └── sprint_state.json   ← machine-readable state
└── implementation/
    └── (populated by deliver-project / run-issue during the sprint)
```

---

## Step 2 — Deliver work during the sprint

Use normal autodev commands to execute work within the sprint directory:

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --repo-path /tmp/my-project \
  --from-scratch true \
  --mode dry-run \
  --allow-mock-executor true
```

Or fix individual bugs:

```bash
autodev fix-bug \
  --bug "summary flag ignores blank lines" \
  --repo-path /tmp/my-project \
  --mode dry-run \
  --allow-mock-executor true
```

---

## Step 3 — Check sprint health

```bash
autodev sprint-status \
  --repo-path /tmp/my-project
```

To check a specific sprint (not just the latest):

```bash
autodev sprint-status \
  --repo-path /tmp/my-project \
  --sprint-id sprint-001
```

Expected output:

```
sprint_id=sprint-001 health=green
tasks_total=12 done=7 failed=0
progress=58.3%
```

Health values: `green` (on track), `yellow` (minor delays), `red` (blockers).

---

## Step 4 — Course-correct mid-sprint

If requirements change mid-sprint, use `sprint-correct` to understand the
blast radius before making changes:

```bash
autodev sprint-correct \
  --repo-path /tmp/my-project \
  --sprint-id sprint-001 \
  --change "Add JSON output mode to the CLI (--format json)"
```

Expected output:

```
sprint_id=sprint-001
impacts=3
  [medium] PRD: new --format flag must be added to scope
  [low]    Architecture: argparse group needs a new option
  [low]    Tests: snapshot test needs JSON variant
actions=2
```

Review the impact list, then adjust the sprint plan before implementing the change.

---

## Step 5 — Retrospective

At the end of the sprint:

```bash
autodev sprint-retro \
  --repo-path /tmp/my-project \
  --sprint-id sprint-001
```

Expected output:

```
sprint_id=sprint-001
well=4 wrong=2
actions=3
carryover_ac=1
generated_at=2024-05-24T09:00:00Z
```

The retrospective report is saved to:

```
.autodev/sprints/sprint-001/retro/
├── retrospective.md   ← narrative: what went well / what went wrong / actions
└── carryover.json     ← acceptance criteria rolling into sprint-002
```

---

## Consecutive sprints

When you start `sprint-002`, autodev picks up carryover from `sprint-001`
automatically:

```bash
autodev sprint-start \
  --repo-path /tmp/my-project \
  --product-name "mdlines" \
  --goal "Polish: JSON output, performance, packaging" \
  --duration-days 10
```

Output includes:

```
sprint_id=sprint-002 started_at=...
previous=sprint-001
planning=.autodev/sprints/sprint-002/planning/
```

The previous sprint's `carryover.json` is merged into the new sprint plan.

---

## See also

- [Tutorial 03 — Multi-CLI routing](03-multi-cli-routing.md)
- [Tutorial 05 — Roundtable party-mode](05-roundtable.md)
- [Architecture reference](../architecture.md)
