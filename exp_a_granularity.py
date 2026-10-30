import time
from multiprocessing import Pool

TOTAL = 1_000_000


def collatz_steps(n):
    steps = 0
    while n > 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


def run_granularity(workers, total_items=TOTAL, chunk_size=1):
    numbers = range(1, total_items + 1)
    t0 = time.perf_counter()
    with Pool(processes=workers) as pool:
        results = pool.map(collatz_steps, numbers, chunksize=chunk_size)
    return time.perf_counter() - t0, sum(results)


if __name__ == "__main__":
    ref = None
    for chunk in (1, 10_000):
        T = {}
        for p in (1, 2, 4, 8):
            T[p], checksum = run_granularity(p, TOTAL, chunk)
            ref = ref or checksum
            assert checksum == ref, "checksum mismatch"
            print(f"chunk={chunk} P={p} T={T[p]:.3f}s", flush=True)
        t1 = T[1]
        print(f"--- chunksize={chunk} ---")
        for p in (2, 4, 8):
            sp = t1 / T[p]
            e = ((p * T[p] / t1) - 1.0) / (p - 1.0)
            print(f"P={p} | T={T[p]:.3f}s | S={sp:.2f}x | E={sp / p * 100:.1f}% | e={e:.3f}")
