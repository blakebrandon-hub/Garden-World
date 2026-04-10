"""
Garden World — JSON Storage
Replaces Supabase with a local JSON save file.
All state lives in memory (GAME_STATE dict) and is flushed to disk on save.
"""

import json
import os
import uuid
import base64
from datetime import datetime
from copy import deepcopy

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SAVE_FILE = "/tmp/garden_world_save.json"

ARCHIVE_THRESHOLD = 10_000   # characters before creating a summary
ARCHIVE_DISPLAY_LAG = 20_000 # characters before showing a summary in context
MAX_SUMMARIES = 4

PLANT_CONFIGS = {
    'tomato':     {'water_frequency': 1, 'name': 'Tomato'},
    'basil':      {'water_frequency': 1, 'name': 'Basil'},
    'lettuce':    {'water_frequency': 1, 'name': 'Lettuce'},
    'carrot':     {'water_frequency': 2, 'name': 'Carrot'},
    'strawberry': {'water_frequency': 2, 'name': 'Strawberry'},
    'mint':       {'water_frequency': 2, 'name': 'Mint'},
    'pepper':     {'water_frequency': 1, 'name': 'Pepper'},
    'cucumber':   {'water_frequency': 1, 'name': 'Cucumber'},
    'spinach':    {'water_frequency': 1, 'name': 'Spinach'},
    'radish':     {'water_frequency': 2, 'name': 'Radish'},
    'sunflower':  {'water_frequency': 1, 'name': 'Sunflower'},
    'bean':       {'water_frequency': 2, 'name': 'Bean'},
}

# ─────────────────────────────────────────────────────────────────────────────
# Default state shape
# ─────────────────────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {
        "game_state": {
            "id": str(uuid.uuid4()),
            "current_day": 0,
            "character_locations": {
                "Rowan": "Garden",
                "Mira": "Garden"
            },
            "inventories": {
                "Rowan": ["datapad", "roller_skates"],
                "Mira": ["roller_skates", "datapad"]
            }
        },
        "messages": [],      # {id, message_type, character, content, timestamp}
        "plants": [],        # {id, name, plant_type, stage, planted_by, health,
                             #  days_since_watered, last_watered_day, created_at}
        "world_objects": [    {
      "id": "f9eee897-2711-4dd3-88c9-a37775415043",
      "name": "watering_can",
      "location": "Garden",
      "created_at": "2026-04-10T18:13:57.770730"
    },
    {
      "id": "f9ee4897-2711-4d23-88c9-a37774415043",
      "name": "movie_projector",
      "location": "Observation Deck",
      "created_at": "2026-04-10T20:13:57.770730"
    }], # {id, name, location, created_at}
        "photos": [],        # {id, narrator_text, visual_prompt, image_url, timestamp}
        "summaries": [],     # {id, content, char_start, char_end, timestamp}
        "mira_journal": []   # {id, content, timestamp}
    }

# ─────────────────────────────────────────────────────────────────────────────
# In-memory store — loaded once at startup
# ─────────────────────────────────────────────────────────────────────────────

GAME_STATE: dict = _default_state()


