# LoopBuster Benchmark Results

*Generated: synthetic benchmark (410 scenarios)*

## Overall

| Metric | Value |
|---|---|
| Total Scenarios | 410 |
| TP | 206 |
| FP | 38 |
| FN | 54 |
| TN | 112 |
| Precision | 84.43% |
| Recall | 79.23% |
| F1 Score | 81.75% |
| Accuracy | 77.56% |

## By Loop Type

| Type | Count | Precision | Recall | F1 | FP |
|---|---|---|---|---|---|
| cycle | 70 | 100% | 69% | 81% | 0 |
| exact_repeat | 95 | 100% | 66% | 80% | 0 |
| fuzzy_repeat | 50 | 100% | 100% | 100% | 0 |
| good_cycle | 40 | - | 100% | - | 33 |
| none | 110 | - | 100% | - | 5 |
| output_stagnation | 45 | 100% | 100% | 100% | 0 |

## By Category

| Category | Count | Precision | Recall | F1 | FP |
|---|---|---|---|---|---|
| cycle | 55 | 100% | 75% | 85% | 0 |
| edge | 40 | 100% | 100% | 100% | 0 |
| exact_repeat | 70 | 100% | 71% | 83% | 0 |
| fuzzy_repeat | 50 | 100% | 100% | 100% | 0 |
| good_cycle | 40 | - | 100% | - | 33 |
| mixed | 30 | 100% | 33% | 50% | 0 |
| normal | 80 | - | 100% | - | 5 |
| stagnation | 45 | 100% | 100% | 100% | 0 |

## False Positives

- `synth_good_cycle_0301` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0302` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0303` (good_cycle, good_cycle): None
- `synth_good_cycle_0304` (good_cycle, good_cycle): None
- `synth_good_cycle_0305` (good_cycle, good_cycle): None
- `synth_good_cycle_0306` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0308` (good_cycle, good_cycle): None
- `synth_good_cycle_0309` (good_cycle, good_cycle): None
- `synth_good_cycle_0310` (good_cycle, good_cycle): None
- `synth_good_cycle_0312` (good_cycle, good_cycle): None
- `synth_good_cycle_0313` (good_cycle, good_cycle): None
- `synth_good_cycle_0314` (good_cycle, good_cycle): None
- `synth_good_cycle_0315` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0316` (good_cycle, good_cycle): None
- `synth_good_cycle_0317` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0318` (good_cycle, good_cycle): None
- `synth_good_cycle_0319` (good_cycle, good_cycle): None
- `synth_good_cycle_0320` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0322` (good_cycle, good_cycle): Fuzzy repeat: 'web_search' used 5/5 times
- `synth_good_cycle_0323` (good_cycle, good_cycle): None
- `synth_good_cycle_0324` (good_cycle, good_cycle): None
- `synth_good_cycle_0325` (good_cycle, good_cycle): None
- `synth_good_cycle_0326` (good_cycle, good_cycle): None
- `synth_good_cycle_0327` (good_cycle, good_cycle): None
- `synth_good_cycle_0329` (good_cycle, good_cycle): None
- `synth_good_cycle_0332` (good_cycle, good_cycle): None
- `synth_good_cycle_0334` (good_cycle, good_cycle): None
- `synth_good_cycle_0335` (good_cycle, good_cycle): None
- `synth_good_cycle_0336` (good_cycle, good_cycle): None
- `synth_good_cycle_0337` (good_cycle, good_cycle): None
- `synth_good_cycle_0338` (good_cycle, good_cycle): None
- `synth_good_cycle_0339` (good_cycle, good_cycle): None
- `synth_good_cycle_0340` (good_cycle, good_cycle): None
- `synth_normal_0042` (normal, None): Cycle detected: [analyze_sentiment → python_repl → web_search → parse_data → api_call] repeated 2 times
- `synth_normal_0047` (normal, None): Cycle detected: [search_database → parse_data → calculate → analyze_sentiment → send_email] repeated 2 times
- `synth_normal_0052` (normal, None): Cycle detected: [calculate → web_fetch → translate → read_news → get_weather] repeated 2 times
- `synth_normal_0056` (normal, None): Cycle detected: [calculate → api_call → read_news → translate → summarize_text] repeated 2 times
- `synth_normal_0059` (normal, None): Cycle detected: [summarize_text → create_document → send_email → web_search → python_repl] repeated 2 times

## False Negatives

