"""Best-effort local PC status report for Discord bot.

Works without admin rights for CPU/RAM/disk/network via psutil.
GPU temperature / power is read through NVIDIA nvidia-smi when available.
CPU temperature and total wall power are not reliably available on Windows without
LibreHardwareMonitor/OpenHardwareMonitor or vendor SDKs, so they are reported as
unknown when unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import os
import platform
import shutil
import socket
import subprocess
import time
import json
import urllib.request

from typing import Any

import psutil

_START_TIME = time.time()


@dataclass
class SystemReport:
    timestamp: str
    hostname: str
    os: str
    uptime: str
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    battery: str
    cpu_temp: str
    gpu: list[dict[str, Any]]
    network_sent_mb: float
    network_recv_mb: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gb(value: float) -> float:
    return round(value / (1024 ** 3), 2)


def _mb(value: float) -> float:
    return round(value / (1024 ** 2), 1)


def _format_uptime(seconds: float) -> str:
    seconds = int(max(0, seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}days {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def _get_windows_lhm_cpu_temp() -> str:
    """
    Read CPU temperature from LibreHardwareMonitor / OpenHardwareMonitor WMI namespace.
    LibreHardwareMonitor or OpenHardwareMonitor must be running.
    """
    if platform.system() != "Windows":
        return ""

    try:
        import wmi
    except Exception:
        return "Unknown (wmi / pywin32 not installed; run pip install wmi pywin32)"

    namespaces = [
        r"root\LibreHardwareMonitor",
        r"root\OpenHardwareMonitor",
    ]

    for namespace in namespaces:
        try:
            conn = wmi.WMI(namespace=namespace)
            sensors = conn.Sensor()
        except Exception:
            continue

        temps: list[tuple[str, float]] = []

        for sensor in sensors:
            try:
                sensor_type = str(getattr(sensor, "SensorType", ""))
                name = str(getattr(sensor, "Name", ""))
                identifier = str(getattr(sensor, "Identifier", ""))
                value = getattr(sensor, "Value", None)

                if sensor_type.lower() != "temperature" or value is None:
                    continue

                key = f"{identifier} {name}".casefold()

                # Prefer CPU Package / CPU Core / CCD / Tctl/Tdie
                if any(k in key for k in ["cpu", "package", "core", "ccd", "tdie", "tctl"]):
                    temps.append((name, float(value)))
            except Exception:
                continue

        if temps:
            # Prefer Package; otherwise show the hottest core
            priority = ["package", "tdie", "tctl", "ccd"]
            for p in priority:
                for name, value in temps:
                    if p in name.casefold():
                        return f"{name}: {value:.1f}°C"

            name, value = max(temps, key=lambda item: item[1])
            return f"{name}: {value:.1f}°C"

    return ""

def _walk_lhm_tree(node: dict, path: list[str] | None = None):
    path = path or []
    text = str(node.get("Text", "")).strip()
    new_path = path + ([text] if text else [])

    yield node, new_path

    for child in node.get("Children", []) or []:
        if isinstance(child, dict):
            yield from _walk_lhm_tree(child, new_path)


def _parse_temp_value(value: object) -> float | None:
    import re

    text = str(value or "")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*°?\s*C", text, flags=re.IGNORECASE)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def _get_lhm_web_temperatures() -> list[tuple[str, float, str]]:
    """
    Read temperatures from LibreHardwareMonitor Remote Web Server.
    Enable LHM: Options -> Remote Web Server -> Run
    Default URL:http://localhost:8085/data.json
    """
    url = os.getenv("LHM_DATA_URL", "http://localhost:8085/data.json").strip()

    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    temps: list[tuple[str, float, str]] = []

    for node, path in _walk_lhm_tree(data):
        name = str(node.get("Text", "")).strip()
        value = _parse_temp_value(node.get("Value"))

        if value is None:
            continue

        path_text = " / ".join(p for p in path if p)
        temps.append((name, value, path_text))

    return temps


def _get_lhm_web_cpu_temp() -> str:
    temps = _get_lhm_web_temperatures()
    if not temps:
        return ""

    # not [cpu temp] Sensor
    exclude_keywords = [
        "distance to tjmax",
        "tjmax distance",
        "load",
        "power",
        "clock",
        "voltage",
        "fan",
        "control",
    ]

    def is_excluded(name: str, path: str) -> bool:
        key = f"{name} {path}".casefold()
        return any(k in key for k in exclude_keywords)

    # 1. first:CPU Package
    for name, value, path in temps:
        key = f"{name} {path}".casefold()
        if is_excluded(name, path):
            continue
        if "cpu package" in key or name.casefold() == "cpu package":
            return f"CPU Package: {value:.1f}°C"

    # 2. else  :Core Max
    for name, value, path in temps:
        key = f"{name} {path}".casefold()
        if is_excluded(name, path):
            continue
        if "core max" in key or name.casefold() == "core max":
            return f"Core Max: {value:.1f}°C"

    # 3.else esle Core Average
    for name, value, path in temps:
        key = f"{name} {path}".casefold()
        if is_excluded(name, path):
            continue
        if "core average" in key or name.casefold() == "core average":
            return f"Core Average: {value:.1f}°C"

    # 4. last try CPU temp, exc Distance/Load/Power
    cpu_keywords = ["cpu", "package", "core", "tctl", "tdie", "ccd", "intel", "i9", "14900"]
    cpu_temps: list[tuple[str, float, str]] = []

    for name, value, path in temps:
        key = f"{name} {path}".casefold()
        if is_excluded(name, path):
            continue
        if any(k in key for k in cpu_keywords):
            cpu_temps.append((name, value, path))

    if cpu_temps:
        name, value, path = max(cpu_temps, key=lambda item: item[1])
        return f"{name}: {value:.1f}°C"

    return ""

def _get_cpu_temp() -> str:
    # 0. Prefer trying LibreHardwareMonitor Web Server
    lhm_web_temp = _get_lhm_web_cpu_temp()
    if lhm_web_temp:
        return lhm_web_temp

    # 1. On Windows, then try LibreHardwareMonitor / OpenHardwareMonitor WMI
    lhm_temp = _get_windows_lhm_cpu_temp()
    if lhm_temp:
        return lhm_temp

    # 2. On non-Windows or other systems, try psutil
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False)
    except Exception:
        temps = {}

    if not temps:
        return "Unknown (please enable LibreHardwareMonitor Options -> Remote Web Server -> Run)"

    readings: list[str] = []
    for name, entries in temps.items():
        for entry in entries[:2]:
            if entry.current is not None:
                label = entry.label or name
                readings.append(f"{label}: {entry.current:.1f}°C")

    return ", ".join(readings[:4]) if readings else "Unknown"


def _query_nvidia_smi() -> list[dict[str, Any]]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        # Windows common path fallback
        fallback = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
        if os.path.exists(fallback):
            exe = fallback
    if not exe:
        return []

    query = (
        "name,utilization.gpu,memory.used,memory.total,temperature.gpu,"
        "power.draw,power.limit"
    )
    try:
        proc = subprocess.run(
            [exe, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    gpus: list[dict[str, Any]] = []
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        name, util, mem_used, mem_total, temp, power_draw, power_limit = parts[:7]
        gpus.append(
            {
                "name": name,
                "util_percent": util,
                "memory_used_mb": mem_used,
                "memory_total_mb": mem_total,
                "temperature_c": temp,
                "power_draw_w": power_draw,
                "power_limit_w": power_limit,
            }
        )
    return gpus

def get_disk_usage_safe():
    """
    On Windows, psutil.disk_usage() may fail because of path format.
    Convert disk paths to root paths such as C:/ and provide a shutil fallback.
    """
    def _usage_with_fallback(path: str):
        try:
            return psutil.disk_usage(path)
        except BaseException:
            usage = shutil.disk_usage(path)

            class DiskUsage:
                total = usage.total
                used = usage.used
                free = usage.free
                percent = (usage.used / usage.total * 100) if usage.total else 0.0

            return DiskUsage()

    if platform.system() == "Windows":
        raw = os.getenv("PC_STATUS_DISK", "C:/").strip().strip('"').strip("'")
        raw = raw.replace("\\", "/")

        # Only use the drive letter to avoid failures from C:/users/... or strange characters.
        if len(raw) >= 2 and raw[1] == ":":
            disk_path = raw[0].upper() + ":/"
        else:
            disk_path = "C:/"

        candidates = [disk_path, "C:/"]
    else:
        raw = os.getenv("PC_STATUS_DISK", "/").strip().strip('"').strip("'")
        candidates = [raw or "/", "/"]

    last_error = None
    for path in candidates:
        try:
            return _usage_with_fallback(path), path
        except BaseException as exc:
            last_error = exc

    raise RuntimeError(f"Unable to read disk usage:{last_error}")
    
def collect_system_report() -> SystemReport:
    cpu_percent = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk, disk_path = get_disk_usage_safe()
    net = psutil.net_io_counters()
    battery_obj = psutil.sensors_battery()
    if battery_obj is None:
        battery = "Desktop / no battery info"
    else:
        plugged = "plugged in" if battery_obj.power_plugged else "battery"
        battery = f"{battery_obj.percent:.0f}% ({plugged})"

    notes = [
        "CPU temperature and total wall power usually cannot be reliably read via psutil on Windows.",
        "GPU temperature/power is read via nvidia-smi; if NVIDIA driver/path is unavailable, it will show not detected.",
    ]
    gpus = _query_nvidia_smi()
    if not gpus:
        notes.append("No nvidia-smi GPU information detected.")

    return SystemReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        hostname=socket.gethostname(),
        os=f"{platform.system()} {platform.release()}",
        uptime=_format_uptime(time.time() - psutil.boot_time()),
        cpu_percent=float(cpu_percent),
        ram_used_gb=_gb(mem.used),
        ram_total_gb=_gb(mem.total),
        ram_percent=float(mem.percent),
        disk_used_gb=_gb(disk.used),
        disk_total_gb=_gb(disk.total),
        disk_percent=float(disk.percent),
        battery=battery,
        cpu_temp=_get_cpu_temp(),
        gpu=gpus,
        network_sent_mb=_mb(net.bytes_sent),
        network_recv_mb=_mb(net.bytes_recv),
        notes=notes,
    )


def format_system_report(report: SystemReport | None = None) -> str:
    report = report or collect_system_report()
    lines = [
        "🖥️ **PC status report**",
        f"Time:{report.timestamp}",
        f"Host:{report.hostname} | {report.os}",
        f"Uptime:{report.uptime}",
        f"CPU:{report.cpu_percent:.1f}% | CPU temperature:{report.cpu_temp}",
        f"RAM:{report.ram_used_gb:.2f}/{report.ram_total_gb:.2f} GB ({report.ram_percent:.1f}%)",
        f"Disk:{report.disk_used_gb:.2f}/{report.disk_total_gb:.2f} GB ({report.disk_percent:.1f}%)",
        f"Power:{report.battery}",
        f"Network total:↑ {report.network_sent_mb:.1f} MB / ↓ {report.network_recv_mb:.1f} MB",
    ]
    if report.gpu:
        for i, gpu in enumerate(report.gpu, start=1):
            lines.append(
                f"GPU{i}:{gpu['name']} | Usage {gpu['util_percent']}% | "
                f"VRAM {gpu['memory_used_mb']}/{gpu['memory_total_mb']} MB | "
                f"Temperature {gpu['temperature_c']}°C | Power draw {gpu['power_draw_w']}/{gpu['power_limit_w']} W"
            )
    else:
        lines.append("GPU:No nvidia-smi information detected")

    lines.append("\nNotes:" + "; ".join(report.notes[:2]))
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_system_report())


def format_detailed_system_report(report: SystemReport | None = None) -> str:
    """Detailed report for admin use. Uses LHM Web Server data when available."""
    report = report or collect_system_report()
    lines = [format_system_report(report)]

    temps = _get_lhm_web_temperatures()
    if temps:
        lines.append("\n🌡️ **LibreHardwareMonitor temperature sensors**")
        for name, value, path in temps[:30]:
            lines.append(f"- {path}: {value:.1f}°C")
    else:
        lines.append("\n🌡️ No temperature data read from LibreHardwareMonitor Web Server.")

    return "\n".join(lines)
