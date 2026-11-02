# Measured results

## d1

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 15/38, 19/38, 16/38 | 43.9 (35.1-53.0) | 11.7 | 30.5% | 0 | 28/76 | 42 | 46 | 5 | 0/0 | 55922 | 138 |
| b1 | 3 | 9/38, 11/38, 10/38 | 26.3 (19.1-35.1) | 6.2 | 25.2% | 0 | 3/73 | 58 | 10 | 1 | 0/0 | 19189 | 34 |
| b2 | 3 | 18/38, 19/38, 20/38 | 50.0 (41.0-59.0) | 12.6 | 29.5% | 0 | 36/75 | 39 | 53 | 6 | 0/0 | 58545 | 113 |
| steward | 3 | 23/38, 24/38, 21/38 | 59.6 (50.5-68.2) | 7.5 | 1.3% | 112 | 7/10 | 20 | 5 | 5 | 0/0 | 53739 | 141 |
| steward_norollback | 3 | 22/38, 24/38, 22/38 | 59.6 (50.5-68.2) | 7.1 | 1.4% | 93 | 8/9 | 21 | 6 | 6 | 0/0 | 52638 | 149 |

- steward vs b0, repeat 0: only steward 10, only b0 2, exact McNemar p = 0.039 (n = 38)
- steward vs b0, repeat 1: only steward 7, only b0 2, exact McNemar p = 0.180 (n = 38)
- steward vs b0, repeat 2: only steward 8, only b0 3, exact McNemar p = 0.227 (n = 38)
- steward vs b1, repeat 0: only steward 15, only b1 1, exact McNemar p = 0.001 (n = 38)
- steward vs b1, repeat 1: only steward 15, only b1 2, exact McNemar p = 0.002 (n = 38)
- steward vs b1, repeat 2: only steward 13, only b1 2, exact McNemar p = 0.007 (n = 38)
- steward vs b2, repeat 0: only steward 7, only b2 2, exact McNemar p = 0.180 (n = 38)
- steward vs b2, repeat 1: only steward 8, only b2 3, exact McNemar p = 0.227 (n = 38)
- steward vs b2, repeat 2: only steward 6, only b2 5, exact McNemar p = 1.000 (n = 38)
- steward vs steward_norollback, repeat 0: only steward 2, only steward_norollback 1, exact McNemar p = 1.000 (n = 38)
- steward vs steward_norollback, repeat 1: only steward 2, only steward_norollback 2, exact McNemar p = 1.000 (n = 38)
- steward vs steward_norollback, repeat 2: only steward 1, only steward_norollback 2, exact McNemar p = 1.000 (n = 38)

## d1h

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 1 | 19/30 | 63.3 (45.5-78.1) | 8.1 | 17.3% | 0 | 10/19 | 9 | 0 | 0 | 0/0 | 62809 | 154 |
| b1 | 1 | 9/30 | 30.0 (16.7-47.9) | 5.8 | 23.0% | 0 | 0/19 | 15 | 0 | 0 | 0/0 | 26182 | 51 |
| b2 | 1 | 23/30 | 76.7 (59.1-88.2) | 9.0 | 17.4% | 0 | 13/19 | 6 | 0 | 0 | 0/0 | 66320 | 129 |
| steward | 1 | 21/30 | 70.0 (52.1-83.3) | 7.1 | 14.1% | 0 | 9/16 | 6 | 0 | 0 | 0/0 | 81096 | 197 |
| steward_norollback | 1 | 20/30 | 66.7 (48.8-80.8) | 7.1 | 10.8% | 0 | 8/15 | 7 | 0 | 0 | 0/0 | 79893 | 131 |

- steward vs b0, repeat 0: only steward 5, only b0 3, exact McNemar p = 0.727 (n = 30)
- steward vs b1, repeat 0: only steward 13, only b1 1, exact McNemar p = 0.002 (n = 30)
- steward vs b2, repeat 0: only steward 1, only b2 3, exact McNemar p = 0.625 (n = 30)
- steward vs steward_norollback, repeat 0: only steward 2, only steward_norollback 1, exact McNemar p = 1.000 (n = 30)

