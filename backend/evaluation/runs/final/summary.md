# Evaluation summary

## Overall

| Mode | n | Accuracy | Answerable acc. | Wrong but confident | Abstain correct | Evidence hit | Graph non-empty | p50 s | p95 s | LLM calls/q | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vanilla | 179 | 62% | 62% | 19% | 67% | 74% | - | 29.7 | 62.1 | 2.0 | 0 |
| graph | 179 | 68% | 69% | 5% | 58% | 0% | 142/179 | 43.9 | 105.1 | 3.2 | 0 |
| hybrid | 179 | 84% | 87% | 8% | 33% | 72% | 142/179 | 27.5 | 62.5 | 3.4 | 0 |
| router | 179 | 80% | 82% | 7% | 50% | 38% | 96/108 | 28.1 | 68.2 | 2.8 | 0 |

## Accuracy by category

| Category | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| aggregation | 9 | 33% | 100% | 100% | 100% |
| disambiguation | 10 | 100% | 90% | 100% | 90% |
| list | 10 | 90% | 100% | 100% | 90% |
| multi_hop | 39 | 13% | 64% | 74% | 64% |
| needle | 5 | 0% | 0% | 0% | 0% |
| relation_lookup | 23 | 87% | 91% | 100% | 100% |
| single_fact | 23 | 87% | 78% | 91% | 87% |
| temporal | 21 | 52% | 95% | 100% | 100% |
| unanswerable | 12 | 67% | 58% | 33% | 50% |
| wave_state | 27 | 93% | 11% | 85% | 78% |

## Accuracy by reasoning depth (hops)

| Hops | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| 1 | 131 | 79% | 68% | 85% | 83% |
| 2 | 9 | 33% | 89% | 100% | 100% |
| 3 | 13 | 15% | 62% | 77% | 62% |
| 4 | 18 | 17% | 61% | 72% | 61% |
| 5 | 8 | 0% | 75% | 75% | 75% |

## Router decisions

graph: 93, hybrid: 3, vanilla: 83
