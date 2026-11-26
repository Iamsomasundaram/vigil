# Projects

Everything else in this repo teaches one idea at a time. A **project** puts several of those
ideas together into one small, real application you can run, measure and extend.

| Folder | What it is | Question it answers |
| --- | --- | --- |
| `levels/` | Capability levels L0 to L6 | What can an agent do? |
| `architectures/` | Orchestration patterns A1 to A4 | How is its reasoning structured? |
| `reliability/` | R1 to R9 | How do I trust it in production? |
| **`projects/`** | Capstone projects | What does it look like when these are combined for a real job? |

Projects reuse the other folders instead of copying them, and each one is self-contained under
its own folder with its own README, tests and (where relevant) an answer key to score against.

## Available projects

| Project | Status | What it is |
| --- | --- | --- |
| [`autonomous_tester/`](autonomous_tester/README.md) | In progress (P1.1 done) | A tester agent that takes plain-language test cases, checks a web app, and classifies what it finds, measured against a demo shop with known, seeded bugs |

The plan for each project lives in [`specs/`](../specs/README.md) (see P1).

## Rules for every project

- **Generic.** No client names, systems, counts or terms. Examples are invented.
- **Measurable.** A project ships with a way to score it, not just a demo.
- **Honest about cost.** Anything that calls a paid model says so and shows an estimate first.
