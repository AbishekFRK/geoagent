| Model | Cases | Tool selection | Answer accuracy | Mean time per case |
|---|---|---|---|---|
| `qwen2.5:14b` | 18 | 94% | 100% | 12.7 s |
| `llama3.1:8b` | 18 | 83% | 67% | 16.8 s |

Per case (tools / answer):

| Case | `qwen2.5:14b` | `llama3.1:8b` |
|---|---|---|
| dist-001 | ✅ / ✅ | ✅ / ✅ |
| dist-002 | ✅ / ✅ | ✅ / ✅ |
| dist-003 | ✅ / ✅ | ✅ / ✅ |
| bearing-001 | ✅ / ✅ | ✅ / ✅ |
| nearest-001 | ✅ / ✅ | ✅ / ✅ |
| nearest-002 | ✅ / ✅ | ❌ / ✅ |
| within-001 | ✅ / ✅ | ❌ / ✅ |
| pip-001 | ✅ / ✅ | ✅ / ❌ |
| pip-002 | ✅ / ✅ | ✅ / ❌ |
| decline-001 | ❌ / ✅ | ✅ / ✅ |
| decline-002 | ✅ / ✅ | ✅ / ❌ |
| dist-004 | ✅ / ✅ | ✅ / ❌ |
| dist-005 | ✅ / ✅ | ✅ / ✅ |
| bearing-002 | ✅ / ✅ | ✅ / ✅ |
| nearest-003 | ✅ / ✅ | ✅ / ✅ |
| within-002 | ✅ / ✅ | ❌ / ✅ |
| decline-003 | ✅ / ✅ | ✅ / ❌ |
| decline-004 | ✅ / ✅ | ✅ / ❌ |
