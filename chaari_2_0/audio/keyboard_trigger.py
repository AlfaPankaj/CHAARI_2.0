# CHAARI 2.0 – audio/ - Keyboard Shortcut Trigger
# Global hotkey (F5) to toggle voice listening
# Works alongside wake word as a backup trigger

import threading

try:
    from config.voice import VOICE_HOTKEY, HOTKEY_ENABLED
except ImportError:
    VOICE_HOTKEY = "f5"
    HOTKEY_ENABLED = True


class KeyboardTrigger:
    """Global keyboard shortcut to trigger voice listening."""

    def __init__(self, on_trigger=None, hotkey: str = VOICE_HOTKEY):
        self.on_trigger = on_trigger 
        self.hotkey = hotkey
        self._active = False
        self._hook_registered = False
        self._lock = threading.Lock()

    def start(self):
        """Register the global hotkey."""
        if not HOTKEY_ENABLED:
            print("  [Hotkey] Keyboard shortcut disabled in config.")
            return False

        try:
            import keyboard

            if self._hook_registered:
                return True

            keyboard.add_hotkey(self.hotkey, self._on_key_press, suppress=False)
            self._hook_registered = True

            with self._lock:
                self._active = True

            print(f"  [Hotkey] Press {self.hotkey.upper()} to activate voice.")
            return True

        except ImportError:
            print("  [Hotkey] 'keyboard' library not installed.")
            return False
        except Exception as e:
            print(f"  [Hotkey] Failed to register hotkey: {e}")
            return False

    def _on_key_press(self):
        """Called when hotkey is pressed."""
        with self._lock:
            if not self._active:
                return

        if self.on_trigger:
            t = threading.Thread(target=self.on_trigger, daemon=True)
            t.start()

    def stop(self):
        """Unregister the global hotkey."""
        try:
            import keyboard

            if self._hook_registered:
                keyboard.remove_hotkey(self.hotkey)
                self._hook_registered = False

            with self._lock:
                self._active = False

            print("  [Hotkey] Keyboard shortcut disabled.")

        except Exception:
            pass

    def pause(self):
        """Temporarily disable the hotkey callback."""
        with self._lock:
            self._active = False

    def resume(self):
        """Re-enable the hotkey callback."""
        with self._lock:
            self._active = True

    def is_active(self) -> bool:
        """Check if hotkey is registered and active."""
        with self._lock:
            return self._active and self._hook_registered

    def set_callback(self, on_trigger):
        """Set the trigger callback."""
        self.on_trigger = on_trigger

    def set_hotkey(self, hotkey: str):
        """Change the hotkey at runtime."""
        was_active = self.is_active()
        if was_active:
            self.stop()
        self.hotkey = hotkey
        if was_active:
            self.start()
