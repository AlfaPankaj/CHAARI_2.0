# CHAARI 2.0 — Dell executor/application_module.py — APPLICATION Capability
# ═══════════════════════════════════════════════════════════
# Handles: LAUNCH, TERMINATE, MINIMIZE, MAXIMIZE, RESTORE
#
# Uses hardcoded APP_WHITELIST — no arbitrary process launching.
# Window management via ctypes user32.dll.
# ═══════════════════════════════════════════════════════════

import os
import subprocess
import ctypes
import ctypes.wintypes

from chaari_dell.models.packet_models import ExecutionResult

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# ── Windows ShowWindow constants ──
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9

# ── APP WHITELIST (same as ASUS side) ──
APP_WHITELIST: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "vscode": r"C:\Users\PANKAJ\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "whatsapp": "whatsapp:",
    "telegram": "tg:",
    "word": "winword",
    "excel": "excel",
    "settings": "ms-settings:",
}

PROCESS_NAMES: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "CalculatorApp.exe",
    "calc": "CalculatorApp.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "vscode": "Code.exe",
    "whatsapp": "WhatsApp.exe",
    "telegram": "Telegram.exe",
}


class ApplicationModule:
    """
    Capability module for APPLICATION group.
    
    Supported intents:
        - APPLICATION.LIFECYCLE.LAUNCH     → open app from whitelist
        - APPLICATION.LIFECYCLE.TERMINATE  → close app
        - APPLICATION.WINDOW.MINIMIZE     → minimize window
        - APPLICATION.WINDOW.MAXIMIZE     → maximize window
        - APPLICATION.WINDOW.RESTORE      → restore window
    """

    SUPPORTED_INTENTS = {
        "APPLICATION.LIFECYCLE.LAUNCH",
        "APPLICATION.LIFECYCLE.TERMINATE",
        "APPLICATION.WINDOW.MINIMIZE",
        "APPLICATION.WINDOW.MAXIMIZE",
        "APPLICATION.WINDOW.RESTORE",
    }

    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        context = context or {}

        if intent not in self.SUPPORTED_INTENTS:
            return ExecutionResult(intent=intent, status="rejected", error=f"Not supported: {intent}")

        app_name = context.get("app_name", "").lower()
        if not app_name:
            return ExecutionResult(intent=intent, status="failure", error="Missing 'app_name' in context")

        if intent == "APPLICATION.LIFECYCLE.LAUNCH":
            return self._launch(app_name)
        elif intent == "APPLICATION.LIFECYCLE.TERMINATE":
            return self._terminate(app_name)
        elif intent in ("APPLICATION.WINDOW.MINIMIZE", "APPLICATION.WINDOW.MAXIMIZE", "APPLICATION.WINDOW.RESTORE"):
            action_map = {
                "APPLICATION.WINDOW.MINIMIZE": SW_MINIMIZE,
                "APPLICATION.WINDOW.MAXIMIZE": SW_MAXIMIZE,
                "APPLICATION.WINDOW.RESTORE": SW_RESTORE,
            }
            return self._window_action(app_name, action_map[intent], intent)

        return ExecutionResult(intent=intent, status="failure", error="Unhandled")

    def _launch(self, app_name: str) -> ExecutionResult:
        """Launch an app from whitelist."""
        cmd = APP_WHITELIST.get(app_name)
        if not cmd:
            return ExecutionResult(
                intent="APPLICATION.LIFECYCLE.LAUNCH",
                status="failure",
                error=f"App not in whitelist: {app_name}",
            )

        try:
            if cmd.endswith(":"):
                os.startfile(cmd)
            elif os.path.exists(cmd):
                subprocess.Popen([cmd], shell=False)
            else:
                subprocess.Popen(cmd, shell=True)

            return ExecutionResult(
                intent="APPLICATION.LIFECYCLE.LAUNCH",
                status="success",
                output=f"Launched: {app_name}",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(
                intent="APPLICATION.LIFECYCLE.LAUNCH",
                status="failure",
                error=str(e),
            )

    def _terminate(self, app_name: str) -> ExecutionResult:
        """Terminate app by process name."""
        if not PSUTIL_AVAILABLE:
            return ExecutionResult(intent="APPLICATION.LIFECYCLE.TERMINATE", status="failure", error="psutil not available")

        proc_name = PROCESS_NAMES.get(app_name, f"{app_name}.exe")
        killed = 0
        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] and proc.info['name'].lower() == proc_name.lower():
                    proc.terminate()
                    killed += 1
            if killed:
                return ExecutionResult(
                    intent="APPLICATION.LIFECYCLE.TERMINATE",
                    status="success",
                    output=f"Terminated {killed} instance(s) of {app_name}",
                    exit_code=0,
                )
            return ExecutionResult(
                intent="APPLICATION.LIFECYCLE.TERMINATE",
                status="failure",
                error=f"No running instances of {app_name}",
            )
        except Exception as e:
            return ExecutionResult(intent="APPLICATION.LIFECYCLE.TERMINATE", status="failure", error=str(e))

    def _window_action(self, app_name: str, action: int, intent: str) -> ExecutionResult:
        """Minimize/Maximize/Restore window."""
        if not PSUTIL_AVAILABLE:
            return ExecutionResult(intent=intent, status="failure", error="psutil not available")

        proc_name = PROCESS_NAMES.get(app_name, f"{app_name}.exe")
        
        try:
            # Find PIDs for the process
            pids = set()
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] and proc.info['name'].lower() == proc_name.lower():
                    pids.add(proc.info['pid'])

            if not pids:
                return ExecutionResult(intent=intent, status="failure", error=f"No running instances of {app_name}")

            # Find windows belonging to those PIDs
            user32 = ctypes.windll.user32
            found = False

            def enum_callback(hwnd, _):
                nonlocal found
                if user32.IsWindowVisible(hwnd):
                    pid = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pids:
                        user32.ShowWindow(hwnd, action)
                        found = True
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            if found:
                action_name = {SW_MINIMIZE: "Minimized", SW_MAXIMIZE: "Maximized", SW_RESTORE: "Restored"}.get(action, "Modified")
                return ExecutionResult(intent=intent, status="success", output=f"{action_name} {app_name}", exit_code=0)
            return ExecutionResult(intent=intent, status="failure", error=f"No visible window for {app_name}")

        except Exception as e:
            return ExecutionResult(intent=intent, status="failure", error=str(e))
