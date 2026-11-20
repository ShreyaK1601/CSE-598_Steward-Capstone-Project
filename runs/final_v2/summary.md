# Measured results

## d1

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 15/38, 19/38, 16/38 | 43.9 (35.1-53.0) | 11.7 | 30.5% | 0 | 28/76 | 42 | 46 | 5 | 0/0 | 36.8% | 38.6% | 55922 | 138 |
| b1 | 3 | 9/38, 11/38, 10/38 | 26.3 (19.1-35.1) | 6.2 | 25.2% | 0 | 3/73 | 58 | 10 | 1 | 0/0 | 0.0% | 72.8% | 19189 | 34 |
| b2 | 3 | 18/38, 19/38, 20/38 | 50.0 (41.0-59.0) | 12.6 | 29.5% | 0 | 36/75 | 39 | 53 | 6 | 0/0 | 31.6% | 32.5% | 58545 | 113 |
| steward_norollback | 3 | 18/38, 20/38, 18/38 | 49.1 (40.1-58.2) | 6.8 | 2.4% | 109 | 7/14 | 32 | 9 | 0 | 0/0 | 19.3% | 27.2% | 57438 | 145 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.34x the tokens of b0 per case
- Cost of b2: 1.05x the tokens of b0 per case
- Cost of steward_norollback: 1.03x the tokens of b0 per case

- steward_norollback vs b0, repeat 0: only steward_norollback 6, only b0 3, exact McNemar p = 0.508 (n = 38)
- steward_norollback vs b0, repeat 1: only steward_norollback 3, only b0 2, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b0, repeat 2: only steward_norollback 5, only b0 3, exact McNemar p = 0.727 (n = 38)
- steward_norollback vs b1, repeat 0: only steward_norollback 12, only b1 3, exact McNemar p = 0.035 (n = 38)
- steward_norollback vs b1, repeat 1: only steward_norollback 11, only b1 2, exact McNemar p = 0.022 (n = 38)
- steward_norollback vs b1, repeat 2: only steward_norollback 11, only b1 3, exact McNemar p = 0.057 (n = 38)
- steward_norollback vs b2, repeat 0: only steward_norollback 4, only b2 4, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b2, repeat 1: only steward_norollback 4, only b2 3, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b2, repeat 2: only steward_norollback 3, only b2 5, exact McNemar p = 0.727 (n = 38)

## d1h

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 19/30, 21/30, 18/30 | 64.4 (54.1-73.6) | 7.9 | 16.7% | 0 | 29/54 | 24 | 0 | 0 | 0/0 | 18.9% | 21.1% | 62603 | 167 |
| b1 | 3 | 9/30, 10/30, 10/30 | 32.2 (23.5-42.4) | 5.8 | 21.6% | 0 | 0/54 | 44 | 0 | 0 | 0/0 | 0.0% | 66.7% | 26177 | 60 |
| b2 | 3 | 23/30, 20/30, 19/30 | 68.9 (58.7-77.5) | 8.6 | 16.7% | 0 | 34/54 | 22 | 0 | 0 | 0/0 | 20.0% | 22.2% | 65767 | 165 |
| steward_norollback | 3 | 18/30, 19/30, 19/30 | 62.2 (51.9-71.5) | 8.0 | 16.6% | 0 | 22/46 | 20 | 0 | 0 | 0/0 | 21.1% | 27.8% | 87803 | 152 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.42x the tokens of b0 per case
- Cost of b2: 1.05x the tokens of b0 per case
- Cost of steward_norollback: 1.40x the tokens of b0 per case

- steward_norollback vs b0, repeat 0: only steward_norollback 5, only b0 6, exact McNemar p = 1.000 (n = 30)
- steward_norollback vs b0, repeat 1: only steward_norollback 3, only b0 5, exact McNemar p = 0.727 (n = 30)
- steward_norollback vs b0, repeat 2: only steward_norollback 5, only b0 4, exact McNemar p = 1.000 (n = 30)
- steward_norollback vs b1, repeat 0: only steward_norollback 11, only b1 2, exact McNemar p = 0.022 (n = 30)
- steward_norollback vs b1, repeat 1: only steward_norollback 10, only b1 1, exact McNemar p = 0.012 (n = 30)
- steward_norollback vs b1, repeat 2: only steward_norollback 10, only b1 1, exact McNemar p = 0.012 (n = 30)
- steward_norollback vs b2, repeat 0: only steward_norollback 1, only b2 6, exact McNemar p = 0.125 (n = 30)
- steward_norollback vs b2, repeat 1: only steward_norollback 4, only b2 5, exact McNemar p = 1.000 (n = 30)
- steward_norollback vs b2, repeat 2: only steward_norollback 4, only b2 4, exact McNemar p = 1.000 (n = 30)

