import argparse, json, os, platform, subprocess, sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from salt import get_student_params


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def ps(query):
    return sh(f'powershell -NoProfile -Command "{query}"')


def parse_size(s):
    s = s.strip().upper()
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3}
    return int(s[:-1]) * mult[s[-1]] if s[-1] in mult else int(s)


#  Linux 
def linux_info():
    info = {}
    cpuinfo = Path("/proc/cpuinfo").read_text()

    def field(name):
        for line in cpuinfo.splitlines():
            if line.startswith(name):
                return line.split(":", 1)[1].strip()

    info["model_name"] = field("model name")
    info["microarch_hint"] = {"family": field("cpu family"),
                              "model": field("model"),
                              "stepping": field("stepping")}
    mhz = field("cpu MHz")
    info["base_freq_mhz"] = float(mhz) if mhz else None
    out = sh("lscpu -p=CORE,SOCKET | grep -v '^#' | sort -u | wc -l")
    info["physical_cores"] = int(out) if out else None
    caches = {}
    base = Path("/sys/devices/system/cpu/cpu0/cache")
    for idx in sorted(base.glob("index*")):
        level = (idx / "level").read_text().strip()
        ctype = (idx / "type").read_text().strip()
        size = parse_size((idx / "size").read_text())
        line = int((idx / "coherency_line_size").read_text())
        key = ("L1d" if ctype == "Data" else "L1i") if level == "1" else f"L{level}"
        caches[key] = {"size_bytes": size, "line_bytes": line, "type": ctype}
    info["caches"] = caches
    return info


#  macOS 
def macos_info():
    g = lambda k: sh(f"sysctl -n {k}")
    toint = lambda v: int(v) if v and v.isdigit() else None
    line = toint(g("hw.cachelinesize"))
    return {
        "model_name": g("machdep.cpu.brand_string"),
        "microarch_hint": None,
        "base_freq_mhz": (toint(g("hw.cpufrequency")) or 0) / 1e6 or None,
        "physical_cores": toint(g("hw.physicalcpu")),
        "caches": {
            "L1d": {"size_bytes": toint(g("hw.l1dcachesize")), "line_bytes": line},
            "L2": {"size_bytes": toint(g("hw.l2cachesize")), "line_bytes": line},
            "L3": {"size_bytes": toint(g("hw.l3cachesize")), "line_bytes": line},
        },
    }


#  Windows 
def windows_caches_and_cores():
    import ctypes
    from ctypes import wintypes

    class CACHE_DESCRIPTOR(ctypes.Structure):
        _fields_ = [("Level", ctypes.c_ubyte), ("Associativity", ctypes.c_ubyte),
                    ("LineSize", ctypes.c_ushort), ("Size", ctypes.c_uint),
                    ("Type", ctypes.c_uint)]

    class _U(ctypes.Union):
        _fields_ = [("Cache", CACHE_DESCRIPTOR),
                    ("Reserved", ctypes.c_ulonglong * 2)]

    class SLPI(ctypes.Structure):
        _fields_ = [("ProcessorMask", ctypes.c_size_t),
                    ("Relationship", ctypes.c_uint), ("u", _U)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    length = wintypes.DWORD(0)
    k32.GetLogicalProcessorInformation(None, ctypes.byref(length))
    buf = ctypes.create_string_buffer(length.value)
    if not k32.GetLogicalProcessorInformation(buf, ctypes.byref(length)):
        raise OSError("GetLogicalProcessorInformation failed")
    n = length.value // ctypes.sizeof(SLPI)
    arr = ctypes.cast(buf, ctypes.POINTER(SLPI))

    cores, caches = 0, {}
    for i in range(n):
        r = arr[i]
        if r.Relationship == 0:            # RelationProcessorCore
            cores += 1
        elif r.Relationship == 2:          # RelationCache
            c = r.u.Cache
            if c.Level == 1 and c.Type == 1:   # L1 instruction: пропуск
                continue
            key = "L1d" if c.Level == 1 else f"L{c.Level}"
            if key not in caches:
                caches[key] = {"size_bytes": c.Size, "line_bytes": c.LineSize}
    return cores, caches


def windows_info():
    info = {
        "model_name": ps("(Get-CimInstance Win32_Processor | Select -First 1).Name"),
        "microarch_hint": platform.processor(),
        "physical_cores": None,
        "caches": {},
    }
    mhz = ps("(Get-CimInstance Win32_Processor | Select -First 1).MaxClockSpeed")
    info["base_freq_mhz"] = float(mhz) if mhz and mhz.isdigit() else None
    try:
        info["physical_cores"], info["caches"] = windows_caches_and_cores()
    except Exception as e:
        info["cache_error"] = str(e)
    # запасной путь для L2/L3 (значения в КБ)
    for key, prop in (("L2", "L2CacheSize"), ("L3", "L3CacheSize")):
        if key not in info["caches"]:
            v = ps(f"(Get-CimInstance Win32_Processor | Select -First 1).{prop}")
            if v and v.isdigit():
                info["caches"][key] = {"size_bytes": int(v) * 1024,
                                       "line_bytes": None}
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", required=True)
    args = ap.parse_args()

    system = platform.system()
    info = {"Linux": linux_info, "Darwin": macos_info,
            "Windows": windows_info}.get(system, lambda: {})()

    logical = os.cpu_count()
    physical = info.get("physical_cores")
    if physical is None:
        try:
            import psutil
            physical = psutil.cpu_count(logical=False)
        except ImportError:
            pass
    info["physical_cores"] = physical
    info["logical_threads"] = logical
    info["smt_enabled"] = bool(physical and logical and logical > physical)
    info["os"] = {"system": system, "kernel": platform.release(),
                  "version": platform.version(), "machine": platform.machine()}
    info["python"] = {"implementation": platform.python_implementation(),
                      "version": platform.python_version()}
    info["cpu_model"] = info.get("model_name")
    info["cache_line_bytes"] = next((c["line_bytes"] for c in info.get("caches", {}).values()
                                 if c.get("line_bytes")), 64)

    out = Path(__file__).resolve().parent.parent / "results"
    out.mkdir(exist_ok=True)
    (out / "host_profile.json").write_text(json.dumps(info, indent=2))
    (out / "salted_params.json").write_text(
        json.dumps(get_student_params(args.student_id), indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()