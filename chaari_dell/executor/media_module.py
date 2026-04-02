# CHAARI 2.0 — Dell Node — Media Module
# ═══════════════════════════════════════════════════════════
# Responsibility:
#   ✔ Capture Screen (Screenshot)
#   ✔ Prepare Image for Remote Visual Reasoning (Base64)
#   ✔ Capture Webcam (Optional/Future)
# ═══════════════════════════════════════════════════════════

import os
import time
import base64
import logging
from io import BytesIO
from datetime import datetime
from PIL import Image

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from chaari_dell.models.packet_models import ExecutionResult, ExecutionStatus

logger = logging.getLogger("chaari.dell.executor.media")

class MediaModule:
    """Handles visual data capture on the Dell User node."""

    def execute(self, intent: str, context: dict, trace_id: str) -> ExecutionResult:
        """Route to specific media capture task."""
        start_time = time.time()
        intent_upper = intent.upper()

        try:
            if intent_upper == "MEDIA.CAPTURE.ANALYZE_SCREEN":
                return self._capture_analyze_screen(context, trace_id, start_time)
            elif intent_upper == "MEDIA.CAPTURE.SCREENSHOT":
                return self._capture_screenshot(context, trace_id, start_time)
            else:
                return ExecutionResult(
                    intent=intent,
                    status=ExecutionStatus.FAILURE,
                    error=f"Unsupported intent in MediaModule: {intent}",
                    trace_id=trace_id
                )
        except Exception as e:
            logger.error(f"MediaModule error: {e}")
            return ExecutionResult(
                intent=intent,
                status=ExecutionStatus.FAILURE,
                error=str(e),
                trace_id=trace_id
            )

    def _capture_analyze_screen(self, context: dict, trace_id: str, start_time: float) -> ExecutionResult:
        """Capture screen and return as Base64 for ASUS Host analysis."""
        if not PYAUTOGUI_AVAILABLE:
            return ExecutionResult(
                intent="MEDIA.CAPTURE.ANALYZE_SCREEN",
                status=ExecutionStatus.FAILURE,
                error="pyautogui not installed on Dell node",
                trace_id=trace_id
            )

        try:
            # 1. Take Screenshot
            screenshot = pyautogui.screenshot()
            
            # 2. Resize/Compress to save bandwidth (Ollama/Llava prefers smaller images)
            # Max width 1280px is plenty for vision models
            max_size = (1280, 1280)
            screenshot.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 3. Save to Buffer
            buffered = BytesIO()
            screenshot.save(buffered, format="JPEG", quality=75) # High compression JPEG
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            duration = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                intent="MEDIA.CAPTURE.ANALYZE_SCREEN",
                status=ExecutionStatus.SUCCESS,
                output=img_str, # ASUS Brain will handle this as image data
                duration_ms=duration,
                trace_id=trace_id
            )
        except Exception as e:
            return ExecutionResult(
                intent="MEDIA.CAPTURE.ANALYZE_SCREEN",
                status=ExecutionStatus.FAILURE,
                error=f"Screen capture failed: {e}",
                trace_id=trace_id
            )

    def _capture_screenshot(self, context: dict, trace_id: str, start_time: float) -> ExecutionResult:
        """Standard screenshot saved to Dell local disk."""
        if not PYAUTOGUI_AVAILABLE:
            return ExecutionResult(intent="MEDIA.CAPTURE.SCREENSHOT", status=ExecutionStatus.FAILURE, error="pyautogui not installed", trace_id=trace_id)
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            # Ensure screenshots dir exists
            save_path = os.path.join(os.getcwd(), "data", "screenshots", filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            pyautogui.screenshot(save_path)
            
            return ExecutionResult(
                intent="MEDIA.CAPTURE.SCREENSHOT",
                status=ExecutionStatus.SUCCESS,
                output=f"Screenshot saved to: {save_path}",
                duration_ms=int((time.time() - start_time) * 1000),
                trace_id=trace_id
            )
        except Exception as e:
            return ExecutionResult(intent="MEDIA.CAPTURE.SCREENSHOT", status=ExecutionStatus.FAILURE, error=str(e), trace_id=trace_id)
