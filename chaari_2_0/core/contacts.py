"""
CHAARI 2.0 — Contact Manager
Loads/saves contacts from data/contacts.json for messaging and calling.
"""

import json
import os
from pathlib import Path

_CONTACTS_FILE = Path(__file__).parent.parent / "data" / "contacts.json"


def _load_store() -> dict:
    """Load the contacts JSON file."""
    try:
        with open(_CONTACTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"contacts": {}}


def _save_store(store: dict):
    """Save the contacts JSON file."""
    _CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=4, ensure_ascii=False)


def get_contact(name: str) -> dict | None:
    """Look up a contact by name (case-insensitive)."""
    store = _load_store()
    contacts = store.get("contacts", {})
    key = name.lower().strip()
    if key in contacts:
        return contacts[key]
    for k, v in contacts.items():
        if key in k.lower() or k.lower() in key:
            return v
    return None


def add_contact(name: str, phone: str = "", telegram: str = "", label: str = "", search_name: str = "") -> str:
    """Add or update a contact. Returns status message."""
    store = _load_store()
    key = name.lower().strip()
    entry = store["contacts"].get(key, {})
    if phone:
        entry["phone"] = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if telegram:
        entry["telegram"] = telegram.strip().lstrip("@")
    if label:
        entry["label"] = label
    if search_name:
        entry["search_name"] = search_name
    store["contacts"][key] = entry
    _save_store(store)
    return f"Contact '{name}' saved: {entry}"


def remove_contact(name: str) -> str:
    """Remove a contact by name."""
    store = _load_store()
    key = name.lower().strip()
    if key in store["contacts"]:
        del store["contacts"][key]
        _save_store(store)
        return f"Contact '{name}' removed."
    return f"Contact '{name}' not found."


def list_contacts() -> str:
    """Return formatted list of all contacts."""
    store = _load_store()
    contacts = store.get("contacts", {})
    if not contacts:
        return "No contacts saved. Use /contacts add <name> <phone> to add one."
    lines = ["─── Contacts ───"]
    for name, info in sorted(contacts.items()):
        phone = info.get("phone", "—")
        telegram = info.get("telegram", "—")
        label = info.get("label", "")
        tag = f" ({label})" if label else ""
        lines.append(f"  {name}{tag}: phone={phone}, telegram=@{telegram}")
    lines.append("────────────────")
    return "\n".join(lines)
