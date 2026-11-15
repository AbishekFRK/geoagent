3 runs per model. Scores are the mean across runs, with the lowest and highest run in brackets.

| Model | Cases per run | Tool selection | Answer accuracy | Mean time per case |
|---|---|---|---|---|
| `qwen2.5:14b` | 18 | 94% (94%-94%) | 100% (100%-100%) | 9.3 s |
| `llama3.1:8b` | 18 | 83% (83%-83%) | 67% (67%-67%) | 6.5 s |

Per case: runs passed out of 3 (tools / answer).

| Case | `qwen2.5:14b` | `llama3.1:8b` |
|---|---|---|
| dist-001 | 3/3 / 3/3 | 3/3 / 3/3 |
| dist-002 | 3/3 / 3/3 | 3/3 / 3/3 |
| dist-003 | 3/3 / 3/3 | 3/3 / 3/3 |
| bearing-001 | 3/3 / 3/3 | 3/3 / 3/3 |
| nearest-001 | 3/3 / 3/3 | 3/3 / 3/3 |
| nearest-002 | 3/3 / 3/3 | 0/3 / 3/3 |
| within-001 | 3/3 / 3/3 | 0/3 / 3/3 |
| pip-001 | 3/3 / 3/3 | 3/3 / 0/3 |
| pip-002 | 3/3 / 3/3 | 3/3 / 0/3 |
| decline-001 | 0/3 / 3/3 | 3/3 / 3/3 |
| decline-002 | 3/3 / 3/3 | 3/3 / 0/3 |
| dist-004 | 3/3 / 3/3 | 3/3 / 0/3 |
| dist-005 | 3/3 / 3/3 | 3/3 / 3/3 |
| bearing-002 | 3/3 / 3/3 | 3/3 / 3/3 |
| nearest-003 | 3/3 / 3/3 | 3/3 / 3/3 |
| within-002 | 3/3 / 3/3 | 0/3 / 3/3 |
| decline-003 | 3/3 / 3/3 | 3/3 / 0/3 |
| decline-004 | 3/3 / 3/3 | 3/3 / 0/3 |