## d2

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 4/10, 4/10, 4/10 | 40.0 (24.6-57.7) | 8.8 | 37.7% | 0 | 11/27 | 15 | 38 | 24 | 2/6 | 23.3% | 50.0% | 29010 | 85 |
| b1 | 3 | 6/10, 6/10, 5/10 | 56.7 (39.2-72.6) | 4.8 | 22.8% | 0 | 5/16 | 11 | 24 | 24 | 3/6 | 0.0% | 36.7% | 8695 | 30 |
| b2 | 3 | 5/10, 3/10, 4/10 | 40.0 (24.6-57.7) | 11.0 | 38.0% | 0 | 11/27 | 14 | 15 | 0 | 2/6 | 30.0% | 46.7% | 32223 | 73 |
| steward_norollback | 3 | 8/10, 8/10, 10/10 | 86.7 (70.3-94.7) | 3.8 | 0.0% | 22 | 0/0 | 3 | 0 | 0 | 1/6 | 3.3% | 3.3% | 25364 | 85 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.30x the tokens of b0 per case
- Cost of b2: 1.11x the tokens of b0 per case
- Cost of steward_norollback: 0.87x the tokens of b0 per case

- steward_norollback vs b0, repeat 0: only steward_norollback 5, only b0 1, exact McNemar p = 0.219 (n = 10)
- steward_norollback vs b0, repeat 1: only steward_norollback 5, only b0 1, exact McNemar p = 0.219 (n = 10)
- steward_norollback vs b0, repeat 2: only steward_norollback 6, only b0 0, exact McNemar p = 0.031 (n = 10)
- steward_norollback vs b1, repeat 0: only steward_norollback 4, only b1 2, exact McNemar p = 0.688 (n = 10)
- steward_norollback vs b1, repeat 1: only steward_norollback 4, only b1 2, exact McNemar p = 0.688 (n = 10)
- steward_norollback vs b1, repeat 2: only steward_norollback 5, only b1 0, exact McNemar p = 0.062 (n = 10)
- steward_norollback vs b2, repeat 0: only steward_norollback 4, only b2 1, exact McNemar p = 0.375 (n = 10)
- steward_norollback vs b2, repeat 1: only steward_norollback 6, only b2 1, exact McNemar p = 0.125 (n = 10)
- steward_norollback vs b2, repeat 2: only steward_norollback 6, only b2 0, exact McNemar p = 0.031 (n = 10)

## d3

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 8/38, 6/38, 8/38 | 19.3 (13.1-27.5) | 12.7 | 32.9% | 0 | 15/87 | 49 | 69 | 10 | 55/114 | 42.1% | 44.7% | 66086 | 194 |
| b1 | 3 | 4/38, 6/38, 5/38 | 13.2 (8.1-20.6) | 8.0 | 28.3% | 0 | 9/84 | 75 | 31 | 15 | 54/114 | 0.9% | 83.3% | 25247 | 62 |
| b2 | 3 | 9/38, 11/38, 4/38 | 21.1 (14.6-29.4) | 14.5 | 30.4% | 0 | 13/84 | 43 | 79 | 15 | 57/114 | 49.1% | 50.9% | 71287 | 151 |
| steward_norollback | 3 | 13/38, 11/38, 13/38 | 32.5 (24.6-41.5) | 6.9 | 1.4% | 141 | 6/9 | 32 | 26 | 0 | 37/114 | 10.5% | 14.0% | 64003 | 168 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.38x the tokens of b0 per case
- Cost of b2: 1.08x the tokens of b0 per case
- Cost of steward_norollback: 0.97x the tokens of b0 per case

- steward_norollback vs b0, repeat 0: only steward_norollback 8, only b0 3, exact McNemar p = 0.227 (n = 38)
- steward_norollback vs b0, repeat 1: only steward_norollback 7, only b0 2, exact McNemar p = 0.180 (n = 38)
- steward_norollback vs b0, repeat 2: only steward_norollback 8, only b0 3, exact McNemar p = 0.227 (n = 38)
- steward_norollback vs b1, repeat 0: only steward_norollback 12, only b1 3, exact McNemar p = 0.035 (n = 38)
- steward_norollback vs b1, repeat 1: only steward_norollback 8, only b1 3, exact McNemar p = 0.227 (n = 38)
- steward_norollback vs b1, repeat 2: only steward_norollback 11, only b1 3, exact McNemar p = 0.057 (n = 38)
- steward_norollback vs b2, repeat 0: only steward_norollback 7, only b2 3, exact McNemar p = 0.344 (n = 38)
- steward_norollback vs b2, repeat 1: only steward_norollback 5, only b2 5, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b2, repeat 2: only steward_norollback 12, only b2 3, exact McNemar p = 0.035 (n = 38)

