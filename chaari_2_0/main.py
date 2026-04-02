# CHAARI 2.0 – Main Entry Point
# Voice + Text mode terminal interface

import sys
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.brain import Brain
from core.memory import Memory
from core.tools import PSUTIL_AVAILABLE
from core.os_executor import OSExecutor
from crypto.key_manager import KeyManager


def print_banner(voice_mode: bool):
    """Print the startup banner."""
    mode_label = "Voice + Text" if voice_mode else "Text Only"
    print("\n" + "═" * 50)
    print("  CHAARI 2.0 — Personal AI Operating Companion")
    print("  Model: chaari-2.0:latest")
    print(f"  Mode: {mode_label} (Phase 6)")
    print("═" * 50)


def load_audio_modules():
    """
    Attempt to load audio modules (Phase 6: Edge TTS + dual STT).
    Returns dict with components or None if audio unavailable.
    """
    try:
        from audio.stt_engine import STTEngine
        from audio.tts_engine import TTSEngine
        from audio.interrupt_handler import InterruptHandler, speak_with_interrupt
        from audio.sound_effects import init_sound_effects

        print("\n  [Boot] Loading audio systems...")

        init_sound_effects()

        stt_backend = "chrome"
        for arg in sys.argv:
            if arg.startswith("--stt-backend="):
                stt_backend = arg.split("=", 1)[1]
        stt = STTEngine(backend=stt_backend)
        stt.load()

        tts = TTSEngine()
        tts.load()

        interrupt = InterruptHandler()
        interrupt.set_tts_engine(tts)
        print("  [Boot] Interrupt handler ready.")

        return {
            "stt": stt,
            "tts": tts,
            "interrupt": interrupt,
            "speak_with_interrupt": speak_with_interrupt,
        }

    except ImportError as e:
        print(f"\n  [Warning] Audio modules not available: {e}")
        print("  Install dependencies: pip install edge-tts pygame SpeechRecognition")
        return None
    except Exception as e:
        print(f"\n  [Warning] Audio init failed: {e}")
        return None


def load_voice_triggers(audio_modules, voice_callback):
    """Load wake word detector and keyboard trigger.
    Returns dict with components or empty dict."""
    triggers = {}

    try:
        from audio.wake_word import WakeWordDetector
        wake = WakeWordDetector(on_wake=voice_callback)
        triggers["wake_word"] = wake
    except ImportError:
        print("  [Boot] Wake word unavailable (install openwakeword)")
    except Exception as e:
        print(f"  [Boot] Wake word init failed: {e}")

    try:
        from audio.keyboard_trigger import KeyboardTrigger
        hotkey = KeyboardTrigger(on_trigger=voice_callback)
        triggers["keyboard"] = hotkey
    except ImportError:
        print("  [Boot] Keyboard trigger unavailable (install keyboard)")
    except Exception as e:
        print(f"  [Boot] Keyboard trigger init failed: {e}")

    return triggers


