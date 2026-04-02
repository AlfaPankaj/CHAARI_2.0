# CHAARI 2.0 – core/ - Tool Truth Layer (Layer 2)
# Real system tools — no guessing, no hallucination
# If a tool exists, call it. If not, say so.

import re
import os
import platform
import socket
import subprocess
import shutil
import json
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import wikipedia
    wikipedia.set_lang("en")
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    WIKIPEDIA_AVAILABLE = False



TIME_KEYWORDS = [
    r"(?i)\b(time|samay|waqt|kitne\s+baje|what\s+time|current\s+time|abhi\s+kya\s+time)\b",
    r"(?i)\b(date|taareekh|aaj\s+kya|today|today'?s\s+date)\b",
]

SYSTEM_KEYWORDS = [
    r"(?i)\b(cpu|processor|ram|memory|system\s+info|system\s+status)\b",
    r"(?i)\b(kitni\s+ram|kitna\s+cpu|system\s+kaisa|pc\s+status)\b",
    r"(?i)\b(battery|charge|power)\b",
]

NETWORK_KEYWORDS = [
    r"(?i)\b(ping|network|ip\s+address|my\s+ip|internet|connectivity|network\s+interface)\b",
    r"(?i)\b(wifi|ethernet|connection\s+status|network\s+info)\b",
]

PROCESS_KEYWORDS = [
    r"(?i)\b(list\s+process(?:es)?|running\s+process(?:es)?|task\s+manager|process\s+list|top\s+process(?:es)?)\b",
    r"(?i)\b(active\s+process(?:es)?|what'?s\s+running|kaun\s+sa\s+process|chalte\s+process)\b",
]

FILE_INFO_KEYWORDS = [
    r"(?i)\b(list\s+(files?|directory|folder|dir)|show\s+(files?|directory|folder))\b",
    r"(?i)\b(file\s+info|file\s+size|file\s+details|folder\s+contents)\b",
    r"(?i)\b(dikhao\s+files?|folder\s+mein\s+kya)\b",
    r"(?i)\b(show|list|display)\s+\w+\s+(directory|folder|files?)\b",
    r"(?i)\b(show|list)\s+(?:all\s+)?(?:files?\s+)?(?:in\s+|of\s+)?\w+\s*$",
]

SYSTEM_UTIL_KEYWORDS = [
    r"(?i)\b(uptime|os\s+info|operating\s+system|system\s+details|computer\s+name)\b",
    r"(?i)\b(disk\s+(usage|space)|drive\s+space|kitna\s+space|storage(\s+left)?|how\s+much\s+storage|space\s+(left|remaining|available|free))\b",
    r"(?i)\b(environment\s+variable|env\s+var)\b",
]

FILE_CHECK_KEYWORDS = [
    r"(?i)\bis\s+\S+\.\w+\s+(?:present|there|available|existing)\b",
    r"(?i)\b(does|do)\s+\S+\.\w+\s+exist\b",
    r"(?i)\b(check\s+if|verify)\s+\S+\.\w+\s+(?:exists?|present|there)\b",
    r"(?i)\b\S+\.\w+\s+(?:hai\s+kya|present\s+hai|exist\s+karta)\b",
    r"(?i)\bis\s+(?:the\s+)?(?:file\s+)?\S+\.\w+\s+(?:in|inside)\b",
]

PATH_KEYWORDS = [
    r"(?i)\b(show|tell|give|what'?s?)\s+(?:me\s+)?(?:the\s+)?path\s+(?:to|of|for)\s+\w+\b",
    r"(?i)\b(where\s+is|locate|find)\s+(?:my\s+)?(?:the\s+)?\w+\s+(?:folder|directory)\b",
    r"(?i)\bpath\s+(?:of|to|for)\s+\w+\b",
    r"(?i)\b\w+\s+(?:ka|ki)\s+path\b",
    r"(?i)\b(?:folder|directory)\s+(?:path|location)\s+(?:of|for)\s+\w+\b",
]

NETWORK_SPEED_KEYWORDS = [
    r"(?i)\b(network\s+speed|internet\s+speed|net\s+speed|download\s+speed|upload\s+speed)\b",
    r"(?i)\b(speed\s+test|bandwidth|data\s+rate|kitni\s+speed)\b",
    r"(?i)\b(network|internet)\s+(?:ki\s+)?speed\b",
]

TEMPERATURE_KEYWORDS = [
    r"(?i)\b(temperature|temp)\b(?!.*(?:erature|late|orary|est))",
    r"(?i)\b(cpu\s+temp|system\s+temp|how\s+hot|thermal|heat)\b",
    r"(?i)\b(kitna\s+garam|temperature\s+kya|temp\s+check)\b",
]

