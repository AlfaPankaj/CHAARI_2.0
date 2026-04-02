# CHAARI 2.0 — Dell Execution Node — Configuration
# ═══════════════════════════════════════════════════════
# All Dell-side configuration: IP whitelist, ports, timeouts
# ═══════════════════════════════════════════════════════

import os

# ─────────────────────────────────────────────
# NODE IDENTITY
# ─────────────────────────────────────────────

NODE_ID = "dell-01"
NODE_NAME = "Dell Latitude Executor"

# ─────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────

# Only accept commands from these IPs (ASUS control plane)
ASUS_IP_WHITELIST = [
    "127.0.0.1",       # Localhost (single-machine dev)
    "192.168.1.100",   # ASUS LAN IP (update for your network)
]

# Packet freshness
TIMESTAMP_WINDOW_SECONDS = 60   # Accept packets within ±60s
NONCE_TTL_SECONDS = 300         # Keep nonces for 5 minutes

# ─────────────────────────────────────────────
# NETWORK
# ─────────────────────────────────────────────

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 9734              # CHAARI protocol port
HEARTBEAT_INTERVAL = 30         # seconds

# ─────────────────────────────────────────────
# KEYS
# ─────────────────────────────────────────────

KEY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")

# Dell signs results with this key
DELL_PRIVATE_KEY_NAME = "dell"

# Dell verifies ASUS commands with this key
ASUS_PUBLIC_KEY_NAME = "asus"

# ─────────────────────────────────────────────
# EXECUTION
# ─────────────────────────────────────────────

EXECUTION_TIMEOUT = 30          # Max seconds per command
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".dell_backup")

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# ─────────────────────────────────────────────
# CAPABILITY AUTHORIZATION
# ─────────────────────────────────────────────

# Which capability groups this Dell node is authorized to execute
AUTHORIZED_CAPABILITIES = {
    "POWER",
    "FILESYSTEM",
    "APPLICATION",
    "COMMUNICATION",
    "SYSTEM",
}
