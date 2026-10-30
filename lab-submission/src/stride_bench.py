import sys, time, statistics
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
STRIDES = [1, 2, 4, 8, 16, 32, 64, 128]
WARMUP, RUNS = 5, 5

def main():
    data = np.ones(16_777_216, dtype=np.float64)   # ~134 MB
    n = data.size
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    rows = ["stride\telements_touched\tmedian_time_ns\tlatency_ns_per_element"]

    for s in STRIDES:
        view = data[::s]
        touched = view.size
        for _ in range(WARMUP):
            view.sum()
        times = []
        for _ in range(RUNS):
            t0 = time.perf_counter_ns()
            total = view.sum()
            times.append(time.perf_counter_ns() - t0)
        assert total == touched         
        med = statistics.median(times)
        rows.append(f"{s}\t{touched}\t{med:.0f}\t{med / touched:.4f}")
        print(rows[-1])

    (out / "stride_results.tsv").write_text("\n".join(rows) + "\n")

if __name__ == "__main__":
    main()