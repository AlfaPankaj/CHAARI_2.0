# CHAARI 2.0 — crypto/signer.py — RSA Signing & Verification
# Responsibility:
# Sign data (SHA-256 hash → RSA signature)
# Verify signatures
# Sign JSON payloads (serialize → hash → sign)

# Design principle (from PDF):
#   "Never sign raw text — always serialize JSON → hash → sign hash"

# Must NEVER:
# Generate keys — that's key_manager.py
# Build packets — that's packet_builder.py
# Execute commands

import json
import hashlib

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature


class CryptoSigner:
    """
    RSA-2048 signer/verifier.
    
    Workflow:
        1. Serialize payload to canonical JSON (sorted keys, no whitespace)
        2. SHA-256 hash the serialized bytes
        3. RSA-sign the hash using PSS padding
        4. Return signature bytes
        
    Verification is the reverse:
        1. Serialize payload to same canonical form
        2. SHA-256 hash
        3. RSA-verify signature against hash
    """

    @staticmethod
    def _canonicalize(payload: dict) -> bytes:
        """
        Convert dict to canonical JSON bytes.
        Sorted keys, no whitespace, UTF-8 encoded.
        This ensures identical payloads always produce identical bytes.
        """
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _hash_bytes(data: bytes) -> bytes:
        """SHA-256 hash of raw bytes."""
        return hashlib.sha256(data).digest()

    @staticmethod
    def sign(payload: dict, private_key) -> bytes:
        """
        Sign a payload dict using RSA-PSS with SHA-256.
        
        Args:
            payload: Dict to sign (will be canonicalized)
            private_key: RSAPrivateKey from key_manager
            
        Returns:
            Signature bytes
        """
        canonical = CryptoSigner._canonicalize(payload)
        
        signature = private_key.sign(
            canonical,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return signature

    @staticmethod
    def verify(payload: dict, signature: bytes, public_key) -> bool:
        """
        Verify a signature against a payload using RSA-PSS with SHA-256.
        
        Args:
            payload: Dict that was signed (will be canonicalized same way)
            signature: Signature bytes to verify
            public_key: RSAPublicKey from key_manager
            
        Returns:
            True if signature is valid, False otherwise
        """
        canonical = CryptoSigner._canonicalize(payload)
        
        try:
            public_key.verify(
                signature,
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

    @staticmethod
    def sign_bytes(data: bytes, private_key) -> bytes:
        """
        Sign raw bytes using RSA-PSS with SHA-256.
        Used for signing pre-serialized data.
        """
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return signature

    @staticmethod
    def verify_bytes(data: bytes, signature: bytes, public_key) -> bool:
        """
        Verify signature against raw bytes.
        """
        try:
            public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    @staticmethod
    def hash_payload(payload: dict) -> str:
        """
        Get SHA-256 hex digest of a canonicalized payload.
        Useful for logging / comparison without exposing raw data.
        """
        canonical = CryptoSigner._canonicalize(payload)
        return hashlib.sha256(canonical).hexdigest()
