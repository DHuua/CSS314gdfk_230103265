# Variant B Results - Granularity and IPC Contention

Hardware: Intel Core i5-13420H (4 P-cores with SMT + 4 E-cores, 8 physical / 12 logical), Windows 11, Python 3.13. Single run per data point.

| Configuration | T1 (s) | T2 (s) | T4 (s) | T8 (s) | S8 | e(2) | e(8) | Verdict |
|---|---|---|---|---|---|---|---|---|
| A: Micro (chunksize=1) | 83.041 | 86.008 | 86.402 | 84.691 | 0.98 | 1.071 | 1.023 | No speedup, e ~ 1: master dispatch serialization (pickling and task scheduling dominate) |
| A: Coarse (chunksize=10000) | 11.544 | 6.298 | 3.506 | 2.488 | 4.64 | 0.091 | 0.103 | Nearly flat small e: healthy strong scaling once dispatch is amortized |
| B: Queue Choke | 4.250 | 8.596 | 8.312 | 23.822 | 0.18 | 3.046 | 6.264 | Negative scaling (T8 > T1, S8 < 0.5) from IPC pipe and lock contention; e is not monotonic (e(4) < e(2)) because the single consumer in the master is itself the bottleneck and 4 of 8 cores are E-cores |
| C: Buffered Batch | 3.272 | 1.748 | 1.072 | 0.848 | 3.86 | 0.068 | 0.153 | Batching removes the queue bottleneck (47.1 M items/s at P=8 versus ~0.1 M items/s in B), but S8 = 3.86 and e(8) = 0.153 miss the targets (S8 > 5, e <= 0.05): process start-up cost and E-cores limit scaling at P=8 |

Conclusion: fine-grained tasks and per-item IPC are the dominant overheads; coarse chunks and local batch aggregation amortize them, and the remaining loss at P=8 reflects hybrid cores and process start-up rather than synchronization.
