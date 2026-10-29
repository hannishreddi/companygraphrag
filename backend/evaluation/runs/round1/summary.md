# Evaluation summary

## Overall

| Mode | n | Accuracy | Answerable acc. | Wrong but confident | Abstain correct | Evidence hit | Graph non-empty | p50 s | p95 s | LLM calls/q | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vanilla | 54 | 63% | 64% | 12% | 50% | 72% | - | 13.0 | 19.1 | 2.0 | 0 |
| graph | 54 | 83% | 84% | 2% | 75% | 0% | 44/54 | 17.2 | 33.3 | 3.1 | 0 |
| hybrid | 54 | 87% | 90% | 8% | 50% | 70% | 44/54 | 13.2 | 20.5 | 3.3 | 0 |
| router | 54 | 89% | 90% | 4% | 75% | 30% | 31/36 | 11.0 | 19.3 | 2.9 | 0 |

## Accuracy by category

| Category | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| aggregation | 3 | 67% | 100% | 100% | 100% |
| disambiguation | 4 | 100% | 75% | 100% | 75% |
| list | 2 | 100% | 100% | 100% | 100% |
| multi_hop | 11 | 0% | 82% | 82% | 82% |
| needle | 1 | 0% | 0% | 0% | 0% |
| relation_lookup | 13 | 85% | 77% | 92% | 92% |
| single_fact | 7 | 100% | 86% | 86% | 100% |
| temporal | 9 | 67% | 100% | 100% | 100% |
| unanswerable | 4 | 50% | 75% | 50% | 75% |

## Accuracy by reasoning depth (hops)

| Hops | n | vanilla | graph | hybrid | router |
| --- | --- | --- | --- | --- | --- |
| 1 | 38 | 84% | 82% | 87% | 89% |
| 2 | 5 | 40% | 100% | 100% | 100% |
| 3 | 2 | 0% | 100% | 100% | 100% |
| 4 | 7 | 0% | 86% | 86% | 86% |
| 5 | 2 | 0% | 50% | 50% | 50% |

## Router decisions

graph: 30, hybrid: 1, vanilla: 23
