import sys, json, time, statistics
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from salt import get_student_params

ROOT = Path(__file__).resolve().parent.parent
STUDENT_ID = "230103265"
RUNS = 3

@njit
def ijk(A, B, C, N, M):
    for i in range(M):
        for j in range(M):
            acc = 0.0
            for k in range(M):
                acc += A[i * N + k] * B[k * N + j]    
            C[i * N + j] = acc

@njit
def ikj(A, B, C, N, M):
    for i in range(M):
        for k in range(M):
            a = A[i * N + k]                            
            for j in range(M):
                C[i * N + j] += a * B[k * N + j]        

def timed(fn, A, B, N, M):
    times, C = [], None
    for _ in range(RUNS):
        C = np.zeros(N * N)
        t0 = time.perf_counter_ns()
        fn(A, B, C, N, M)
        times.append(time.perf_counter_ns() - t0)
    return statistics.median(times), C

def main():
    p = get_student_params(STUDENT_ID)
    N, M = p["N"], p["N"] // 2
    rng = np.random.default_rng(p["seed"])
    A = rng.random(N * N)
    B = rng.random(N * N)

    ijk(A, B, np.zeros(N * N), N, 8)
    ikj(A, B, np.zeros(N * N), N, 8)

    t_naive, C1 = timed(ijk, A, B, N, M)
    t_inter, C2 = timed(ikj, A, B, N, M)
    max_diff = float(np.max(np.abs(C1 - C2)))

    res = {"N": N, "M": M, "runs": RUNS,
           "t_naive_ns": t_naive, "t_interchanged_ns": t_inter,
           "speedup": t_naive / t_inter, "max_abs_diff": max_diff,
           "naive_time_s": t_naive / 1e9, "interchanged_time_s": t_inter / 1e9,}
    (ROOT / "results" / "loop_interchange.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    assert max_diff < 1e-12

if __name__ == "__main__":
    main()