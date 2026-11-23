"""PC istatistikleri: CPU, RAM, ağ (psutil) + NVIDIA GPU (NVML) + CPU sıcaklığı (LibreHardwareMonitor)."""
import json
import re
import time
import urllib.request

import psutil

try:
    import pynvml
except ImportError:  # pragma: no cover
    pynvml = None

LHM_URL = "http://127.0.0.1:8085/data.json"
CPU_TEMP_NAMES = ("core (tctl/tdie)", "tctl/tdie", "tctl", "tdie", "cpu package", "package")


class Stats:
    def __init__(self):
        psutil.cpu_percent(None)
        self._net = (time.monotonic(), psutil.net_io_counters())
        self._gpu = None
        self.gpu_name = None
        if pynvml:
            try:
                pynvml.nvmlInit()
                self._gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(self._gpu)
                self.gpu_name = name.decode() if isinstance(name, bytes) else name
            except Exception:
                self._gpu = None
        self._lhm_next = 0.0
        self.cpu_name = _cpu_name()
        self.cores = psutil.cpu_count(logical=False)
        self.threads = psutil.cpu_count()

    def snapshot(self) -> dict:
        vm = psutil.virtual_memory()
        now = time.monotonic()
        net = psutil.net_io_counters()
        t0, n0 = self._net
        dt = max(now - t0, 0.001)
        self._net = (now, net)
        return {
            "cpu": {
                "load": psutil.cpu_percent(None),
                "temp": self._cpu_temp(),
                "name": self.cpu_name,
                "cores": self.cores,
                "threads": self.threads,
                "procs": len(psutil.pids()),
                "uptime": time.time() - psutil.boot_time(),
            },
            "ram": {"used": vm.used, "total": vm.total, "percent": vm.percent},
            "gpu": self._gpu_stats(),
            "net": {
                "down": max(0, (net.bytes_recv - n0.bytes_recv) / dt),
                "up": max(0, (net.bytes_sent - n0.bytes_sent) / dt),
            },
        }

    def _gpu_stats(self):
        if not self._gpu:
            return None
        h = self._gpu
        out = {"name": self.gpu_name}
        for key, fn in (
            ("load", lambda: pynvml.nvmlDeviceGetUtilizationRates(h).gpu),
            ("temp", lambda: pynvml.nvmlDeviceGetTemperature(h, 0)),
            ("power", lambda: pynvml.nvmlDeviceGetPowerUsage(h) / 1000),
            ("fan", lambda: pynvml.nvmlDeviceGetFanSpeed(h)),
        ):
            try:
                out[key] = fn()
            except Exception:
                out[key] = None
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            out["mem_used"], out["mem_total"] = mem.used, mem.total
        except Exception:
            out["mem_used"] = out["mem_total"] = None
        return out

    def _cpu_temp(self):
        """Windows CPU sıcaklığını doğrudan vermez; LibreHardwareMonitor'ün web sunucusundan okuruz."""
        now = time.monotonic()
        if now < self._lhm_next:
            return None
        try:
            with urllib.request.urlopen(LHM_URL, timeout=0.4) as r:
                tree = json.load(r)
        except Exception:
            self._lhm_next = now + 30  # çalışmıyorsa 30 sn'de bir dene
            return None
        best = None
        for sensor_id, text, value, in_cpu in _walk(tree):
            if not value.endswith("°C"):
                continue
            is_cpu = in_cpu or "/amdcpu/" in sensor_id or "/intelcpu/" in sensor_id
            if not is_cpu:
                continue
            low = text.lower()
            rank = next((i for i, n in enumerate(CPU_TEMP_NAMES) if n in low), len(CPU_TEMP_NAMES))
            m = re.search(r"[-\d.,]+", value)
            if m and (best is None or rank < best[0]):
                best = (rank, float(m.group().replace(",", ".")))
        return best[1] if best else None


def _cpu_name() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:
        return "CPU"


def _walk(node, in_cpu=False):
    text = node.get("Text", "")
    low = text.lower()
    here_cpu = in_cpu or any(k in low for k in ("ryzen", "intel core", "amd cpu", "intel cpu"))
    yield node.get("SensorId", ""), text, str(node.get("Value", "")), here_cpu
    for child in node.get("Children", []):
        yield from _walk(child, here_cpu)
