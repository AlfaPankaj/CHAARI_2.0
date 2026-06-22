# CHAARI 2.0

> **C**omprehensive **H**inglish **A**I **A**gentic **R**untime **I**nterface

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
![VRAM](https://img.shields.io/badge/VRAM-4GB%20RTX%202050-orange)
![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Tests](https://img.shields.io/badge/Tests-369%2B%20automated-blue)

---

**CHAARI 2.0 is a privacy-first, full-duplex, bilingual agentic AI voice operating companion** — not a chatbot. It controls your computer, speaks Hinglish natively, runs on 4 GB VRAM, and operates across a two-node cryptographic mesh with RSA-2048 signed command packets, replay-protected nonces, and a 7-layer safety pipeline. Built for Indian developers and the next billion users; designed to interest anyone working on edge-deployed, safety-critical agentic AI systems.

---
## 📸 Demo

### Terminal Interface
![CHAARI 2.0 Terminal](assets/demo_terminal.png)
*CLI mode — boots with a welcome message and full command list*

### Web Dashboard
![CHAARI 2.0 Web Dashboard](assets/demo_web.png)
*Gradio-powered web UI at `http://127.0.0.1:7860` with system status panel*
---

## Key Features

### 🎙️ Full-Duplex Voice
- **Wake word**: "Hey CHAARI" (OpenWakeWord) + `Ctrl+Space` keyboard trigger
- **STT**: Chrome Web Speech API (live, word-by-word) with Faster Whisper fallback
- **TTS**: Microsoft Edge TTS neural voices (`en-US-AriaNeural` / `hi-IN-SwaraNeural`) with Jarvis-style echo effect and pre-cached phrase playback for instant responses
- Sub-800 ms end-to-end voice conversation latency; sub-100 ms for tool calls

### 🇮🇳 Hinglish-Native Personality
- Fine-tuned **Qwen 3.5 4.2B** on a custom Hinglish dataset — 30–40 tok/s on 4 GB VRAM
- Feminine Hindi grammar enforced at the prompt level (`kar rahi hoon`, `karungi`, `sakti hoon`)
- Cultural register vocabulary: *Boss*, *Sir-ji*, *Yaar*, *Bilkul*, *Theek hai*
- Hard-coded identity lock: name = Chaari, creator = Pankaj — cannot be overridden at runtime

### 🔐 Cryptographic Security
- **RSA-2048** signing on every command packet (ASUS private key → Dell public key verification)
- **Nonce replay protection** — every packet carries a unique nonce; replays rejected by `DellNonceStore`
- **3-step handshake**: `hello → response → ack` before any command is accepted
- IP whitelist enforcement on the Dell node; timestamp window (±60 s) + nonce TTL (5 min)
- Append-only `AuditLogger` with structured `AuditEventType` + `AuditSeverity` classification

### 🛡️ 7-Layer Safety Pipeline
Runs **before and after** the LLM — code-based logic, not prompt-based:
`Safety → Audit → Identity → Policy → Tools → Confirm → Privilege → LLM`

### 🧠 RAPTOR Hierarchical RAG
- **3-level RAPTOR tree**: Layer 0 (raw chunks) → Layer 1 (cluster summaries) → Layer 2 (abstract)
- `tree_builder.py` constructs the hierarchy; `rag_agent.py` retrieves across all levels
- Groq API used for cluster summarization; local embeddings for retrieval
- RAG pipeline latency: 10–12 s (indexing); sub-second retrieval on a pre-built tree

### ⚡ Hardware-Constrained Design
- Runs on ASUS laptop with **RTX 2050 (4 GB VRAM)**, 16 GB RAM
- Target: 4–8 GB RAM devices — no cloud dependency for core voice/tool loop
- Groq API as primary LLM (llama-3.1-8b-instant, ~200 ms first token) → Ollama local fallback
- Lazy imports, reduced context windows (1024 tok default), fast LLM options for simple queries

### 📡 S2S Pipeline (In Development)
- Speech-to-Speech pipeline targeting sub-200 ms round-trip
- Dell node carries its own `audio/voice_interface.py` for local TTS output

### 👁️ Vision Module
- OCR + **Llava 7B** (via Ollama) for screen and image understanding
- `VisionEngine` integrated directly into the Brain pipeline

### 🔧 Agentic OS Control
- Opens, closes, minimizes, maximizes, types into applications
- File operations (create, delete, copy, move) with tiered confirmation
- System info (CPU %, RAM %, battery, disk, network, uptime) via `psutil`
- WhatsApp / Telegram messaging and calls
- Compound command splitting (`open notepad and then type hello`)
- Shutdown / restart with 6-digit safety code (Tier 3 privilege gate)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CHAARI 2.0 — Two-Node Mesh                   │
│                                                                      │
│  ┌──────────────────────────────────┐                               │
│  │       ASUS Brain Node            │  RTX 2050 · 4 GB VRAM        │
│  │  ┌────────────────────────────┐  │  16 GB RAM · Windows         │
│  │  │  Wake Word / Keyboard      │  │                               │
│  │  │  STT (Chrome / Whisper)    │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  7-Layer Safety Pipeline   │  │                               │
│  │  │  Safety → Audit → Identity │  │                               │
│  │  │  → Policy → Tools →        │  │                               │
│  │  │  Confirm → Privilege       │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  Brain (LLM Orchestrator)  │  │                               │
│  │  │  ├─ Groq API (primary)     │  │                               │
│  │  │  ├─ Ollama local (fallback)│  │                               │
│  │  │  ├─ RAPTOR RAG Agent       │  │                               │
│  │  │  ├─ Vision Engine          │  │                               │
│  │  │  └─ Session / Memory       │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  RSA-2048 Packet Signer    │  │                               │
│  │  └────────────────────────────┘  │                               │
│  │           │  TCP :9734           │                               │
│  └───────────┼──────────────────────┘                               │
│              │  3-step handshake                                     │
│              │  Signed + nonce-protected packets                     │
│              ↓                                                       │
│  ┌──────────────────────────────────┐                               │
│  │       Dell Executor Node         │  Dell Latitude · Windows      │
│  │  ┌────────────────────────────┐  │                               │
│  │  │  TCP Server (DellServer)   │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  7-Step Validation          │  │                               │
│  │  │  1. Structure               │  │                               │
│  │  │  2. IP Whitelist            │  │                               │
│  │  │  3. RSA Signature           │  │                               │
│  │  │  4. Timestamp Window        │  │                               │
│  │  │  5. Nonce Replay Check      │  │                               │
│  │  │  6. Capability Auth         │  │                               │
│  │  │  7. Privilege Token         │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  Capability Router          │  │                               │
│  │  │  ├─ POWER module            │  │                               │
│  │  │  ├─ FILESYSTEM module       │  │                               │
│  │  │  ├─ APPLICATION module      │  │                               │
│  │  │  ├─ SYSTEM module           │  │                               │
│  │  │  ├─ COMMUNICATION module    │  │                               │
│  │  │  └─ MEDIA module            │  │                               │
│  │  │  ↓                         │  │                               │
│  │  │  Dell RSA-2048 Result Sign  │  │                               │
│  │  └────────────────────────────┘  │                               │
│  └──────────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

**Key design principle**: The ASUS Brain thinks and decides. The Dell Executor only runs hardcoded OS actions against validated, cryptographically-signed packets. A `FILESYSTEM` command can never reach the `POWER` module — routing is capability-group–based, not intent-string–based.

---

## 🛠️ Tool Selection & Intent Hierarchy

To prevent cross-module safety breaches, CHAARI 2.0 uses a structured **Intent Hierarchy System** mapped to isolated **Capability Groups** on the execution plane. Each capability group handles exactly one domain of system operations, ensuring that filesystems, media interfaces, and network sockets are strictly walled from each other.

### Capability Isolation Groups
1. **POWER:** Critical power control actions (Shutdown, Restart, Lock).
2. **FILESYSTEM:** File operations (Create, Open, Copy, Move, Delete).
3. **APPLICATION:** App lifecycle and window management (Launch, Close, Minimize, Maximize, discovery).
4. **COMMUNICATION:** External integration interface (Telegram/WhatsApp GUI macros, contact dialing, text input simulation).
5. **MEDIA:** Capture and audio drivers (Volume controls, screenshots, OCR processes).
6. **WEB:** Browser and search bindings (Google searches, YouTube player controls, domain routing).
7. **SYSTEM:** Deep OS system utilities (Registry modifications, active processes management, storage formatting).

### Namespace & Safety Tier Mapping Table
User speech inputs are parsed and resolved into one of the following hardcoded intents. No dynamic strings or shell commands are ever passed directly to the executor nodes:

| Flat Intent | Capability Group | Hierarchical Namespace | Execution Safety Tier | Details & Automation Library |
|---|---|---|---|---|
| `SHUTDOWN` | `POWER` | `SYSTEM.POWER.SHUTDOWN` | **Tier 3** (Destructive) | Shutdown command (requires 6-digit OTC) |
| `RESTART` | `POWER` | `SYSTEM.POWER.RESTART` | **Tier 3** (Destructive) | Reboot system (requires 6-digit OTC) |
| `LOCK_SCREEN` | `POWER` | `SYSTEM.POWER.LOCK` | **Tier 1** (Safe) | Locks the Windows screen via User32 DLL |
| `CREATE_FILE` | `FILESYSTEM` | `FILESYSTEM.FILE.CREATE` | **Tier 2** (High-Risk) | Creates files with verified file extension |
| `DELETE_FILE` | `FILESYSTEM` | `FILESYSTEM.FILE.DELETE` | **Tier 2** (High-Risk) | Deletes files with user confirmation |
| `COPY_FILE` | `FILESYSTEM` | `FILESYSTEM.FILE.COPY` | **Tier 2** (High-Risk) | Copies files to target directory paths |
| `MOVE_FILE` | `FILESYSTEM` | `FILESYSTEM.FILE.MOVE` | **Tier 2** (High-Risk) | Moves files to target directory paths |
| `OPEN_FILE` | `FILESYSTEM` | `FILESYSTEM.FILE.OPEN` | **Tier 2** (High-Risk) | Safely opens local files using os.startfile |
| `OPEN_FOLDER` | `FILESYSTEM` | `FILESYSTEM.FOLDER.OPEN` | **Tier 1** (Safe) | Opens directories in Windows Explorer |
| `OPEN_APP` | `APPLICATION` | `APPLICATION.LIFECYCLE.LAUNCH` | **Tier 1** (Safe) | Launches whitelisted application binaries |
| `CLOSE_APP` | `APPLICATION` | `APPLICATION.LIFECYCLE.TERMINATE` | **Tier 2** (High-Risk) | Closes active application window threads |
| `MINIMIZE_APP` | `APPLICATION` | `APPLICATION.WINDOW.MINIMIZE` | **Tier 1** (Safe) | Minimizes foreground window via Win32 GUI |
| `MAXIMIZE_APP` | `APPLICATION` | `APPLICATION.WINDOW.MAXIMIZE` | **Tier 1** (Safe) | Maximizes active application viewport |
| `RESTORE_APP` | `APPLICATION` | `APPLICATION.WINDOW.RESTORE` | **Tier 1** (Safe) | Restores application windows from taskbar |
| `SWITCH_WINDOW` | `APPLICATION` | `APPLICATION.WINDOW.SWITCH` | **Tier 1** (Safe) | Toggles active foreground window targets |
| `LIST_APPS` | `APPLICATION` | `APPLICATION.DISCOVERY.LIST` | **Tier 1** (Safe) | Scans system start menu directories |
| `SEND_MESSAGE` | `COMMUNICATION` | `COMMUNICATION.MESSAGING.SEND` | **Tier 2** (High-Risk) | WhatsApp Desktop GUI macros (PyAutoGUI) |
| `MAKE_CALL` | `COMMUNICATION` | `COMMUNICATION.CALLING.DIAL` | **Tier 2** (High-Risk) | WhatsApp Desktop voice calling automation |
| `TYPE_TEXT` | `COMMUNICATION` | `COMMUNICATION.INPUT.TYPE_TEXT` | **Tier 2** (High-Risk) | Simulates keyboard text entry sequences |
| `VOLUME_UP` | `MEDIA` | `MEDIA.AUDIO.VOLUME_UP` | **Tier 1** (Safe) | Increments system volume level using ctypes |
| `VOLUME_DOWN` | `MEDIA` | `MEDIA.AUDIO.VOLUME_DOWN` | **Tier 1** (Safe) | Decrements system volume level using ctypes |
| `MUTE` | `MEDIA` | `MEDIA.AUDIO.MUTE` | **Tier 1** (Safe) | Toggles system volume mute state |
| `SCREENSHOT` | `MEDIA` | `MEDIA.CAPTURE.SCREENSHOT` | **Tier 1** (Safe) | Captures desktop screen (Pillow library) |
| `SCREENSHOT_WINDOW` | `MEDIA` | `MEDIA.CAPTURE.SCREENSHOT_WINDOW` | **Tier 1** (Safe) | Captures currently focused window viewport |
| `OCR_SCREEN` | `MEDIA` | `MEDIA.CAPTURE.OCR_SCREEN` | **Tier 1** (Safe) | OCR scan using Tesseract engine |
| `SEARCH_GOOGLE` | `WEB` | `WEB.SEARCH.GOOGLE` | **Tier 1** (Safe) | Searches query via selenium / default browser |
| `SEARCH_YOUTUBE` | `WEB` | `WEB.SEARCH.YOUTUBE` | **Tier 1** (Safe) | Opens query query in Youtube webpage |
| `OPEN_WEBSITE` | `WEB` | `WEB.BROWSE.OPEN` | **Tier 1** (Safe) | Opens verified URL in browser |
| `KILL_PROCESS` | `SYSTEM` | `SYSTEM.PROCESS.KILL` | **Tier 2** (High-Risk) | Terminates running processes using psutil |
| `MODIFY_REGISTRY` | `SYSTEM` | `SYSTEM.REGISTRY.MODIFY` | **Tier 4** (Creator-Only) | Edits Windows registry properties (restricted) |
| `FORMAT_DISK` | `SYSTEM` | `SYSTEM.STORAGE.FORMAT` | **Tier 4** (Creator-Only) | Administrative disk formatting commands (restricted) |

---

## Performance Benchmarks

| Component | Target | Notes |
|---|---|---|
| Tool call round-trip | **< 100 ms** | OS actions (open app, file op, system info) |
| LLM voice conversation | **< 800 ms** | Groq API primary; Ollama fallback ~2–4 s |
| Groq first token | **~200 ms** | `llama-3.1-8b-instant` |
| RAG retrieval (pre-built tree) | **< 1 s** | RAPTOR 3-level hierarchical |
| RAG indexing (build tree) | **10–12 s** | Cluster summarization via Groq |
| TTS (pre-cached phrases) | **< 50 ms** | MD5-hashed phrase cache (`audio_cache/phrases/`) |
| TTS (new utterance) | **< 400 ms** | Edge TTS streaming + pygame |
| S2S round-trip (target) | **< 200 ms** | In development |
| Qwen 3.5 4.2B (local) | **30–40 tok/s** | RTX 2050 4 GB VRAM |

---

## 🛠️ Tech Stack

### LLM & Inference
| Component | Technology |
|---|---|
| Cloud LLM (primary) | Groq API — `llama-3.1-8b-instant` |
| Local LLM (fallback) | Ollama — `chaari-2.0:latest` (Qwen 2.5 4B fine-tune) |
| Fine-tuning base | Qwen 2.5 4B · custom Hinglish instruction dataset (GenderShield verified) |
| Vision | Llava 7B via Ollama · Tesseract OCR |

### Voice Pipeline
| Component | Technology |
|---|---|
| STT (primary) | Chrome Web Speech API (live streaming) |
| STT (fallback) | Faster Whisper (offline, local) |
| TTS | Microsoft Edge TTS · `en-IN-NeerjaNeural` (Indian Female Voice) |
| Audio playback | pygame · Jarvis-style stereo echo effect |
| Wake word | OpenWakeWord — `Hey CHAARI` |
| Keyboard trigger | `Ctrl+Space` / `F5` |

### Security & Crypto
| Component | Technology |
|---|---|
| Packet signing | RSA-2048 (PyCryptodome / cryptography) |
| Replay protection | Nonce store with TTL expiry |
| Session handshake | 3-step challenge-response |
| Audit trail | Append-only structured JSONL event log |
| Confirmation codes | OTC-style 6-digit one-time codes |

### RAG & Memory
| Component | Technology / Library | Version / Depth |
|---|---|---|
| Vector Store | ChromaDB | `>=0.4.0` |
| Text Embeddings | `sentence-transformers` | `>=2.2.0` |
| Clustering Engine | `scikit-learn` | `>=1.3.0` |
| RAG Architecture | RAPTOR Hierarchical Retrieval Tree | 3-Level (Raw, Clusters, Summaries) |
| PDF Parsing | `pypdf` | `>=3.0.0` |
| Tokenizer | `tiktoken` | `>=0.5.0` |
| Memory | In-session sliding window | Configurable history depth |

### Infrastructure
| Component | Technology |
|---|---|
| Inter-node transport | Encrypted TCP · RSA-signed packets |
| Web UI | Gradio chatbot interface |
| Testing | pytest · 369+ automated tests |
| Config management | Per-module Python config files |

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running (`ollama serve`)
- [Groq API key](https://console.groq.com/) (free tier is sufficient)
- For voice mode: Chrome browser (STT) + `edge-tts`, `pygame`, `pynput`
- For wake word: `openwakeword`
- RTX GPU recommended (4 GB+ VRAM) for local Qwen inference; CPU-only works in Groq-only mode

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/chaari-2.0.git
cd chaari-2.0

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the base model (or use your fine-tuned Qwen)
ollama pull llama3.2:3b      # Lightweight fallback
# ollama run chaari-2.0:latest  # Your fine-tuned model

# 5. Generate RSA-2048 keypairs for both nodes
python -m chaari_2_0.crypto.key_manager --generate
```

### Configuration

```bash
# Set your Groq API key
# Windows
set GROQ_API_KEY=your_key_here

# Linux/macOS
export GROQ_API_KEY=your_key_here
```

Edit `chaari_dell/config.py` to set the ASUS node's LAN IP:
```python
ASUS_IP_WHITELIST = [
    "127.0.0.1",
    "192.168.1.XXX",   # ← your ASUS machine's LAN IP
]
```

### Running the ASUS Brain Node

```bash
# Text-only mode
python chaari_2_0/main.py

# Voice mode (Chrome STT + Edge TTS)
python chaari_2_0/main.py --voice

# Voice with Whisper fallback
python chaari_2_0/main.py --voice --stt-backend=whisper

# Launch Gradio web UI
python chaari_2_0/skills/chaari-web-ui/scripts/gradio_app.py
```

### Running the Dell Executor Node

```bash
cd chaari_dell

# Start the Dell execution agent
python agent.py

# Self-test with synthetic packets (no ASUS connection needed)
python agent.py --test-local

# Run Dell-side tests
python test_phase4_dell.py
```

### Running the Test Suite

```bash
# Full test suite
python chaari_2_0/Tests/run_master_test.py

# Individual test modules
python -m pytest chaari_2_0/Tests/test_phase3_crypto.py -v
python -m pytest chaari_2_0/Tests/test_rag_pipeline.py -v
python -m pytest chaari_2_0/Tests/test_phase6_voice.py -v
```

---

## Project Structure

```
CHAARI 2.0/
│
├── chaari_2_0/                      # ASUS Brain Node
│   ├── main.py                      # Entry point: voice + text terminal interface
│   ├── index_knowledge.py           # RAPTOR RAG index builder
│   ├── test_gradio_chatbot.py       # Gradio chatbot test harness
│   │
│   ├── audio/                       # Voice I/O subsystem
│   │   ├── stt_engine.py            # STT: Chrome Web Speech + Whisper fallback
│   │   ├── tts_engine.py            # TTS: Edge TTS + pygame + echo effect + phrase cache
│   │   ├── wake_word.py             # OpenWakeWord — "Hey CHAARI" trigger
│   │   ├── keyboard_trigger.py      # Ctrl+Space hotkey listener (pynput)
│   │   ├── interrupt_handler.py     # Mid-speech interrupt detection
│   │   ├── mic_listener.py          # Microphone input manager
│   │   └── sound_effects.py         # Boot/confirm/error sound effects
│   │
│   ├── core/                        # Brain and all pipeline layers
│   │   ├── brain.py                 # Central orchestrator: wires all 7 layers + LLM
│   │   ├── safety.py                # Layer 0: injection detection, tier classification
│   │   ├── audit_logger.py          # Layer 0.5: append-only JSONL audit trail
│   │   ├── identity.py              # Layer 1: hard-coded identity lock (name, creator)
│   │   ├── policy_engine.py         # Layer 1.5: governance rules, tier thresholds
│   │   ├── tools.py                 # Layer 2: tool registry and OS action dispatch
│   │   ├── confirmation.py          # Layer 2.5: one-time code management
│   │   ├── privilege.py             # Layer 2.6: creator mode state tracking
│   │   ├── session_manager.py       # Layer 2.7: per-session strikes and state
│   │   ├── os_executor.py           # OS command executor (injected into Brain)
│   │   ├── commands.py              # SystemCommandRegistry: Tier 1–3 actions
│   │   ├── executor_port.py         # CommandExecutorPort abstraction + NoOpExecutor
│   │   ├── intent_parser.py         # Raw intent extraction from user text
│   │   ├── intent_resolver.py       # Intent resolution: maps parsed intent → action
│   │   ├── system_intent.py         # SystemIntent enum (structured intent types)
│   │   ├── groq_provider.py         # Groq API client wrapper
│   │   ├── rag_agent.py             # RAPTOR RAG retrieval agent
│   │   ├── tree_builder.py          # RAPTOR tree construction (3-level hierarchy)
│   │   ├── vectorstore.py           # Local vector store (embeddings + FAISS/Chroma)
│   │   ├── embeddings.py            # Embedding model wrapper
│   │   ├── doc_loader.py            # Document ingestion (PDF, TXT, MD)
│   │   ├── vision_engine.py         # Vision: OCR + Llava 7B via Ollama
│   │   ├── personality.py           # Personality engine: guardrails + Hinglish style
│   │   ├── memory.py                # Conversation memory (session + persistent)
│   │   ├── contacts.py              # Contact book for WhatsApp/Telegram
│   │   └── ...                      # (39+ modules total)
│   │
│   ├── crypto/                      # ASUS-side cryptographic primitives
│   │   ├── key_manager.py           # RSA-2048 key generation and loading
│   │   ├── signer.py                # Packet signing (ASUS private key)
│   │   ├── packet_builder.py        # Constructs signed command packets
│   │   └── nonce_store.py           # Nonce issuance and tracking
│   │
│   ├── network/                     # ASUS-side network layer
│   │   └── connection_manager.py    # TCP connection to Dell node
│   │
│   ├── config/                      # Configuration files
│   │   ├── rag.py                   # RAG chunking, tree depth, retrieval params
│   │   ├── security.py              # Safety thresholds, tier definitions
│   │   └── voice.py                 # TTS voice selection, echo params, cache dirs
│   │
│   ├── models/                      # Shared data models
│   │   └── intent_hierarchy.py      # Intent type hierarchy
│   │
│   ├── skills/                      # UI skills
│   │   └── chaari-web-ui/
│   │       └── scripts/gradio_app.py  # Gradio web chat interface
│   │
│   └── Tests/                       # Automated test suite (369+ tests)
│       ├── run_master_test.py        # Run full suite
│       ├── test_phase2_tools.py      # Tool execution tests
│       ├── test_phase3_crypto.py     # Crypto signing/verification tests
│       ├── test_phase5_network.py    # Network protocol tests
│       ├── test_phase6_voice.py      # Voice pipeline tests
│       ├── test_rag_pipeline.py      # RAPTOR RAG tests
│       ├── test_master_flow.py       # End-to-end flow tests
│       ├── test_audit_logger.py      # Audit trail tests
│       ├── test_executor_pipeline.py # Executor pipeline tests
│       └── test_vision_host.py       # Vision engine tests
│
└── chaari_dell/                     # Dell Executor Node
    ├── agent.py                     # Entry point: boots DellAgent, starts TCP server
    ├── config.py                    # Node ID, IP whitelist, ports, key paths
    │
    ├── crypto/                      # Dell-side crypto
    │   ├── signature_verifier.py    # Verifies ASUS RSA-2048 signatures
    │   ├── validation_pipeline.py   # 7-step packet validation pipeline
    │   └── nonce_store.py           # Dell-side nonce replay store
    │
    ├── executor/                    # Capability modules (hardcoded OS actions)
    │   ├── capability_router.py     # Routes packets to correct module by group
    │   ├── power_module.py          # Shutdown, restart, sleep
    │   ├── filesystem_module.py     # File create, delete, copy, move
    │   ├── application_module.py    # Open, close, minimize, maximize apps
    │   ├── system_module.py         # CPU, RAM, disk, network queries
    │   ├── communication_module.py  # WhatsApp, Telegram messaging
    │   └── media_module.py          # Media playback control
    │
    ├── network/
    │   └── server.py                # TCP server: handshake, recv commands, send results
    │
    ├── models/
    │   └── packet_models.py         # ExecutionResult, ValidationResult, ValidationStatus
    │
    ├── audio/                       # Dell-local voice output (for S2S)
    │   └── voice_interface.py       # TTS output on Dell node
    │
    └── test_phase4_dell.py          # Dell node integration tests
```

---

## 🛡️ Safety Architecture

CHAARI 2.0 implements a **7-layer safety pipeline** that runs entirely in code — not in prompts. Every user input passes through all layers before reaching the LLM; LLM output is sanitized before execution.

| Layer | Component | Responsibility |
|---|---|---|
| **L0** | Safety Kernel | Injection detection, intent classification, tier assignment, severity scoring, LLM output sanitization |
| **L0.5** | Audit Logger | Append-only, tamper-evident log of every security event with timestamp and severity |
| **L1** | Identity Lock | Hard-codes `name=Chaari` and `creator=Pankaj` into every prompt — cannot be overridden at runtime |
| **L1.5** | Policy Engine | Governance rules — maps intents to allowed tiers, enforces context-based access control |
| **L2** | Tool Truth | App whitelist, tool registry — LLM can only invoke pre-approved tools with validated parameters |
| **L2.5** | Confirmation Engine | Manages pending confirmations and one-time codes (OTC) for Tier 3 destructive operations |
| **L2.6** | Privilege Manager | Creator mode state — Tier 4 commands only execute when creator identity is verified |

**Tier system:**
- **Tier 1** — Safe (open apps, read system info) — execute immediately
- **Tier 2** — High-risk (file operations, process kill) — require explicit confirmation
- **Tier 3** — Destructive (shutdown, restart, mass delete) — require 6-digit one-time code
- **Tier 4** — Creator-only — only accessible when creator mode is active via Privilege Manager

The Safety Kernel **never executes OS commands** — it only classifies and signals. Execution is always delegated to `SystemCommandRegistry` → `OSExecutor` on the Executor node.

---

## 🧪 Fine-Tuning & Data Preparation

CHAARI 2.0 uses a fine-tuned **Qwen 2.5 4B** as its local LLM backbone (`chaari-2.0:latest`).

**Dataset Preparation (`text_expander.py`):**
- **Data Scaling:** A custom text expansion engine, `text_expander.py`, leverages Ollama to scale a base set of 249 seed conversation samples up to a dataset of **1,000+ Hinglish dialogues**.
- **GenderShield Validation:** A regex-based safety layer (`GenderShield`) validates every generated script to ensure that CHAARI uses feminine Hindi verb endings (e.g., *rahi*, *karti*, *karungi*) for all self-representation.
- **Checkpointing:** Includes automatic recovery saving every 25 samples during compilation tasks.

**Training Configurations:**
- Base model: `Qwen/Qwen2.5-4B-Instruct`
- Method: QLoRA fine-tuning (4-bit quantized, fits in 4GB VRAM)
- Inference speed: **30–40 tok/s** on RTX 2050 4GB via Ollama

---

## 🗺️ Roadmap

- [x] **Phase 7: Triple-Brain Orchestrator** — Reflex/Core/Reasoning latency paths, VAD-based voice barge-in, and production-level CLI.
- [ ] **Phase 8: E2E S2S Model** — Perform architecture surgery on Qwen 2.5 4B for 8 audio heads and integrate Mimi codec tokenization for direct speech-to-speech inference (target: <200ms latency).
- [ ] **Offline 4GB RAM Target** — Full functionality on CPU-only devices with quantized models; designed for Tier-2/3 city users in India without high-end hardware.
- [ ] **Multi-Node Scaling** — Extend the cryptographic mesh beyond two nodes; support phone (Android) as a third executor node.
- [ ] **Android Companion App** — Lightweight mobile node that pairs with the Brain over LAN.
- [ ] **Hinglish Dataset Release** — Open-source the fine-tuning dataset for the research community.
- [ ] **Extended Tool Registry** — Calendar, email, browser automation, IoT device control.
- [ ] **Research Paper Publication** — arXiv preprint (see below).

---

## Research Paper

A research paper describing CHAARI 2.0's architecture — covering the two-node cryptographic mesh, 7-layer safety pipeline, RAPTOR RAG integration, and Hinglish fine-tuning methodology — is currently in preparation.

> 📄 **arXiv preprint coming soon**

If you are working on edge-deployed agentic AI, safety-critical voice systems, or low-resource multilingual LLMs and would like to collaborate or discuss the work, reach out directly.

---

## Author

**Pankaj Yadav**  
M.Sc. Information Technology — Lovely Professional University (LPU), Phagwara  
*Expected graduation: May 2026*

- 📧 [pankajya0003@gmail.com](mailto:pankajya0003@gmail.com)
- 💼 [LinkedIn](linkedin.com/in/pankaj-ya)
- 🐙 [GitHub](github.com/AlfaPankaj) 

Built solo on an ASUS laptop with an RTX 2050. Every module, every test, every cryptographic primitive — written by one person.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---
## Related Research
**NMOS (Neural Memory Operating System)** — a companion research project exploring Anticipatory Inference for LLMs. Achieves 70B+ model reasoning on 4 GB VRAM via behavioral signal prediction and async layer prefetching. [View NMOS →](https://github.com/AlfaPankaj/Neural_Memory_Operating_system.git)

<div align="center">

*"We are not building AI for the next billion dollars.*  
*We are building AI for the next billion users."*

**— CHAARI 2.0, built in Rudrapur, running everywhere.**

</div>
