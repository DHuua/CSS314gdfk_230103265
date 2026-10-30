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

    rows = ["variant\tP\tK\tmedian_time_s\ttotal_count\texpected_count\t"
            "S_scaled\te_scaled\tS_literal\te_literal"]
    for variant in ("unpadded", "padded", "privatized"):
        t1 = None
        for P in PROCS:
            times, total = [], None
            for _ in range(REPS):
                t, total = run_once(variant, P, arr, off)
                times.append(t)
            med = statistics.median(times)
            assert total == P * K, f"{variant} P={P}: {total} != {P * K}"
            if P == 1:
                t1 = med
                s_sc = e_sc = s_li = e_li = ""
            else:
                S_sc = P * t1 / med               
                S_li = t1 / med                     
                s_sc, e_sc = f"{S_sc:.4f}", f"{karp_flatt(S_sc, P):.4f}"
                s_li, e_li = f"{S_li:.4f}", f"{karp_flatt(S_li, P):.4f}"
            rows.append(f"{variant}\t{P}\t{K}\t{med / 1e9:.4f}\t{total}\t{P * K}\t"
                        f"{s_sc}\t{e_sc}\t{s_li}\t{e_li}")
            print(rows[-1])

    (ROOT / "results" / "false_sharing_karp_flatt.tsv").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    mp.freeze_support()
    main()