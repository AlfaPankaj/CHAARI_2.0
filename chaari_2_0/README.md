# CHAARI 2.0

<div align="center">

**Privacy-First · Full-Duplex · Bilingual AI Operating Companion**

*Built for the next billion users — not just the next billion dollars.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2011-lightgrey?logo=windows)](https://www.microsoft.com/windows)
[![Hardware](https://img.shields.io/badge/GPU-RTX%202050%204GB-76b900?logo=nvidia)](https://www.nvidia.com/)
[![LLM](https://img.shields.io/badge/LLM-Qwen%202.5%204.2B-orange)](https://huggingface.co/Qwen)
[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)]()

</div>

---

CHAARI 2.0 is a privacy-first, full-duplex, bilingual (Hindi + English / Hinglish) agentic AI voice operating companion that runs on commodity hardware — sub-800ms conversation latency, sub-100ms tool execution, cryptographically signed inter-node communication, and a 7-layer safety pipeline — designed from the ground up for Indian users and deployable on 4–8GB RAM devices.

---

---

## ✨ Key Features

### 🎙️ Voice & Language
- **Full-Duplex Voice** — simultaneous listening and speaking; interrupt mid-sentence with a new command
- **Hinglish-Native Persona** — 60–70% English, 30–40% Hindi flavor (`kar rahi hoon`, `Boss`, `Sir-ji`, `Yaar`); feminine Hindi conjugation enforced at model level
- **Dual STT** — Chrome Web Speech API (live word-by-word streaming) with Faster Whisper as offline fallback
- **Neural TTS** — Microsoft Edge TTS with a Jarvis-style stereo echo effect; pre-cached common phrases for <50ms playback latency
- **Wake Word** — `Hey CHAARI` (OpenWakeWord) + `Ctrl+Space` keyboard trigger

### 🧠 Intelligence & RAG
- **Fine-tuned Qwen 3.5 4.2B** — custom Hinglish instruction dataset; 30–40 tok/s on 4GB VRAM
- **Groq API Primary** — `llama-3.1-8b-instant` for cloud-speed inference (~200ms first token); Ollama local fallback when quota exhausted
- **RAPTOR 3-Level Hierarchical RAG** — Layer 0 raw chunks → Layer 1 semantic clusters → Layer 2 abstract summaries; 10–12s deep retrieval
- **Persistent Memory** — session-aware conversation context with configurable history window

### 🔐 Security & Safety
- **7-Layer Safety Pipeline** — Safety → Audit → Identity → Policy → Tools → Confirm → Privilege → LLM (code-based logic, not prompt-based)
- **RSA-2048 Cryptographic Signing** — every inter-node packet is signed and verified
- **Nonce Replay Protection** — prevents replay attacks on the TCP mesh
- **3-Step Handshake** — authenticated session establishment between Brain and Executor nodes
- **Tiered Confirmation System** — Tier 1 (safe) → Tier 2 (high-risk) → Tier 3 (destructive, requires 6-digit one-time code) → Tier 4 (creator-only)
- **Append-Only Audit Log** — tamper-evident security event trail

### ⚡ Hardware & Performance
- **Designed for 4GB VRAM** — runs on ASUS laptop with RTX 2050; target: 4–8GB RAM commodity devices
- **Two-Node Cryptographic Mesh** — ASUS Brain node orchestrates; Dell Executor node runs OS commands
- **S2S Pipeline** — Speech-to-Speech direct inference under active development (target: <200ms)

### 👁️ Vision
- **OCR + Llama 7B Vision** — screenshot analysis, document reading, screen-aware context

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CHAARI 2.0 — Two-Node Mesh                  │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────┐
  │           ASUS BRAIN NODE (Orchestrator)      │
  │                                               │
  │  [Wake Word / Ctrl+Space]                     │
  │         │                                     │
  │  [STT Engine] ──Chrome WebSpeech / Whisper    │
  │         │                                     │
  │  [7-Layer Safety Pipeline]                    │
  │    L0: Safety Kernel   (injection detection)  │
  │    L0.5: Audit Logger  (append-only trail)    │
  │    L1: Identity Lock   (Chaari / Pankaj)      │
  │    L1.5: Policy Engine (governance rules)     │
  │    L2: Tool Truth      (app whitelist)        │
  │    L2.5: Confirmation  (OTC codes)            │
  │    L2.6: Privilege     (creator mode)         │
  │         │                                     │
  │  [Intent Resolver] → [Intent Parser]          │
  │         │                                     │
  │  ┌──────┴──────┐                              │
  │  │ Groq API    │ llama-3.1-8b-instant         │
  │  │ (primary)   │ ~200ms first token           │
  │  └──────┬──────┘                              │
  │         │ (fallback)                          │
  │  ┌──────┴──────┐                              │
  │  │ Ollama Local│ chaari-2.0:latest (Qwen 3.5) │
  │  └──────┬──────┘                              │
  │         │                                     │
  │  [RAPTOR RAG Agent]  ← VectorStore            │
  │  [Vision Engine]     ← OCR + Llava 7B         │
  │  [Memory]            ← Session context        │
  │         │                                     │
  │  [TTS Engine] ──Edge TTS + Echo Effect        │
  └──────────────────┬───────────────────────────┘
                     │  RSA-2048 Signed TCP Packets
                     │  Nonce-Protected · 3-Step Handshake
                     │
  ┌──────────────────▼───────────────────────────┐
  │           DELL EXECUTOR NODE                  │
  │                                               │
  │  [ExecutorPort] → [OSExecutor]                │
  │  [SystemCommandRegistry]                      │
  │         │                                     │
  │  Tier 1: Open/Close apps, read system info    │
  │  Tier 2: File ops, process kill, network ping │
  │  Tier 3: Shutdown/restart (6-digit OTC)       │
  │  Tier 4: Creator-only privileged commands     │
  │                                               │
  │  WhatsApp · Telegram · File Manager           │
  │  CPU/RAM/Battery/Disk/Network monitoring      │
  └───────────────────────────────────────────────┘
```

---

## 📊 Performance Benchmarks

| Metric | Target | Notes |
|---|---|---|
| Tool call execution | **< 100ms** | OS commands, app control, system info |
| LLM conversation (Groq) | **< 800ms** | Full-duplex response, first token ~200ms |
| LLM conversation (Ollama) | **~1–3s** | Local fallback, 30–40 tok/s on 4GB VRAM |
| RAPTOR RAG retrieval | **10–12s** | 3-level tree traversal, deep document search |
| TTS cached phrases | **< 50ms** | Pre-warmed phrase cache on boot |
| TTS neural (Edge TTS) | **< 400ms** | Streaming generate + play in parallel |
| S2S pipeline (target) | **< 200ms** | Direct Speech-to-Speech, in development |
| Wake word response | **< 300ms** | OpenWakeWord local detection |

> Hardware: ASUS laptop · RTX 2050 4GB VRAM · 16GB RAM · Windows 11

---

## 🛠️ Tech Stack

### LLM & Inference
| Component | Technology |
|---|---|
| Cloud LLM (primary) | Groq API — `llama-3.1-8b-instant` |
| Local LLM (fallback) | Ollama — `chaari-2.0:latest` (Qwen 3.5 4.2B fine-tune) |
| Fine-tuning base | Qwen 3.5 4.2B · custom Hinglish instruction dataset |
| Vision | Llava 7B via Ollama · Tesseract OCR |

### Voice Pipeline
| Component | Technology |
|---|---|
| STT (primary) | Chrome Web Speech API (live streaming) |
| STT (fallback) | Faster Whisper (offline, local) |
| TTS | Microsoft Edge TTS · `en-US-AriaNeural` / `hi-IN-SwaraNeural` |
| Audio playback | pygame · Jarvis-style stereo echo effect |
| Wake word | OpenWakeWord — `Hey CHAARI` |
| Keyboard trigger | `Ctrl+Space` (pynput) |

### Security & Crypto
| Component | Technology |
|---|---|
| Packet signing | RSA-2048 (PyCryptodome) |
| Replay protection | Nonce store with TTL expiry |
| Session handshake | 3-step challenge-response |
| Audit trail | Append-only structured event log |
| Confirmation codes | TOTP-style 6-digit one-time codes |

### RAG & Memory
| Component | Technology |
|---|---|
| Vector store | ChromaDB · sentence-transformers embeddings |
| RAG architecture | RAPTOR 3-level hierarchical tree |
| Document loading | LangChain document loaders |
| Memory | In-session sliding window (configurable depth) |

### Infrastructure
| Component | Technology |
|---|---|
| Inter-node transport | Encrypted TCP · RSA-signed packets |
| Web UI | Gradio chatbot interface |
| Testing | pytest · 369+ automated tests |
| Config management | Per-module Python config files |

---

## 🚀 Getting Started

### Prerequisites

```
OS:       Windows 10/11 (primary); Linux untested
Python:   3.10+
GPU:      NVIDIA with CUDA (4GB+ VRAM recommended)
RAM:      8GB minimum (16GB recommended)
Storage:  10GB+ for models and vector store
```

Install system dependencies:
- [Ollama](https://ollama.com/) — local LLM runtime
- [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) — for GPU inference
- Chrome browser — for Web Speech API STT

### Installation

```bash
# Clone the repository
git clone https://github.com/pankajya0003/chaari-2.0.git
cd chaari-2.0

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install Python dependencies
pip install -r requirements.txt

# Pull the local LLM model via Ollama
ollama pull chaari-2.0:latest
```

### Configuration

```bash
# Copy example configs and fill in your keys
cp chaari_2_0/config/voice.py.example     chaari_2_0/config/voice.py
cp chaari_2_0/config/security.py.example  chaari_2_0/config/security.py
cp chaari_2_0/config/rag.py.example       chaari_2_0/config/rag.py
```

Set your Groq API key in `config/security.py`:
```python
GROQ_API_KEY = "gsk_your_key_here"
```

Generate RSA key pair for node communication:
```bash
python -m crypto.key_manager --generate
```

### Running the Brain Node (ASUS / primary machine)

```bash
# Text-only mode
python chaari_2_0/main.py

# Voice mode (Chrome STT + Edge TTS)
python chaari_2_0/main.py --voice --stt-backend=chrome

# Voice mode with Whisper fallback
python chaari_2_0/main.py --voice --stt-backend=whisper
```

### Running the Executor Node (Dell / secondary machine)

```bash
# Start the OS executor service
python chaari_2_0/core/os_executor.py --serve

# The Brain node connects automatically via encrypted TCP
# Default port: configure in config/security.py
```

### Running the Web UI

```bash
python chaari_2_0/skills/chaari-web-ui/scripts/gradio_app.py
# Open browser: http://localhost:7860
```

### Indexing Your Knowledge Base (RAG)

```bash
# Index documents into the RAPTOR vector store
python chaari_2_0/index_knowledge.py --source ./your_docs_folder
```

---

## 📁 Project Structure

```
chaari_2_0/
│
├── main.py                         # Entry point — voice/text mode launcher
├── index_knowledge.py              # RAG document indexer (RAPTOR tree builder)
├── test_gradio_chatbot.py          # Gradio UI test harness
│
├── audio/                          # Voice pipeline
│   ├── stt_engine.py               # Dual STT: Chrome WebSpeech + Faster Whisper
│   ├── tts_engine.py               # Edge TTS neural + pygame echo playback
│   ├── wake_word.py                # OpenWakeWord "Hey CHAARI" detector
│   ├── keyboard_trigger.py         # Ctrl+Space push-to-talk handler
│   ├── interrupt_handler.py        # Mid-speech interrupt + barge-in detection
│   ├── mic_listener.py             # Microphone input stream manager
│   ├── sound_effects.py            # Boot chimes, confirmation tones, error sounds
│   ├── stt_engine_old.py           # Legacy STT (archived)
│   └── tts_engine_old.py           # Legacy TTS (archived)
│
├── core/                           # Brain orchestration + all 7 pipeline layers
│   ├── brain.py                    # Master orchestrator — wires all 7 layers
│   ├── safety.py                   # L0: Safety Kernel — injection/risk detection
│   ├── audit_logger.py             # L0.5: Append-only security audit trail
│   ├── identity.py                 # L1: Identity Lock — Chaari/Pankaj hardcoded
│   ├── policy_engine.py            # L1.5: Policy Engine — governance + tier rules
│   ├── tools.py                    # L2: Tool Truth — app whitelist + tool registry
│   ├── confirmation.py             # L2.5: Confirmation Engine — OTC codes
│   ├── privilege.py                # L2.6: Privilege Manager — creator mode
│   ├── session_manager.py          # L2.7: Session state — strikes, mode, history
│   ├── commands.py                 # System command registry (Tier 1–4 dispatcher)
│   ├── os_executor.py              # OS-level command executor (runs on Executor node)
│   ├── executor_port.py            # Abstract executor interface + NoOpExecutor
│   ├── intent_parser.py            # Raw text → structured intent
│   ├── intent_resolver.py          # Intent → action routing
│   ├── system_intent.py            # SystemIntent enum and data model
│   ├── groq_provider.py            # Groq API client (primary LLM)
│   ├── rag_agent.py                # RAPTOR RAG orchestrator
│   ├── vectorstore.py              # ChromaDB vector store wrapper
│   ├── embeddings.py               # Sentence-transformer embedding manager
│   ├── tree_builder.py             # RAPTOR hierarchical tree construction
│   ├── doc_loader.py               # Multi-format document loader
│   ├── vision_engine.py            # Llava 7B vision + Tesseract OCR
│   ├── memory.py                   # Conversation memory manager
│   ├── personality.py              # Personality engine — Hinglish style + guardrails
│   ├── contacts.py                 # WhatsApp/Telegram contact resolver
│   └── ...
│
├── crypto/                         # Cryptographic mesh layer
│   ├── key_manager.py              # RSA-2048 key generation + storage
│   ├── signer.py                   # Packet signing + verification
│   ├── nonce_store.py              # Nonce registry with TTL (replay protection)
│   ├── packet_builder.py           # Signed packet construction + parsing
│   └── __init__.py
│
├── network/                        # Inter-node TCP transport
│   ├── connection_manager.py       # Brain ↔ Executor encrypted TCP sessions
│   └── __init__.py
│
├── models/                         # Data models + enums
│   ├── intent_hierarchy.py         # Intent classification hierarchy
│   └── __init__.py
│
├── config/                         # Runtime configuration
│   ├── voice.py                    # TTS/STT parameters, voice selection, audio settings
│   ├── security.py                 # API keys, crypto config, node addresses
│   └── rag.py                      # RAG chunking, embedding model, retrieval params
│
├── skills/
│   └── chaari-web-ui/
│       └── scripts/
│           └── gradio_app.py       # Gradio chatbot web UI
│
└── Tests/                          # 369+ automated tests
    ├── run_master_test.py          # Full test suite runner
    ├── run_test_subset.py          # Selective test runner
    ├── test_master_flow.py         # End-to-end pipeline integration tests
    ├── test_executor_pipeline.py   # Executor node tests
    ├── test_phase2_tools.py        # Tool layer tests
    ├── test_phase3_crypto.py       # Crypto signing + nonce tests
    ├── test_phase5_network.py      # Network transport tests
    ├── test_phase6_voice.py        # STT/TTS/wake word tests
    ├── test_rag_pipeline.py        # RAPTOR RAG tests
    ├── test_vision_host.py         # Vision engine tests
    ├── test_audit_logger.py        # Audit trail integrity tests
    └── check_confirmation_bug.py   # Confirmation engine regression check
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

## 🧪 Fine-Tuning

CHAARI 2.0 uses a fine-tuned **Qwen 3.5 4.2B** as its local LLM backbone.

**Dataset:**
- Custom Hinglish instruction-response dataset built specifically for the Indian conversational register
- Covers: feminine Hindi grammar enforcement, Hinglish code-switching, OS command acknowledgments, cultural vocabulary (`Boss`, `Sir-ji`, `Yaar`, `bilkul`, `kar diya`)
- Dataset construction followed a two-stage process: seed examples → LLM-augmented expansion → manual review

**Training:**
- Base model: `Qwen/Qwen3.5-4.2B-Instruct`
- Method: QLoRA fine-tuning (4-bit quantized, fits in 4GB VRAM)
- Inference speed: **30–40 tok/s** on RTX 2050 4GB via Ollama
- Served locally as `chaari-2.0:latest` Ollama model

---

## 🗺️ Roadmap

- [ ] **S2S Completion** — Ship the Speech-to-Speech pipeline with <200ms end-to-end latency
- [ ] **Offline 4GB RAM Target** — Full functionality on CPU-only devices with quantized models; designed for Tier-2/3 city users in India without high-end hardware
- [ ] **Multi-Node Scaling** — Extend the cryptographic mesh beyond two nodes; support phone (Android) as a third executor node
- [ ] **Android Companion App** — Lightweight mobile node that pairs with the Brain over LAN
- [ ] **Hinglish Dataset Release** — Open-source the fine-tuning dataset for the research community
- [ ] **Extended Tool Registry** — Calendar, email, browser automation, IoT device control
- [ ] **Research Paper Publication** — arXiv preprint (see below)

---

## 📄 Research Paper

A research paper documenting CHAARI 2.0's architecture — covering the two-node cryptographic mesh, 7-layer safety pipeline, RAPTOR RAG adaptation for low-resource bilingual inference, and performance benchmarks on 4GB VRAM hardware — is currently in preparation.

> **arXiv preprint: coming soon**
> `[Placeholder: https://arxiv.org/abs/XXXX.XXXXX]`

If you are a researcher working on edge AI, low-resource multilingual systems, or agentic voice pipelines, feel free to reach out.

---

## 👤 Author

**Pankaj Yadav**
M.Sc. Information Technology — Lovely Professional University (LPU), completing May 2026

| | |
|---|---|
| 📧 Email | [pankajya0003@gmail.com](mailto:pankajya0003@gmail.com) |
| 💼 LinkedIn | [linkedin.com/in/pankajya0003](https://linkedin.com/in/pankajya0003) *(update link)* |
| 🐙 GitHub | [github.com/pankajya0003](https://github.com/pankajya0003) *(update link)* |

*Built solo on an ASUS laptop with 4GB VRAM and 16GB RAM — because constraints are where engineering happens.*

---

## 📜 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

*"The next great leap in AI won't come from adding more zeros to a model's parameter count —*
*it will come from making intelligence small enough, fast enough, and personal enough*
*to run in the hands of the next billion people."*

**— CHAARI 2.0 · Built in India · Built for the world**

</div>
