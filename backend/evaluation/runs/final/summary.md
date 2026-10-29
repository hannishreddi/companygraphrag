# Evaluation summary

## Overall

| Mode | n | Accuracy | Answerable acc. | Wrong but confident | Abstain correct | Evidence hit | Graph non-empty | p50 s | p95 s | LLM calls/q | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vanilla | 177 | 63% | 62% | 18% | 67% | 75% | - | 30.5 | 60.5 | 2.0 | 0 |
| graph | 177 | 70% | 70% | 5% | 67% | 2% | 137/173 | 46.5 | 105.1 | 3.1 | 0 |
| hybrid | 176 | 84% | 87% | 8% | 42% | 74% | 136/172 | 30.1 | 63.6 | 3.3 | 0 |
| router | 176 | 80% | 82% | 7% | 58% | 39% | 92/104 | 29.6 | 68.2 | 2.8 | 0 |

## Accuracy by category

| Category | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| aggregation | 7 | 43% | 100% | 100% | 100% |
| disambiguation | 10 | 100% | 90% | 100% | 90% |
| list | 10 | 90% | 100% | 100% | 90% |
| multi_hop | 39 | 13% | 64% | 74% | 64% |
| needle | 5 | 0% | 0% | 0% | 0% |
| relation_lookup | 23 | 87% | 91% | 100% | 100% |
| single_fact | 23 | 87% | 78% | 91% | 87% |
| temporal | 21 | 52% | 100% | 100% | 100% |
| unanswerable | 12 | 67% | 67% | 42% | 58% |
| wave_state | 27 | 93% | 19% | 85% | 78% |

## Accuracy by reasoning depth (hops)

| Hops | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| 1 | 129 | 80% | 70% | 86% | 84% |
| 2 | 9 | 33% | 100% | 100% | 100% |
| 3 | 13 | 15% | 62% | 77% | 62% |
| 4 | 18 | 17% | 61% | 72% | 61% |
| 5 | 8 | 0% | 75% | 75% | 75% |

## Router decisions

graph: 89, hybrid: 3, vanilla: 84
