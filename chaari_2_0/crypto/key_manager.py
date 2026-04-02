# CHAARI 2.0 — crypto/key_manager.py — RSA Key Management
# Responsibility:
# Generate RSA-2048 key pairs
# Save/load PEM files
# Key rotation support

# Must NEVER:
# Sign or verify — that's signer.py
# Build packets — that's packet_builder.py
# Store keys in memory after loading — load on demand


import os
from pathlib import Path
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend




KEY_SIZE = 2048
PUBLIC_EXPONENT = 65537

DEFAULT_KEY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "keys"
)



class KeyManager:
    """
    Manages RSA key pairs for ASUS (control plane) and Dell (execution node).
    
    Key naming convention:
        asus_private.pem  — ASUS signs commands with this
        asus_public.pem   — Dell verifies ASUS signatures with this
        dell_private.pem  — Dell signs results with this
        dell_public.pem   — ASUS verifies Dell signatures with this
    """

    def __init__(self, key_dir: str = None):
        self.key_dir = key_dir or DEFAULT_KEY_DIR
        os.makedirs(self.key_dir, exist_ok=True)

    def generate_key_pair(self, name: str, passphrase: bytes = None) -> tuple[str, str]:
        """
        Generate an RSA-2048 key pair and save as PEM files.
        
        Args:
            name: Key pair name (e.g., "asus" or "dell")
            passphrase: Optional passphrase to encrypt private key
            
        Returns:
            (private_key_path, public_key_path)
        """
        private_key = rsa.generate_private_key(
            public_exponent=PUBLIC_EXPONENT,
            key_size=KEY_SIZE,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        if passphrase:
            encryption = serialization.BestAvailableEncryption(passphrase)
        else:
            encryption = serialization.NoEncryption()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        private_path = os.path.join(self.key_dir, f"{name}_private.pem")
        public_path = os.path.join(self.key_dir, f"{name}_public.pem")

        with open(private_path, "wb") as f:
            f.write(private_pem)
        with open(public_path, "wb") as f:
            f.write(public_pem)

        return private_path, public_path

    def generate_all_keys(self) -> dict[str, tuple[str, str]]:
        """
        Generate both ASUS and Dell key pairs.
        
        Returns:
            {"asus": (priv_path, pub_path), "dell": (priv_path, pub_path)}
        """
        result = {}
        for name in ("asus", "dell"):
            priv, pub = self.generate_key_pair(name)
            result[name] = (priv, pub)
        return result

    def load_private_key(self, name: str, passphrase: bytes = None):
        """
        Load a private key from PEM file.
        
        Args:
            name: Key name (e.g., "asus" or "dell")
            passphrase: Passphrase if key is encrypted
            
        Returns:
            RSAPrivateKey object
            
        Raises:
            FileNotFoundError: If key file doesn't exist
        """
        path = os.path.join(self.key_dir, f"{name}_private.pem")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Private key not found: {path}")

        with open(path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=passphrase,
                backend=default_backend(),
            )
        return private_key

    def load_public_key(self, name: str):
        """
        Load a public key from PEM file.
        
        Args:
            name: Key name (e.g., "asus" or "dell")
            
        Returns:
            RSAPublicKey object
            
        Raises:
            FileNotFoundError: If key file doesn't exist
        """
        path = os.path.join(self.key_dir, f"{name}_public.pem")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Public key not found: {path}")

        with open(path, "rb") as f:
            public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend(),
            )
        return public_key

    def keys_exist(self, name: str) -> dict[str, bool]:
        """
        Check if key files exist for a given name.
        
        Returns:
            {"private": bool, "public": bool}
        """
        return {
            "private": os.path.exists(os.path.join(self.key_dir, f"{name}_private.pem")),
            "public": os.path.exists(os.path.join(self.key_dir, f"{name}_public.pem")),
        }

    def all_keys_present(self) -> bool:
        """Check if both ASUS and Dell key pairs are fully present."""
        for name in ("asus", "dell"):
            status = self.keys_exist(name)
            if not status["private"] or not status["public"]:
                return False
        return True

    def get_key_info(self) -> dict:
        """Get info about all keys (existence, size, modified time)."""
        info = {}
        for name in ("asus", "dell"):
            for key_type in ("private", "public"):
                path = os.path.join(self.key_dir, f"{name}_{key_type}.pem")
                if os.path.exists(path):
                    stat = os.stat(path)
                    info[f"{name}_{key_type}"] = {
                        "exists": True,
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                else:
                    info[f"{name}_{key_type}"] = {"exists": False}
        return info
