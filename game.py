"""Game data and pure-logic helpers for the hunting bot."""

from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Iterable

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

COOLDOWN_SECONDS = 10 * 60
HUNT_XP_FAIL = 0  # XP given on a miss

LEVEL_ACCURACY_STEP = 5  # +5% accuracy every 5 levels
LEVEL_ACCURACY_MAX = 30  # cap at +30%

EVENT_CHANCE = 0.01  # 1% chance per hunt
GEM_REWARD = 500
CRIT_POINTS_MULTIPLIER = 1.5

# Mythic-animal chance during premium safari
SAFARI_MYTHIC_CHANCE = 0.05
SAFARI_REWARD_MULT = 3
SAFARI_DOG_BONUS = 25  # extra accuracy in safari
SAFARI_BASE_ACCURACY = 95
SAFARI_STARS_PER_SHOT = 50

DOG_ACCURACY_BONUS = 10  # permanent +10% if user owns the dog
WEAPON_UPGRADE_BONUS = 5  # +5% per stack on the upgraded weapon

LUCK_POTION_BONUS = 20  # +20% accuracy
LUCK_POTION_CHARGES = 3  # for 3 hunts
BINOCULARS_RARE_BONUS = 0.15  # +15% rare chance
BINOCULARS_CHARGES = 5
BIG_BACKPACK_SLOTS = 10
BACKPACK_BASE_SLOTS = 50

# Premium shot packs purchasable with Telegram Stars.
PREMIUM_PACKS: dict[str, dict] = {
    "1":  {"shots": 1,  "stars": 1, "title": "1 выстрел",       "desc": "1 платный выстрел без кулдауна, гарантированное попадание"},
    "5":  {"shots": 5,  "stars": 4, "title": "5 выстрелов −1⭐", "desc": "5 платных выстрелов со скидкой"},
    "10": {"shots": 10, "stars": 7, "title": "10 выстрелов −3⭐","desc": "10 платных выстрелов с большой скидкой"},
}

# ---------------------------------------------------------------------------
# Animals (with XP multiplier per spec)
#   XP per kill = (weight_kg / 10) * xp_mult, rounded to int.
#   Mythic animals use a fixed XP value (`fixed_xp`).
# ---------------------------------------------------------------------------

ANIMALS: dict[str, dict] = {
    # commons
    "hare":     {"emoji": "🐰", "name": "Заяц",     "rarity": "common",    "xp_mult": 1.0, "price": 10,    "weight_min": 2.5,  "weight_max": 4.5,   "chance": 40},
    "fox":      {"emoji": "🦊", "name": "Лиса",     "rarity": "common",    "xp_mult": 1.0, "price": 25,    "weight_min": 5,    "weight_max": 10,    "chance": 35},
    # mid
    "deer":     {"emoji": "🦌", "name": "Олень",    "rarity": "rare",      "xp_mult": 1.5, "price": 50,    "weight_min": 80,   "weight_max": 150,   "chance": 25},
    "boar":     {"emoji": "🐗", "name": "Кабан",    "rarity": "rare",      "xp_mult": 1.5, "price": 75,    "weight_min": 100,  "weight_max": 200,   "chance": 20},
    "wolf":     {"emoji": "🐺", "name": "Волк",     "rarity": "rare",      "xp_mult": 2.0, "price": 100,   "weight_min": 30,   "weight_max": 80,    "chance": 15},
    # epic
    "bear":     {"emoji": "🐻", "name": "Медведь",  "rarity": "epic",      "xp_mult": 2.0, "price": 150,   "weight_min": 150,  "weight_max": 400,   "chance": 10},
    "eagle":    {"emoji": "🦅", "name": "Орел",     "rarity": "epic",      "xp_mult": 2.5, "price": 200,   "weight_min": 3,    "weight_max": 7,     "chance": 8},
    "lion":     {"emoji": "🦁", "name": "Лев",      "rarity": "epic",      "xp_mult": 3.0, "price": 300,   "weight_min": 150,  "weight_max": 250,   "chance": 5},
    "tiger":    {"emoji": "🐯", "name": "Тигр",     "rarity": "epic",      "xp_mult": 4.0, "price": 500,   "weight_min": 180,  "weight_max": 300,   "chance": 3},
    # legendary
    "rhino":    {"emoji": "🦏", "name": "Носорог",  "rarity": "legendary", "xp_mult": 5.0, "price": 800,   "weight_min": 1000, "weight_max": 2500,  "chance": 2},
    "elephant": {"emoji": "🐘", "name": "Слон",     "rarity": "legendary", "xp_mult": 6.0, "price": 1500,  "weight_min": 3000, "weight_max": 6000,  "chance": 1},
    # mythic — only obtainable on premium safari
    "unicorn":  {"emoji": "🦄", "name": "Единорог", "rarity": "mythic",    "xp_mult": 0.0, "price": 5000,  "weight_min": 250,  "weight_max": 400,   "chance": 0, "fixed_xp": 500},
    "dragon":   {"emoji": "🐉", "name": "Дракон",   "rarity": "mythic",    "xp_mult": 0.0, "price": 10000, "weight_min": 800,  "weight_max": 2000,  "chance": 0, "fixed_xp": 1000},
    "phoenix":  {"emoji": "🔥", "name": "Феникс",   "rarity": "mythic",    "xp_mult": 0.0, "price": 7500,  "weight_min": 8,    "weight_max": 15,    "chance": 0, "fixed_xp": 750},
}

