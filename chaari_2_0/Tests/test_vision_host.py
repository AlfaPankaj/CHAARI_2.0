# CHAARI 2.0 — Vision Engine Integration Test
# ═══════════════════════════════════════════════════════════
# Verifies: Screenshot -> Base64 -> Llava -> Description
# ═══════════════════════════════════════════════════════════

import os
import sys
import base64
from io import BytesIO
from PIL import Image
import pyautogui

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_2_0.core.vision_engine import VisionEngine

def run_vision_test():
    print("\n" + "═" * 60)
    print("  CHAARI 2.0 — LOCAL VISION TEST (ASUS HOST)")
    print("═" * 60)

    # 1. Initialize Engine
    engine = VisionEngine(model="llava:7b")
    
    print("\n  [1/3] Capturing screen...")
    try:
        screenshot = pyautogui.screenshot()
        # Resize to save time
        screenshot.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        buffered = BytesIO()
        screenshot.save(buffered, format="JPEG", quality=70)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        print(f"  [✓] Screen captured ({len(img_str)//1024} KB)")
    except Exception as e:
        print(f"  [✗] Capture failed: {e}")
        return

    # 2. Analyze
    print("\n  [2/3] Sending to Llava:7b (This may take ~10-20s)...")
    prompt = "Tell me what you see on this screen. Focus on the main window and any text or errors visible."
    
    analysis = engine.analyze_image(img_str, prompt)
    
    print("\n  [3/3] Visual Analysis Result:")
    print("─" * 60)
    print(analysis)
    print("─" * 60)

    print("\n  ✅ Vision Test Complete.")

if __name__ == "__main__":
    run_vision_test()
