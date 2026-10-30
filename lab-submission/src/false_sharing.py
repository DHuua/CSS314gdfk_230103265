import sys, time, ctypes, statistics
sys.dont_write_bytecode = True
from pathlib import Path
import multiprocessing as mp
from multiprocessing.sharedctypes import RawArray

ROOT = Path(__file__).resolve().parent.parent
K = 5_000_000
PROCS = [1, 2, 4, 8]
REPS = 3


def worker_shared(arr, idx, k, barrier):
    barrier.wait()
    for _ in range(k):
        arr[idx] += 1


def worker_privatized(arr, idx, k, barrier):
    barrier.wait()
    local = 0
    for _ in range(k):
        local += 1
    arr[idx] = local


def run_once(variant, P, arr, off):
    for i in range(len(arr)):
        arr[i] = 0
    stride = 1 if variant == "unpadded" else 8   # 8 x int64 = 64 bytes
    target = worker_privatized if variant == "privatized" else worker_shared
    barrier = mp.Barrier(P + 1)
    procs = [mp.Process(target=target, args=(arr, off + p * stride, K, barrier))
             for p in range(P)]
    for pr in procs:
        pr.start()
    barrier.wait()
    t0 = time.perf_counter_ns()
    for pr in procs:
        pr.join()
    elapsed = time.perf_counter_ns() - t0
    total = sum(arr[off + p * stride] for p in range(P))
    return elapsed, total


def karp_flatt(S, P):
    return (1 / S - 1 / P) / (1 - 1 / P)


def main():
    arr = RawArray(ctypes.c_int64, 80)
    off = ((-ctypes.addressof(arr)) % 64) // 8
    variants = ("unpadded", "padded", "privatized")
    T = {}
    for v in variants:
        for P in PROCS:
            times, total = [], None
            for _ in range(REPS):
                t, total = run_once(v, P, arr, off)
                times.append(t)
            assert total == P * K, f"{v} P={P}: {total} != {P * K}"
            T[v, P] = statistics.median(times) / 1e9

    header = ["P", "K", "expected_count"]
    for v in variants:
        header += [f"time_s_{v}", f"e_{v}", f"e_literal_{v}"]
    rows = ["\t".join(header)]
    for P in PROCS:
        cells = [str(P), str(K), str(P * K)]
        for v in variants:
            t, t1 = T[v, P], T[v, 1]
            if P == 1:
                cells += [f"{t:.4f}", "NA", "NA"]
            else:
                e_scaled = karp_flatt(P * t1 / t, P)   
                e_literal = karp_flatt(t1 / t, P)     
                cells += [f"{t:.4f}", f"{e_scaled:.4f}", f"{e_literal:.4f}"]
        rows.append("\t".join(cells))
        print(rows[-1])
    (ROOT / "results" / "false_sharing_karp_flatt.tsv").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    mp.freeze_support()
    main()