# Rising CLSVOF K Replacement Canary Summary (20260709T174800Z)

## Run health

| mode | status | issues |
| --- | --- | --- |
| original | OK |  |
| native_perturbed | OK |  |
| native_wrapper | OK |  |
| nn_baseline_128_hgradient | OK |  |
| nn_baseline_256_hgradient | OK |  |
| nn_baseline_512_hgradient | OK |  |
| nn_baseline_64_hgradient | OK |  |

## Provider stats

| mode | provider evals | clamp hits |
| --- | --- | --- |
| original | n/a | n/a |
| native_perturbed | 102828 | 0 |
| native_wrapper | 102828 | 0 |
| nn_baseline_128_hgradient | 102672 | 0 |
| nn_baseline_256_hgradient | 102862 | 0 |
| nn_baseline_512_hgradient | 102638 | 0 |
| nn_baseline_64_hgradient | 102641 | 0 |

## Hysing benchmark quantities

| mode | max(vb) | t at max(vb) | final vb | final xb | max volume drift | shape mean dist | shape max dist |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original | 0.251139 | 0.740444 | 0.18848 | 1.11211 | 0.000170148 | 0.149037 | 0.489396 |
| native_perturbed | 0.251139 | 0.740444 | 0.18848 | 1.11211 | 0.000170067 | 0.149037 | 0.489396 |
| native_wrapper | 0.251139 | 0.740444 | 0.18848 | 1.11211 | 0.000170148 | 0.149037 | 0.489396 |
| nn_baseline_128_hgradient | 0.251139 | 0.740444 | 0.18866 | 1.11212 | 0.000170874 | 0.149041 | 0.489404 |
| nn_baseline_256_hgradient | 0.251139 | 0.740444 | 0.188769 | 1.11212 | 0.000169621 | 0.14904 | 0.489404 |
| nn_baseline_512_hgradient | 0.251139 | 0.740444 | 0.188567 | 1.1121 | 0.000169223 | 0.149045 | 0.489419 |
| nn_baseline_64_hgradient | 0.251139 | 0.740444 | 0.188625 | 1.1121 | 0.000172343 | 0.149046 | 0.489419 |

## Delta vs original

| mode | d max(vb) | d final vb | d final xb | d max volume drift | d shape mean | d shape max |
| --- | --- | --- | --- | --- | --- | --- |
| native_perturbed | 0 | 0 | 0 | -8.1e-08 | 2.20532e-09 | 0 |
| native_wrapper | 0 | 0 | 0 | 0 | 0 | 0 |
| nn_baseline_128_hgradient | 0 | 0.00018 | 1e-05 | 7.26e-07 | 4.03116e-06 | 7.66553e-06 |
| nn_baseline_256_hgradient | 0 | 0.000289 | 1e-05 | -5.27e-07 | 3.21746e-06 | 7.66553e-06 |
| nn_baseline_512_hgradient | 0 | 8.7e-05 | -1e-05 | -9.25e-07 | 7.97625e-06 | 2.29969e-05 |
| nn_baseline_64_hgradient | 0 | 0.000145 | -1e-05 | 2.195e-06 | 8.62167e-06 | 2.29969e-05 |