WIKI_KEYWORDS = [
    r"(?i)\b(what\s+is|what\s+are|who\s+is|who\s+was|who\s+are)\b",
    r"(?i)\b(define|definition\s+of|meaning\s+of)\b",
    r"(?i)\b(tell\s+me\s+about|explain|describe)\b",
    r"(?i)\b(kya\s+hai|kya\s+hota\s+hai|kaun\s+hai|kaun\s+tha|ke\s+baare\s+mein|batao)\b",
    r"(?i)\b(history\s+of|origin\s+of|invention\s+of|founder\s+of)\b",
    r"(?i)\b(wikipedia|wiki)\b",
]




AVAILABLE_TOOLS = {
    "time": True,
    "date": True,
    "system_info": PSUTIL_AVAILABLE,
    "battery": PSUTIL_AVAILABLE,
    "network_info": True,
    "network_speed": PSUTIL_AVAILABLE,
    "ping": True,
    "process_list": PSUTIL_AVAILABLE,
    "file_info": True,
    "file_check": True,
    "list_directory": True,
    "path_resolve": True,
    "os_info": True,
    "uptime": PSUTIL_AVAILABLE,
    "disk_usage": PSUTIL_AVAILABLE,
    "temperature": PSUTIL_AVAILABLE,
    "wikipedia": WIKIPEDIA_AVAILABLE,
}


def get_time() -> str:
    now = datetime.now()
    return now.strftime("%I:%M %p")


def get_date() -> str:
    now = datetime.now()
    return now.strftime("%A, %d %B %Y")


LOCATION_TIMEZONE_MAP: dict[str, str] = {
    "japan": "Asia/Tokyo", "india": "Asia/Kolkata", "china": "Asia/Shanghai",
    "korea": "Asia/Seoul", "russia": "Europe/Moscow", "brazil": "America/Sao_Paulo",
    "australia": "Australia/Sydney", "uk": "Europe/London", "usa": "America/New_York",
    "america": "America/New_York", "germany": "Europe/Berlin", "france": "Europe/Paris",
    "italy": "Europe/Rome", "spain": "Europe/Madrid", "pakistan": "Asia/Karachi",
    "bangladesh": "Asia/Dhaka", "saudi": "Asia/Riyadh", "uae": "Asia/Dubai",
    "turkey": "Europe/Istanbul", "egypt": "Africa/Cairo", "nigeria": "Africa/Lagos",
    "mexico": "America/Mexico_City", "argentina": "America/Argentina/Buenos_Aires",
    "canada": "America/Toronto", "europe": "Europe/London",
    "tokyo": "Asia/Tokyo", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "chennai": "Asia/Kolkata",
    "shanghai": "Asia/Shanghai", "beijing": "Asia/Shanghai", "hong kong": "Asia/Hong_Kong",
    "seoul": "Asia/Seoul", "london": "Europe/London", "paris": "Europe/Paris",
    "berlin": "Europe/Berlin", "moscow": "Europe/Moscow", "dubai": "Asia/Dubai",
    "singapore": "Asia/Singapore", "sydney": "Australia/Sydney",
    "new york": "America/New_York", "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago", "toronto": "America/Toronto",
    "brampton": "America/Toronto", "vancouver": "America/Vancouver",
    "montreal": "America/Toronto", "ottawa": "America/Toronto",
    "mississauga": "America/Toronto", "calgary": "America/Edmonton",
    "california": "America/Los_Angeles", "texas": "America/Chicago",
    "lahore": "Asia/Karachi", "karachi": "Asia/Karachi", "islamabad": "Asia/Karachi",
    "dhaka": "Asia/Dhaka", "bangkok": "Asia/Bangkok", "jakarta": "Asia/Jakarta",
    "riyadh": "Asia/Riyadh", "istanbul": "Europe/Istanbul", "cairo": "Africa/Cairo",
    "lagos": "Africa/Lagos", "nairobi": "Africa/Nairobi",
    "sao paulo": "America/Sao_Paulo", "mexico city": "America/Mexico_City",
}


def get_time_for_location(location: str) -> str | None:
    """Get current time for a known location. Returns formatted string or None."""
    loc = location.strip().lower()
    tz_name = LOCATION_TIMEZONE_MAP.get(loc)
    if not tz_name:
        return None
    try:
        now = datetime.now(ZoneInfo(tz_name))
        return (
            f"Time in {location.title()}: {now.strftime('%I:%M %p')} | "
            f"Date: {now.strftime('%A, %d %B %Y')} ({tz_name})"
        )
    except Exception:
        return None


