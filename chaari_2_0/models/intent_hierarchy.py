# CHAARI 2.0 — models/intent_hierarchy.py — Hierarchical Intent System

# Responsibility:
# Define CapabilityGroup enum
# Map SystemIntent → hierarchical namespace
# Map SystemIntent → CapabilityGroup
# Provide lookup helpers

# This extends the flat SystemIntent enum with:
#   - Namespace: "SYSTEM.POWER.SHUTDOWN" (for crypto packets)
#   - CapabilityGroup: POWER, FILESYSTEM, etc. (for Dell capability isolation)

# The flat SystemIntent enum is preserved for backward compatibility.
# This module adds the hierarchical classification ON TOP.

from enum import Enum
from core.system_intent import SystemIntent



class CapabilityGroup(Enum):
    """
    Capability groups for intent isolation.
    
    Each Dell execution module handles exactly one capability group.
    This ensures a filesystem command can never reach the power module.
    """
    POWER = "POWER"                    
    FILESYSTEM = "FILESYSTEM"           
    APPLICATION = "APPLICATION"        
    COMMUNICATION = "COMMUNICATION"     
    NETWORK = "NETWORK"                 
    SYSTEM = "SYSTEM"                   
    MEDIA = "MEDIA"                   
    WEB = "WEB"                       

    @classmethod
    def from_string(cls, value: str) -> "CapabilityGroup | None":
        try:
            return cls(value.upper())
        except ValueError:
            return None



INTENT_NAMESPACE: dict[SystemIntent, str] = {
    SystemIntent.SHUTDOWN:          "SYSTEM.POWER.SHUTDOWN",
    SystemIntent.RESTART:           "SYSTEM.POWER.RESTART",

    SystemIntent.CREATE_FILE:       "FILESYSTEM.FILE.CREATE",
    SystemIntent.DELETE_FILE:       "FILESYSTEM.FILE.DELETE",
    SystemIntent.COPY_FILE:         "FILESYSTEM.FILE.COPY",
    SystemIntent.MOVE_FILE:         "FILESYSTEM.FILE.MOVE",

    SystemIntent.OPEN_APP:          "APPLICATION.LIFECYCLE.LAUNCH",
    SystemIntent.CLOSE_APP:         "APPLICATION.LIFECYCLE.TERMINATE",
    SystemIntent.MINIMIZE_APP:      "APPLICATION.WINDOW.MINIMIZE",
    SystemIntent.MAXIMIZE_APP:      "APPLICATION.WINDOW.MAXIMIZE",
    SystemIntent.RESTORE_APP:       "APPLICATION.WINDOW.RESTORE",

    SystemIntent.TYPE_TEXT:          "COMMUNICATION.INPUT.TYPE_TEXT",
    SystemIntent.SEND_MESSAGE:      "COMMUNICATION.MESSAGING.SEND",
    SystemIntent.MAKE_CALL:         "COMMUNICATION.CALLING.DIAL",

    SystemIntent.VOLUME_UP:         "MEDIA.AUDIO.VOLUME_UP",
    SystemIntent.VOLUME_DOWN:       "MEDIA.AUDIO.VOLUME_DOWN",
    SystemIntent.MUTE:              "MEDIA.AUDIO.MUTE",
    SystemIntent.SCREENSHOT:        "MEDIA.CAPTURE.SCREENSHOT",
    SystemIntent.SCREENSHOT_WINDOW: "MEDIA.CAPTURE.SCREENSHOT_WINDOW",
    SystemIntent.OCR_SCREEN:        "MEDIA.CAPTURE.OCR_SCREEN",

    SystemIntent.SEARCH_GOOGLE:     "WEB.SEARCH.GOOGLE",
    SystemIntent.SEARCH_YOUTUBE:    "WEB.SEARCH.YOUTUBE",
    SystemIntent.OPEN_WEBSITE:      "WEB.BROWSE.OPEN",

    SystemIntent.SWITCH_WINDOW:     "APPLICATION.WINDOW.SWITCH",
    SystemIntent.LOCK_SCREEN:       "SYSTEM.POWER.LOCK",
    SystemIntent.LIST_APPS:         "APPLICATION.DISCOVERY.LIST",

    SystemIntent.FORMAT_DISK:       "SYSTEM.STORAGE.FORMAT",
    SystemIntent.KILL_PROCESS:      "SYSTEM.PROCESS.KILL",
    SystemIntent.MODIFY_REGISTRY:   "SYSTEM.REGISTRY.MODIFY",
}

