"""Telegram hunting bot — entry point and handlers."""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from html import escape
from flask import Flask

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    TypeHandler,
    filters,
)

from game import (
    ACHIEVEMENTS,
    ANIMALS,
    BINOCULARS_CHARGES,
    BINOCULARS_RARE_BONUS,
    CRIT_POINTS_MULTIPLIER,
    DOG_ACCURACY_BONUS,
    GEM_REWARD,
    HUNT_XP_FAIL,
    LOCATIONS,
    LUCK_POTION_BONUS,
    LUCK_POTION_CHARGES,
    MYTHIC_KEYS,
    ORESHNIK_KILL_MAX,
    ORESHNIK_KILL_MIN,
    ORESHNIK_STARS,
    PREMIUM_PACKS,
    PREMIUM_WEAPONS,
    RARITY_LABELS,
    SAFARI_BASE_ACCURACY,
    SAFARI_DOG_BONUS,
    SAFARI_REWARD_MULT,
    SAFARI_STARS_PER_SHOT,
    SAFARI_WEAPON,
    SHOP_IMPROVEMENTS,
    WEAPON_UPGRADE_BONUS,
    WEAPONS,
    WEATHER,
    _OLD_WEAPON_TO_NEW,
    _RETIRED_PREMIUM_KEYS,
    apply_task_progress,
    backpack_capacity,
    check_achievements,
    compute_hit_chance,
    cooldown_remaining,
    ensure_tasks,
    format_remaining,
    format_task_reward,
    format_time_left,
    get_time_of_day,
    get_weather,
    group_inventory_by_rarity,
    inventory_total_count,
    inventory_total_value,
    iter_animals_sorted,
    level_accuracy_bonus,
    level_from_xp,
    pick_animal,
    pick_safari_animal,
    random_animal_weight,
    resolve_animal_query,
    roll_hit,
    roll_random_event,
    upgrade_to_rare_animal,
    weapon_info,
    xp_for_kill,
    xp_progress,
)
from storage import all_users, get_user, record_chat, touch_user, update_user

OWNER_ID = 5060558519


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("hunting-bot")


ANIMAL_STICKERS: dict[str, str] = {
    "hare":     "CAACAgIAAxkBAAERIAhp7wO4wOPZ1WkRB5ZauAY1G9nIhQACJKgAAgmceEs5o8d6vvjpaDsE",
    "fox":      "CAACAgIAAxkBAAERIAxp7wRQD5dgu5pIGv4FAAFgAaWzz2YAAtyfAAI6MXhLGIpNwyq_7EY7BA",
    "deer":     "CAACAgIAAxkBAAERIA5p7wRqGuZUEko40JNGmuaY_1MU-AAC5I8AApOTeUsM1n-vTuBJQTsE",
    "boar":     "CAACAgIAAxkBAAERIBBp7wR-omhtvYyBncipNIyQhP81BQACDJYAAkhSeEvO3xLJrTTdLjsE",
    "wolf":     "CAACAgIAAxkBAAERIBJp7wSXTc_pKKR3txsJ81pIeC2_bQACjYwAAouYeUs4bDvB8cj2FjsE",
    "bear":     "CAACAgIAAxkBAAERIBRp7wS3UchaGE1e0sy0gV0K5V7tiwACCacAAoFdeEtSkwj0d_vrBzsE",
    "eagle":    "CAACAgIAAxkBAAERIBZp7wTSsXSl0ZO_XAivtUU_QXWR6gAC0ZUAAuwWeUtnVY2z-2MIczsE",
    "lion":     "CAACAgIAAxkBAAERIBhp7wUgXaobat3tqC8Z2qc3oWzmqQACN6AAAkuveUtfbNZ8ePSisTsE",
    "tiger":    "CAACAgIAAxkBAAERIBpp7wUzoONBYhpyZBT-uoTDi-VY1AACRZsAAkMIeUum0Y7VOk9k4TsE",
    "rhino":    "CAACAgIAAxkBAAERIBxp7wVHvDVp7lu-eDBBp-OwvBj8IwACrJ8AAsCreEsY1KhJ2wsBWjsE",
    "elephant": "CAACAgIAAxkBAAERIB5p7wVc64nGDOaDBJZEaulbgIXuDQACXp8AAvGqeUvLKvWSc1VTTDsE",
    "unicorn":  "CAACAgIAAxkBAAERICBp7wVuSQABA3jxJjirpEvAr9wCGKoAAn-WAAJnpnhLd0ftlOHGtLM7BA",
    "dragon":   "CAACAgIAAxkBAAERICJp7wWCjKIvMbq_7w3_4yUbBi_oXwACypwAAgwIeEtbnfEUoTnsGDsE",
    "phoenix":  "CAACAgIAAxkBAAERICRp7wW0AY8HQZq5X7FNZl5e-YXhuAACVZcAAtkFeUvnQOcZEzV2-TsE",
}