def _extract_location_from_query(text: str) -> str | None:
    """Try to extract a location name from a time-related query."""
    text_lower = text.lower().strip()

    for loc in sorted(LOCATION_TIMEZONE_MAP.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(loc) + r'\b', text_lower):
            return loc

    _non_location = {
        "what", "kya", "hua", "hai", "current", "abhi", "the", "my", "your",
        "aaj", "how", "much", "local", "yeh", "woh", "batao", "bata",
        "please", "now", "check", "time", "samay", "waqt", "this", "that",
        "kitne", "baje", "kab", "konsa", "today", "kal",
    }

    m = re.search(
        r'\b(?:in|on|at|of|for)\s+([a-z][a-z ]{1,25}?)(?:\s+(?:time|samay|waqt|kya|hai)|[.?!]?$)',
        text_lower,
    )
    if m:
        candidate = m.group(1).strip()
        if len(candidate) >= 3 and candidate not in _non_location:
            return candidate

    m = re.search(r'\b([a-z]{3,})\s+(?:me|mein|mai|ka|ke|ki|pe|par)\b', text_lower)
    if m:
        candidate = m.group(1).strip()
        if candidate not in _non_location:
            return candidate

    m = re.search(r'\b([a-z]{3,})\s+(?:time|samay|waqt)\b', text_lower)
    if m:
        candidate = m.group(1).strip()
        if candidate not in _non_location:
            return candidate

    m = re.search(r'(?:time|samay|waqt)\s+([a-z]{3,})\b', text_lower)
    if m:
        candidate = m.group(1).strip()
        if candidate not in _non_location:
            return candidate

    return None


def get_system_info() -> str | None:
    if not PSUTIL_AVAILABLE:
        return None
    cpu_percent = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    info = (
        f"CPU Usage: {cpu_percent}% | "
        f"RAM: {ram.percent}% used ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB) | "
        f"Disk: {disk.percent}% used ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
    )
    return info


def get_battery_info() -> str | None:
    if not PSUTIL_AVAILABLE:
        return None
    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery detected (desktop PC)."
    plugged = "Charging" if battery.power_plugged else "Not charging"
    return f"Battery: {battery.percent}% | {plugged}"