- `synth_cycle_0205` (cycle, type=cycle, steps=6)
- `synth_cycle_0213` (cycle, type=cycle, steps=6)
- `synth_cycle_0214` (cycle, type=cycle, steps=6)
- `synth_cycle_0221` (cycle, type=cycle, steps=6)
- `synth_cycle_0223` (cycle, type=cycle, steps=6)
- `synth_cycle_0226` (cycle, type=cycle, steps=6)
- `synth_cycle_0229` (cycle, type=cycle, steps=6)
- `synth_cycle_0230` (cycle, type=cycle, steps=6)
- `synth_cycle_0231` (cycle, type=cycle, steps=6)
- `synth_cycle_0232` (cycle, type=cycle, steps=6)
- `synth_cycle_0238` (cycle, type=cycle, steps=6)
- `synth_cycle_0239` (cycle, type=cycle, steps=6)
- `synth_cycle_0240` (cycle, type=cycle, steps=6)
- `synth_cycle_0242` (cycle, type=cycle, steps=6)
- `synth_exact_repeat_0131` (exact_repeat, type=exact_repeat, steps=8)
- `synth_exact_repeat_0132` (exact_repeat, type=exact_repeat, steps=8)
- `synth_exact_repeat_0133` (exact_repeat, type=exact_repeat, steps=9)
- `synth_exact_repeat_0134` (exact_repeat, type=exact_repeat, steps=9)
- `synth_exact_repeat_0135` (exact_repeat, type=exact_repeat, steps=12)
- `synth_exact_repeat_0136` (exact_repeat, type=exact_repeat, steps=11)
- `synth_exact_repeat_0137` (exact_repeat, type=exact_repeat, steps=7)
- `synth_exact_repeat_0138` (exact_repeat, type=exact_repeat, steps=6)
- `synth_exact_repeat_0139` (exact_repeat, type=exact_repeat, steps=6)
- `synth_exact_repeat_0140` (exact_repeat, type=exact_repeat, steps=5)
- `synth_exact_repeat_0141` (exact_repeat, type=exact_repeat, steps=11)
- `synth_exact_repeat_0142` (exact_repeat, type=exact_repeat, steps=11)
- `synth_exact_repeat_0143` (exact_repeat, type=exact_repeat, steps=7)
- `synth_exact_repeat_0144` (exact_repeat, type=exact_repeat, steps=8)
- `synth_exact_repeat_0145` (exact_repeat, type=exact_repeat, steps=10)
- `synth_exact_repeat_0146` (exact_repeat, type=exact_repeat, steps=6)
- `synth_exact_repeat_0147` (exact_repeat, type=exact_repeat, steps=10)
- `synth_exact_repeat_0148` (exact_repeat, type=exact_repeat, steps=8)
- `synth_exact_repeat_0149` (exact_repeat, type=exact_repeat, steps=6)
- `synth_exact_repeat_0150` (exact_repeat, type=exact_repeat, steps=8)
- `synth_mixed_0341` (mixed, type=exact_repeat, steps=9)
- `synth_mixed_0342` (mixed, type=exact_repeat, steps=6)
- `synth_mixed_0343` (mixed, type=exact_repeat, steps=7)
- `synth_mixed_0344` (mixed, type=exact_repeat, steps=8)
- `synth_mixed_0345` (mixed, type=exact_repeat, steps=7)
- `synth_mixed_0346` (mixed, type=exact_repeat, steps=8)
- `synth_mixed_0348` (mixed, type=exact_repeat, steps=7)
- `synth_mixed_0350` (mixed, type=exact_repeat, steps=7)
- `synth_mixed_0352` (mixed, type=exact_repeat, steps=7)
- `synth_mixed_0353` (mixed, type=exact_repeat, steps=6)
- `synth_mixed_0354` (mixed, type=exact_repeat, steps=6)
- `synth_mixed_0355` (mixed, type=exact_repeat, steps=6)
- `synth_mixed_0356` (mixed, type=cycle, steps=9)
- `synth_mixed_0357` (mixed, type=cycle, steps=9)
- `synth_mixed_0358` (mixed, type=cycle, steps=8)
- `synth_mixed_0361` (mixed, type=cycle, steps=10)
- `synth_mixed_0363` (mixed, type=cycle, steps=7)
- `synth_mixed_0364` (mixed, type=cycle, steps=7)
- `synth_mixed_0365` (mixed, type=cycle, steps=11)
- `synth_mixed_0370` (mixed, type=cycle, steps=9)
