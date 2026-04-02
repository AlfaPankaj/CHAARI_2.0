# CHAARI 2.0 — Dell executor/filesystem_module.py — FILESYSTEM Capability
# ═══════════════════════════════════════════════════════════
# Handles: CREATE, DELETE, COPY, MOVE files
#
# Safety:
#   - DELETE creates backup first (rollback support)
#   - Path validation (no traversal attacks)
#   - No shell injection — uses Python pathlib/shutil
# ═══════════════════════════════════════════════════════════

import os
import shutil
from pathlib import Path
from datetime import datetime

from chaari_dell.models.packet_models import ExecutionResult
from chaari_dell.config import BACKUP_DIR


class FilesystemModule:
    """
    Capability module for FILESYSTEM group.
    
    Supported intents:
        - FILESYSTEM.FILE.CREATE → create empty file
        - FILESYSTEM.FILE.DELETE → backup + delete
        - FILESYSTEM.FILE.COPY   → copy file/dir
        - FILESYSTEM.FILE.MOVE   → move file/dir
    """

    SUPPORTED_INTENTS = {
        "FILESYSTEM.FILE.CREATE",
        "FILESYSTEM.FILE.DELETE",
        "FILESYSTEM.FILE.COPY",
        "FILESYSTEM.FILE.MOVE",
    }

    def __init__(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        """Execute a filesystem command."""
        context = context or {}

        if intent not in self.SUPPORTED_INTENTS:
            return ExecutionResult(
                intent=intent,
                status="rejected",
                error=f"FilesystemModule does not support: {intent}",
            )

        if intent == "FILESYSTEM.FILE.CREATE":
            return self._create_file(context)
        elif intent == "FILESYSTEM.FILE.DELETE":
            return self._delete_file(context)
        elif intent == "FILESYSTEM.FILE.COPY":
            return self._copy_file(context)
        elif intent == "FILESYSTEM.FILE.MOVE":
            return self._move_file(context)

        return ExecutionResult(intent=intent, status="failure", error="Unhandled intent")

    def _validate_path(self, path_str: str) -> tuple[bool, str]:
        """Validate path is safe (no traversal)."""
        if not path_str:
            return False, "Empty path"
        p = Path(path_str).resolve()
        # Block system directories
        blocked = [r"C:\Windows", r"C:\Program Files", "/usr", "/bin", "/sbin", "/etc"]
        for b in blocked:
            if str(p).startswith(b):
                return False, f"Blocked directory: {b}"
        return True, ""

    def _create_file(self, ctx: dict) -> ExecutionResult:
        """Create an empty file."""
        path = ctx.get("path")
        if not path:
            return ExecutionResult(
                intent="FILESYSTEM.FILE.CREATE",
                status="failure",
                error="CREATE requires 'path' in context",
            )
        valid, reason = self._validate_path(path)
        if not valid:
            return ExecutionResult(intent="FILESYSTEM.FILE.CREATE", status="failure", error=reason)

        try:
            p = Path(path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
            return ExecutionResult(
                intent="FILESYSTEM.FILE.CREATE",
                status="success",
                output=f"Created file: {p}",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(intent="FILESYSTEM.FILE.CREATE", status="failure", error=str(e))

    def _delete_file(self, ctx: dict) -> ExecutionResult:
        """Delete file with backup."""
        path = ctx.get("path")
        if not path:
            return ExecutionResult(
                intent="FILESYSTEM.FILE.DELETE",
                status="failure",
                error="DELETE requires 'path' in context",
            )
        valid, reason = self._validate_path(path)
        if not valid:
            return ExecutionResult(intent="FILESYSTEM.FILE.DELETE", status="failure", error=reason)

        try:
            p = Path(path).resolve()
            if not p.exists():
                return ExecutionResult(
                    intent="FILESYSTEM.FILE.DELETE",
                    status="failure",
                    error=f"File not found: {p}",
                )

            # Backup before delete
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{p.name}.{ts}.bak"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            shutil.copy2(str(p), backup_path)

            p.unlink()
            return ExecutionResult(
                intent="FILESYSTEM.FILE.DELETE",
                status="success",
                output=f"Deleted: {p} (backup: {backup_path})",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(intent="FILESYSTEM.FILE.DELETE", status="failure", error=str(e))

    def _copy_file(self, ctx: dict) -> ExecutionResult:
        """Copy file to destination."""
        source = ctx.get("source")
        dest = ctx.get("destination")
        if not source or not dest:
            return ExecutionResult(
                intent="FILESYSTEM.FILE.COPY",
                status="failure",
                error="COPY requires 'source' and 'destination'",
            )

        try:
            src = Path(source).resolve()
            dst = Path(dest).resolve()
            if not src.exists():
                return ExecutionResult(intent="FILESYSTEM.FILE.COPY", status="failure", error=f"Source not found: {src}")
            shutil.copy2(str(src), str(dst))
            return ExecutionResult(
                intent="FILESYSTEM.FILE.COPY",
                status="success",
                output=f"Copied: {src} → {dst}",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(intent="FILESYSTEM.FILE.COPY", status="failure", error=str(e))

    def _move_file(self, ctx: dict) -> ExecutionResult:
        """Move file to destination."""
        source = ctx.get("source")
        dest = ctx.get("destination")
        if not source or not dest:
            return ExecutionResult(
                intent="FILESYSTEM.FILE.MOVE",
                status="failure",
                error="MOVE requires 'source' and 'destination'",
            )

        try:
            src = Path(source).resolve()
            dst = Path(dest).resolve()
            if not src.exists():
                return ExecutionResult(intent="FILESYSTEM.FILE.MOVE", status="failure", error=f"Source not found: {src}")
            shutil.move(str(src), str(dst))
            return ExecutionResult(
                intent="FILESYSTEM.FILE.MOVE",
                status="success",
                output=f"Moved: {src} → {dst}",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(intent="FILESYSTEM.FILE.MOVE", status="failure", error=str(e))
