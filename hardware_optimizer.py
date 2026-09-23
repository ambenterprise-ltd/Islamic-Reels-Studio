import os
import sys
import multiprocessing

# --- GLOBAL ENCODING FIX ---
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def get_system_ram_gb():
    """
    Returns total physical RAM in GB.
    """
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        pass

    try:
        if sys.platform == "win32":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        pass

    return 4.0 # Failsafe fallback

def get_gpu_info():
    """
    Checks PyTorch or CUDA GPU availability.
    """
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            return True, device_name
    except Exception:
        pass
    return False, "None"

def get_hardware_profile():
    """
    Classifies system into LOW_END_VPS, BALANCED, or HIGH_PERFORMANCE.
    """
    ram_gb = get_system_ram_gb()
    cpu_cores = multiprocessing.cpu_count()
    has_gpu, gpu_name = get_gpu_info()

    if ram_gb >= 12.0 and cpu_cores >= 4:
        profile = "HIGH_PERFORMANCE"
    elif ram_gb >= 6.0 and cpu_cores >= 2:
        profile = "BALANCED"
    else:
        profile = "LOW_END_VPS"

    return {
        "profile": profile,
        "ram_gb": ram_gb,
        "cpu_cores": cpu_cores,
        "has_gpu": has_gpu,
        "gpu_name": gpu_name
    }

def get_optimal_render_config(user_setting="Auto-Detect Hardware (Recommended)"):
    """
    Resolves optimal render threads, FFmpeg presets, and bitrates based on user setting or auto detection.
    """
    hw = get_hardware_profile()
    cpu_cores = hw["cpu_cores"]
    profile = hw["profile"]

    if "1 Core" in str(user_setting):
        threads = 1
        preset = "ultrafast"
        bitrate = "3500k"
        bufsize = "1500k"
        tune = "fastdecode"
        desc = "1 Core Forced (Low-RAM / VPS Profile)"
    elif "Max Performance" in str(user_setting) or "Fast PC" in str(user_setting):
        threads = max(1, cpu_cores - 1) if cpu_cores > 1 else 1
        preset = "faster"
        bitrate = "6000k"
        bufsize = "3000k"
        tune = None
        desc = f"Max Performance ({threads} Cores)"
    else: # Auto-Detect Hardware
        if profile == "HIGH_PERFORMANCE":
            threads = max(2, cpu_cores - 1)
            preset = "faster"
            bitrate = "6000k"
            bufsize = "3000k"
            tune = None
            desc = f"Auto High Performance ({threads} Cores / {hw['ram_gb']}GB RAM)"
        elif profile == "BALANCED":
            threads = max(2, cpu_cores // 2)
            preset = "veryfast"
            bitrate = "4500k"
            bufsize = "2000k"
            tune = "fastdecode"
            desc = f"Auto Balanced ({threads} Cores / {hw['ram_gb']}GB RAM)"
        else:
            threads = 1
            preset = "ultrafast"
            bitrate = "3500k"
            bufsize = "1500k"
            tune = "fastdecode"
            desc = f"Auto Low Spec (1 Core / {hw['ram_gb']}GB RAM)"

    return {
        "threads": threads,
        "preset": preset,
        "bitrate": bitrate,
        "bufsize": bufsize,
        "tune": tune,
        "desc": desc,
        "ram_gb": hw["ram_gb"],
        "cpu_cores": cpu_cores,
        "has_gpu": hw["has_gpu"],
        "gpu_name": hw["gpu_name"]
    }

def trim_memory():
    """
    Forces Python garbage collection and trims process working set on Windows.
    Safely releases unused physical memory back to the operating system.
    """
    try:
        import gc
        gc.collect()
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass

def get_optimal_whisper_config():
    """
    Returns optimal FasterWhisper model settings based on system hardware.
    """
    hw = get_hardware_profile()
    if hw["has_gpu"]:
        return {"model": "base", "device": "cuda", "compute_type": "float16", "cpu_threads": hw["cpu_cores"]}
    elif hw["profile"] == "HIGH_PERFORMANCE":
        return {"model": "base", "device": "cpu", "compute_type": "int8", "cpu_threads": hw["cpu_cores"]}
    elif hw["profile"] == "BALANCED":
        return {"model": "tiny", "device": "cpu", "compute_type": "int8", "cpu_threads": max(2, hw["cpu_cores"] // 2)}
    else:
        return {"model": "tiny", "device": "cpu", "compute_type": "int8", "cpu_threads": 1}

def get_hardware_report():
    hw = get_hardware_profile()
    cfg = get_optimal_render_config()
    w_cfg = get_optimal_whisper_config()
    
    report = []
    report.append("======================================================================")
    report.append(f"🚀 HARDWARE OPTIMIZER: {hw['profile']} PROFILE DETECTED")
    report.append(f"💻 CPU: {hw['cpu_cores']} Logical Cores | 🧠 RAM: {hw['ram_gb']} GB Physical")
    report.append(f"🎮 GPU Acceleration: {'Active (' + hw['gpu_name'] + ')' if hw['has_gpu'] else 'CPU Processing'}")
    report.append(f"⚡ Video Render Config: {cfg['desc']} | Preset: {cfg['preset']}")
    report.append(f"🧠 Whisper AI Alignment: Model '{w_cfg['model']}' on {w_cfg['device']} ({w_cfg['cpu_threads']} Threads)")
    report.append("======================================================================")
    return "\n".join(report)

if __name__ == "__main__":
    print(get_hardware_report())