INTENT_CAPABILITY_MAP: dict[SystemIntent, CapabilityGroup] = {
    SystemIntent.SHUTDOWN:          CapabilityGroup.POWER,
    SystemIntent.RESTART:           CapabilityGroup.POWER,

    SystemIntent.CREATE_FILE:       CapabilityGroup.FILESYSTEM,
    SystemIntent.DELETE_FILE:       CapabilityGroup.FILESYSTEM,
    SystemIntent.COPY_FILE:         CapabilityGroup.FILESYSTEM,
    SystemIntent.MOVE_FILE:         CapabilityGroup.FILESYSTEM,

    SystemIntent.OPEN_APP:          CapabilityGroup.APPLICATION,
    SystemIntent.CLOSE_APP:         CapabilityGroup.APPLICATION,
    SystemIntent.MINIMIZE_APP:      CapabilityGroup.APPLICATION,
    SystemIntent.MAXIMIZE_APP:      CapabilityGroup.APPLICATION,
    SystemIntent.RESTORE_APP:       CapabilityGroup.APPLICATION,

    SystemIntent.TYPE_TEXT:          CapabilityGroup.COMMUNICATION,
    SystemIntent.SEND_MESSAGE:      CapabilityGroup.COMMUNICATION,
    SystemIntent.MAKE_CALL:         CapabilityGroup.COMMUNICATION,

    SystemIntent.VOLUME_UP:         CapabilityGroup.MEDIA,
    SystemIntent.VOLUME_DOWN:       CapabilityGroup.MEDIA,
    SystemIntent.MUTE:              CapabilityGroup.MEDIA,
    SystemIntent.SCREENSHOT:        CapabilityGroup.MEDIA,
    SystemIntent.SCREENSHOT_WINDOW: CapabilityGroup.MEDIA,
    SystemIntent.OCR_SCREEN:        CapabilityGroup.MEDIA,

    SystemIntent.SEARCH_GOOGLE:     CapabilityGroup.WEB,
    SystemIntent.SEARCH_YOUTUBE:    CapabilityGroup.WEB,
    SystemIntent.OPEN_WEBSITE:      CapabilityGroup.WEB,

    SystemIntent.SWITCH_WINDOW:     CapabilityGroup.APPLICATION,
    SystemIntent.LIST_APPS:         CapabilityGroup.APPLICATION,

    SystemIntent.LOCK_SCREEN:       CapabilityGroup.POWER,

    SystemIntent.FORMAT_DISK:       CapabilityGroup.SYSTEM,
    SystemIntent.KILL_PROCESS:      CapabilityGroup.SYSTEM,
    SystemIntent.MODIFY_REGISTRY:   CapabilityGroup.SYSTEM,
}

_NAMESPACE_TO_INTENT: dict[str, SystemIntent] = {v: k for k, v in INTENT_NAMESPACE.items()}



def get_namespace(intent: SystemIntent) -> str:
    """Get the hierarchical namespace for an intent."""
    return INTENT_NAMESPACE.get(intent, f"UNKNOWN.{intent.value.upper()}")


def get_capability_group(intent: SystemIntent) -> CapabilityGroup:
    """Get the capability group for an intent."""
    return INTENT_CAPABILITY_MAP.get(intent, CapabilityGroup.SYSTEM)


def intent_from_namespace(namespace: str) -> SystemIntent | None:
    """Resolve a namespace string back to a SystemIntent."""
    return _NAMESPACE_TO_INTENT.get(namespace)


def get_group_intents(group: CapabilityGroup) -> list[SystemIntent]:
    """Get all intents belonging to a capability group."""
    return [
        intent for intent, grp in INTENT_CAPABILITY_MAP.items()
        if grp == group
    ]


def list_hierarchy() -> dict[str, dict]:
    """
    Return full hierarchy as a structured dict.
    Useful for debugging and display.
    
    Returns:
        {
            "POWER": {
                "SYSTEM.POWER.SHUTDOWN": "shutdown",
                "SYSTEM.POWER.RESTART": "restart",
            },
            ...
        }
    """
    result = {}
    for intent, group in INTENT_CAPABILITY_MAP.items():
        group_name = group.value
        if group_name not in result:
            result[group_name] = {}
        namespace = INTENT_NAMESPACE.get(intent, intent.value)
        result[group_name][namespace] = intent.value
    return result