## d4

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 5/15, 4/15, 3/15 | 26.7 (16.0-41.0) | 4.6 | 21.7% | 0 | 6/22 | 0 | 18 | 64 | 12/24 | 13.3% | 48.9% | 18978 | 66 |
| b1 | 3 | 4/15, 4/15, 4/15 | 26.7 (16.0-41.0) | 7.3 | 25.3% | 0 | 3/29 | 0 | 74 | 90 | 20/24 | 0.0% | 60.0% | 8788 | 39 |
| b2 | 3 | 3/15, 5/15, 4/15 | 26.7 (16.0-41.0) | 4.6 | 25.0% | 0 | 6/21 | 0 | 16 | 65 | 12/24 | 11.1% | 53.3% | 19570 | 57 |
| steward_norollback | 3 | 10/15, 9/15, 8/15 | 60.0 (45.5-73.0) | 4.6 | 1.0% | 37 | 2/2 | 0 | 9 | 9 | 12/24 | 31.1% | 35.6% | 27922 | 108 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.46x the tokens of b0 per case
- Cost of b2: 1.03x the tokens of b0 per case
- Cost of steward_norollback: 1.47x the tokens of b0 per case

Acceptance test (10 requests; target 8 completed):

- b0: 2/10, 1/10, 0/10 per repeat
- b1: 2/10, 2/10, 2/10 per repeat
- b2: 0/10, 2/10, 1/10 per repeat
- steward_norollback: 7/10, 6/10, 6/10 per repeat

- steward_norollback vs b0, repeat 0: only steward_norollback 6, only b0 1, exact McNemar p = 0.125 (n = 15)
- steward_norollback vs b0, repeat 1: only steward_norollback 7, only b0 2, exact McNemar p = 0.180 (n = 15)
- steward_norollback vs b0, repeat 2: only steward_norollback 6, only b0 1, exact McNemar p = 0.125 (n = 15)
- steward_norollback vs b1, repeat 0: only steward_norollback 6, only b1 0, exact McNemar p = 0.031 (n = 15)
- steward_norollback vs b1, repeat 1: only steward_norollback 5, only b1 0, exact McNemar p = 0.062 (n = 15)
- steward_norollback vs b1, repeat 2: only steward_norollback 5, only b1 1, exact McNemar p = 0.219 (n = 15)
- steward_norollback vs b2, repeat 0: only steward_norollback 8, only b2 1, exact McNemar p = 0.039 (n = 15)
- steward_norollback vs b2, repeat 1: only steward_norollback 6, only b2 2, exact McNemar p = 0.289 (n = 15)
- steward_norollback vs b2, repeat 2: only steward_norollback 5, only b2 1, exact McNemar p = 0.219 (n = 15)

## d5

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b0 | 3 | 12/38, 13/38, 11/38 | 31.6 (23.8-40.6) | 16.6 | 30.4% | 0 | 26/93 | 60 | 65 | 17 | 73/114 | 30.7% | 32.5% | 71942 | 238 |
| b1 | 3 | 9/38, 10/38, 10/38 | 25.4 (18.3-34.1) | 10.0 | 34.6% | 0 | 24/98 | 69 | 12 | 3 | 47/114 | 0.0% | 74.6% | 24535 | 68 |
| b2 | 3 | 11/38, 15/38, 10/38 | 31.6 (23.8-40.6) | 19.2 | 28.2% | 0 | 28/95 | 58 | 83 | 15 | 72/114 | 30.7% | 33.3% | 79435 | 215 |
| steward_norollback | 3 | 9/38, 11/38, 11/38 | 27.2 (19.9-36.0) | 12.4 | 10.0% | 287 | 7/43 | 46 | 34 | 0 | 74/114 | 17.5% | 27.2% | 91680 | 200 |

- Cost of b0: 1.00x the tokens of b0 per case
- Cost of b1: 0.34x the tokens of b0 per case
- Cost of b2: 1.10x the tokens of b0 per case
- Cost of steward_norollback: 1.27x the tokens of b0 per case

- steward_norollback vs b0, repeat 0: only steward_norollback 5, only b0 8, exact McNemar p = 0.581 (n = 38)
- steward_norollback vs b0, repeat 1: only steward_norollback 5, only b0 7, exact McNemar p = 0.774 (n = 38)
- steward_norollback vs b0, repeat 2: only steward_norollback 7, only b0 7, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b1, repeat 0: only steward_norollback 6, only b1 6, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b1, repeat 1: only steward_norollback 8, only b1 7, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b1, repeat 2: only steward_norollback 7, only b1 6, exact McNemar p = 1.000 (n = 38)
- steward_norollback vs b2, repeat 0: only steward_norollback 4, only b2 6, exact McNemar p = 0.754 (n = 38)
- steward_norollback vs b2, repeat 1: only steward_norollback 4, only b2 8, exact McNemar p = 0.388 (n = 38)
- steward_norollback vs b2, repeat 2: only steward_norollback 7, only b2 6, exact McNemar p = 1.000 (n = 38)

## march

| System | Runs | Pass (per repeat) | Pooled % (Wilson 95%) | Tool calls/case | Tool error rate | Blocked | Recovery | State mismatch | Residue | Unintended | Guessed/asked-for turns | Silent wrong success | Undisclosed failure | Tokens/case | Wall s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| steward_norollback | 20 | 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1, 1/1 | 100.0 (83.9-100.0) | 5.0 | 0.0% | 0 | 0/0 | 0 | 0 | 0 | 0/0 | 0.0% | 0.0% | 14853 | 54 |


