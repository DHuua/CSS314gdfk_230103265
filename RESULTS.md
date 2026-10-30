# Karp-Flatt Practice Lab - Results

Hardware: Intel Core i5-13420H (4 P-cores with SMT + 4 E-cores, 8 physical / 12 logical), Windows 11, Python 3.13. Each runtime is the median of 3 runs.

| Experiment | Mode | T1 (s) | T2 (s) | T4 (s) | e(2) | e(4) | Architectural Diagnosis |
|---|---|---|---|---|---|---|---|
| A: Serial Tail | 0.40 s sequential sleep | 3.539 | 1.988 | 1.315 | 0.124 | 0.162 | Nearly constant e (~ serial share 0.113): fixed Amdahl serialization; the small rise at P=4 is process start-up cost on Windows |
| B: Lock Contention | Shared counter + mutex per increment | 2.864 | 11.737 | 14.031 | 7.197 | 6.199 | Negative speedup (0.24x, 0.20x) and e far above 1.5: lock thrashing. e saturates already at P=2, so e(4) is not larger than e(2) |
| C: Privatized State | Local counter, one reduction | 1.830 | 0.935 | 0.544 | 0.022 | 0.063 | e collapses toward 0 (E4 = 84%): linear scalability restored |

Conclusion: constant e identifies a fixed serial path (A); a huge e with Sp < 1 identifies contention over a shared lock (B); privatizing state before synchronizing removes the contention (C).