def get_network_info() -> str:
    """Get IP address and hostname."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        parts = [f"Hostname: {hostname}", f"Local IP: {local_ip}"]
        if PSUTIL_AVAILABLE:
            interfaces = psutil.net_if_addrs()
            for iface_name, addrs in interfaces.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                        parts.append(f"{iface_name}: {addr.address}")
        return " | ".join(parts)
    except Exception as e:
        return f"Network info unavailable: {e}"


def ping_host(host: str = "8.8.8.8") -> str:
    """Ping a host and return result."""
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        result = subprocess.run(
            ["ping", param, "1", host],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            reply_line = [l for l in lines if re.search(r'time[=<]\d+', l, re.IGNORECASE)]
            if reply_line:
                return f"Ping {host}: {reply_line[0].strip()}"
            stats_line = [l for l in lines if re.search(r'average|minimum|maximum', l, re.IGNORECASE)]
            if stats_line:
                return f"Ping {host}: {stats_line[0].strip()}"
            return f"Ping {host}: Success (reachable)"
        return f"Ping {host}: Failed (host unreachable)"
    except subprocess.TimeoutExpired:
        return f"Ping {host}: Timed out"
    except Exception as e:
        return f"Ping {host}: Error — {e}"


def get_process_list(top_n: int = 10) -> str:
    """Get top N processes by CPU usage."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        lines = [f"Top {top_n} processes by CPU:"]
        for p in procs[:top_n]:
            name = p.get('name', 'unknown')[:25]
            pid = p.get('pid', '?')
            cpu = p.get('cpu_percent', 0) or 0
            mem = p.get('memory_percent', 0) or 0
            lines.append(f"  PID {pid:>6} | {name:<25} | CPU: {cpu:5.1f}% | MEM: {mem:5.1f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"Process list error: {e}"


def get_file_info(path: str) -> str:
    """Get info about a file or directory."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"Path does not exist: {path}"
        if p.is_file():
            size = p.stat().st_size
            modified = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size_str = _format_size(size)
            return f"File: {p.name} | Size: {size_str} | Modified: {modified} | Path: {p}"
        elif p.is_dir():
            items = list(p.iterdir())
            files = [i for i in items if i.is_file()]
            dirs = [i for i in items if i.is_dir()]
            return f"Directory: {p.name} | Files: {len(files)} | Subdirs: {len(dirs)} | Path: {p}"
        return f"Path exists but is neither file nor directory: {path}"
    except Exception as e:
        return f"File info error: {e}"


def list_directory(path: str = ".") -> str:
    """List contents of a directory."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"Directory does not exist: {path}"
        if not p.is_dir():
            return f"Not a directory: {path}"
        items = []
        for item in p.iterdir():
            try:
                item.is_dir()  
                items.append(item)
            except (OSError, PermissionError):
                pass
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = [f"Contents of {p}:"]
        for item in items[:30]:  
            try:
                if item.is_dir():
                    lines.append(f"  📁 {item.name}/")
                else:
                    size = _format_size(item.stat().st_size)
                    lines.append(f"  📄 {item.name} ({size})")
            except (OSError, PermissionError):
                lines.append(f"  ⚠️ {item.name} (inaccessible)")
        if len(items) > 30:
            lines.append(f"  ... and {len(items) - 30} more items")
        return "\n".join(lines)
    except Exception as e:
        return f"Directory listing error: {e}"


def _resolve_common_directory(name: str) -> str | None:
    """Resolve common directory names (Desktop, Documents, etc.) to actual paths.
    
    OneDrive-aware: checks OneDrive-redirected folders first since Windows
    often redirects Desktop/Documents/Pictures there (real files live there).
    """
    import os as _os
    name_clean = name.strip().rstrip('.,;:!?')
    name_lower = name_clean.lower().rstrip('s')
    home = Path.home()

    standard_dirs = {
        'desktop': 'Desktop',
        'document': 'Documents',
        'download': 'Downloads',
        'picture': 'Pictures',
        'video': 'Videos',
        'music': 'Music',
    }
    folder_name = standard_dirs.get(name_lower)
    if folder_name:
        onedrive = _os.environ.get('OneDrive', '')
        if onedrive:
            od_path = Path(onedrive) / folder_name
            if od_path.is_dir():
                return str(od_path)
        home_path = home / folder_name
        if home_path.is_dir():
            return str(home_path)

    onedrive = _os.environ.get('OneDrive', '')
    for parent_name in ['Documents', 'Desktop']:
        for base in ([Path(onedrive)] if onedrive else []) + [home]:
            child = base / parent_name / name_clean
            if child.is_dir():
                return str(child)
    return None


def get_os_info() -> str:
    """Get operating system information."""
    info = [
        f"OS: {platform.system()} {platform.release()}",
        f"Version: {platform.version()}",
        f"Architecture: {platform.machine()}",
        f"Processor: {platform.processor() or 'Unknown'}",
        f"Computer: {platform.node()}",
        f"Python: {platform.python_version()}",
    ]
    return " | ".join(info)


def get_uptime() -> str | None:
    """Get system uptime."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"Uptime: {hours}h {minutes}m {seconds}s | Boot: {boot_time.strftime('%Y-%m-%d %H:%M')}"
    except Exception as e:
        return f"Uptime unavailable: {e}"


def get_disk_usage() -> str | None:
    """Get disk usage for all partitions."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        partitions = psutil.disk_partitions()
        lines = []
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total = _format_size(usage.total)
                used = _format_size(usage.used)
                free = _format_size(usage.free)
                lines.append(f"{part.device} ({part.mountpoint}): {used}/{total} used ({usage.percent}%), {free} free")
            except (PermissionError, OSError):
                continue
        return " | ".join(lines) if lines else "No accessible disk partitions"
    except Exception as e:
        return f"Disk usage error: {e}"


def get_network_speed() -> str | None:
    """Get network speed (bytes sent/received) using psutil."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        counters1 = psutil.net_io_counters()
        time_module = __import__('time')
        time_module.sleep(1)
        counters2 = psutil.net_io_counters()
        dl_speed = (counters2.bytes_recv - counters1.bytes_recv)
        ul_speed = (counters2.bytes_sent - counters1.bytes_sent)
        return (
            f"Download Speed: {_format_size(dl_speed)}/s | "
            f"Upload Speed: {_format_size(ul_speed)}/s | "
            f"Total Received: {_format_size(counters2.bytes_recv)} | "
            f"Total Sent: {_format_size(counters2.bytes_sent)}"
        )
    except Exception as e:
        return f"Network speed unavailable: {e}"


def get_temperature() -> str | None:
    """Get system temperature using psutil (Linux/some Windows)."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        if not hasattr(psutil, 'sensors_temperatures'):
            return "Temperature monitoring not supported on this OS."
        temps = psutil.sensors_temperatures()
        if not temps:
            return "No temperature sensors detected (common on Windows desktops — use HWMonitor for detailed readings)."
        lines = []
        for sensor_name, entries in temps.items():
            for entry in entries:
                label = entry.label or sensor_name
                current = entry.current
                high = f" (High: {entry.high}°C)" if entry.high else ""
                critical = f" (Critical: {entry.critical}°C)" if entry.critical else ""
                lines.append(f"{label}: {current}°C{high}{critical}")
        return " | ".join(lines) if lines else "No temperature readings available."
    except Exception as e:
        return f"Temperature unavailable: {e}"


def is_file_present(filename: str, folder: str = None) -> str:
    """Check if a file exists in a given folder or common directories."""
    try:
        if folder:
            resolved = _resolve_common_directory(folder)
            if resolved:
                target = Path(resolved) / filename
                if target.exists():
                    return f"✅ Yes, '{filename}' is present in {resolved} ({_format_size(target.stat().st_size)})"
                else:
                    return f"❌ No, '{filename}' is NOT present in {resolved}"
            target = Path(folder) / filename
            if target.exists():
                return f"✅ Yes, '{filename}' is present in {folder}"
            return f"❌ No, '{filename}' is NOT found in '{folder}'"
        
        cwd_target = Path.cwd() / filename
        if cwd_target.exists():
            return f"✅ Yes, '{filename}' is present in current directory ({cwd_target.parent})"
        
        for dir_name in ['Documents', 'Desktop', 'Downloads']:
            resolved = _resolve_common_directory(dir_name)
            if resolved:
                target = Path(resolved) / filename
                if target.exists():
                    return f"✅ Yes, '{filename}' found in {resolved}"
        
        return f"❌ No, '{filename}' was not found in common directories (Documents, Desktop, Downloads) or current directory."
    except Exception as e:
        return f"File check error: {e}"


def resolve_folder_path(folder_name: str) -> str:
    """Resolve and return the full path to a named folder."""
    resolved = _resolve_common_directory(folder_name)
    if resolved:
        return f"📂 Path to {folder_name}: {resolved}"
    home_path = Path.home() / folder_name
    if home_path.is_dir():
        return f"📂 Path to {folder_name}: {home_path}"
    return f"❌ Could not find a folder named '{folder_name}' on this system."


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}PB"


