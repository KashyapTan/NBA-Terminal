# Progressive local waiver exploration

The browser's arbitrary total forecast cutoff is removed. Search continues from one frozen fetched snapshot in local slices, retaining the best legally verified beneficial result. “Finished” describes the admitted market, beam and daily lineup policy; it is not proof of global optimality. Provider bounds, pickup qualification, outcome guards and acquisition usage remain enforced.

## Confirmed comparisons (controlled synthetic inputs)

| Case | Before | Progressive result |
|---|---|---|
| Late availability, 460 neutral pickups / 12 dates | 5,000 evaluations, no plan; last date unseen | Full first layer, >5,000 evaluations; legal beneficial last-date pickup found |
| Small no-benefit market | No material move | Finishes without inventing a recommendation |
| Small two-add exhaustive subset oracle | Independently enumerated legal subsets/objective | Same best pickups and full forecast totals |
| Dated interim/direct scenarios | V9 legal beneficial chains and direct shortcuts | Identical actions and forecasts; no wasteful extra adds |
| 400 pickups, ten slots, four adds | Total quota could terminate early | 79,616 evaluations; scoped completion in 17.21s; early plan 0.40s; two beneficial moves |
| Same market, seven adds | Same quota ceiling | 155,456 evaluations; scoped completion in 35.67s; early plan 0.39s; two beneficial moves |

Full-run benchmark peak process RSS was 50.5 MiB for both runs (pure Python optimizer harness, not the full web server). At an earlier cancellation sample, both budgets passed 22,000 evaluations in about four seconds. Timing is observed on this machine, not a service-level guarantee. The benchmark scripts, outputs and original screenshot are retained outside Git in the task's durable evidence directory, with hashes.

Real HTTP tests run the production routes, provider normalization, adapter and optimizer through Vite4219 and production8219; only external provider transports are synthetic. The legacy 5,000 path and additional local continuation use the identical provider request budget. Progress and cancellation never request ESPN/NBA data. Tests cover health responsiveness during CPU work, cross-session isolation, required request headers, cancellation, refresh invalidation, replacement races, job capacity/expiry and stable visible plans. Browser latency is held only for one local progress request to capture intermediate UI; no planner response is fabricated.

Desktop/mobile screenshots show the verified plan and visible sequence gains/losses while continuing. The full nine-category forecast and ordered dated move cards stay coherent. Raw provider-shaped snapshots and counts remain outside Git; screenshots and tests are compact tracked evidence.

The original image alone does not prove beneficial moves exist. The current private league snapshot could not be obtained through authorized browser surfaces; no exact private-user recommendation is claimed. Browser-host and native-window availability were checked without accessing credential stores or changing login.

Check results and exact publication/CI SHA are recorded in the task handoff; human merge is separate.

For the larger 902-pickup HTTP fixture, the old 5,000-budget path evaluated 3,339 states (four adds) / 3,345 states (seven adds) because of reserved/layer budgets. Progressive search finished 10,820 states for each. The same snapshot used two market pages, the same roster/card/actual batches, and the same NBA rate/team/schedule batches; each additional progress request added zero provider calls. CDN attempts are counted separately in the retained HTTP evidence. [Local checks](checks.txt), [self-review](../../../code_review/waiver-search.md), and `tests/waiver_search_benchmark.py` provide reproducible commands and scope.