HELP_TEXT = (
    "🏹 <b>Бот-охотник</b>\n\n"
    "<b>Охота:</b>\n"
    "/hunt — выйти на охоту (кулдаун 10 мин)\n"
    "/cooldown — когда можно охотиться снова\n"
    "/premium_hunt [1|5|10] — купить выстрелы за ⭐\n"
    "/premium_shots — остаток платных выстрелов\n"
    "/premium_safari — премиум-сафари в Заповеднике (4⭐ за выстрел)\n\n"
    "<b>Снаряжение:</b>\n"
    "/location — выбрать локацию\n"
    "/weapon — выбрать оружие (только купленное)\n\n"
    "<b>Профиль:</b>\n"
    "/me — твой охотничий профиль\n"
    "/score — общий счёт баллов\n"
    "/inventory — рюкзак с добычей\n"
    "/sell — продать добычу (с кнопками)\n\n"
    "<b>Магазин:</b>\n"
    "/shop — улучшения, оружие, премиум\n\n"
    "<b>Задания:</b>\n"
    "/tasks — текущие ежедневные и еженедельные задания\n\n"
    "<b>Мир:</b>\n"
    "/stats — статистика бота и топ охотников\n"
    "/weather — текущая погода и время\n"
    "/animals — бестиарий\n"
    "/top [global|chat] — топ охотников\n"
    "/help — это сообщение"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_username(user: dict) -> str:
    if user.get("username"):
        return f"@{escape(user['username'])}"
    return f"#{user.get('user_id', '?')}"


def _ensure_valid_selections(user: dict) -> None:
    level = user["level"]
    # Validate location.
    if (
        user.get("current_location") not in LOCATIONS
        or LOCATIONS[user["current_location"]].get("safari_only")
        or LOCATIONS[user["current_location"]]["level"] > level
    ):
        user["current_location"] = "forest"

    # Migrate old silver weapon keys in weapons_owned list.
    owned: list[str] = user.get("weapons_owned") or []
    migrated_owned: list[str] = []
    for w in owned:
        new_key = _OLD_WEAPON_TO_NEW.get(w, w)
        # Drop retired premium keys.
        if new_key in _RETIRED_PREMIUM_KEYS:
            continue
        if new_key not in migrated_owned:
            migrated_owned.append(new_key)
    if "slingshot" not in migrated_owned:
        migrated_owned.insert(0, "slingshot")
    user["weapons_owned"] = migrated_owned

    # Validate current_weapon.
    cw = user.get("current_weapon") or "slingshot"
    cw = _OLD_WEAPON_TO_NEW.get(cw, cw)  # migrate old key
    star_weapons: dict = user.get("star_weapons") or {}

    if cw in PREMIUM_WEAPONS:
        # Star weapon valid only if there are charges.
        if star_weapons.get(cw, 0) <= 0:
            cw = "slingshot"
    elif cw in _RETIRED_PREMIUM_KEYS:
        cw = "slingshot"
    elif cw not in WEAPONS:
        cw = "slingshot"

    user["current_weapon"] = cw


def _maybe_level_up(user: dict) -> tuple[bool, int]:
    new_level = level_from_xp(user["xp"])
    leveled_up = new_level > user.get("level", 1)
    user["level"] = new_level
    return leveled_up, new_level


def _format_weight(kg: float) -> str:
    if kg >= 1000:
        return f"{kg/1000:.2f} т ({int(kg)} кг)"
    return f"{kg} кг ({int(kg*1000)} г)"


def _format_weather_line(time_key: str, time_info: dict, weather_info: dict) -> str:
    acc = weather_info["accuracy"]
    parts = [f"{time_info['emoji']} {time_info['name']}", f"{weather_info['emoji']} {weather_info['name']}"]
    mods: list[str] = []
    if acc:
        mods.append(f"{acc:+d}% точность")
    if time_key == "night":
        mods.append("−20% точность (ночь)")
    line = " | ".join(parts)
    if mods:
        line += f" ({', '.join(mods)})"
    return line


# ---------------------------------------------------------------------------
# Group support — chat-tracking middleware
# ---------------------------------------------------------------------------

async def _track_chat(update: Update) -> None:
    user_obj = update.effective_user
    chat = update.effective_chat
    if not user_obj or not chat:
        return
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await record_chat(user_obj.id, user_obj.username, chat.id)


# ---------------------------------------------------------------------------
# /start, /help, /animals
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_obj = update.effective_user
    await get_user(user_obj.id, user_obj.username if user_obj else None)
    await _track_chat(update)
    name = escape(user_obj.first_name) if user_obj and user_obj.first_name else "охотник"
    await update.message.reply_html(
        f"🏹 Привет, <b>{name}</b>!\n\n"
        "Добро пожаловать в мир охоты. Стартовый набор:\n"
        "🌲 Локация: <b>Лес</b>\n"
        "🏹 Оружие: <b>Лук</b> (40% точности)\n"
        "💰 Серебро: <b>0</b> 🥈\n\n"
        "Жми /hunt чтобы выйти на охоту, или /help для списка команд.\n"
        "Открой /shop — там улучшения за серебро, оружие и премиум за ⭐."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    await update.message.reply_html(HELP_TEXT)


async def animals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    rarity_order = ["common", "rare", "epic", "legendary", "mythic"]
    by_rarity: dict[str, list[tuple[str, dict]]] = {r: [] for r in rarity_order}
    for key, info in ANIMALS.items():
        by_rarity[info["rarity"]].append((key, info))

    lines = ["📖 <b>Бестиарий</b>\n"]
    for rarity in rarity_order:
        if not by_rarity[rarity]:
            continue
        lines.append(f"<b>{RARITY_LABELS[rarity]}</b>")
        for _, info in by_rarity[rarity]:
            xp_hint = (
                f"~{int((info['weight_min']+info['weight_max'])/20 * info['xp_mult'])} XP"
                if info.get("xp_mult") else f"{info.get('fixed_xp', 0)} XP (фикс.)"
            )
            mult_text = (
                f"x{info['xp_mult']:g} XP"
                if info.get("xp_mult") else "мифическая"
            )
            chance = info.get("chance", 0)
            chance_text = f"шанс {chance}%" if chance else "только в Заповеднике"
            lines.append(
                f"  {info['emoji']} {escape(info['name'])} — {chance_text}, "
                f"{info['price']} 🥈, {mult_text}\n"
                f"     вес {info['weight_min']}–{info['weight_max']} кг ({xp_hint})"
            )
        lines.append("")
    await update.message.reply_html("\n".join(lines).strip())


# ---------------------------------------------------------------------------
# /location
# ---------------------------------------------------------------------------

async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    user_obj = update.effective_user
    user = await get_user(user_obj.id, user_obj.username if user_obj else None)
    await update.message.reply_html(_location_text(user), reply_markup=_location_keyboard(user))


def _location_text(user: dict) -> str:
    current = LOCATIONS.get(user["current_location"], LOCATIONS["forest"])
    return (
        "🗺️ <b>Локации</b>\n\n"
        f"Сейчас ты в: {current['emoji']} <b>{escape(current['name'])}</b>\n"
        f"Твой уровень: <b>{user['level']}</b>\n\n"
        "Выбери локацию ниже:"
    )


def _location_keyboard(user: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, info in LOCATIONS.items():
        if info.get("safari_only"):
            continue
        unlocked = user["level"] >= info["level"]
        is_current = user["current_location"] == key
        marker = "✅ " if is_current else ""
        if unlocked:
            label = f"{marker}{info['emoji']} {info['name']}"
        else:
            label = f"🔒 {info['emoji']} {info['name']} (ур. {info['level']})"
        rows.append([InlineKeyboardButton(label, callback_data=f"loc:{key}")])
    return InlineKeyboardMarkup(rows)


async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not query.data or not query.data.startswith("loc:"):
        return
    key = query.data.split(":", 1)[1]
    user_obj = query.from_user
    if key not in LOCATIONS or LOCATIONS[key].get("safari_only"):
        await query.answer("Неизвестная локация.", show_alert=True)
        return
    user = await get_user(user_obj.id, user_obj.username)
    if user["level"] < LOCATIONS[key]["level"]:
        await query.answer(
            f"🔒 Открывается на уровне {LOCATIONS[key]['level']}.",
            show_alert=True,
        )
        return
    user = await update_user(
        user_obj.id,
        user_obj.username,
        lambda u: u.__setitem__("current_location", key),
    )
    info = LOCATIONS[key]
    await query.edit_message_text(
        text=(
            f"📍 Вы перешли в локацию: {info['emoji']} <b>{escape(info['name'])}</b>\n\n"
            + _location_text(user)
        ),
        parse_mode="HTML",
        reply_markup=_location_keyboard(user),
    )


# ---------------------------------------------------------------------------
# /weapon — only owned weapons appear; lock hint sends user to /shop
# ---------------------------------------------------------------------------

async def weapon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    user_obj = update.effective_user
    user = await get_user(user_obj.id, user_obj.username if user_obj else None)
    await update.message.reply_html(_weapon_text(user), reply_markup=_weapon_keyboard(user))


def _weapon_text(user: dict) -> str:
    current = weapon_info(user["current_weapon"])
    upgrades = (user.get("items", {}).get("weapon_upgrades", {}) or {}).get(user["current_weapon"], 0)
    upg_text = f" + улучшения ×{upgrades}" if upgrades else ""
    dog_text = " + 🐕 +10%" if user.get("items", {}).get("dog") else ""
    return (
        "🎯 <b>Арсенал</b>\n\n"
        f"Сейчас в руках: {current['emoji']} <b>{escape(current['name'])}</b> "
        f"(точность {current['accuracy']}%{upg_text}{dog_text})\n"
        f"Бонус от уровня: <b>+{level_accuracy_bonus(user['level'])}%</b>\n\n"
        "Выбери оружие ниже. Заблокированные пункты можно купить в /shop."
    )


def _weapon_keyboard(user: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    owned = set(user.get("weapons_owned") or ["slingshot"])
    star_weapons: dict = user.get("star_weapons") or {}
    # Regular weapons (sorted by level)
    for key, info in sorted(WEAPONS.items(), key=lambda kv: kv[1]["level"]):
        is_current = user["current_weapon"] == key
        marker = "✅ " if is_current else ""
        if key in owned:
            label = f"{marker}{info['emoji']} {info['name']} ({info['accuracy']}%)"
        else:
            label = f"🔒 {info['emoji']} {info['name']} — {info['price']} 🥈, ур. {info['level']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"wpn:{key}")])
    # Star (disposable) weapons — show only if user has charges
    for key, info in PREMIUM_WEAPONS.items():
        charges = star_weapons.get(key, 0)
        if charges <= 0:
            continue
        is_current = user["current_weapon"] == key
        marker = "✅ " if is_current else ""
        label = f"{marker}{info['emoji']} {info['name']} ({info['accuracy']}%) ×{charges} заряд(а)"
        rows.append([InlineKeyboardButton(label, callback_data=f"wpn:{key}")])
    return InlineKeyboardMarkup(rows)


async def weapon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not query.data or not query.data.startswith("wpn:"):
        return
    key = query.data.split(":", 1)[1]
    user_obj = query.from_user
    if key not in WEAPONS and key not in PREMIUM_WEAPONS:
        await query.answer("Неизвестное оружие.", show_alert=True)
        return
    user = await get_user(user_obj.id, user_obj.username)
    star_weapons: dict = user.get("star_weapons") or {}
    owned_silver = user.get("weapons_owned") or []
    if key in PREMIUM_WEAPONS:
        if star_weapons.get(key, 0) <= 0:
            pw = PREMIUM_WEAPONS[key]
            await query.answer(
                f"🔒 Купи в /shop → ⭐ Звёздное оружие за {pw['stars']}⭐. (Одноразовое)",
                show_alert=True,
            )
            return
    elif key not in owned_silver:
        if key in WEAPONS:
            await query.answer(
                f"🔒 Купи в /shop за {WEAPONS[key]['price']} 🥈 (требуется ур. {WEAPONS[key]['level']}).",
                show_alert=True,
            )
        else:
            await query.answer("Неизвестное оружие.", show_alert=True)
        return
    user = await update_user(
        user_obj.id,
        user_obj.username,
        lambda u: u.__setitem__("current_weapon", key),
    )
    info = weapon_info(key)
    await query.edit_message_text(
        text=(
            f"✅ Оружие выбрано: {info['emoji']} <b>{escape(info['name'])}</b>\n\n"
            + _weapon_text(user)
        ),
        parse_mode="HTML",
        reply_markup=_weapon_keyboard(user),
    )


# ---------------------------------------------------------------------------
# /weather
# ---------------------------------------------------------------------------

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    time_info = get_time_of_day()
    weather_key, weather_info = get_weather()
    lines = [
        "🌍 <b>Состояние мира</b>\n",
        f"Время суток: {time_info['emoji']} <b>{escape(time_info['name'])}</b>",
        f"Погода:      {weather_info['emoji']} <b>{escape(weather_info['name'])}</b>"
        f" ({weather_info['accuracy']:+d}% точность)",
    ]
    if time_info["key"] == "night":
        lines.append("Ночной штраф к точности: <b>−20%</b>")
        lines.append("Ночью чаще встречаются 🐺 волк и 🐻 медведь.")
    elif time_info["key"] in ("dawn", "evening"):
        lines.append("В сумерках чаще встречаются 🦌 олень и 🐰 заяц.")
    elif time_info["key"] == "day":
        lines.append("Днём чаще встречаются обычные звери: 🐰 🦊 🦌.")

    lines.append("")
    lines.append("<b>Погода во всех локациях одинакова:</b>")
    for _, loc in LOCATIONS.items():
        if loc.get("safari_only"):
            continue
        lines.append(f"  {loc['emoji']} {escape(loc['name'])}: {weather_info['emoji']} {escape(weather_info['name'])}")

    await update.message.reply_html("\n".join(lines))


# ---------------------------------------------------------------------------
# /hunt and /cooldown
# ---------------------------------------------------------------------------

async def cooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    user_obj = update.effective_user
    user = await get_user(user_obj.id, user_obj.username if user_obj else None)
    remaining = cooldown_remaining(user.get("last_hunt_time", 0))
    if remaining <= 0:
        await update.message.reply_html("✅ Можно охотиться прямо сейчас! Жми /hunt")
    else:
        extra = ""
        if user.get("premium_shots", 0) > 0:
            extra = f"\n⭐ У тебя есть <b>{user['premium_shots']}</b> платных выстрелов — они без кулдауна."
        await update.message.reply_html(
            f"⏳ До следующей охоты: <b>{format_remaining(remaining)}</b>{extra}"
        )


async def hunt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _track_chat(update)
    user_obj = update.effective_user
    user = await get_user(user_obj.id, user_obj.username if user_obj else None)

    if user.get("premium_shots", 0) > 0:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏹 Обычная", callback_data="hunt:normal"),
                InlineKeyboardButton(f"⭐ Платная (×{user['premium_shots']})", callback_data="hunt:premium"),
            ]
        ])
        cd = cooldown_remaining(user.get("last_hunt_time", 0))
        cd_text = "готова прямо сейчас" if cd <= 0 else f"через {format_remaining(cd)}"
        await update.message.reply_html(
            f"❓ Какой охотой воспользоваться?\n"
            f"🏹 Обычная — кулдаун 10 мин ({cd_text})\n"
            f"⭐ Платная — без кулдауна (осталось {user['premium_shots']} выстрелов)",
            reply_markup=kb
        )
        return
