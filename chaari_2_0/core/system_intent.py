# CHAARI 2.0 — core/system_intent.py — Layer 1.5: SystemIntent Enum
# ═══════════════════════════════════════════════════════════════════════════
# Responsibility: Define strict enum of allowed system intents
#
# This is critical for injection prevention:
#   • Only enum values allowed (no dynamic strings)
#   • IntentRouter maps detected strings → enum
#   • Brain receives enum (never raw strings)
#   • Executor checks enum (hardcoded mappings)
# ═══════════════════════════════════════════════════════════════════════════

from enum import Enum


class SystemIntent(Enum):
    """
    Strict enum of allowed system intents.
    
    No dynamic intent values allowed.
    Only values in this enum can be executed.
    """

    OPEN_APP = "open_app"
    OPEN_FILE = "open_file"
    CLOSE_APP = "close_app"
    MINIMIZE_APP = "minimize_app"
    MAXIMIZE_APP = "maximize_app"
    RESTORE_APP = "restore_app"
    TYPE_TEXT = "type_text"
    SEND_MESSAGE = "send_message"
    MAKE_CALL = "make_call"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    MUTE = "mute"
    SCREENSHOT = "screenshot"
    SCREENSHOT_WINDOW = "screenshot_window"
    LOCK_SCREEN = "lock_screen"
    SEARCH_GOOGLE = "search_google"
    SEARCH_YOUTUBE = "search_youtube"
    OPEN_WEBSITE = "open_website"
    OPEN_FOLDER = "open_folder"
    SWITCH_WINDOW = "switch_window"
    LIST_APPS = "list_apps"
    OCR_SCREEN = "ocr_screen"

    SHUTDOWN = "shutdown"
    RESTART = "restart"
    DELETE_FILE = "delete_file"
    CREATE_FILE = "create_file"
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"

    FORMAT_DISK = "format_disk"
    KILL_PROCESS = "kill_process"
    MODIFY_REGISTRY = "modify_registry"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if value is a valid SystemIntent."""
        try:
            cls(value)
            return True
        except ValueError:
            return False

    @classmethod
    def from_string(cls, value: str) -> "SystemIntent | None":
        """
        Convert string to SystemIntent enum (safe).

        Args:
            value: String value to convert

        Returns:
            SystemIntent or None if not valid
        """
        if not value:
            return None
        try:
            return cls(value.lower())
        except ValueError:
            return None
