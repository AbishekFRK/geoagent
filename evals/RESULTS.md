| Model | Cases | Tool selection | Answer accuracy | Mean time per case |
|---|---|---|---|---|
| `qwen2.5:14b` | 11 | 91% | 91% | 12.1 s |
| `llama3.1:8b` | 11 | 73% | 73% | 8.7 s |

Per case (tools / answer):

| Case | `qwen2.5:14b` | `llama3.1:8b` |
|---|---|---|
| dist-001 | ✅ / ✅ | ✅ / ✅ |
| dist-002 | ❌ / ❌ | ✅ / ✅ |
| dist-003 | ✅ / ✅ | ✅ / ✅ |
| bearing-001 | ✅ / ✅ | ✅ / ✅ |
| nearest-001 | ✅ / ✅ | ❌ / ✅ |
| nearest-002 | ✅ / ✅ | ❌ / ✅ |
| within-001 | ✅ / ✅ | ❌ / ✅ |
| pip-001 | ✅ / ✅ | ✅ / ❌ |
| pip-002 | ✅ / ✅ | ✅ / ❌ |
| decline-001 | ✅ / ✅ | ✅ / ✅ |
| decline-002 | ✅ / ✅ | ✅ / ❌ |
