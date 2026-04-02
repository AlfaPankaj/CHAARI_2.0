# CHAARI 2.0 — Dell crypto/signature_verifier.py — Signature Verification
# ═══════════════════════════════════════════════════════════
# Responsibility:
#   ✔ Load ASUS public key (to verify incoming commands)
#   ✔ Load Dell private key (to sign outgoing results)
#   ✔ Verify command packet signatures
#   ✔ Sign result packets
#
# Must NEVER:
#   ✘ Generate keys — keys are pre-distributed
#   ✘ Execute commands — that's the executor modules
# ═══════════════════════════════════════════════════════════

import os
import json
import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class SignatureVerifier:
    """
    Dell-side crypto operations:
      - Verify ASUS signatures on incoming command packets
      - Sign outgoing result packets with Dell private key
    """

    def __init__(self, key_dir: str):
        self._key_dir = key_dir
        self._asus_public_key = None
        self._dell_private_key = None

    # ══════════════════════════════════════════
    # KEY LOADING
    # ══════════════════════════════════════════

    def load_keys(self, asus_pub_name: str = "asus", dell_priv_name: str = "dell"):
        """
        Load ASUS public key and Dell private key.
        
        Raises:
            FileNotFoundError: If key files missing
        """
        asus_pub_path = os.path.join(self._key_dir, f"{asus_pub_name}_public.pem")
        dell_priv_path = os.path.join(self._key_dir, f"{dell_priv_name}_private.pem")

        if not os.path.exists(asus_pub_path):
            raise FileNotFoundError(f"ASUS public key not found: {asus_pub_path}")
        if not os.path.exists(dell_priv_path):
            raise FileNotFoundError(f"Dell private key not found: {dell_priv_path}")

        with open(asus_pub_path, "rb") as f:
            self._asus_public_key = serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )

        with open(dell_priv_path, "rb") as f:
            self._dell_private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

    def keys_loaded(self) -> bool:
        """Check if both keys are loaded."""
        return self._asus_public_key is not None and self._dell_private_key is not None

    # ══════════════════════════════════════════
    # VERIFY ASUS COMMAND SIGNATURE
    # ══════════════════════════════════════════

    def verify_command(self, packet: dict) -> bool:
        """
        Verify the ASUS signature on a command packet.
        
        Args:
            packet: Signed command packet (must have 'signature' field)
            
        Returns:
            True if signature is valid
        """
        if not self._asus_public_key:
            raise RuntimeError("ASUS public key not loaded")

        signature_b64 = packet.get("signature")
        if not signature_b64:
            return False

        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception:
            return False

        # Reconstruct signable payload
        signable = {k: v for k, v in packet.items() if k != "signature"}
        canonical = json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        try:
            self._asus_public_key.verify(
                signature_bytes,
                canonical,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    # ══════════════════════════════════════════
    # SIGN DELL RESULT
    # ══════════════════════════════════════════

    def sign_result(self, packet: dict) -> dict:
        """
        Sign a result packet with Dell private key.
        
        Args:
            packet: Unsigned result packet
            
        Returns:
            New packet dict with 'signature' field added
        """
        if not self._dell_private_key:
            raise RuntimeError("Dell private key not loaded")

        signable = {k: v for k, v in packet.items() if k != "signature"}
        canonical = json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        signature = self._dell_private_key.sign(
            canonical,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        signed = dict(packet)
        signed["signature"] = base64.b64encode(signature).decode("ascii")
        return signed