def boot_chaari():
    """Initialize all systems and run the main loop."""

    voice_mode = "--voice" in sys.argv or "-v" in sys.argv
    live_mode = "--live" in sys.argv
    print_banner(voice_mode)

    memory = Memory()
    memory.start_session()
    session_num = memory.get_session_count()

    brain = Brain(memory=memory)

    if live_mode:
        brain.inject_executor(OSExecutor())
        print("  [Boot] Executor: OSExecutor (LIVE mode)")
    else:
        print("  [Boot] Executor: NoOp (safe mode — use --live for real execution)")

    key_mgr = KeyManager()
    if not key_mgr.all_keys_present():
        print("\n  [Boot] Generating RSA-2048 key pairs (first run)...")
        key_mgr.generate_all_keys()
        print("  [Boot] Keys generated: asus + dell (keys/ directory)")
    crypto_status = "✅ ACTIVE" if key_mgr.all_keys_present() else "❌ MISSING"

    print("\n  [Boot] Checking Ollama connection...")
    if not brain.is_ollama_running():
        print("  [Error] Ollama is not running!")
        print("  Start Ollama first: ollama serve")
        print("  Then pull the model: ollama pull llama3.2:3b")
        return

    if not brain.is_model_available():
        print(f"  [Error] Model '{brain.model}' not found!")
        print(f"  Pull it first: ollama pull {brain.model}")
        return

    print(f"  [Boot] Ollama connected. Model ready.")
    print(f"  [Boot] Session #{session_num}")

    print("  [Boot] Warming up LLM (keeping model loaded)...")
    import threading as _threading_boot
    _threading_boot.Thread(target=brain.warmup_llm, daemon=True).start()

    print(f"  [Boot] Layer 0 — Safety Kernel: ACTIVE")
    print(f"  [Boot] Layer 1 — Identity Lock: {brain.identity.get_name()} by {brain.identity.get_creator()}")
    tools = brain.tools.list_tools()
    active_tools = [k for k, v in tools.items() if v]
    print(f"  [Boot] Layer 2 — Tools: {', '.join(active_tools) if active_tools else 'None'}")
    print(f"  [Boot] Layer 2.5 — Crypto: {crypto_status}")
    print(f"  [Boot] Layer 3 — Memory: {'Returning user' if memory.is_returning_user() else 'New user'}")
    print(f"  [Boot] Layer 4 — Personality: Locked")

    groq_status = brain.groq.get_status()
    if groq_status["available"]:
        remaining = groq_status["today_remaining"]
        print(f"  [Boot] Layer 5 — LLM: Groq API ({groq_status['model']}) — {remaining} requests left today")
    elif groq_status["has_key"]:
        print(f"  [Boot] Layer 5 — LLM: Groq daily limit reached — using Ollama (local)")
    else:
        print(f"  [Boot] Layer 5 — LLM: Ollama local (set GROQ_API_KEY for fast cloud LLM)")

    audio_modules = None
    voice_triggers = {}
    voice_event = None  

    if voice_mode:
        audio_modules = load_audio_modules()
        if not audio_modules:
            print("  [Fallback] Switching to text-only mode.")
            voice_mode = False
        else:
            import threading as _threading
            voice_event = _threading.Event()

            def _voice_trigger_callback():
                """Called by wake word or keyboard shortcut."""
                try:
                    from audio.sound_effects import play_wake_sfx
                    play_wake_sfx()
                except Exception:
                    pass
                voice_event.set()

            voice_triggers = load_voice_triggers(audio_modules, _voice_trigger_callback)
            if "wake_word" in voice_triggers:
                voice_triggers["wake_word"].start()
            if "keyboard" in voice_triggers:
                voice_triggers["keyboard"].start()

    user_name = memory.get_user_name()
    if user_name:
        print(f"  [Boot] Welcome back, {user_name}!")
    else:
        print("  [Boot] New user detected.")

    print("\n  Commands:")
    print("    /quit     — Exit")
    print("    /clear    — Clear conversation history")
    print("    /memory   — Show stored memory")
    print("    /name     — Set your name")
    print("    /reset    — Reset all memory")
    print("    /stream   — Toggle streaming mode")
    print("    /voice    — Toggle voice mode (on/off/status)")
    print("    /voices   — Show TTS voice configuration")
    print("    /tools    — List all available tools")
    print("    /contacts — Manage contacts (add/remove/list)")
    print("    /crypto   — Show crypto key status")
    print("    /hierarchy— Show intent hierarchy")
    print("    /groq     — Show Groq API status and usage")
    print("    /connect  — Connect to Dell execution node")
    print("    /nodes    — Show Dell node connection status")
    print("    /remote   — Send command to Dell node")
    print("    /unblock  — Reset session block (if blocked by safety)")
    print("─" * 50 + "\n")

    streaming = True  

    conn_mgr = None
    if "--connect" in sys.argv or live_mode:
        try:
            from network.connection_manager import ConnectionManager
            conn_mgr = ConnectionManager()
        except ImportError:
            pass


    while True:
        if voice_mode and audio_modules:
            stt = audio_modules["stt"]
            tts = audio_modules["tts"]
            voice_event.clear() 

            try:
                if "wake_word" in voice_triggers:
                    print("\n  [System] Waiting for Wake Word ('Chaari')...")
                    while not voice_event.is_set():
                        voice_event.wait(timeout=0.1)
                
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=1) as executor:
                    print("\n  [Voice] Listening... (say something)")
                    future = executor.submit(stt.listen)
                    user_input = future.result() 

                if not user_input:
                    print("  [STT] No speech detected. Returning to standby.")
                    continue

                print(f"\n  You (voice): {user_input}")

            except KeyboardInterrupt:
                print("\n\n  Chaari: Chal, bye Boss. Take care. \u2764\ufe0f")
                break
        else:
            try:
                user_input = input("\n  You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\n  Chaari: Chal, bye Boss. Take care. \u2764\ufe0f")
                break

            if not user_input:
                continue


        if user_input.lower() == "/quit":
            farewell = "Roger that, Boss. Signing off. See you soon!"
            print(f"\n  Chaari: {farewell}")
            if voice_mode and audio_modules:
                audio_modules["tts"].speak(farewell)
            for t in voice_triggers.values():
                try:
                    t.stop()
                except Exception:
                    pass
            break

        if user_input.lower() == "/clear":
            brain.clear_history()
            print("  [System] Conversation history cleared.")
            continue

        if user_input.lower() == "/memory":
            print("\n  ─── Stored Memory ───")
            name = memory.get_user_name()
            print(f"  Name: {name or 'Unknown'}")
            print(f"  Sessions: {memory.get_session_count()}")
            print(f"  Last active: {memory.get_last_active() or 'N/A'}")
            facts = memory.get_facts()
            if facts:
                print(f"  Facts: {', '.join(facts[-5:])}")
            prefs = memory.data['user'].get('preferences', {})
            if prefs:
                for k, v in prefs.items():
                    print(f"  Pref [{k}]: {v}")
            moods = memory.get_recent_moods(5)
            if moods:
                print(f"  Recent moods: {', '.join(m['mood'] for m in moods)}")
            print("  ────────────────────")
            continue

        if user_input.lower().startswith("/name"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                name = parts[1].strip()
                memory.set_user_name(name)
                print(f"  [System] Name set to: {name}")
            else:
                print("  [System] Usage: /name YourName")
            continue

        if user_input.lower() == "/reset":
            confirm = input("  [System] Reset ALL memory? (y/n): ").strip().lower()
            if confirm == "y":
                memory.reset()
                brain.clear_history()
                print("  [System] Memory wiped. Fresh start.")
            else:
                print("  [System] Reset cancelled.")
            continue

        if user_input.lower() == "/stream":
            streaming = not streaming
            mode = "ON" if streaming else "OFF"
            print(f"  [System] Streaming mode: {mode}")
            continue

        if user_input.lower().startswith("/voice"):
            parts = user_input.strip().split()
            subcmd = parts[1].lower() if len(parts) > 1 else "toggle"

            if subcmd == "off":
                voice_mode = False
                for t in voice_triggers.values():
                    try:
                        t.stop()
                    except Exception:
                        pass
                print("  [System] Voice mode: OFF (text only)")
            elif subcmd == "on":
                if not audio_modules:
                    audio_modules = load_audio_modules()
                if audio_modules:
                    voice_mode = True
                    if not voice_triggers:
                        import threading as _threading
                        voice_event = _threading.Event()
                        def _vcb():
                            try:
                                from audio.sound_effects import play_wake_sfx
                                play_wake_sfx()
                            except Exception:
                                pass
                            voice_event.set()
                        voice_triggers = load_voice_triggers(audio_modules, _vcb)
                    for t in voice_triggers.values():
                        try:
                            t.start()
                        except Exception:
                            pass
                    print("  [System] Voice mode: ON")
                else:
                    print("  [System] Audio not available. Install dependencies first.")
            elif subcmd == "status":
                print(f"\n  ─── Voice Status ───")
                print(f"    Voice mode: {'ON' if voice_mode else 'OFF'}")
                if audio_modules:
                    stt = audio_modules["stt"]
                    tts = audio_modules["tts"]
                    print(f"    STT backend: {stt.backend_name}")
                    print(f"    TTS loaded: {tts.is_loaded()}")
                    print(f"    TTS speaking: {tts.is_speaking()}")
                wk = voice_triggers.get("wake_word")
                kb = voice_triggers.get("keyboard")
                print(f"    Wake word: {'Active' if wk and wk.is_listening() else 'Inactive'}")
                print(f"    Keyboard hotkey: {'Active' if kb and kb.is_active() else 'Inactive'}")
                print(f"  ────────────────────")
            else:
                if voice_mode:
                    voice_mode = False
                    for t in voice_triggers.values():
                        try:
                            t.stop()
                        except Exception:
                            pass
                    print("  [System] Voice mode: OFF (text only)")
                else:
                    if not audio_modules:
                        audio_modules = load_audio_modules()
                    if audio_modules:
                        voice_mode = True
                        for t in voice_triggers.values():
                            try:
                                t.start()
                            except Exception:
                                pass
                        print("  [System] Voice mode: ON")
                    else:
                        print("  [System] Audio not available. Install dependencies first.")
            continue

        if user_input.lower() == "/voices":
            if audio_modules:
                print("\n  ─── TTS Voice Info ───")
                try:
                    from config.voice import ASSISTANT_VOICE, HINDI_VOICE
                    print(f"    Primary: {ASSISTANT_VOICE}")
                    print(f"    Hindi: {HINDI_VOICE}")
                    print(f"    Engine: Edge TTS (neural)")
                    print(f"    Fallback: pyttsx3 (offline)")
                except Exception:
                    print("    Voice config not available.")
                print("  ────────────────────")
            else:
                print("  [System] TTS not loaded. Enable voice mode first: /voice on")
            continue

        if user_input.lower() == "/tools":
            print("\n  ─── Available Tools ───")
            tools = brain.tools.list_tools()
            for name, available in tools.items():
                status = "✅ Active" if available else "❌ Unavailable"
                print(f"    {name}: {status}")
            executor_type = type(brain.executor).__name__
            print(f"\n  Executor: {executor_type}")
            supported = brain.executor.get_supported_intents()
            print(f"  Supported intents: {', '.join(supported)}")
            print("  ────────────────────")
            continue

        if user_input.lower() == "/unblock":
            brain.safety.reset_session_block()
            brain.clear_history()
            print("  [System] Session unblocked. Strikes reset. Be careful, Boss!")
            continue

        if user_input.lower() == "/crypto":
            print("\n  ─── Crypto Layer Status ───")
            info = key_mgr.get_key_info()
            for key_name, key_info in info.items():
                if key_info["exists"]:
                    print(f"    🔑 {key_name}: ✅ ({key_info['size_bytes']}B, modified {key_info['modified'][:19]})")
                else:
                    print(f"    🔑 {key_name}: ❌ Missing")
            print("  ────────────────────")
            continue

        if user_input.lower() == "/hierarchy":
            from models.intent_hierarchy import list_hierarchy, CapabilityGroup
            print("\n  ─── Intent Hierarchy ───")
            hierarchy = list_hierarchy()
            for group_name, intents in hierarchy.items():
                print(f"\n  📦 {group_name}:")
                for ns, flat in intents.items():
                    print(f"    {ns} → {flat}")
            print("\n  ────────────────────")
            continue

        if user_input.lower() == "/groq":
            status = brain.groq.get_status()
            print("\n  ─── Groq API Status ───")
            print(f"    SDK installed: {'✅' if status['sdk_installed'] else '❌'}")
            print(f"    API key set:   {'✅' if status['has_key'] else '❌ (set GROQ_API_KEY)'}")
            print(f"    Available:     {'✅ Active' if status['available'] else '⚠️ Using Ollama'}")
            print(f"    Model:         {status['model']}")
            print(f"    Today used:    {status['today_used']} / {status['daily_limit']}")
            print(f"    Remaining:     {status['today_remaining']}")
            if status['rate_limited']:
                print(f"    ⚠️ Rate limited — cooling down")
            current = brain._llm_backend_label()
            print(f"    Current LLM:   {current}")
            print("  ────────────────────")
            continue

        if user_input.lower().startswith("/connect"):
            parts = user_input.strip().split()
            if conn_mgr is None:
                from network.connection_manager import ConnectionManager
                conn_mgr = ConnectionManager()
            host = parts[1] if len(parts) > 1 else "127.0.0.1"
            port = int(parts[2]) if len(parts) > 2 else 9734
            print(f"\n  [NET] Connecting to Dell at {host}:{port}...")
            ok = conn_mgr.connect(host, port)
            if ok:
                print(f"  [NET] ✅ Connected to {conn_mgr.peer_node_id}")
            else:
                print(f"  [NET] ❌ Connection failed (will retry in background)")
            continue

        if user_input.lower() == "/nodes":
            if conn_mgr is None:
                print("\n  [NET] Not initialized. Use /connect first.")
            else:
                print("\n  ─── Dell Node Status ───")
                reg = conn_mgr.get_registry()
                if not reg:
                    print("    No nodes registered. Use /connect <host> [port]")
                else:
                    for key, info in reg.items():
                        s = info.get('status', 'unknown')
                        icon = {"connected": "✅", "unavailable": "⚠️", "disconnected": "⭕"}.get(s, "❓")
                        print(f"    {icon} {key} ({info.get('node_id','?')}) — {s}")
                        if info.get('error'):
                            print(f"       Error: {info['error']}")
                print("  ────────────────────")
            continue

        if user_input.lower().startswith("/remote"):
            if conn_mgr is None or not conn_mgr.is_connected:
                print("\n  [NET] Not connected to Dell. Use /connect first.")
                continue
            parts = user_input.strip().split(maxsplit=2)
            if len(parts) < 2:
                print("  Usage: /remote <intent> [context_json]")
                print("  Example: /remote FILESYSTEM.FILE.CREATE {\"path\":\"C:\\\\test.txt\"}")
                continue
            intent = parts[1]
            ctx = {}
            if len(parts) > 2:
                try:
                    import json as _json
                    ctx = _json.loads(parts[2])
                except Exception as e:
                    print(f"  ❌ Invalid context JSON: {e}")
                    continue
            from crypto.packet_builder import PacketBuilder
            from models.intent_hierarchy import INTENT_CAPABILITY_MAP, INTENT_NAMESPACE
            from core.system_intent import SystemIntent
            cap_group = "FILESYSTEM"  
            for si, ns in INTENT_NAMESPACE.items():
                if ns == intent:
                    cap_group = INTENT_CAPABILITY_MAP.get(si, "FILESYSTEM").value if hasattr(INTENT_CAPABILITY_MAP.get(si), 'value') else str(INTENT_CAPABILITY_MAP.get(si, "FILESYSTEM"))
                    break
            packet = PacketBuilder.build_command_packet(
                node_id="dell-01", intent=intent,
                capability_group=cap_group, tier=1, context=ctx,
            )
            asus_priv = key_mgr.load_private_key("asus")
            signed = PacketBuilder.sign_packet(packet, asus_priv)
            print(f"  [NET] Sending: {intent}...")
            try:
                result = conn_mgr.send_command(signed)
                status = result.get('status', 'unknown')
                icon = "✅" if status == "success" else "❌"
                print(f"  [NET] Result: {icon} {status}")
                if result.get('output'):
                    print(f"  [NET] Output: {result['output']}")
                if result.get('error'):
                    print(f"  [NET] Error: {result['error']}")
            except ConnectionError as e:
                print(f"  [NET] ❌ {e}")
            continue

        if user_input.lower().startswith("/contacts"):
            from core.contacts import list_contacts, add_contact, remove_contact, _load_store
            parts = user_input.strip().split(maxsplit=4)
            if len(parts) == 1:
                store = _load_store()
                contacts = store.get("contacts", {})
                if not contacts:
                    print("\n  📇 No contacts saved.")
                    print("  Usage:")
                    print("    /contacts add <name> <phone> [tg_user] [search_name]")
                    print("    /contacts remove <name>")
                    print("    /contacts set <name> search_name <value>")
                else:
                    print("\n  ─── Contacts ───")
                    for name, info in contacts.items():
                        phone = info.get('phone', '—')
                        tg = info.get('telegram', '')
                        sn = info.get('search_name', '')
                        tg_str = f" | TG: @{tg}" if tg else ""
                        sn_str = f" | Search: \"{sn}\"" if sn else ""
                        print(f"    {name}: {phone}{tg_str}{sn_str}")
                    print("  ────────────────")
            elif len(parts) >= 3 and parts[1].lower() == "add":
                name = parts[2].lower()
                rest = parts[3] if len(parts) > 3 else ""
                if not rest:
                    print("  Usage: /contacts add <name> <phone> [tg_user] [search_name]")
                else:
                    rest_parts = rest.split(maxsplit=2)
                    phone = rest_parts[0]
                    tg_user = rest_parts[1] if len(rest_parts) > 1 else ""
                    search_n = rest_parts[2] if len(rest_parts) > 2 else ""
                    add_contact(name, phone, tg_user, search_name=search_n)
                    msg = f"  ✅ Contact '{name}' added: {phone}"
                    if tg_user:
                        msg += f" | TG: @{tg_user}"
                    if search_n:
                        msg += f" | Search name: \"{search_n}\""
                    print(msg)
            elif len(parts) >= 5 and parts[1].lower() == "set":
                name = parts[2].lower()
                field = parts[3].lower()
                value = parts[4] if len(parts) > 4 else ""
                if field == "search_name" and value:
                    add_contact(name, search_name=value)
                    print(f"  ✅ Set search_name for '{name}' to \"{value}\"")
                elif field == "telegram" and value:
                    add_contact(name, telegram=value)
                    print(f"  ✅ Set Telegram username for '{name}' to @{value}")
                else:
                    print("  Usage: /contacts set <name> search_name <value>")
                    print("         /contacts set <name> telegram <username>")
            elif len(parts) >= 3 and parts[1].lower() == "remove":
                name = parts[2].lower()
                result = remove_contact(name)
                if "removed" in result.lower():
                    print(f"  ✅ {result}")
                else:
                    print(f"  ❌ {result}")
            else:
                print("  Usage:")
                print("    /contacts                              — List all contacts")
                print("    /contacts add <name> <phone> [tg] [sn] — Add contact")
                print("    /contacts remove <name>                — Remove contact")
                print("    /contacts set <name> search_name <val> — Set search name")
            continue


        if voice_mode and audio_modules:
            tts = audio_modules["tts"]
            interrupt = audio_modules["interrupt"]

            print("\n  Chaari: ", end="", flush=True)
            full_response = ""
            
            if "wake_word" in voice_triggers:
                voice_triggers["wake_word"].pause()

            tts.start_chunk_stream()
            for chunk in brain.chat_stream_chunks(user_input):
                print(chunk, end=" ", flush=True)
                full_response += chunk + " "
                if not tts.stop_flag:
                    tts.push_chunk(chunk)
            tts.finish_chunk_stream()
            
            print() 

            if "wake_word" in voice_triggers:
                voice_triggers["wake_word"].resume()

        elif streaming:
            print("\n  Chaari: ", end="", flush=True)
            full_response = ""
            for token in brain.chat_stream(user_input):
                print(token, end="", flush=True)
                full_response += token
            print()  
        else:
            full_response = brain.chat(user_input)
            print(f"\n  Chaari: {full_response}")

        if voice_mode and audio_modules and full_response.strip() and not (voice_mode and streaming):
            tts = audio_modules["tts"]
            interrupt = audio_modules["interrupt"]
            speak_with_interrupt_fn = audio_modules["speak_with_interrupt"]
            if "wake_word" in voice_triggers:
                voice_triggers["wake_word"].pause()
            was_interrupted = speak_with_interrupt_fn(tts, full_response.strip(), interrupt)
            if "wake_word" in voice_triggers:
                voice_triggers["wake_word"].resume()
            if was_interrupted:
                print("  [System] Speech interrupted — listening for new input...")


if __name__ == "__main__":
    boot_chaari()