MYTHIC_KEYS = [k for k, v in ANIMALS.items() if v["rarity"] == "mythic"]

LOCATIONS: dict[str, dict] = {
    "forest":    {"emoji": "🌲", "name": "Лес",        "level": 1,   "animals": ["hare", "fox", "deer", "boar", "wolf"]},
    "mountains": {"emoji": "🏔️", "name": "Горы",       "level": 5,   "animals": ["eagle", "bear", "wolf", "hare"]},
    "savanna":   {"emoji": "🌾", "name": "Саванна",    "level": 10,  "animals": ["lion", "eagle", "deer", "boar"]},
    "jungle":    {"emoji": "🌴", "name": "Джунгли",    "level": 15,  "animals": ["tiger", "boar", "deer", "lion"]},
    "tundra":    {"emoji": "❄️", "name": "Тундра",     "level": 20,  "animals": ["bear", "wolf", "hare", "eagle"]},
    "desert":    {"emoji": "🏜️", "name": "Пустыня",    "level": 25,  "animals": ["lion", "eagle", "rhino"]},
    "volcano":   {"emoji": "🌋", "name": "Вулкан",     "level": 30,  "animals": ["rhino", "elephant", "tiger", "bear"]},
    # Safari-only — never selectable from /location
    "preserve":  {"emoji": "🏆", "name": "Заповедник", "level": 999, "animals": ["deer", "wolf", "bear", "lion", "tiger", "rhino", "elephant", "eagle", "boar"], "safari_only": True},
}

# Regular weapons (silver-priced; slingshot is free starter, bought permanently).
WEAPONS: dict[str, dict] = {
    "slingshot":     {"emoji": "🪃", "name": "Рогатка",              "level": 1,  "accuracy": 40, "price": 0,     "damage_mult": 1.0},
    "crossbow":      {"emoji": "🏹", "name": "Арбалет",              "level": 2,  "accuracy": 55, "price": 900,   "damage_mult": 1.2},
    "hunting_rifle": {"emoji": "🔫", "name": "Охотничье ружьё",      "level": 3,  "accuracy": 63, "price": 1500,  "damage_mult": 1.4},
    "shotgun":       {"emoji": "💥", "name": "Дробовик",             "level": 5,  "accuracy": 70, "price": 3500,  "damage_mult": 1.7},
    "sniper_rifle":  {"emoji": "🔭", "name": "Снайперская винтовка", "level": 7,  "accuracy": 80, "price": 6000,  "damage_mult": 2.2},
    "taser":         {"emoji": "⚡", "name": "Электрошокер",          "level": 10, "accuracy": 87, "price": 12000, "damage_mult": 2.8},
    "railgun":       {"emoji": "🔱", "name": "Рейлган",              "level": 15, "accuracy": 92, "price": 25000, "damage_mult": 3.5},
    "gravity_gun":   {"emoji": "🌀", "name": "Гравитронная пушка",   "level": 20, "accuracy": 95, "price": 50000, "damage_mult": 4.5},
}

# Keys from the old weapon system — kept for migration only.
# "crossbow", "shotgun", "taser" are now valid keys in WEAPONS — no migration needed.
_OLD_WEAPON_TO_NEW: dict[str, str] = {
    "bow":    "slingshot",
    "rifle":  "hunting_rifle",
    "sniper": "sniper_rifle",
}