_WIKI_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "wiki_cache")
os.makedirs(_WIKI_CACHE_DIR, exist_ok=True)


def _wiki_cache_path(topic: str) -> str:
    """Get cache file path for a topic (SHA-256 hash as filename)."""
    key = hashlib.sha256(topic.lower().strip().encode()).hexdigest()[:16]
    return os.path.join(_WIKI_CACHE_DIR, f"{key}.json")


def wiki_search(topic: str, sentences: int = 4, lang: str = "en") -> dict:
    """
    Fetch Wikipedia summary for a topic.
    Returns cached result if available, otherwise fetches live.
    
    Returns:
        {
            "found": bool,
            "topic": str,
            "summary": str,
            "url": str,
            "cached": bool,
            "lang": str,
            "suggestions": list[str]  (if not found)
        }
    """
    topic = topic.strip()
    if not topic:
        return {"found": False, "topic": "", "summary": "", "url": "", "cached": False, "lang": lang, "suggestions": []}
    
    cache_file = _wiki_cache_path(f"{lang}:{topic}")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["cached"] = True
            return cached
        except Exception:
            pass
    
    if not WIKIPEDIA_AVAILABLE:
        return {"found": False, "topic": topic, "summary": "Wikipedia module not installed.", "url": "", "cached": False, "lang": lang, "suggestions": []}
    
    try:
        wikipedia.set_lang(lang)
        search_results = wikipedia.search(topic, results=5)
        best_title = topic
        if search_results:
            for sr in search_results:
                if sr.lower() == topic.lower():
                    best_title = sr
                    break
            else:
                best_title = search_results[0]
        
        page = wikipedia.summary(best_title, sentences=sentences, auto_suggest=False)
        url = wikipedia.page(best_title, auto_suggest=False).url
        
        result = {
            "found": True,
            "topic": topic,
            "summary": page,
            "url": url,
            "cached": False,
            "lang": lang,
            "suggestions": [],
        }
        
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        return result
    
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:5] if e.options else []
        for opt in options:
            try:
                page = wikipedia.summary(opt, sentences=sentences)
                url = wikipedia.page(opt).url
                result = {
                    "found": True, "topic": opt, "summary": page,
                    "url": url, "cached": False, "lang": lang, "suggestions": [],
                }
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return result
            except Exception:
                continue
        return {"found": False, "topic": topic, "summary": f"Multiple matches. Did you mean: {', '.join(options)}?", "url": "", "cached": False, "lang": lang, "suggestions": options}
    
    except wikipedia.exceptions.PageError:
        try:
            suggestions = wikipedia.search(topic, results=5)
            for s in suggestions:
                try:
                    page = wikipedia.summary(s, sentences=sentences)
                    url = wikipedia.page(s).url
                    result = {
                        "found": True, "topic": s, "summary": page,
                        "url": url, "cached": False, "lang": lang, "suggestions": [],
                    }
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    return result
                except Exception:
                    continue
        except Exception:
            pass
        return {"found": False, "topic": topic, "summary": f"No article found for '{topic}'.", "url": "", "cached": False, "lang": lang, "suggestions": []}
    
    except Exception as e:
        return {"found": False, "topic": topic, "summary": f"Wikipedia error: {str(e)[:100]}", "url": "", "cached": False, "lang": lang, "suggestions": []}


