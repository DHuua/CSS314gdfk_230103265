import time
from multiprocessing import Process, Queue

TOTAL = 40_000_000


def expected_sum(n):
    return (n // 7) * 21 + sum(range(n % 7))     # sum of i % 7 for i in range(n)


def buffered_worker(out_queue, items_per_worker, batch_size=10_000):
    buffer = []
    for i in range(items_per_worker):
        buffer.append(i % 7)
        if len(buffer) >= batch_size:
            out_queue.put(sum(buffer))           # one flush per 10,000 items
            buffer.clear()
    if buffer:
        out_queue.put(sum(buffer))
    out_queue.put(None)                          # end-of-work sentinel


def run_buffered(p, total_items=TOTAL):
    q = Queue()
    items_per_worker = total_items // p
    workers = [Process(target=buffered_worker, args=(q, items_per_worker)) for _ in range(p)]
    t0 = time.perf_counter()
    for w in workers:
        w.start()
    total_sum, active = 0, p
    while active > 0:
        val = q.get()
        if val is None:
            active -= 1
        else:
            total_sum += val
    for w in workers:
        w.join()
    elapsed = time.perf_counter() - t0
    assert total_sum == p * expected_sum(items_per_worker), "wrong total"
    return elapsed


if __name__ == "__main__":
    T = {}
    for p in (1, 2, 4, 8):
        T[p] = run_buffered(p)
        print(f"P={p} T={T[p]:.3f}s | throughput={TOTAL / T[p] / 1e6:.1f} M items/s", flush=True)
    t1 = T[1]
    for p in (2, 4, 8):
        sp = t1 / T[p]
        e = ((p * T[p] / t1) - 1.0) / (p - 1.0)
        print(f"P={p} | S={sp:.2f}x | E={sp / p * 100:.1f}% | e={e:.3f}")
