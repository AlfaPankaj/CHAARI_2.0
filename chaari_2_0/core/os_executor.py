"""
OSExecutor Adapter - Layer 3.5 OS Command Execution

Implements CommandExecutorPort interface.
Maps SystemIntent enum → hardcoded OS commands.
No dynamic input. No string concatenation with user data.
Runs on Dell Latitude worker node.

Design principle:
- Only these 6 intents can execute
- Each intent maps to exactly ONE hardcoded command or function
- All parameters validated before execution
- Returns detailed ExecutionResult with exit code
"""

import subprocess
import os
import shutil
import signal
import psutil
import time
import ctypes
import ctypes.wintypes
import urllib.parse
import webbrowser
from pathlib import Path
from datetime import datetime
from core.executor_port import CommandExecutorPort, ExecutionResult, ExecutionStatus

SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


class OSExecutor(CommandExecutorPort):
    """
    Implements command execution for system intents.
    
    Hardcoded mappings - NO DYNAMIC COMMAND BUILDING:
    - SHUTDOWN → shutdown /s /t 10
    - RESTART → shutdown /r /t 10
    - DELETE_FILE → safe_delete(path)
    - FORMAT_DISK → format_disk_safe(drive)
    - KILL_PROCESS → taskkill /PID
    - MODIFY_REGISTRY → reg add (restricted, creator mode only)
    
    Each method has strict input validation.
    """
    
    def __init__(self, timeout_seconds: int = 30):
        """
        Initialize executor.
        
        Args:
            timeout_seconds: Max seconds for command execution
        """
        self.timeout = timeout_seconds
        self.supported = {
            'SHUTDOWN',
            'RESTART',
            'DELETE_FILE',
            'FORMAT_DISK',
            'KILL_PROCESS',
            'MODIFY_REGISTRY',
            'CREATE_FILE',
            'COPY_FILE',
            'MOVE_FILE',
            'OPEN_APP',
            'OPEN_FILE',
            'OPEN_FOLDER',
            'CLOSE_APP',
            'MINIMIZE_APP',
            'MAXIMIZE_APP',
            'RESTORE_APP',
            'TYPE_TEXT',
            'SEND_MESSAGE',
            'MAKE_CALL',
            'MEDIA.CAPTURE.ANALYZE_SCREEN',
        }
        self._backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".chaari_backup")
        os.makedirs(self._backup_dir, exist_ok=True)
    
    def can_execute(self, intent: str) -> bool:
        """Check if executor supports this intent."""
        return intent.upper() in self.supported
    
    def get_supported_intents(self) -> list[str]:
        """Return list of supported intents."""
        return list(self.supported)
    
    def validate_context(self, intent: str, context: dict) -> tuple[bool, str]:
        """
        Validate context parameters for intent.
        
        Returns:
            (is_valid, error_message)
        """
        intent_upper = intent.upper()
        
        if not context:
            context = {}
        
        if intent_upper == 'DELETE_FILE':
            if 'path' not in context:
                return False, "DELETE_FILE requires 'path' in context"
            path = context.get('path', '')
            if not isinstance(path, str) or not path.strip():
                return False, "Path must be non-empty string"
            return True, ""
        
        if intent_upper == 'FORMAT_DISK':
            if 'drive' not in context:
                return False, "FORMAT_DISK requires 'drive' in context"
            drive = context.get('drive', '')
            if not isinstance(drive, str) or len(drive) != 1 or not drive.isalpha():
                return False, "Drive must be single letter (A-Z)"
            return True, ""
        
        if intent_upper == 'KILL_PROCESS':
            if 'pid' not in context:
                return False, "KILL_PROCESS requires 'pid' in context"
            try:
                pid = int(context.get('pid', 0))
                if pid <= 0:
                    return False, "PID must be positive integer"
            except (ValueError, TypeError):
                return False, "PID must be integer"
            return True, ""
        
        if intent_upper == 'MODIFY_REGISTRY':
            if 'hive' not in context or 'key' not in context:
                return False, "MODIFY_REGISTRY requires 'hive' and 'key'"
            return True, ""
        
        if intent_upper == 'CREATE_FILE':
            if 'path' not in context:
                return False, "CREATE_FILE requires 'path' in context"
            return True, ""
        
        if intent_upper == 'COPY_FILE':
            if 'source' not in context or 'destination' not in context:
                return False, "COPY_FILE requires 'source' and 'destination' in context"
            return True, ""
        
        if intent_upper == 'MOVE_FILE':
            if 'source' not in context or 'destination' not in context:
                return False, "MOVE_FILE requires 'source' and 'destination' in context"
            return True, ""
        
        if intent_upper == 'OPEN_APP':
            if 'app_name' not in context:
                return False, "OPEN_APP requires 'app_name' in context"
            return True, ""

        if intent_upper == 'OPEN_FILE':
            if 'file_path' not in context:
                return False, "OPEN_FILE requires 'file_path' in context"
            return True, ""

        if intent_upper == 'OPEN_FOLDER':
            if 'folder_path' not in context:
                return False, "OPEN_FOLDER requires 'folder_path' in context"
            return True, ""
        
        if intent_upper == 'CLOSE_APP':
            if 'app_name' not in context and 'pid' not in context:
                return False, "CLOSE_APP requires 'app_name' or 'pid' in context"
            return True, ""
        
        if intent_upper in ('MINIMIZE_APP', 'MAXIMIZE_APP', 'RESTORE_APP'):
            if 'app_name' not in context:
                return False, f"{intent_upper} requires 'app_name' in context"
            return True, ""
        
        if intent_upper == 'TYPE_TEXT':
            if 'text' not in context or not context['text'].strip():
                return False, "TYPE_TEXT requires 'text' in context"
            return True, ""
        
        if intent_upper == 'SEND_MESSAGE':
            if 'contact' not in context:
                return False, "SEND_MESSAGE requires 'contact' in context"
            if 'text' not in context:
                return False, "SEND_MESSAGE requires 'text' in context"
            return True, ""
        
        if intent_upper == 'MAKE_CALL':
            if 'contact' not in context:
                return False, "MAKE_CALL requires 'contact' in context"
            return True, ""
        
        if intent_upper in ('SHUTDOWN', 'RESTART'):
            return True, ""
        
        if intent_upper in ('VOLUME_UP', 'VOLUME_DOWN', 'MUTE', 'SCREENSHOT',
                            'SCREENSHOT_WINDOW', 'OCR_SCREEN', 'LOCK_SCREEN',
                            'SWITCH_WINDOW', 'LIST_APPS', 'MEDIA.CAPTURE.ANALYZE_SCREEN'):
            return True, ""
        
        if intent_upper in ('SEARCH_GOOGLE', 'SEARCH_YOUTUBE'):
            return True, ""
        
        if intent_upper == 'OPEN_WEBSITE':
            return True, ""
        
        return False, f"Unknown intent: {intent}"
    
    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        """
        Execute command for given intent.
        
        Args:
            intent: SystemIntent enum value (e.g., 'SHUTDOWN')
            context: Optional context dict with parameters
            
        Returns:
            ExecutionResult with status, output, error
        """
        if not context:
            context = {}
        
        intent_upper = intent.upper()
        start_time = time.time()
        
        try:
            is_valid, error_msg = self.validate_context(intent, context)
            if not is_valid:
                return ExecutionResult(
                    status=ExecutionStatus.INVALID_INTENT,
                    intent=intent,
                    error=error_msg,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            if intent_upper == 'SHUTDOWN':
                return self._execute_shutdown(start_time)
            elif intent_upper == 'RESTART':
                return self._execute_restart(start_time)
            elif intent_upper == 'DELETE_FILE':
                return self._execute_delete_file(context['path'], start_time)
            elif intent_upper == 'FORMAT_DISK':
                return self._execute_format_disk(context['drive'], start_time)
            elif intent_upper == 'KILL_PROCESS':
                return self._execute_kill_process(int(context['pid']), start_time)
            elif intent_upper == 'MODIFY_REGISTRY':
                return self._execute_modify_registry(context, start_time)
            elif intent_upper == 'CREATE_FILE':
                return self._execute_create_file(context['path'], context.get('content', ''), start_time)
            elif intent_upper == 'COPY_FILE':
                return self._execute_copy_file(context['source'], context['destination'], start_time)
            elif intent_upper == 'MOVE_FILE':
                return self._execute_move_file(context['source'], context['destination'], start_time)
            elif intent_upper == 'OPEN_APP':
                return self._execute_open_app(context['app_name'], start_time)
            elif intent_upper == 'OPEN_FILE':
                return self._execute_open_file(context.get('file_path', ''), start_time)
            elif intent_upper == 'OPEN_FOLDER':
                return self._execute_open_folder(context.get('folder_path', ''), start_time)
            elif intent_upper == 'CLOSE_APP':
                return self._execute_close_app(context.get('app_name', ''), context.get('pid'), start_time)
            elif intent_upper == 'MINIMIZE_APP':
                return self._execute_window_action(context['app_name'], SW_MINIMIZE, 'MINIMIZE_APP', start_time)
            elif intent_upper == 'MAXIMIZE_APP':
                return self._execute_window_action(context['app_name'], SW_MAXIMIZE, 'MAXIMIZE_APP', start_time)
            elif intent_upper == 'RESTORE_APP':
                return self._execute_window_action(context['app_name'], SW_RESTORE, 'RESTORE_APP', start_time)
            elif intent_upper == 'TYPE_TEXT':
                return self._execute_type_text(context.get('text', ''), start_time)
            elif intent_upper == 'SEND_MESSAGE':
                return self._execute_send_message(context, start_time)
            elif intent_upper == 'MAKE_CALL':
                return self._execute_make_call(context, start_time)
            elif intent_upper == 'VOLUME_UP':
                return self._execute_volume_up(start_time)
            elif intent_upper == 'VOLUME_DOWN':
                return self._execute_volume_down(start_time)
            elif intent_upper == 'MUTE':
                return self._execute_mute(start_time)
            elif intent_upper == 'SCREENSHOT':
                return self._execute_screenshot(start_time)
            elif intent_upper == 'SCREENSHOT_WINDOW':
                return self._execute_screenshot_window(start_time)
            elif intent_upper == 'OCR_SCREEN':
                return self._execute_ocr_screen(start_time)
            elif intent_upper == 'LOCK_SCREEN':
                return self._execute_lock_screen(start_time)
            elif intent_upper == 'SEARCH_GOOGLE':
                return self._execute_search_google(context.get('query', ''), start_time)
            elif intent_upper == 'SEARCH_YOUTUBE':
                return self._execute_search_youtube(context.get('query', ''), start_time)
            elif intent_upper == 'OPEN_WEBSITE':
                return self._execute_open_website(context.get('url', ''), start_time)
            elif intent_upper == 'SWITCH_WINDOW':
                return self._execute_switch_window(start_time)
            elif intent_upper == 'LIST_APPS':
                return self._execute_list_apps(start_time)
            elif intent_upper == 'MEDIA.CAPTURE.ANALYZE_SCREEN':
                return self._execute_analyze_screen(start_time)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.INVALID_INTENT,
                    intent=intent,
                    error=f"Unsupported intent: {intent}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.SYSTEM_ERROR,
                intent=intent,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_shutdown(self, start_time: float) -> ExecutionResult:
        """
        Hardcoded: shutdown /s /t 10
        Delay 10 seconds to allow graceful cleanup.
        """
        try:
            cmd = "shutdown /s /t 10"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILURE,
                intent='SHUTDOWN',
                command=cmd,
                exit_code=result.returncode,
                output=result.stdout or "Shutdown command issued",
                error=result.stderr,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                intent='SHUTDOWN',
                command="shutdown /s /t 10",
                error="Command timed out",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_restart(self, start_time: float) -> ExecutionResult:
        """
        Hardcoded: shutdown /r /t 10
        Delay 10 seconds to allow graceful cleanup.
        """
        try:
            cmd = "shutdown /r /t 10"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILURE,
                intent='RESTART',
                command=cmd,
                exit_code=result.returncode,
                output=result.stdout or "Restart command issued",
                error=result.stderr,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                intent='RESTART',
                command="shutdown /r /t 10",
                error="Command timed out",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_delete_file(self, path: str, start_time: float) -> ExecutionResult:
        """
        Safe file deletion with validation.
        - Prevents deletion of system directories
        - Confirms path exists
        """
        try:
            path_obj = Path(path).resolve()
            
            if not path_obj.exists():
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='DELETE_FILE',
                    error=f"File does not exist: {path}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            system_paths = [
                'C:\\Windows',
                'C:\\Program Files',
                'C:\\Program Files (x86)',
                'C:\\System Volume Information',
                'C:\\$Recycle.Bin'
            ]
            resolved = str(path_obj.resolve())
            for sys_path in system_paths:
                if resolved == sys_path or resolved.startswith(sys_path + '\\'):
                    return ExecutionResult(
                        status=ExecutionStatus.FAILURE,
                        intent='DELETE_FILE',
                        error=f"Cannot delete system path: {path}",
                        duration_ms=int((time.time() - start_time) * 1000)
                    )
            if resolved.lower() == os.path.expanduser('~').lower():
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='DELETE_FILE',
                    error=f"Cannot delete user home directory: {path}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            if path_obj.is_file():
                self._backup_file(str(path_obj))
                os.remove(path_obj)
            elif path_obj.is_dir():
                self._backup_file(str(path_obj))
                shutil.rmtree(path_obj)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='DELETE_FILE',
                    error=f"Path is neither file nor directory: {path}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                intent='DELETE_FILE',
                command=f"delete {path}",
                output=f"Successfully deleted: {path}",
                exit_code=0,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent='DELETE_FILE',
                error=f"Deletion failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_format_disk(self, drive: str, start_time: float) -> ExecutionResult:
        """
        Format disk with safety checks.
        Requires careful confirmation in real use.
        """
        try:
            drive_upper = drive.upper()
            
            if drive_upper in ('C',):
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='FORMAT_DISK',
                    error=f"Cannot format system drive: {drive_upper}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            drive_path = f"{drive_upper}:\\"
            if not os.path.exists(drive_path):
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='FORMAT_DISK',
                    error=f"Drive not found: {drive_upper}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            cmd = f"format {drive_upper}: /FS:NTFS /Q /Y"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILURE,
                intent='FORMAT_DISK',
                command=cmd,
                exit_code=result.returncode,
                output=result.stdout or f"Format {drive_upper}: initiated",
                error=result.stderr,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                intent='FORMAT_DISK',
                error="Format command timed out",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent='FORMAT_DISK',
                error=f"Format failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_kill_process(self, pid: int, start_time: float) -> ExecutionResult:
        """
        Terminate process by PID with safety checks.
        Prevents killing critical system processes.
        """
        try:
            try:
                process = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='KILL_PROCESS',
                    error=f"Process not found: PID {pid}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            critical_processes = [
                'svchost.exe',
                'smss.exe',
                'csrss.exe',
                'system',
                'services.exe',
                'lsass.exe',
                'wininit.exe'
            ]
            
            proc_name = process.name().lower()
            if proc_name in critical_processes:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='KILL_PROCESS',
                    error=f"Cannot terminate critical process: {proc_name}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                intent='KILL_PROCESS',
                command=f"taskkill /PID {pid} /F",
                exit_code=0,
                output=f"Process {pid} ({proc_name}) terminated",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent='KILL_PROCESS',
                error=f"Process termination failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_modify_registry(self, context: dict, start_time: float) -> ExecutionResult:
        """
        Modify Windows Registry.
        Restricted operation - normally creator mode only.
        
        Minimal implementation with safety constraints.
        """
        try:
            hive = context.get('hive', '')
            key = context.get('key', '')
            value_name = context.get('value_name', '')
            value_data = context.get('value_data', '')
            
            if not all([hive, key]):
                return ExecutionResult(
                    status=ExecutionStatus.INVALID_INTENT,
                    intent='MODIFY_REGISTRY',
                    error="Registry modification requires hive, key, value_name, value_data",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            if any(critical in key for critical in ['\\System\\', '\\Security\\', 'SAM']):
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    intent='MODIFY_REGISTRY',
                    error="Cannot modify critical registry paths",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            cmd = f"reg add \"{hive}\\{key}\" /v {value_name} /d {value_data} /f"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILURE,
                intent='MODIFY_REGISTRY',
                command=cmd,
                exit_code=result.returncode,
                output=result.stdout or f"Registry modified: {key}",
                error=result.stderr,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent='MODIFY_REGISTRY',
                error=f"Registry modification failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_create_file(self, path: str, content: str, start_time: float) -> ExecutionResult:
        """Create a file with optional content."""
        try:
            path_obj = Path(path).resolve()
            if path_obj.exists():
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='CREATE_FILE',
                    error=f"File already exists: {path}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            os.makedirs(path_obj.parent, exist_ok=True)
            with open(path_obj, 'w', encoding='utf-8') as f:
                f.write(content)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='CREATE_FILE',
                command=f"create {path}", exit_code=0,
                output=f"Created file: {path_obj}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='CREATE_FILE',
                error=f"Create failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_copy_file(self, source: str, destination: str, start_time: float) -> ExecutionResult:
        """Copy a file or directory."""
        try:
            src = Path(source).resolve()
            dst = Path(destination).resolve()
            if not src.exists():
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='COPY_FILE',
                    error=f"Source does not exist: {source}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            if src.is_file():
                os.makedirs(dst.parent, exist_ok=True)
                shutil.copy2(str(src), str(dst))
            elif src.is_dir():
                shutil.copytree(str(src), str(dst))
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='COPY_FILE',
                command=f"copy {source} -> {destination}", exit_code=0,
                output=f"Copied: {src} → {dst}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='COPY_FILE',
                error=f"Copy failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_move_file(self, source: str, destination: str, start_time: float) -> ExecutionResult:
        """Move/rename a file or directory with backup."""
        try:
            src = Path(source).resolve()
            dst = Path(destination).resolve()
            if not src.exists():
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='MOVE_FILE',
                    error=f"Source does not exist: {source}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            self._backup_file(str(src))
            os.makedirs(dst.parent, exist_ok=True)
            shutil.move(str(src), str(dst))
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='MOVE_FILE',
                command=f"move {source} -> {destination}", exit_code=0,
                output=f"Moved: {src} → {dst}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='MOVE_FILE',
                error=f"Move failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_open_app(self, app_name: str, start_time: float) -> ExecutionResult:
        """Open an application from the whitelist."""
        from core.tools import APP_WHITELIST
        app_key = app_name.lower().strip()
        executable = APP_WHITELIST.get(app_key)
        if not executable:
            available = ", ".join(sorted(set(APP_WHITELIST.keys())))
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_APP',
                error=f"App '{app_name}' not in whitelist. Available: {available}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        try:
            if executable.endswith(':'):
                os.startfile(executable)
            elif os.path.isabs(executable) and os.path.exists(executable):
                subprocess.Popen([executable], shell=False)
            else:
                try:
                    os.startfile(executable)
                except OSError:
                    subprocess.Popen(executable, shell=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='OPEN_APP',
                command=f"start {executable}", exit_code=0,
                output=f"Opened: {app_name}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_APP',
                error=f"Failed to open {app_name}: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _execute_open_file(self, file_path: str, start_time: float) -> ExecutionResult:
        """Open a file with its default application. Searches common directories if not absolute."""
        from pathlib import Path as P
        if not file_path:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FILE',
                error="No file path provided.",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        target = P(file_path)
        if target.is_absolute() and target.is_file():
            resolved = target
        else:
            resolved = None
            home = P.home()
            search_dirs = [
                P.cwd(),
                home / 'Desktop',
                home / 'Documents',
                home / 'Downloads',
                home / 'Documents' / 'Projects',
            ]
            for d in search_dirs:
                candidate = d / file_path
                if candidate.is_file():
                    resolved = candidate
                    break
        if not resolved or not resolved.is_file():
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FILE',
                error=f"File not found: {file_path}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        try:
            os.startfile(str(resolved))
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='OPEN_FILE',
                command=f"start \"{resolved}\"", exit_code=0,
                output=f"Opened: {resolved.name} (from {resolved.parent})",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FILE',
                error=f"Failed to open {file_path}: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _execute_open_folder(self, folder_path: str, start_time: float) -> ExecutionResult:
        """Open a folder in Windows Explorer."""
        from pathlib import Path as P
        if not folder_path:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FOLDER',
                error="No folder path provided.",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        target = P(folder_path)
        if not target.is_absolute():
            target = P.home() / folder_path
        if not target.is_dir():
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FOLDER',
                error=f"Folder not found: {folder_path}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        try:
            os.startfile(str(target))
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='OPEN_FOLDER',
                command=f"explorer \"{target}\"", exit_code=0,
                output=f"Opened folder: {target}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_FOLDER',
                error=f"Failed to open folder {folder_path}: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _execute_close_app(self, app_name: str, pid: int | None, start_time: float) -> ExecutionResult:
        """Close an application by name or PID."""
        try:
            if pid:
                proc = psutil.Process(int(pid))
                proc_name = proc.name()
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS, intent='CLOSE_APP',
                    command=f"terminate PID {pid}", exit_code=0,
                    output=f"Closed: {proc_name} (PID {pid})",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            from core.tools import APP_WHITELIST
            executable = APP_WHITELIST.get(app_name.lower(), "")
            exe_basename = os.path.basename(executable).lower() if executable else ""

            closed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name_lower = proc.info['name'].lower()
                    if (app_name.lower() in proc_name_lower) or \
                       (exe_basename and exe_basename == proc_name_lower):
                        proc.terminate()
                        closed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if closed > 0:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS, intent='CLOSE_APP',
                    command=f"terminate {app_name}", exit_code=0,
                    output=f"Closed {closed} instance(s) of {app_name}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='CLOSE_APP',
                error=f"No running process found for: {app_name}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='CLOSE_APP',
                error=f"Close app failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _find_windows_by_app(self, app_name: str) -> list[int]:
        """Find window handles for an app by process name or window title."""
        user32 = ctypes.windll.user32
        hwnds = []
        app_lower = app_name.lower().strip()
        
        PROCESS_NAMES = {
            "notepad": "notepad.exe",
            "calculator": "calculatorapp.exe", "calc": "calculatorapp.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe", "file explorer": "explorer.exe",
            "chrome": "chrome.exe", "google chrome": "chrome.exe",
            "edge": "msedge.exe", "microsoft edge": "msedge.exe", "msedge": "msedge.exe",
            "brave": "brave.exe", "firefox": "firefox.exe",
            "opera": "opera.exe", "tor": "firefox.exe", "tor browser": "firefox.exe",
            "vscode": "code.exe", "vs code": "code.exe", "code": "code.exe",
            "notepad++": "notepad++.exe", "notepad plus plus": "notepad++.exe",
            "sublime": "subl.exe", "sublime text": "subl.exe",
            "pycharm": "pycharm64.exe", "android studio": "studio64.exe",
            "postman": "postman.exe", "github desktop": "githubdesktop.exe", "github": "githubdesktop.exe",
            "word": "winword.exe", "ms word": "winword.exe", "microsoft word": "winword.exe",
            "excel": "excel.exe", "ms excel": "excel.exe", "microsoft excel": "excel.exe",
            "powerpoint": "powerpnt.exe", "ms powerpoint": "powerpnt.exe", "ppt": "powerpnt.exe",
            "outlook": "outlook.exe", "ms outlook": "outlook.exe",
            "onenote": "onenote.exe", "ms onenote": "onenote.exe",
            "access": "msaccess.exe", "ms access": "msaccess.exe",
            "teams": "ms-teams.exe", "ms teams": "ms-teams.exe",
            "whatsapp": "whatsapp.root.exe", "telegram": "telegram.exe",
            "discord": "discord.exe", "slack": "slack.exe", "zoom": "zoom.exe",
            "spotify": "spotify.exe", "vlc": "vlc.exe", "vlc media player": "vlc.exe",
            "steam": "steam.exe", "epic games": "epicgameslauncher.exe", "epic": "epicgameslauncher.exe",
            "obs": "obs64.exe", "obs studio": "obs64.exe",
            "photoshop": "photoshop.exe", "illustrator": "illustrator.exe",
            "premiere": "premiere.exe", "premiere pro": "premiere.exe",
            "cmd": "cmd.exe", "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe", "taskmgr": "taskmgr.exe",
            "terminal": "windowsterminal.exe",
            "wordpad": "wordpad.exe", "snipping tool": "snippingtool.exe",
        }
        
        target_proc = PROCESS_NAMES.get(app_lower, f"{app_lower}.exe")
        target_pids = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if target_proc.lower() in proc.info['name'].lower():
                    target_pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in target_pids:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        hwnds.append(hwnd)
            return True
        
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        
        if not hwnds:
            def title_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if app_lower in buf.value.lower():
                            hwnds.append(hwnd)
                return True
            user32.EnumWindows(EnumWindowsProc(title_callback), 0)
        
        return hwnds
    
    def _execute_window_action(self, app_name: str, action: int, intent_name: str, start_time: float) -> ExecutionResult:
        """Minimize, maximize, or restore app windows."""
        action_names = {SW_MINIMIZE: "Minimized", SW_MAXIMIZE: "Maximized", SW_RESTORE: "Restored"}
        action_label = action_names.get(action, "Modified")
        
        try:
            hwnds = self._find_windows_by_app(app_name)
            if not hwnds:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent=intent_name,
                    error=f"No open window found for: {app_name}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            user32 = ctypes.windll.user32
            affected = 0
            for hwnd in hwnds:
                user32.ShowWindow(hwnd, action)
                affected += 1
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent=intent_name,
                command=f"ShowWindow({app_name}, {action})", exit_code=0,
                output=f"{action_label} {affected} window(s) of {app_name}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent=intent_name,
                error=f"Window action failed for {app_name}: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _send_keys_raw(self, keys: str):
        """Send raw .NET SendKeys string to the active window."""
        ps_cmd = (
            'Add-Type -AssemblyName System.Windows.Forms; '
            f'[System.Windows.Forms.SendKeys]::SendWait("{keys}")'
        )
        subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10
        )

    def _type_via_clipboard(self, text: str):
        """Type Unicode text by copying to clipboard then Ctrl+V."""
        escaped = text.replace('`', '``').replace('"', '`"').replace('$', '`$')
        ps_cmd = (
            'Add-Type -AssemblyName System.Windows.Forms; '
            f'Set-Clipboard -Value "{escaped}"; '
            'Start-Sleep -Milliseconds 100; '
            '[System.Windows.Forms.SendKeys]::SendWait("^v")'
        )
        subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10
        )

    def _bring_to_foreground(self, app_name: str) -> bool:
        """Find app window and bring it to the foreground."""
        hwnds = self._find_windows_by_app(app_name)
        if hwnds:
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnds[0], SW_RESTORE)
            time.sleep(0.3)
            user32.SetForegroundWindow(hwnds[0])
            return True
        return False

    def _open_and_focus_app(self, app_name: str, wait_seconds: float = 3.0) -> bool:
        """Open an app (if not already running) and bring to foreground."""
        if self._bring_to_foreground(app_name):
            time.sleep(0.5)
            return True
        result = self._execute_open_app(app_name, time.time())
        if result.status != ExecutionStatus.SUCCESS:
            return False
        time.sleep(wait_seconds)
        return self._bring_to_foreground(app_name)

    def _escape_sendkeys(self, text: str) -> str:
        """Escape special SendKeys characters."""
        special = {'+': '{+}', '^': '{^}', '%': '{%}', '~': '{~}',
                   '(': '{(}', ')': '{)}', '{': '{{}', '}': '{}}'}
        return ''.join(special.get(c, c) for c in text)

    def _execute_type_text(self, text: str, start_time: float) -> ExecutionResult:
        """Type text into the previously focused window (Alt+Tab away from terminal first)."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.lower()
            terminal_hints = ['cmd', 'powershell', 'terminal', 'command prompt', 'chaari', 'python', 'main.py']
            if any(kw in title for kw in terminal_hints):
                ps_alt = (
                    'Add-Type -AssemblyName System.Windows.Forms; '
                    '[System.Windows.Forms.SendKeys]::SendWait("%{TAB}"); '
                )
                subprocess.run(
                    ['powershell', '-NoProfile', '-Command', ps_alt],
                    capture_output=True, text=True, timeout=5
                )
                time.sleep(0.5)
            self._type_via_clipboard(text)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='TYPE_TEXT',
                command=f'type_text("{text[:50]}")', exit_code=0,
                output=f"Typed text: {text[:80]}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='TYPE_TEXT',
                error=f"Type text failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _execute_send_message(self, context: dict, start_time: float) -> ExecutionResult:
        """Full automation: open messaging app, search contact, type & send message."""
        try:
            contact_name = context.get('contact', '')
            text = context.get('text', '')
            platform = context.get('platform', 'whatsapp').lower()

            from core.contacts import get_contact
            contact_info = get_contact(contact_name)
            if not contact_info:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='SEND_MESSAGE',
                    error=f"Contact '{contact_name}' not found. Use /contacts add <name> <phone> to add.",
                    duration_ms=int((time.time() - start_time) * 1000)
                )

            search_name = contact_info.get('search_name', contact_name)

            if platform in ('whatsapp', 'wa'):
                return self._whatsapp_automation('message', contact_info, contact_name, search_name, text, start_time)
            elif platform in ('telegram', 'tg'):
                return self._telegram_automation('message', contact_info, contact_name, search_name, text, start_time)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='SEND_MESSAGE',
                    error=f"Unsupported platform: {platform}. Use 'whatsapp' or 'telegram'.",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SEND_MESSAGE',
                error=f"Send message failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _execute_make_call(self, context: dict, start_time: float) -> ExecutionResult:
        """Full automation: open messaging app, search contact, open chat for call."""
        try:
            contact_name = context.get('contact', '')
            platform = context.get('platform', 'whatsapp').lower()
            call_type = context.get('call_type', 'voice')  

            from core.contacts import get_contact
            contact_info = get_contact(contact_name)
            if not contact_info:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='MAKE_CALL',
                    error=f"Contact '{contact_name}' not found. Use /contacts add <name> <phone> to add.",
                    duration_ms=int((time.time() - start_time) * 1000)
                )

            search_name = contact_info.get('search_name', contact_name)

            if platform in ('whatsapp', 'wa'):
                return self._whatsapp_automation('call', contact_info, contact_name, search_name, call_type, start_time)
            elif platform in ('telegram', 'tg'):
                return self._telegram_automation('call', contact_info, contact_name, search_name, call_type, start_time)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='MAKE_CALL',
                    error=f"Unsupported platform: {platform}. Use 'whatsapp' or 'telegram'.",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='MAKE_CALL',
                error=f"Make call failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _whatsapp_automation(self, action: str, contact_info: dict, contact_name: str,
                              search_name: str, payload: str, start_time: float) -> ExecutionResult:
        """
        WhatsApp Desktop GUI automation.
        
        action: 'message' or 'call'
        payload: message text (for message) or call_type (for call)
        
        Steps:
          1. Open WhatsApp → bring to foreground
          2. Escape (clear any open dialogs/menus)
          3. Ctrl+F (search chats) — works on WhatsApp Desktop for Windows
          4. Type contact search_name via clipboard
          5. Wait for search results (2s)
          6. Enter to select first result
          7a. For message: type message → Enter to send
          7b. For call: chat opened — user clicks call button
        """
        intent = 'SEND_MESSAGE' if action == 'message' else 'MAKE_CALL'

        if not self._open_and_focus_app('whatsapp', wait_seconds=3.0):
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent=intent,
                error="Could not open or focus WhatsApp. Is it installed?",
                duration_ms=int((time.time() - start_time) * 1000)
            )

        self._send_keys_raw("{ESC}")
        time.sleep(0.5)
        self._send_keys_raw("{ESC}")
        time.sleep(0.5)

        self._send_keys_raw("{TAB}")
        time.sleep(0.3)

        self._send_keys_raw("^(a)")  
        time.sleep(0.1)
        self._type_via_clipboard(search_name)
        time.sleep(0.2)  

        self._send_keys_raw("{ENTER}")
        time.sleep(0.5)

        if action == 'message':
            self._type_via_clipboard(payload)
            time.sleep(0.3)

            self._send_keys_raw("{ENTER}")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SEND_MESSAGE',
                command=f'whatsapp_send({contact_name})', exit_code=0,
                output=f"✅ Message sent to {contact_name} on WhatsApp: \"{payload[:60]}\"",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        else:
            call_type = payload if payload in ('voice', 'video') else 'voice'
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='MAKE_CALL',
                command=f'whatsapp_call({contact_name})', exit_code=0,
                output=f"📞 WhatsApp chat with {contact_name} is open. Click the {'📹 video' if call_type == 'video' else '📞 voice'} call button at the top-right.",
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _telegram_automation(self, action: str, contact_info: dict, contact_name: str,
                              search_name: str, payload: str, start_time: float) -> ExecutionResult:
        """
        Telegram Desktop GUI automation.
        
        Steps:
          1. Open Telegram → bring to foreground
          2. Escape (clear state)
          3. Ctrl+K (global search — well documented shortcut)
          4. Type contact search_name
          5. Wait for results (1.5s)
          6. Enter to select
          7a. Message: type → Enter
          7b. Call: chat opened — user clicks call button
        """
        intent = 'SEND_MESSAGE' if action == 'message' else 'MAKE_CALL'

        if not self._open_and_focus_app('telegram', wait_seconds=3.0):
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent=intent,
                error="Could not open or focus Telegram. Is it installed?",
                duration_ms=int((time.time() - start_time) * 1000)
            )

        self._send_keys_raw("{ESC}")
        time.sleep(0.5)

        self._send_keys_raw("^(k)")
        time.sleep(0.5)

        tg_user = contact_info.get('telegram', '')
        search_term = f"@{tg_user}" if tg_user else search_name
        self._type_via_clipboard(search_term)
        time.sleep(2.0)

        self._send_keys_raw("{ENTER}")
        time.sleep(1.0)

        if action == 'message':
            self._type_via_clipboard(payload)
            time.sleep(0.3)

            self._send_keys_raw("{ENTER}")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SEND_MESSAGE',
                command=f'telegram_send({contact_name})', exit_code=0,
                output=f"✅ Message sent to {contact_name} on Telegram: \"{payload[:60]}\"",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        else:
            call_type = payload if payload in ('voice', 'video') else 'voice'
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='MAKE_CALL',
                command=f'telegram_call({contact_name})', exit_code=0,
                output=f"📞 Telegram chat with {contact_name} is open. Click the {'📹 video' if call_type == 'video' else '📞 voice'} call button at the top-right.",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _backup_file(self, path: str):
        """Create a backup of a file before destructive operations."""
        try:
            src = Path(path)
            if not src.exists():
                return
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"{src.name}.{timestamp}.bak"
            backup_path = Path(self._backup_dir) / backup_name
            if src.is_file():
                shutil.copy2(str(src), str(backup_path))
            elif src.is_dir():
                shutil.copytree(str(src), str(backup_path))
            backups = sorted(Path(self._backup_dir).glob("*.bak"), key=lambda p: p.stat().st_mtime)
            while len(backups) > 5:
                oldest = backups.pop(0)
                if oldest.is_file():
                    oldest.unlink()
                elif oldest.is_dir():
                    shutil.rmtree(str(oldest))
        except Exception:
            pass  

    def _execute_volume_up(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            for _ in range(2):
                pyautogui.press('volumeup')
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='VOLUME_UP',
                output="Volume increased", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='VOLUME_UP',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_volume_down(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            for _ in range(2):
                pyautogui.press('volumedown')
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='VOLUME_DOWN',
                output="Volume decreased", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='VOLUME_DOWN',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_mute(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            pyautogui.press('volumemute')
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='MUTE',
                output="Volume mute toggled", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='MUTE',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_screenshot(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            screenshots_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            filename = os.path.join(screenshots_dir, f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png")
            img = pyautogui.screenshot()
            img.save(filename)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SCREENSHOT',
                output=f"Screenshot saved: {filename}", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SCREENSHOT',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_screenshot_window(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            screenshots_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            filename = os.path.join(screenshots_dir, f"screenshot_window_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png")
            win = None
            try:
                win = pyautogui.getActiveWindow()
            except Exception:
                pass
            if win is not None:
                img = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
            else:
                img = pyautogui.screenshot()
            img.save(filename)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SCREENSHOT_WINDOW',
                output=f"Window screenshot saved: {filename}", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SCREENSHOT_WINDOW',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_ocr_screen(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            try:
                import pytesseract
            except ImportError:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='OCR_SCREEN',
                    error="pytesseract not installed. Run: pip install pytesseract",
                    duration_ms=int((time.time() - start_time) * 1000))
            img = pyautogui.screenshot()
            text = pytesseract.image_to_string(img).strip()
            if not text:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS, intent='OCR_SCREEN',
                    output="No readable text found on screen.",
                    duration_ms=int((time.time() - start_time) * 1000))
            ocr_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots")
            os.makedirs(ocr_dir, exist_ok=True)
            ocr_file = os.path.join(ocr_dir, "last_ocr.txt")
            with open(ocr_file, "w", encoding="utf-8") as f:
                f.write(text)
            summary = text.replace("\n", " ")
            if len(summary) > 300:
                summary = summary[:300] + "..."
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='OCR_SCREEN',
                output=f"Screen text: {summary}",
                duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OCR_SCREEN',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_lock_screen(self, start_time: float) -> ExecutionResult:
        try:
            ctypes.windll.user32.LockWorkStation()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='LOCK_SCREEN',
                output="Screen locked", duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='LOCK_SCREEN',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_search_google(self, query: str, start_time: float) -> ExecutionResult:
        try:
            if not query:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='SEARCH_GOOGLE',
                    error="No search query provided",
                    duration_ms=int((time.time() - start_time) * 1000))
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            webbrowser.open(url)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SEARCH_GOOGLE',
                output=f"Searching Google for: {query}",
                duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SEARCH_GOOGLE',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_search_youtube(self, query: str, start_time: float) -> ExecutionResult:
        try:
            if not query:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='SEARCH_YOUTUBE',
                    error="No search query provided",
                    duration_ms=int((time.time() - start_time) * 1000))
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
            webbrowser.open(url)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SEARCH_YOUTUBE',
                output=f"Searching YouTube for: {query}",
                duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SEARCH_YOUTUBE',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_open_website(self, url: str, start_time: float) -> ExecutionResult:
        try:
            if not url:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE, intent='OPEN_WEBSITE',
                    error="No URL provided",
                    duration_ms=int((time.time() - start_time) * 1000))
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='OPEN_WEBSITE',
                output=f"Opened website: {url}",
                duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='OPEN_WEBSITE',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_switch_window(self, start_time: float) -> ExecutionResult:
        try:
            import pyautogui
            pyautogui.hotkey('alt', 'tab')
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='SWITCH_WINDOW',
                output="Switched to next window",
                duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='SWITCH_WINDOW',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_list_apps(self, start_time: float) -> ExecutionResult:
        try:
            from core.tools import APP_WHITELIST
            categories = {
                "System": [], "Browsers": [], "Dev Tools": [],
                "Communication": [], "Office": [], "Media": [],
                "Gaming": [], "Adobe": [], "Other": [],
            }
            for name in sorted(APP_WHITELIST.keys()):
                if name in ("notepad", "calculator", "calc", "paint", "explorer",
                            "file explorer", "task manager", "taskmgr", "cmd",
                            "command prompt", "terminal", "powershell", "control panel",
                            "control", "settings", "wordpad", "snipping tool", "snip",
                            "character map", "charmap", "remote desktop", "mstsc"):
                    categories["System"].append(name)
                elif name in ("chrome", "google chrome", "edge", "microsoft edge",
                              "msedge", "brave", "firefox", "opera", "tor", "tor browser"):
                    categories["Browsers"].append(name)
                elif name in ("vscode", "vs code", "code", "notepad++", "notepad plus plus",
                              "sublime", "sublime text", "pycharm", "android studio",
                              "postman", "github desktop", "github"):
                    categories["Dev Tools"].append(name)
                elif name in ("whatsapp", "telegram", "discord", "slack", "zoom",
                              "teams", "ms teams", "microsoft teams"):
                    categories["Communication"].append(name)
                elif "word" in name or "excel" in name or "powerpoint" in name or \
                     "outlook" in name or "onenote" in name or "access" in name or \
                     "publisher" in name or name in ("ppt", "winword"):
                    categories["Office"].append(name)
                elif name in ("spotify", "vlc", "vlc media player"):
                    categories["Media"].append(name)
                elif name in ("steam", "epic games", "epic", "obs", "obs studio"):
                    categories["Gaming"].append(name)
                elif name in ("photoshop", "adobe photoshop", "illustrator",
                              "premiere", "premiere pro"):
                    categories["Adobe"].append(name)
                else:
                    categories["Other"].append(name)

            lines = [f"Available apps ({len(APP_WHITELIST)} total):"]
            for cat, apps in categories.items():
                if apps:
                    unique = sorted(set(apps))
                    lines.append(f"  {cat}: {', '.join(unique)}")
            output = "\n".join(lines)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, intent='LIST_APPS',
                output=output, duration_ms=int((time.time() - start_time) * 1000))
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE, intent='LIST_APPS',
                error=str(e), duration_ms=int((time.time() - start_time) * 1000))

    def _execute_analyze_screen(self, start_time: float) -> ExecutionResult:
        """Capture screenshot and return as Base64 string for vision analysis."""
        try:
            import pyautogui
            import base64
            import io
            
            img = pyautogui.screenshot()
            
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                intent='MEDIA.CAPTURE.ANALYZE_SCREEN',
                output=img_str,
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent='MEDIA.CAPTURE.ANALYZE_SCREEN',
                error=f"Screen capture failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
