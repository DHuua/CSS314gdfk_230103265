import time
from multiprocessing import Process, Queue


def queue_worker(out_queue, items_per_worker):
    for i in range(items_per_worker):
        out_queue.put(i % 7)          


def run_queue_benchmark(p, total_items=400_000):
    q = Queue()
    items_per_worker = total_items // p
    workers = [Process(target=queue_worker, args=(q, items_per_worker)) for _ in range(p)]
    t0 = time.perf_counter()
    for w in workers:
        w.start()
    collected = 0
    while collected < total_items:
        q.get()
        collected += 1
    for w in workers:
        w.join()
    return time.perf_counter() - t0


if __name__ == "__main__":
    runtimes = {}
    for p in (1, 2, 4, 8):
        runtimes[p] = run_queue_benchmark(p)
        print(f"P={p} T={runtimes[p]:.3f}s", flush=True)
    t1 = runtimes[1]
    print("\n--- Queue Contention Karp-Flatt Analysis ---")
    for p in (2, 4, 8):
        tp = runtimes[p]
        sp = t1 / tp
        e = ((p * tp / t1) - 1.0) / (p - 1.0)
        print(f"P={p:2d} | Time={tp:6.3f}s | Speedup={sp:5.2f}x | Karp-Flatt e={e:6.3f}")