# Premium weapons — bought with Telegram Stars; DISPOSABLE (one shot per purchase).
PREMIUM_WEAPONS: dict[str, dict] = {
    "laser_sight":  {
        "emoji": "🔴", "name": "Лазерный прицел",   "stars": 1, "accuracy": 95,
        "damage_mult": 3.0, "double_loot": False,
        "desc": "Точность 95%, урон ×3. Одноразовое!",
    },
    "plasma_rifle": {
        "emoji": "🌌", "name": "Плазменная винтовка","stars": 3, "accuracy": 100,
        "damage_mult": 4.0, "double_loot": False,
        "desc": "Точность 100%, урон ×4. Одноразовая!",
    },
    "quantum_gun":  {
        "emoji": "⚛️", "name": "Квантовое ружьё",    "stars": 5, "accuracy": 100,
        "damage_mult": 5.0, "double_loot": True,
        "desc": "Точность 100%, урон ×5 + шанс двойной добычи. Одноразовое!",
    },
}

# Oreshnik — mass-kill super-weapon; disposable, charged per purchase.
ORESHNIK_STARS   = 150
ORESHNIK_KILL_MIN = 10
ORESHNIK_KILL_MAX = 15

# Virtual safari weapon used during /premium_safari.
SAFARI_WEAPON = {"emoji": "🏆", "name": "Супер-оружие сафари", "accuracy": SAFARI_BASE_ACCURACY}

# Retired premium weapon keys (no longer exist in the system).
_RETIRED_PREMIUM_KEYS: frozenset[str] = frozenset({
    "golden_rifle", "diamond_crossbow", "fire_bow", "legendary",
})


def all_weapon_keys() -> set[str]:
    return set(WEAPONS) | set(PREMIUM_WEAPONS)


def weapon_info(weapon_key: str) -> dict:
    """Return a normalised info dict for any weapon key (falls back to slingshot)."""
    if weapon_key in WEAPONS:
        w = dict(WEAPONS[weapon_key])
        w.setdefault("damage_mult", 1.0)
        w.setdefault("double_loot", False)
        return w
    # Migrate old silver weapon keys on the fly.
    if weapon_key in _OLD_WEAPON_TO_NEW:
        return weapon_info(_OLD_WEAPON_TO_NEW[weapon_key])
    if weapon_key in PREMIUM_WEAPONS:
        info = PREMIUM_WEAPONS[weapon_key]
        return {
            "emoji": info["emoji"],
            "name": info["name"],
            "level": 1,
            "accuracy": info["accuracy"],
            "price": 0,
            "stars": info["stars"],
            "premium": True,
            "disposable": True,
            "damage_mult": info.get("damage_mult", 1.0),
            "double_loot": info.get("double_loot", False),
        }
    return weapon_info("slingshot")


RARITY_LABELS = {
    "common":    "🟢 Обычная",
    "rare":      "🔵 Редкая",
    "epic":      "🟣 Эпическая",
    "legendary": "🟡 Легендарная",
    "mythic":    "✨ Мифическая",
}

# ---------------------------------------------------------------------------
# Weather & time of day
# ---------------------------------------------------------------------------

TIMES_OF_DAY: list[dict] = [
    {"key": "dawn",    "emoji": "🌅", "name": "Рассвет", "hours": [5, 6]},
    {"key": "morning", "emoji": "☀️", "name": "Утро",    "hours": [7, 8, 9, 10, 11]},
    {"key": "day",     "emoji": "🌞", "name": "День",    "hours": [12, 13, 14, 15, 16]},
    {"key": "evening", "emoji": "🌆", "name": "Вечер",   "hours": [17, 18, 19]},
    {"key": "night",   "emoji": "🌙", "name": "Ночь",    "hours": [20, 21, 22, 23, 0, 1, 2, 3, 4]},
]

WEATHER: dict[str, dict] = {
    "clear":  {"emoji": "☀️", "name": "Ясно",     "accuracy": 10},
    "cloudy": {"emoji": "⛅", "name": "Облачно",   "accuracy": 0},
    "rain":   {"emoji": "🌧️", "name": "Дождь",   "accuracy": -10},
    "snow":   {"emoji": "❄️", "name": "Снег",     "accuracy": -15},
    "fog":    {"emoji": "🌫️", "name": "Туман",   "accuracy": -20},
    "storm":  {"emoji": "⛈️", "name": "Гроза",    "accuracy": -25},
}

NIGHT_ACCURACY_PENALTY = -20

TIME_SPAWN_BONUS: dict[str, dict[str, float]] = {
    "dawn":    {"deer": 1.20, "hare": 1.20},
    "evening": {"deer": 1.20, "hare": 1.20},
    "day":     {"hare": 1.15, "fox": 1.15, "deer": 1.15},
    "night":   {"wolf": 1.30, "bear": 1.30},
    "morning": {},
}

_weather_cache: dict[str, object] = {"hour_key": None, "weather_key": None}


