import time, math, statistics
from multiprocessing import Pool

SERIAL_SLEEP = 0.40
REPS = 3


def heavy_math(n):
    return sum(math.sin(i) * math.cos(i) for i in range(1, n))


def calibrate(target_parallel_s=2.9, total_chunks=16):
    # Pick a chunk size so that the parallel work takes ~2.9 s at P=1,
    # which makes the 0.40 s sleep about 12% of T1.
    probe = 300_000
    t0 = time.perf_counter()
    heavy_math(probe)
    per_item = (time.perf_counter() - t0) / probe
    return int(target_parallel_s / total_chunks / per_item)


def run_experiment(workers, total_chunks, chunk_size):
    t0 = time.perf_counter()
    time.sleep(SERIAL_SLEEP)                      # intentional sequential bottleneck
    with Pool(processes=workers) as pool:
        pool.map(heavy_math, [chunk_size] * total_chunks)
    return time.perf_counter() - t0


if __name__ == "__main__":
    total_chunks = 16
    chunk_size = calibrate()
    print(f"chunk_size = {chunk_size}")
    T = {}
    for p in (1, 2, 4):
        T[p] = statistics.median(run_experiment(p, total_chunks, chunk_size)
                                 for _ in range(REPS))
    t1 = T[1]
    print(f"P=1 | T={t1:.3f}s | serial share = {SERIAL_SLEEP / t1:.3f}")
    e = {}
    for p in (2, 4):
        sp = t1 / T[p]
        e[p] = ((p * T[p] / t1) - 1.0) / (p - 1.0)
        print(f"P={p} | T={T[p]:.3f}s | Speedup={sp:.2f}x | KarpFlatt e={e[p]:.3f}")
    print(f"e(4)/e(2) = {e[4] / e[2]:.2f}  (target 0.80-1.25)")