def extract_wiki_topic(user_input: str) -> str | None:
    """
    Extract the knowledge topic from user input.
    Returns the topic string or None if no topic detected.
    """
    text = user_input.strip()
    
    patterns = [
        r"(?i)(?:what\s+(?:is|are)\s+(?:a|an|the)?\s*)(.+?)[\?\.]?\s*$",
        r"(?i)(?:who\s+(?:is|was|are)\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:tell\s+me\s+about\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:explain\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:describe\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:define\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:definition\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:meaning\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:history\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:origin\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:founder\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(?:invention\s+of\s+)(.+?)[\?\.]?\s*$",
        r"(?i)(.+?)\s+(?:kya\s+hai|kya\s+hota\s+hai|kya\s+hoti\s+hai)[\?\.]?\s*$",
        r"(?i)(.+?)\s+(?:kaun\s+hai|kaun\s+tha|kaun\s+thi)[\?\.]?\s*$",
        r"(?i)(.+?)\s+(?:ke\s+baare\s+mein|ke\s+bare\s+me)\s+(?:batao|bata)[\?\.]?\s*$",
        r"(?i)(?:batao\s+)(.+?)(?:\s+ke\s+baare\s+mein)?[\?\.]?\s*$",
        r"(?i)(?:wikipedia|wiki)\s+(.+?)[\?\.]?\s*$",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            topic = m.group(1).strip()
            if topic.lower() in ("this", "that", "it", "the", "a", "an", "your", "my", "tum", "tu", "ye", "yeh", "wo", "woh"):
                return None
            if len(topic) < 2 or len(topic) > 100:
                return None
            return topic
    
    return None


APP_WHITELIST: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "cmd.exe",
    "powershell": "powershell.exe",
    "control panel": "control.exe",
    "control": "control.exe",
    "settings": "ms-settings:",
    "character map": "charmap.exe",
    "charmap": "charmap.exe",
    "remote desktop": "mstsc.exe",
    "mstsc": "mstsc.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "vscode": r"C:\Users\PANKAJ\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vs code": r"C:\Users\PANKAJ\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "code": r"C:\Users\PANKAJ\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "whatsapp": "whatsapp:",
    "telegram": "tg:",
    "discord": "discord:",
    "slack": "slack:",
    "zoom": "zoom:",
    "microsoft teams": "ms-teams:",
    "ms teams": "ms-teams:",
    "teams": "ms-teams:",
    "spotify": r"C:\Users\PANKAJ\AppData\Roaming\Spotify\Spotify.exe",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "vlc media player": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "word": "winword.exe",
    "ms word": "winword.exe",
    "microsoft word": "winword.exe",
    "winword": "winword.exe",
    "excel": "excel.exe",
    "ms excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "ms powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "ppt": "powerpnt.exe",
    "outlook": "outlook.exe",
    "ms outlook": "outlook.exe",
    "microsoft outlook": "outlook.exe",
    "onenote": "onenote.exe",
    "ms onenote": "onenote.exe",
    "access": "msaccess.exe",
    "ms access": "msaccess.exe",
    "microsoft access": "msaccess.exe",
    "publisher": "mspub.exe",
    "ms publisher": "mspub.exe",
    "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
    "notepad plus plus": r"C:\Program Files\Notepad++\notepad++.exe",
    "sublime": "subl.exe",
    "sublime text": "subl.exe",
    "pycharm": "pycharm64.exe",
    "android studio": "studio64.exe",
    "postman": r"C:\Users\PANKAJ\AppData\Local\Postman\Postman.exe",
    "github desktop": r"C:\Users\PANKAJ\AppData\Local\GitHubDesktop\GitHubDesktop.exe",
    "github": r"C:\Users\PANKAJ\AppData\Local\GitHubDesktop\GitHubDesktop.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "epic games": "epicgameslauncher.exe",
    "epic": "epicgameslauncher.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "photoshop": "photoshop.exe",
    "adobe photoshop": "photoshop.exe",
    "illustrator": "illustrator.exe",
    "premiere": "premiere.exe",
    "premiere pro": "premiere.exe",
    "wordpad": "write.exe",
    "snipping tool": "SnippingTool.exe",
    "snip": "SnippingTool.exe",
    "microsoft store": "ms-windows-store:",
    "store": "ms-windows-store:",
    "app store": "ms-windows-store:",
    "opera": r"C:\Users\PANKAJ\AppData\Local\Programs\Opera\opera.exe",
    "tor": r"C:\Users\PANKAJ\OneDrive\Desktop\Tor Browser\Browser\firefox.exe",
    "tor browser": r"C:\Users\PANKAJ\OneDrive\Desktop\Tor Browser\Browser\firefox.exe",
}