## d2

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 4/10, 4/10, 4/10 | 40.0 (24.6-57.7) | 8.8 | 37.7% | 0 | 11/27 | 15 | 38 | 24 | 2/6 | 29010 | 85 |
| b1 | 3 | 6/10, 6/10, 5/10 | 56.7 (39.2-72.6) | 4.8 | 22.8% | 0 | 5/16 | 11 | 24 | 24 | 3/6 | 8695 | 30 |
| b2 | 3 | 5/10, 3/10, 4/10 | 40.0 (24.6-57.7) | 11.0 | 38.0% | 0 | 11/27 | 14 | 15 | 0 | 2/6 | 32223 | 73 |
| steward | 3 | 8/10, 7/10, 8/10 | 76.7 (59.1-88.2) | 4.8 | 0.0% | 24 | 0/0 | 4 | 26 | 24 | 4/6 | 26399 | 85 |
| steward_norollback | 3 | 8/10, 8/10, 8/10 | 80.0 (62.7-90.5) | 4.2 | 0.0% | 22 | 0/0 | 4 | 24 | 24 | 3/6 | 25692 | 70 |

- steward vs b0, repeat 0: only steward 5, only b0 1, exact McNemar p = 0.219 (n = 10)
- steward vs b0, repeat 1: only steward 5, only b0 2, exact McNemar p = 0.453 (n = 10)
- steward vs b0, repeat 2: only steward 5, only b0 1, exact McNemar p = 0.219 (n = 10)
- steward vs b1, repeat 0: only steward 3, only b1 1, exact McNemar p = 0.625 (n = 10)
- steward vs b1, repeat 1: only steward 2, only b1 1, exact McNemar p = 1.000 (n = 10)
- steward vs b1, repeat 2: only steward 4, only b1 1, exact McNemar p = 0.375 (n = 10)
- steward vs b2, repeat 0: only steward 5, only b2 2, exact McNemar p = 0.453 (n = 10)
- steward vs b2, repeat 1: only steward 6, only b2 2, exact McNemar p = 0.289 (n = 10)
- steward vs b2, repeat 2: only steward 5, only b2 1, exact McNemar p = 0.219 (n = 10)
- steward vs steward_norollback, repeat 0: only steward 0, only steward_norollback 0, exact McNemar p = 1.000 (n = 10)
- steward vs steward_norollback, repeat 1: only steward 0, only steward_norollback 1, exact McNemar p = 1.000 (n = 10)
- steward vs steward_norollback, repeat 2: only steward 0, only steward_norollback 0, exact McNemar p = 1.000 (n = 10)

## d3

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 1 | 8/38 | 21.1 (11.1-36.3) | 12.9 | 30.1% | 0 | 5/29 | 14 | 15 | 4 | 19/38 | 66134 | 193 |
| b1 | 1 | 4/38 | 10.5 (4.2-24.1) | 8.2 | 29.6% | 0 | 3/28 | 25 | 12 | 5 | 18/38 | 25240 | 61 |
| b2 | 1 | 9/38 | 23.7 (13.0-39.2) | 16.3 | 32.4% | 0 | 5/29 | 13 | 31 | 4 | 20/38 | 75486 | 168 |
| steward | 1 | 11/38 | 28.9 (17.0-44.8) | 9.6 | 2.2% | 58 | 2/5 | 9 | 4 | 7 | 18/38 | 73982 | 198 |
| steward_norollback | 1 | 10/38 | 26.3 (15.0-42.0) | 8.7 | 1.8% | 65 | 3/5 | 10 | 12 | 8 | 17/38 | 67944 | 184 |

- steward vs b0, repeat 0: only steward 6, only b0 3, exact McNemar p = 0.508 (n = 38)
- steward vs b1, repeat 0: only steward 11, only b1 4, exact McNemar p = 0.118 (n = 38)
- steward vs b2, repeat 0: only steward 6, only b2 4, exact McNemar p = 0.754 (n = 38)
- steward vs steward_norollback, repeat 0: only steward 3, only steward_norollback 2, exact McNemar p = 1.000 (n = 38)

