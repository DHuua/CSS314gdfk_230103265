import sys, json, time, math, statistics
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
import multiprocessing as mp
from multiprocessing.shared_memory import SharedMemory
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from salt import get_student_params

ROOT = Path(__file__).resolve().parent.parent
STUDENT_ID = "230103265"
PROCS = [1, 2, 4, 8]
ITERS = 200
REPS = 3

PEAK_BW_GBS = 83.2             
PEAK_GFLOPS_PER_CORE = 16 * 4.6   
PEAK_CORES = 4               
FLOPS_PER_POINT = 4          
BYTES_PER_POINT = 16        


@njit(cache=True)
def sweep(src, dst, N, r0, r1):
    for i in range(r0, r1):
        for j in range(1, N - 1):
            dst[i * N + j] = 0.25 * (src[(i - 1) * N + j] + src[(i + 1) * N + j]
                                     + src[i * N + j - 1] + src[i * N + j + 1])


def worker(name0, name1, N, r0, r1, iters, start_barrier, step_barrier):
    shm = [SharedMemory(name=name0), SharedMemory(name=name1)]
    g = [np.ndarray(N * N, dtype=np.float64, buffer=s.buf) for s in shm]
    if r1 > r0:
        sweep(g[0], g[1], N, r0, r0 + 1)     
    start_barrier.wait()
    for it in range(iters):
        sweep(g[it & 1], g[(it + 1) & 1], N, r0, r1)
        step_barrier.wait()
    del g
    for s in shm:
        s.close()


def run(N, P, iters, seed):
    nbytes = N * N * 8
    shm = [SharedMemory(create=True, size=nbytes), SharedMemory(create=True, size=nbytes)]
    g = [np.ndarray(N * N, dtype=np.float64, buffer=s.buf) for s in shm]
    init = np.random.default_rng(seed).random(N * N)
    g[0][:] = init
    g[1][:] = init                            
    bounds = np.linspace(1, N - 1, P + 1).astype(int)
    start_barrier, step_barrier = mp.Barrier(P + 1), mp.Barrier(P)
    procs = [mp.Process(target=worker, args=(shm[0].name, shm[1].name, N,
                                             int(bounds[p]), int(bounds[p + 1]),
                                             iters, start_barrier, step_barrier))
             for p in range(P)]
    for pr in procs:
        pr.start()
    start_barrier.wait()
    t0 = time.perf_counter_ns()
    for pr in procs:
        pr.join()
    elapsed = time.perf_counter_ns() - t0
    checksum = float(g[iters & 1].sum())
    del g
    for s in shm:
        s.close()
        s.unlink()
    return elapsed / 1e9, checksum


def median_run(N, P, iters, seed):
    ts, cs = [], None
    for _ in range(REPS):
        t, cs = run(N, P, iters, seed)
        ts.append(t)
    return statistics.median(ts), cs


def main():
    prm = get_student_params(STUDENT_ID)
    N, seed = prm["N"], prm["seed"]
    rows = ["mode\tP\tN_P\titers\tmedian_time_s\tspeedup\tefficiency_pct\t"
            "serial_fraction_s\tscaled_speedup_literal\tscaled_speedup_throughput\t"
            "checksum\tref_checksum\tmatch"]

    # ---- Strong scaling ----
    ref_sum, t1, s_vals = None, None, []
    for P in PROCS:
        t, cs = median_run(N, P, ITERS, seed)
        if P == 1:
            t1, ref_sum = t, cs
            sp = eff = s = ""
        else:
            S = t1 / t
            s_P = (1 / S - 1 / P) / (1 - 1 / P)
            s_vals.append(s_P)
            sp, eff, s = f"{S:.4f}", f"{S / P * 100:.1f}", f"{s_P:.4f}"
        ok = math.isclose(cs, ref_sum, rel_tol=1e-12)
        rows.append(f"strong\t{P}\t{N}\t{ITERS}\t{t:.4f}\t{sp}\t{eff}\t{s}\t\t\t"
                    f"{cs:.10f}\t{ref_sum:.10f}\t{ok}")
        print(rows[-1])
        assert ok, f"strong P={P}: checksum mismatch"

    s_fit = statistics.median(s_vals)
    s_max = 1 / s_fit if s_fit > 0 else float("inf")

    work1 = N * N * ITERS
    tw1 = None
    for P in PROCS:
        N_P = math.ceil(N * math.sqrt(P))
        t, cs = median_run(N_P, P, ITERS, seed)
        _, ref = run(N_P, 1, ITERS, seed)         
        workP = N_P * N_P * ITERS
        if P == 1:
            tw1 = t
        lit = P * work1 * tw1 / (workP * t)       
        thr = (workP / t) / (work1 / tw1)         
        ok = math.isclose(cs, ref, rel_tol=1e-12)
        rows.append(f"weak\t{P}\t{N_P}\t{ITERS}\t{t:.4f}\t\t\t\t{lit:.4f}\t{thr:.4f}\t"
                    f"{cs:.10f}\t{ref:.10f}\t{ok}")
        print(rows[-1])
        assert ok, f"weak P={P}: checksum mismatch"

    (ROOT / "results" / "scaling_metrics.tsv").write_text("\n".join(rows) + "\n")

    ai = FLOPS_PER_POINT / BYTES_PER_POINT
    peak_gflops = PEAK_GFLOPS_PER_CORE * PEAK_CORES
    ridge = peak_gflops / PEAK_BW_GBS
    grid_mb = N * N * 8 / 2**20
    l3_mb = json.loads((ROOT / "results" / "host_profile.json").read_text()
                       )["caches"]["L3"]["size_bytes"] / 2**20
    achieved_gflops = FLOPS_PER_POINT * (N - 2) ** 2 * ITERS / t1 / 1e9
    summary = {
        "arithmetic_intensity": ai,
        "kernel": "5-point Jacobi stencil, double precision",
        "flops_per_point": FLOPS_PER_POINT,
        "dram_bytes_per_point": BYTES_PER_POINT,
        "arithmetic_intensity_flop_per_byte": ai,
        "peak_bandwidth_gbs_assumed": PEAK_BW_GBS,
        "peak_gflops_assumed": peak_gflops,
        "ridge_point_flop_per_byte": ridge,
        "working_set_mb_two_grids": 2 * grid_mb,
        "l3_mb": l3_mb,
        "working_set_exceeds_l3": 2 * grid_mb > l3_mb,
        "bandwidth_roof_gflops": ai * PEAK_BW_GBS,
        "achieved_gflops_P1": achieved_gflops,
        "regime": "memory-bandwidth bound" if ai < ridge else "compute bound",
        "scaling_fit": {"serial_fraction_s_median": s_fit, "S_max": s_max},
    }
    (ROOT / "results" / "roofline_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    mp.freeze_support()
    main()