def _now() -> str:
    return datetime.utcnow().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_to_disk(path: str = SAVE_FILE) -> None:
    """Write current in-memory state to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(GAME_STATE, f, indent=2, ensure_ascii=False)


def load_from_disk(path: str = SAVE_FILE) -> bool:
    """Load state from a JSON file into memory. Returns True on success."""
    global GAME_STATE
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    GAME_STATE = data
    return True


def export_save_json() -> str:
    """Return the current state serialized as a JSON string (for download)."""
    return json.dumps(GAME_STATE, indent=2, ensure_ascii=False)


def import_save_json(json_str: str) -> None:
    """Replace in-memory state from a JSON string (from upload)."""
    global GAME_STATE
    GAME_STATE = json.loads(json_str)


def reset_to_default() -> None:
    """Wipe all state back to a fresh game."""
    global GAME_STATE
    GAME_STATE = _default_state()


# ─────────────────────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────────────────────

def add_message(message_type: str, character: str, content: str) -> dict:
    msg = {
        "id": str(uuid.uuid4()),
        "message_type": message_type,
        "character": character,
        "content": content,
        "timestamp": _now()
    }
    GAME_STATE["messages"].append(msg)
    return msg


def get_messages() -> list:
    return list(GAME_STATE["messages"])


def get_message_count() -> int:
    return len(GAME_STATE["messages"])


def get_conversation_history(limit: int = 24) -> list:
    msgs = GAME_STATE["messages"][-limit:]
    return [
        {"type": m["message_type"], "character": m["character"], "text": m["content"]}
        for m in msgs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Game state
# ─────────────────────────────────────────────────────────────────────────────

def get_game_state() -> dict:
    return GAME_STATE["game_state"]


def update_game_state(
    character_locations: dict = None,
    inventories: dict = None,
    current_day: int = None
) -> dict:
    gs = GAME_STATE["game_state"]
    if character_locations is not None:
        gs["character_locations"] = character_locations
    if inventories is not None:
        gs["inventories"] = inventories
    if current_day is not None:
        gs["current_day"] = current_day
    return gs


# ─────────────────────────────────────────────────────────────────────────────
# Plants
# ─────────────────────────────────────────────────────────────────────────────

def add_plant(plant_name: str, plant_type: str, planted_by: str) -> dict:
    gs = get_game_state()
    current_day = gs.get("current_day", 0)
    config = PLANT_CONFIGS.get(plant_type, {"water_frequency": 1})
    water_freq = config["water_frequency"]

    plant = {
        "id": str(uuid.uuid4()),
        "name": plant_name,
        "plant_type": plant_type,
        "stage": "Seed",
        "planted_by": planted_by,
        "health": 100,
        "days_since_watered": water_freq,
        "last_watered_day": current_day - water_freq,
        "created_at": _now()
    }
    GAME_STATE["plants"].append(plant)
    return plant


def get_plants() -> list:
    return list(GAME_STATE["plants"])


def _find_plant(plant_id: str) -> dict | None:
    for p in GAME_STATE["plants"]:
        if p["id"] == plant_id:
            return p
    return None


def update_plant_stage(plant_id: str, new_stage: str) -> dict | None:
    valid = ['Seed', 'Sprout', 'Leafing', 'Flowering', 'Fruit', 'Harvest']
    if new_stage not in valid:
        raise ValueError(f"Invalid stage: {new_stage}")
    p = _find_plant(plant_id)
    if p:
        p["stage"] = new_stage
    return p


def water_plant(plant_id: str) -> dict | None:
    gs = get_game_state()
    current_day = gs.get("current_day", 0)
    p = _find_plant(plant_id)
    if p:
        p["days_since_watered"] = 0
        p["last_watered_day"] = current_day
        p["health"] = min(100, p.get("health", 100) + 10)
    return p


def update_plant_health(plant_id: str, health_change: int) -> dict | None:
    p = _find_plant(plant_id)
    if p:
        p["health"] = max(0, min(100, p.get("health", 100) + health_change))
    return p


def remove_plant(plant_id: str) -> dict | None:
    plants = GAME_STATE["plants"]
    for i, p in enumerate(plants):
        if p["id"] == plant_id:
            return plants.pop(i)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# World objects
# ─────────────────────────────────────────────────────────────────────────────

def add_world_object(name: str, location: str) -> dict:
    # Prevent duplicates
    for obj in GAME_STATE["world_objects"]:
        if obj["name"] == name:
            return obj
    obj = {"id": str(uuid.uuid4()), "name": name, "location": location, "created_at": _now()}
    GAME_STATE["world_objects"].append(obj)
    return obj


def get_world_objects(location: str = None) -> list:
    objs = GAME_STATE["world_objects"]
    if location:
        objs = [o for o in objs if o["location"] == location]
    return list(objs)


def move_world_object(name: str, new_location: str) -> dict | None:
    for obj in GAME_STATE["world_objects"]:
        if obj["name"] == name:
            obj["location"] = new_location
            return obj
    return None


def remove_world_object(name: str) -> dict | None:
    objs = GAME_STATE["world_objects"]
    for i, obj in enumerate(objs):
        if obj["name"] == name:
            return objs.pop(i)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Photos
# ─────────────────────────────────────────────────────────────────────────────

def upload_photo_to_storage(image_bytes: bytes) -> str:
    """
    Save image bytes locally as a PNG and return a file:// URL.
    In production you can swap this for S3/GCS/etc.
    """
    photos_dir = "static/photos"
    os.makedirs(photos_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    path = os.path.join(photos_dir, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    # Return a path that Flask can serve via /static/photos/<filename>
    return f"/static/photos/{filename}"


def save_photo(narrator_text: str, visual_prompt: str, image_url: str) -> dict:
    photo = {
        "id": str(uuid.uuid4()),
        "narrator_text": narrator_text,
        "visual_prompt": visual_prompt,
        "image_url": image_url,
        "timestamp": _now()
    }
    GAME_STATE["photos"].append(photo)
    return photo


def get_photos() -> list:
    return list(GAME_STATE["photos"])


# ─────────────────────────────────────────────────────────────────────────────
# Summaries / Archive
# ─────────────────────────────────────────────────────────────────────────────

def get_summaries() -> list:
    summaries = sorted(GAME_STATE["summaries"], key=lambda s: s.get("char_start", 0))
    return summaries[:MAX_SUMMARIES]


def save_summary(content: str, char_start: int, char_end: int) -> dict:
    summaries = GAME_STATE["summaries"]
    # Rolling window: evict oldest if full
    if len(summaries) >= MAX_SUMMARIES:
        summaries.sort(key=lambda s: s.get("timestamp", ""))
        evicted = summaries.pop(0)
        print(f"🗂️  Evicted oldest summary (id: {evicted['id']})")

    summary = {
        "id": str(uuid.uuid4()),
        "content": content,
        "char_start": char_start,
        "char_end": char_end,
        "timestamp": _now()
    }
    summaries.append(summary)
    print(f"📚 Saved summary: chars {char_start:,} – {char_end:,}")
    return summary


def get_total_character_count() -> int:
    return sum(len(m.get("content", "")) for m in GAME_STATE["messages"])


def get_current_character_position() -> int:
    return get_total_character_count()


def should_create_summary() -> tuple:
    summaries = get_summaries()
    messages = get_messages()
    if not messages:
        return (False, 0, 0)

    if summaries:
        last_summary = max(summaries, key=lambda s: s.get("char_end", 0))
        last_summarized_char = last_summary.get("char_end", 0)
    else:
        last_summarized_char = 0

    total_chars = get_total_character_count()
    chars_since = total_chars - last_summarized_char

    if chars_since >= ARCHIVE_THRESHOLD:
        cutoff_char = last_summarized_char + ARCHIVE_THRESHOLD
        return (True, last_summarized_char, cutoff_char)

    return (False, 0, 0)


def get_messages_in_char_range(start_char: int, end_char: int) -> list:
    all_messages = get_messages()
    result = []
    current_pos = 0
    for msg in all_messages:
        msg_len = len(msg.get("content", ""))
        msg_start = current_pos
        msg_end = current_pos + msg_len
        if msg_end > start_char and msg_start < end_char:
            result.append(msg)
        current_pos = msg_end
        if current_pos >= end_char:
            break
    return result


def format_messages_for_archiving(messages: list) -> str:
    lines = []
    for msg in messages:
        t = msg.get("message_type", "unknown")
        char = msg.get("character", "Unknown")
        content = msg.get("content", "")
        if t == "action":
            lines.append(f"[ACTION] {char}: {content}")
        elif t == "dialog":
            lines.append(f'[DIALOG] {char}: "{content}"')
        elif t == "narrator":
            lines.append(f"[NARRATOR] {content}")
        elif t == "photo":
            lines.append(f'[PHOTO] {char} took a photo: "{content}"')
        else:
            lines.append(f"[{t.upper()}] {char}: {content}")
    return "\n".join(lines)


def get_visible_summaries() -> list:
    current_pos = get_current_character_position()
    visible = [
        s for s in get_summaries()
        if current_pos - s.get("char_end", 0) >= ARCHIVE_DISPLAY_LAG
    ]
    return sorted(visible, key=lambda s: s.get("char_start", 0))


def check_and_create_summary_if_needed(llm_summarize_fn) -> bool:
    should, char_start, char_end = should_create_summary()
    if not should:
        return False

    print(f"\n🗂️  ARCHIVING: {char_start:,} – {char_end:,} characters")
    msgs = get_messages_in_char_range(char_start, char_end)
    log_segment = format_messages_for_archiving(msgs)
    summary_text = llm_summarize_fn(log_segment)
    save_summary(summary_text, char_start, char_end)
    print("✅ Summary created and saved")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Mira Journal
# ─────────────────────────────────────────────────────────────────────────────

def write_to_journal(content: str) -> dict:
    entry = {"id": str(uuid.uuid4()), "content": content, "timestamp": _now()}
    GAME_STATE["mira_journal"].append(entry)
    return entry


def get_journal(limit: int = 10) -> list:
    entries = GAME_STATE["mira_journal"]
    return list(entries[-limit:])


# ─────────────────────────────────────────────────────────────────────────────
# Context window builder
# ─────────────────────────────────────────────────────────────────────────────

def build_context_window() -> str:
    state = get_game_state()
    plants = get_plants()
    history = get_conversation_history(limit=24)
    all_objects = get_world_objects()
    summaries = get_visible_summaries()

    current_day = state.get("current_day", 0)
    character_locations = state.get("character_locations", {})
    characters = list(character_locations.keys())
    inventories = state.get("inventories", {})

    objects_by_location = {}
    for obj in all_objects:
        loc = obj["location"]
        if loc not in characters:
            objects_by_location.setdefault(loc, []).append(obj["name"])

    ctx = f"=== SHIP DAY {current_day} ===\n\n"

    ctx += "📍 CHARACTER LOCATIONS\n------------------------\n"
    for char, loc in character_locations.items():
        ctx += f"• {char} is currently in the {loc}\n"

    ctx += "\n🎒 INVENTORIES\n------------------------\n"
    for char, items in inventories.items():
        ctx += f"• {char}: {', '.join(items) if items else '(Empty)'}\n"

    ctx += "\n🌱 GARDEN STATE\n------------------------\n"
    if plants:
        for plant in plants:
            health = plant.get("health", 100)
            days = plant.get("days_since_watered", 0)
            icon = "💚" if health >= 80 else "💛" if health >= 50 else "🧡" if health >= 20 else "❤️"
            line = (f"• {plant['name']} ({plant.get('plant_type','unknown').capitalize()}) "
                    f"| Stage: {plant['stage']} | Health: {icon} {health}%"
                    f" | Planted by: {plant['planted_by']}")
            if days > 0:
                line += f" | 💧 Needs water! ({days} days dry)"
            ctx += line + "\n"
    else:
        ctx += "• The garden beds are empty.\n"

    ctx += "\n📦 WORLD OBJECTS (By Room)\n------------------------\n"
    if objects_by_location:
        for loc, objs in sorted(objects_by_location.items()):
            ctx += f"• {loc}: {', '.join(objs)}\n"
    else:
        ctx += "• No loose objects recorded.\n"

    ctx += "\n📚 SHIP'S ARCHIVE (What came before)\n------------------------\n"
    if summaries:
        for i, s in enumerate(summaries, 1):
            ctx += f"[Archive {i}]\n{s['content'].strip()}\n\n"
    else:
        ctx += "• No archive entries yet.\n"

    ctx += "\n📜 RECENT HISTORY\n------------------------\n"
    if history:
        for msg in history:
            t = msg["type"]
            if t == "action":
                ctx += f"[ACTION] {msg['character']}: {msg['text']}\n"
            elif t == "dialog":
                ctx += f"[DIALOG] {msg['character']}: \"{msg['text']}\"\n"
            elif t == "narrator":
                ctx += f"[NARRATOR] {msg['text'].replace(chr(10), ' ')}\n"
            elif t == "photo":
                ctx += f"[PHOTO] {msg['character']} took a photo: \"{msg['text']}\"\n"
    else:
        ctx += "• No recent history.\n"

    return ctx
