"""JSON-backed per-user storage for the hunting bot."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "users.json"

_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _default_user(user_id: int, username: str | None, first_name: str | None = None) -> dict:
    return {
        "user_id": user_id,
        "username": username or "",
        "first_name": first_name or "",
        "registered": _today_iso(),
        "last_active": _now_iso(),
        "level": 1,
        "xp": 0,
        "silver": 0,
        "score": 0,
        "total_hunts": 0,
        "successful_hunts": 0,
        "hit_streak": 0,
        "current_location": "forest",
        "current_weapon": "slingshot",
        "weapons_owned": ["slingshot"],
        "inventory": {},
        "items": {
            "luck_charges": 0,
            "binoculars_charges": 0,
            "bait_charges": 0,
            "big_backpack": 0,
            "dog": False,
            "weapon_upgrades": {},
        },
        "star_weapons": {},
        "stats": {"mythic_kills": 0},
        "last_hunt_time": 0.0,
        "premium_shots": 0,
        "achievements": [],
        "chats": [],
        "daily_task": None,
        "weekly_task": None,
        "buffs": {"accuracy_until": 0.0, "lure_charges": 0},
    }


def _normalize(user: dict) -> dict:
    """Backfill missing fields onto an existing user record (forward-compat)."""
    defaults = _default_user(user.get("user_id", 0), user.get("username"))
    for key, value in defaults.items():
        user.setdefault(key, value)
    # Make sure date strings are present (older records may lack them).
    if not user.get("registered"):
        user["registered"] = _today_iso()
    if not user.get("last_active"):
        user["last_active"] = _now_iso()

    # Migrate old "gold" → "silver" (one-way; keep gold for safety until cleared).
    if user.get("silver", 0) == 0 and user.get("gold", 0):
        user["silver"] = user.get("gold", 0)
        user["gold"] = 0

    # Type guards.
    if not isinstance(user.get("inventory"), dict):
        user["inventory"] = {}
    if not isinstance(user.get("achievements"), list):
        user["achievements"] = []
    if not isinstance(user.get("chats"), list):
        user["chats"] = []
    if not isinstance(user.get("weapons_owned"), list):
        user["weapons_owned"] = ["slingshot"]
    # Ensure slingshot is the starter weapon (migrate old "bow" → "slingshot").
    owned = user["weapons_owned"]
    if "bow" in owned and "slingshot" not in owned:
        idx = owned.index("bow")
        owned[idx] = "slingshot"
    if "slingshot" not in owned:
        owned.insert(0, "slingshot")

    # Backfill star_weapons dict.
    if not isinstance(user.get("star_weapons"), dict):
        user["star_weapons"] = {}

    if not isinstance(user.get("items"), dict):
        user["items"] = defaults["items"]
    items = user["items"]
    items.setdefault("luck_charges", 0)
    items.setdefault("binoculars_charges", 0)
    items.setdefault("bait_charges", 0)
    items.setdefault("big_backpack", 0)
    items.setdefault("dog", False)
    if not isinstance(items.get("weapon_upgrades"), dict):
        items["weapon_upgrades"] = {}

    # Migrate old buffs.lure_charges → items.bait_charges (same effect now).
    if isinstance(user.get("buffs"), dict):
        legacy_lure = int(user["buffs"].get("lure_charges", 0) or 0)
        if legacy_lure and items.get("bait_charges", 0) == 0:
            items["bait_charges"] = legacy_lure
            user["buffs"]["lure_charges"] = 0

    if not isinstance(user.get("stats"), dict):
        user["stats"] = {"mythic_kills": 0}
    user["stats"].setdefault("mythic_kills", 0)

    if not isinstance(user.get("buffs"), dict):
        user["buffs"] = {"accuracy_until": 0.0, "lure_charges": 0}
    else:
        user["buffs"].setdefault("accuracy_until", 0.0)
        user["buffs"].setdefault("lure_charges", 0)

    return user


def _load() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


async def touch_user(
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> dict:
    """Register the user if new, otherwise update last_active and identity fields."""
    async with _lock:
        data = _load()
        key = str(user_id)
        if key not in data:
            data[key] = _default_user(user_id, username, first_name)
        else:
            _normalize(data[key])
            if username and data[key].get("username") != username:
                data[key]["username"] = username
            if first_name and data[key].get("first_name") != first_name:
                data[key]["first_name"] = first_name
        data[key]["last_active"] = _now_iso()
        _save(data)
        return dict(data[key])


async def get_user(user_id: int, username: str | None = None) -> dict:
    async with _lock:
        data = _load()
        key = str(user_id)
        if key not in data:
            data[key] = _default_user(user_id, username)
            _save(data)
        else:
            _normalize(data[key])
            if username and data[key].get("username") != username:
                data[key]["username"] = username
                _save(data)
        return dict(data[key])


async def update_user(
    user_id: int,
    username: str | None,
    mutator: Callable[[dict], None],
) -> dict:
    async with _lock:
        data = _load()
        key = str(user_id)
        if key not in data:
            data[key] = _default_user(user_id, username)
        else:
            _normalize(data[key])
            if username and data[key].get("username") != username:
                data[key]["username"] = username
        mutator(data[key])
        _save(data)
        return dict(data[key])


async def record_chat(user_id: int, username: str | None, chat_id: int) -> None:
    if chat_id == user_id:
        return
    async with _lock:
        data = _load()
        key = str(user_id)
        if key not in data:
            data[key] = _default_user(user_id, username)
        else:
            _normalize(data[key])
        chats = data[key].setdefault("chats", [])
        if chat_id not in chats:
            chats.append(chat_id)
            _save(data)


async def all_users() -> list[dict]:
    async with _lock:
        data = _load()
        users = []
        for record in data.values():
            users.append(dict(_normalize(record)))
        return users