class ToolTruth:
    """
    Detects when the user is asking for real-time data.
    Calls real tools if available, or returns honest denial.
    No guessing. No hallucination.
    """

    def __init__(self):
        self._time_patterns = [re.compile(p) for p in TIME_KEYWORDS]
        self._system_patterns = [re.compile(p) for p in SYSTEM_KEYWORDS]
        self._network_patterns = [re.compile(p) for p in NETWORK_KEYWORDS]
        self._process_patterns = [re.compile(p) for p in PROCESS_KEYWORDS]
        self._file_patterns = [re.compile(p) for p in FILE_INFO_KEYWORDS]
        self._sysutil_patterns = [re.compile(p) for p in SYSTEM_UTIL_KEYWORDS]
        self._wiki_patterns = [re.compile(p) for p in WIKI_KEYWORDS]
        self._file_check_patterns = [re.compile(p) for p in FILE_CHECK_KEYWORDS]
        self._path_patterns = [re.compile(p) for p in PATH_KEYWORDS]
        self._net_speed_patterns = [re.compile(p) for p in NETWORK_SPEED_KEYWORDS]
        self._temperature_patterns = [re.compile(p) for p in TEMPERATURE_KEYWORDS]

    def detect_tool_intent(self, user_input: str) -> dict | None:
        """
        Detect tool intent from user input. Rule-based, NOT LLM-based.

        Returns:
            {
                "tool": str,
                "confidence": float,
                "data": str,
                "real": bool,
            }
            or None if no tool intent detected.
        """
        text = user_input.strip()
        if not text:
            return None

        time_matches = sum(1 for p in self._time_patterns if p.search(text))
        system_matches = sum(1 for p in self._system_patterns if p.search(text))
        network_matches = sum(1 for p in self._network_patterns if p.search(text))
        process_matches = sum(1 for p in self._process_patterns if p.search(text))
        file_matches = sum(1 for p in self._file_patterns if p.search(text))
        sysutil_matches = sum(1 for p in self._sysutil_patterns if p.search(text))
        file_check_matches = sum(1 for p in self._file_check_patterns if p.search(text))
        path_matches = sum(1 for p in self._path_patterns if p.search(text))
        net_speed_matches = sum(1 for p in self._net_speed_patterns if p.search(text))
        temperature_matches = sum(1 for p in self._temperature_patterns if p.search(text))

        if time_matches > 0:
            location = _extract_location_from_query(text)
            if location:
                tz_result = get_time_for_location(location)
                if tz_result:
                    return {
                        "tool": "time",
                        "confidence": 0.95,
                        "data": tz_result,
                        "real": True,
                    }
                return None

            confidence = min(1.0, 0.7 + (time_matches * 0.15))
            return {
                "tool": "time",
                "confidence": confidence,
                "data": f"Current time: {get_time()} | Date: {get_date()}",
                "real": True,
            }

        if system_matches > 0:
            confidence = min(1.0, 0.7 + (system_matches * 0.15))
            if re.search(r"(?i)\b(battery|charge|power)\b", text):
                info = get_battery_info()
                if info:
                    return {"tool": "battery", "confidence": confidence, "data": info, "real": True}
                return {"tool": "battery", "confidence": confidence, "data": "I don't have battery monitoring access yet.", "real": False}
            info = get_system_info()
            if info:
                return {"tool": "system_info", "confidence": confidence, "data": info, "real": True}
            return {"tool": "system_info", "confidence": confidence, "data": "I don't have real-time system monitoring access yet. Install psutil to enable this.", "real": False}

        if network_matches > 0:
            if net_speed_matches > 0:
                confidence = min(1.0, 0.7 + (net_speed_matches * 0.15))
                info = get_network_speed()
                if info:
                    return {"tool": "network_speed", "confidence": confidence, "data": info, "real": True}
                return {"tool": "network_speed", "confidence": confidence, "data": "Network speed monitoring not available. Install psutil.", "real": False}
            confidence = min(1.0, 0.7 + (network_matches * 0.15))
            if re.search(r"(?i)\bping\b", text):
                host_match = re.search(r"ping\s+(\S+)", text, re.IGNORECASE)
                host = host_match.group(1) if host_match else "8.8.8.8"
                data = ping_host(host)
            else:
                data = get_network_info()
            return {"tool": "network_info", "confidence": confidence, "data": data, "real": True}

        if net_speed_matches > 0:
            confidence = min(1.0, 0.7 + (net_speed_matches * 0.15))
            info = get_network_speed()
            if info:
                return {"tool": "network_speed", "confidence": confidence, "data": info, "real": True}
            return {"tool": "network_speed", "confidence": confidence, "data": "Network speed monitoring not available. Install psutil.", "real": False}

        if process_matches > 0:
            confidence = min(1.0, 0.7 + (process_matches * 0.15))
            info = get_process_list()
            if info:
                return {"tool": "process_list", "confidence": confidence, "data": info, "real": True}
            return {"tool": "process_list", "confidence": confidence, "data": "Process monitoring not available. Install psutil.", "real": False}

        if file_matches > 0:
            confidence = min(1.0, 0.7 + (file_matches * 0.15))
            if re.search(r'(?i)\b(this|current|present)\s+(directory|folder|dir)\b', text):
                data = list_directory(".")
            else:
                _dir_patterns = [
                    r'(?:show|list|display)\s+(?:all\s+)?(\w+)\s+(?:directory|folder|files?|dir|contents)',
                    r'(?:list|show)\s+(?:all\s+)?(?:files?\s+)?(?:in|of|from)\s+["\']?(\w+)',
                    r'(?:list|show)\s+(?:all\s+)?files?\s+(\w+)\s*[.!?]?\s*$',
                ]
                skip_words = {"the", "this", "current", "my", "a", "all", "more"}
                dir_name = None
                for pat in _dir_patterns:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        candidate = m.group(1).strip().rstrip('.,;:!?')
                        if candidate.lower() not in skip_words:
                            dir_name = candidate
                            break

                resolved_path = None
                if dir_name:
                    resolved_path = _resolve_common_directory(dir_name)
                    if not resolved_path and Path(dir_name).is_dir():
                        resolved_path = dir_name

                if resolved_path:
                    data = list_directory(resolved_path)
                else:
                    path_match = re.search(r'(?:of|in|at|for)\s+["\']?([^\s"\']+)', text, re.IGNORECASE)
                    if path_match:
                        path = path_match.group(1).rstrip('.,;:!?')
                        if path.lower() in ("this", "current", "my", "the", "a"):
                            data = list_directory(".")
                        else:
                            rp = _resolve_common_directory(path)
                            if rp:
                                data = list_directory(rp)
                            elif Path(path).is_dir():
                                data = list_directory(path)
                            else:
                                data = get_file_info(path)
                    else:
                        data = list_directory(".")
            return {"tool": "file_info", "confidence": confidence, "data": data, "real": True}

        if file_check_matches > 0:
            confidence = min(1.0, 0.7 + (file_check_matches * 0.15))
            fn_match = re.search(r'(\S+\.\w{1,10})', text)
            filename = fn_match.group(1) if fn_match else None
            folder = None
            folder_m = re.search(r'\b(?:in|inside|from)\s+(?:the\s+)?["\']?(\w+)["\']?\s*(?:folder|directory)?[.!?]?\s*$', text, re.IGNORECASE)
            if folder_m:
                candidate = folder_m.group(1).lower()
                if candidate not in ("the", "this", "a", "folder", "directory"):
                    folder = folder_m.group(1)
            if filename:
                data = is_file_present(filename, folder)
                return {"tool": "file_check", "confidence": confidence, "data": data, "real": True}

        if path_matches > 0:
            confidence = min(1.0, 0.7 + (path_matches * 0.15))
            skip_words = {"the", "this", "my", "a", "me", "of", "to", "for", "show", "tell", "give", "path", "where", "is", "locate", "find", "folder", "directory"}
            folder_name = None
            m = re.search(r'\bpath\s+(?:to|of|for)\s+["\']?(\w+)', text, re.IGNORECASE)
            if m and m.group(1).lower() not in skip_words:
                folder_name = m.group(1)
            if not folder_name:
                m = re.search(r'\b(?:where\s+is|locate|find)\s+(?:my\s+)?(?:the\s+)?(\w+)', text, re.IGNORECASE)
                if m and m.group(1).lower() not in skip_words:
                    folder_name = m.group(1)
            if folder_name:
                data = resolve_folder_path(folder_name)
                return {"tool": "path_resolve", "confidence": confidence, "data": data, "real": True}

        if sysutil_matches > 0:
            confidence = min(1.0, 0.7 + (sysutil_matches * 0.15))
            if re.search(r"(?i)\b(uptime)\b", text):
                info = get_uptime()
                if info:
                    return {"tool": "uptime", "confidence": confidence, "data": info, "real": True}
                return {"tool": "uptime", "confidence": confidence, "data": "Uptime not available. Install psutil.", "real": False}
            if re.search(r"(?i)\b(disk|drive|space|storage)\b", text):
                info = get_disk_usage()
                if info:
                    return {"tool": "disk_usage", "confidence": confidence, "data": info, "real": True}
                return {"tool": "disk_usage", "confidence": confidence, "data": "Disk usage not available. Install psutil.", "real": False}
            data = get_os_info()
            return {"tool": "os_info", "confidence": confidence, "data": data, "real": True}

        if temperature_matches > 0:
            confidence = min(1.0, 0.7 + (temperature_matches * 0.15))
            info = get_temperature()
            if info:
                return {"tool": "temperature", "confidence": confidence, "data": info, "real": True}
            return {"tool": "temperature", "confidence": confidence, "data": "Temperature monitoring not available. Install psutil.", "real": False}

        wiki_matches = sum(1 for p in self._wiki_patterns if p.search(text))
        if wiki_matches > 0:
            topic = extract_wiki_topic(text)
            if topic:
                confidence = min(1.0, 0.6 + (wiki_matches * 0.15))
                result = wiki_search(topic)
                if result["found"]:
                    cache_tag = " (cached)" if result["cached"] else ""
                    data = f"📖 Wikipedia{cache_tag}: {result['summary'][:500]}"
                    if result["url"]:
                        data += f"\n🔗 {result['url']}"
                    return {"tool": "wikipedia", "confidence": confidence, "data": data, "real": True}
                elif result["suggestions"]:
                    data = f"No exact match for '{topic}'. Suggestions: {', '.join(result['suggestions'])}"
                    return {"tool": "wikipedia", "confidence": confidence, "data": data, "real": False}

        return None

    def build_tool_context(self, tool_result: dict) -> str:
        if tool_result["real"]:
            return f"\n## REAL-TIME TOOL DATA (VERIFIED)\n- {tool_result['data']}\n- This is REAL data from a tool. You may report it accurately."
        else:
            return f"\n## TOOL STATUS\n- {tool_result['data']}\n- Do NOT guess or fabricate this data. Report exactly what is stated above."

    def tool_available(self, name: str) -> bool:
        return AVAILABLE_TOOLS.get(name, False)

    def list_tools(self) -> dict:
        return AVAILABLE_TOOLS.copy()
