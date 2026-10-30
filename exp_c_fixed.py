import time, statistics
from multiprocessing import Pool

REPS = 3


def private_worker(iterations):
    local_sum = 0                                 # private state, no locks
    for _ in range(iterations):
        local_sum += 1
    return local_sum


def run_privatized(p, total_increments=80_000_000):
    tasks = [total_increments // p] * p
    t0 = time.perf_counter()
    with Pool(processes=p) as pool:
        results = pool.map(private_worker, tasks)
    total = sum(results)                          # synchronize exactly once
    t1 = time.perf_counter()
    assert total == total_increments
    return t1 - t0


if __name__ == "__main__":
    T = {p: statistics.median(run_privatized(p) for _ in range(REPS)) for p in (1, 2, 4)}
    t1 = T[1]
    print(f"P=1 | Runtime={t1:.3f}s")
    for p in (2, 4):
        sp = t1 / T[p]
        e = ((p * T[p] / t1) - 1.0) / (p - 1.0)
        print(f"P={p} | Runtime={T[p]:.3f}s | Speedup={sp:.2f}x | "
              f"Efficiency={sp / p * 100:.1f}% | KarpFlatt e={e:.3f}")