def _hour_key(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    return now.strftime("%Y-%m-%dT%H")


def get_time_of_day(now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    hour = now.hour
    for tod in TIMES_OF_DAY:
        if hour in tod["hours"]:
            return tod
    return TIMES_OF_DAY[2]


def get_weather(now: datetime | None = None) -> tuple[str, dict]:
    now = now or datetime.utcnow()
    key = _hour_key(now)
    if _weather_cache["hour_key"] != key:
        rng = random.Random(key)
        _weather_cache["hour_key"] = key
        _weather_cache["weather_key"] = rng.choice(list(WEATHER.keys()))
    weather_key: str = _weather_cache["weather_key"]  # type: ignore[assignment]
    return weather_key, WEATHER[weather_key]


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

ACHIEVEMENTS: dict[str, dict] = {
    "first_blood": {"emoji": "🏹", "name": "Первая кровь", "desc": "Первая успешная охота"},
    "sniper":      {"emoji": "💯", "name": "Снайпер",      "desc": "100 попаданий подряд"},
    "legend":      {"emoji": "👑", "name": "Легенда",      "desc": "Достичь 50 уровня"},
    "rich":        {"emoji": "💰", "name": "Богач",        "desc": "Накопить 100 000 серебра"},
    "mythic":      {"emoji": "✨", "name": "Охотник на мифы","desc": "Подстрелить мифическое существо"},
}


def check_achievements(user: dict) -> list[str]:
    earned: set[str] = set(user.get("achievements", []))
    new: list[str] = []
    if "first_blood" not in earned and user.get("successful_hunts", 0) >= 1:
        new.append("first_blood")
    if "sniper" not in earned and user.get("hit_streak", 0) >= 100:
        new.append("sniper")
    if "legend" not in earned and user.get("level", 1) >= 50:
        new.append("legend")
    if "rich" not in earned and user.get("silver", 0) >= 100_000:
        new.append("rich")
    if "mythic" not in earned and user.get("stats", {}).get("mythic_kills", 0) >= 1:
        new.append("mythic")
    if new:
        user["achievements"] = sorted(earned.union(new))
    return new


# ---------------------------------------------------------------------------
# Levels & XP
#   Step XP: 1→2: 100, 2→3: 250, 3→4: 500; then prev * 1.5
# ---------------------------------------------------------------------------

_LEVEL_THRESHOLDS: list[int] = [0, 0]  # cumulative XP needed to BE at index level


def _step_xp(level: int) -> int:
    """XP required to go from `level` to `level + 1`."""
    if level <= 0:
        return 0
    if level == 1:
        return 100
    if level == 2:
        return 250
    if level == 3:
        return 500
    return int(round(_step_xp(level - 1) * 1.5))


def xp_required_for_level(level: int) -> int:
    """Cumulative XP to BE at this level (level 1 = 0)."""
    if level <= 1:
        return 0
    while len(_LEVEL_THRESHOLDS) <= level:
        prev_level = len(_LEVEL_THRESHOLDS) - 1
        _LEVEL_THRESHOLDS.append(_LEVEL_THRESHOLDS[-1] + _step_xp(prev_level))
    return _LEVEL_THRESHOLDS[level]


def level_from_xp(xp: int) -> int:
    if xp < 0:
        return 1
    level = 1
    while level < 200 and xp_required_for_level(level + 1) <= xp:
        level += 1
    return level


def xp_progress(xp: int) -> tuple[int, int, int]:
    """Return (current_level, xp_into_level, xp_needed_for_next_level)."""
    level = level_from_xp(xp)
    current_threshold = xp_required_for_level(level)
    next_threshold = xp_required_for_level(level + 1)
    return level, xp - current_threshold, next_threshold - current_threshold


def level_accuracy_bonus(level: int) -> int:
    return min(LEVEL_ACCURACY_MAX, (level // LEVEL_ACCURACY_STEP) * LEVEL_ACCURACY_STEP)


def xp_for_kill(animal_key: str, weight_kg: float) -> int:
    """XP gained for a successful kill: (weight/10) * xp_mult, or fixed for mythic."""
    info = ANIMALS.get(animal_key)
    if not info:
        return 0
    if "fixed_xp" in info and info.get("fixed_xp"):
        return int(info["fixed_xp"])
    return max(1, int(round((weight_kg / 10.0) * info.get("xp_mult", 1.0))))


# ---------------------------------------------------------------------------
# Hunt mechanics
# ---------------------------------------------------------------------------

def pick_animal(location_key: str, time_key: str | None = None, rare_boost: float = 0.0) -> str:
    """Weighted-random animal pick from the location, with time-of-day bonuses."""
    animal_keys = LOCATIONS[location_key]["animals"]
    bonuses = TIME_SPAWN_BONUS.get(time_key or "", {})
    weights = []
    for a in animal_keys:
        w = ANIMALS[a]["chance"] * bonuses.get(a, 1.0)
        if rare_boost > 0 and ANIMALS[a]["rarity"] in ("rare", "epic", "legendary"):
            w *= 1.0 + rare_boost
        weights.append(w)
    return random.choices(animal_keys, weights=weights, k=1)[0]


def compute_hit_chance(
    weapon_accuracy: int,
    level: int,
    weather_mod: int,
    time_key: str,
    item_bonus: int = 0,
    dog_bonus: int = 0,
    weapon_upgrade_bonus: int = 0,
) -> int:
    """Compute final hit chance percentage (0..100)."""
    bonus = level_accuracy_bonus(level)
    night_pen = NIGHT_ACCURACY_PENALTY if time_key == "night" else 0
    chance = weapon_accuracy + bonus + weather_mod + night_pen + item_bonus + dog_bonus + weapon_upgrade_bonus
    return max(0, min(100, chance))


def roll_hit(chance: int) -> tuple[bool, int]:
    roll = random.randint(1, 100)
    return roll <= chance, roll


def cooldown_remaining(last_hunt_time: float, now: float | None = None) -> int:
    now = now if now is not None else time.time()
    elapsed = now - (last_hunt_time or 0)
    remaining = COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))


def format_remaining(seconds: int) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes} мин {secs:02d} сек"


def random_animal_weight(animal_key: str) -> float:
    info = ANIMALS[animal_key]
    return round(random.uniform(info["weight_min"], info["weight_max"]), 1)


def roll_random_event() -> str | None:
    if random.random() >= EVENT_CHANCE:
        return None
    return random.choice(["lucky", "critical", "gem"])


def upgrade_to_rare_animal(location_key: str) -> str:
    pool = LOCATIONS[location_key]["animals"]
    upgraded = [a for a in pool if ANIMALS[a]["rarity"] in ("rare", "epic", "legendary")]
    if not upgraded:
        upgraded = pool
    weights = [1.0 / max(1, ANIMALS[a]["chance"]) for a in upgraded]
    return random.choices(upgraded, weights=weights, k=1)[0]


def pick_safari_animal() -> str:
    """Choose an animal for /premium_safari. 5% chance of mythic."""
    if random.random() < SAFARI_MYTHIC_CHANCE:
        return random.choice(MYTHIC_KEYS)
    return upgrade_to_rare_animal("preserve")


# ---------------------------------------------------------------------------
# Unlocks & ownership
# ---------------------------------------------------------------------------

def unlocked_locations(level: int) -> list[str]:
    return [k for k, v in LOCATIONS.items() if not v.get("safari_only") and level >= v["level"]]


def unlocked_weapons(level: int) -> list[str]:
    return [k for k, v in WEAPONS.items() if level >= v["level"]]


# ---------------------------------------------------------------------------
# Inventory grouping
# ---------------------------------------------------------------------------

RARITY_ORDER = ["common", "rare", "epic", "legendary", "mythic"]


def group_inventory_by_rarity(inventory: dict[str, int]) -> dict[str, list[tuple[str, int]]]:
    groups: dict[str, list[tuple[str, int]]] = {r: [] for r in RARITY_ORDER}
    for key, count in inventory.items():
        if count <= 0 or key not in ANIMALS:
            continue
        groups[ANIMALS[key]["rarity"]].append((key, count))
    return groups


def inventory_total_value(inventory: dict[str, int]) -> int:
    total = 0
    for key, count in inventory.items():
        if key in ANIMALS:
            total += ANIMALS[key]["price"] * max(0, count)
    return total


def backpack_capacity(items: dict) -> int:
    extras = int(items.get("big_backpack", 0)) if isinstance(items, dict) else 0
    return BACKPACK_BASE_SLOTS + extras * BIG_BACKPACK_SLOTS


def inventory_total_count(inventory: dict[str, int]) -> int:
    return sum(max(0, c) for c in inventory.values())


# Map Russian animal name (lowercase) -> internal key, used by /sell
RU_ANIMAL_NAME_TO_KEY: dict[str, str] = {
    info["name"].lower(): key for key, info in ANIMALS.items()
}


def resolve_animal_query(query: str) -> str | None:
    if not query:
        return None
    q = query.strip().lower()
    if q in ANIMALS:
        return q
    return RU_ANIMAL_NAME_TO_KEY.get(q)


def iter_animals_sorted() -> Iterable[tuple[str, dict]]:
    return sorted(ANIMALS.items(), key=lambda kv: kv[1]["price"])


# ---------------------------------------------------------------------------
