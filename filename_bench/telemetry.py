"""Sample whole-device GPU usage and owned process RAM. Missing measurements stay null."""
import shutil
import subprocess
import threading
import time


class Monitor:
    def __init__(self, backend, interval=0.5, gpu_index=0):
        self.backend, self.interval, self.gpu_index = backend, interval, gpu_index
        self.samples, self.errors = [], []
        self.stop_event = threading.Event()
        self.thread = None
        self.smi = shutil.which("nvidia-smi")

    def sample(self):
        row = {"elapsed_s": time.perf_counter() - self.start, "gpu_used_mib": None,
               "gpu_total_mib": None, "process_rss_mib": None, "active_slots": None}
        if self.smi:
            try:
                r = subprocess.run([self.smi, f"--id={self.gpu_index}",
                                    "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=2, check=True)
                used, total = r.stdout.strip().splitlines()[0].split(",")
                row.update(gpu_used_mib=float(used), gpu_total_mib=float(total))
            except Exception as e:
                self.errors.append(type(e).__name__)
        pid = self.backend.pid
        if pid:
            try:
                import psutil
                row["process_rss_mib"] = psutil.Process(pid).memory_info().rss / 1024**2
            except (ImportError, OSError):
                pass
            except Exception as e:
                self.errors.append(type(e).__name__)
        if hasattr(self.backend, "request") and self.backend.pid:
            try:
                slots = self.backend.request("/slots", timeout=1)
                row["active_slots"] = sum(bool(s.get("is_processing")) for s in slots)
            except Exception as e:
                self.errors.append(type(e).__name__)
        self.samples.append(row)

    def loop(self):
        while not self.stop_event.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.start = time.perf_counter()
        self.sample()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join(timeout=6)
        if self.thread.is_alive():
            raise RuntimeError("Telemetry thread did not stop")
        self.sample()

    def summary(self):
        def peak(key):
            values = [r[key] for r in self.samples if r[key] is not None]
            return max(values) if values else None
        first = self.samples[0] if self.samples else {}
        return {"gpu_memory_source": "nvidia-smi whole-device sampled" if self.smi else None,
                "gpu_baseline_mib": first.get("gpu_used_mib"), "gpu_peak_mib": peak("gpu_used_mib"),
                "gpu_total_mib": peak("gpu_total_mib"), "process_rss_peak_mib": peak("process_rss_mib"),
                "observed_active_slots_peak": peak("active_slots"), "sampling_interval_s": self.interval,
                "measurement_errors": sorted(set(self.errors))}
