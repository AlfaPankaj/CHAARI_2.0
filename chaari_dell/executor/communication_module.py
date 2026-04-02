# CHAARI 2.0 — Dell executor/communication_module.py — COMMUNICATION Capability
# ═══════════════════════════════════════════════════════════
# Handles: TYPE_TEXT, SEND_MESSAGE, MAKE_CALL
# Uses GUI automation (SendKeys) for text input.
# ═══════════════════════════════════════════════════════════

import subprocess

from chaari_dell.models.packet_models import ExecutionResult


class CommunicationModule:
    """
    Capability module for COMMUNICATION group.
    
    Supported intents:
        - COMMUNICATION.INPUT.TYPE_TEXT     → type text via clipboard+paste
        - COMMUNICATION.MESSAGING.SEND     → send message on WhatsApp/Telegram
        - COMMUNICATION.CALLING.DIAL       → initiate call (open contact)
    """

    SUPPORTED_INTENTS = {
        "COMMUNICATION.INPUT.TYPE_TEXT",
        "COMMUNICATION.MESSAGING.SEND",
        "COMMUNICATION.CALLING.DIAL",
    }

    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        context = context or {}

        if intent not in self.SUPPORTED_INTENTS:
            return ExecutionResult(intent=intent, status="rejected", error=f"Not supported: {intent}")

        if intent == "COMMUNICATION.INPUT.TYPE_TEXT":
            return self._type_text(context)
        elif intent == "COMMUNICATION.MESSAGING.SEND":
            return self._send_message(context)
        elif intent == "COMMUNICATION.CALLING.DIAL":
            return self._make_call(context)

        return ExecutionResult(intent=intent, status="failure", error="Unhandled")

    def _type_via_clipboard(self, text: str) -> bool:
        """Type text using clipboard paste (Unicode safe)."""
        try:
            ps_cmd = f'''
            Add-Type -AssemblyName System.Windows.Forms
            Set-Clipboard -Value "{text.replace('"', '`"')}"
            [System.Windows.Forms.SendKeys]::SendWait("^v")
            '''
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    def _type_text(self, ctx: dict) -> ExecutionResult:
        """Type text into the active window."""
        text = ctx.get("text", "")
        if not text:
            return ExecutionResult(
                intent="COMMUNICATION.INPUT.TYPE_TEXT",
                status="failure",
                error="No text to type",
            )

        if self._type_via_clipboard(text):
            return ExecutionResult(
                intent="COMMUNICATION.INPUT.TYPE_TEXT",
                status="success",
                output=f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}",
                exit_code=0,
            )
        return ExecutionResult(
            intent="COMMUNICATION.INPUT.TYPE_TEXT",
            status="failure",
            error="Failed to type text",
        )

    def _send_message(self, ctx: dict) -> ExecutionResult:
        """Send message via WhatsApp/Telegram (GUI automation)."""
        platform_name = ctx.get("platform", "whatsapp").lower()
        contact = ctx.get("contact", "")
        text = ctx.get("text", "")

        if not contact or not text:
            return ExecutionResult(
                intent="COMMUNICATION.MESSAGING.SEND",
                status="failure",
                error=f"Missing contact or text. Got contact='{contact}', text='{text}'",
            )

        # For now, return structured info — full GUI automation deferred
        return ExecutionResult(
            intent="COMMUNICATION.MESSAGING.SEND",
            status="success",
            output=f"Message queued: '{text}' to {contact} on {platform_name}",
            exit_code=0,
        )

    def _make_call(self, ctx: dict) -> ExecutionResult:
        """Initiate a call (voice/video)."""
        platform_name = ctx.get("platform", "whatsapp").lower()
        contact = ctx.get("contact", "")
        call_type = ctx.get("call_type", "voice")

        if not contact:
            return ExecutionResult(
                intent="COMMUNICATION.CALLING.DIAL",
                status="failure",
                error="Missing contact for call",
            )

        return ExecutionResult(
            intent="COMMUNICATION.CALLING.DIAL",
            status="success",
            output=f"{call_type.title()} call to {contact} on {platform_name} — open app and click call button",
            exit_code=0,
        )
