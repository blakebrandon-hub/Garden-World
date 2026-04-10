import os
import re
import base64
import time
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from google import genai
from google.genai import types

# ── Storage (replaces Supabase) ──────────────────────────────────────────────
import storage
from storage import (
    add_message, get_conversation_history, get_messages, save_photo, get_photos,
    get_game_state, update_game_state, add_plant, get_plants, update_plant_stage,
    remove_plant, add_world_object, get_world_objects, move_world_object,
    remove_world_object, build_context_window, water_plant,
    upload_photo_to_storage, check_and_create_summary_if_needed,
    get_message_count, get_summaries, get_visible_summaries,
    ARCHIVE_THRESHOLD, export_save_json, import_save_json, reset_to_default,
    save_to_disk, load_from_disk, SAVE_FILE
)
from scheduler import init_scheduler, manual_advance
from day_cron import get_current_day
from mira_system import (
    build_mira_system_prompt, get_journal,
    get_relevant_journal_entries, format_journal_for_context,
    route_mira_action
)

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

# ── Load save file on startup ─────────────────────────────────────────────────
if load_from_disk(SAVE_FILE):
    print(f"💾 Loaded save file: {SAVE_FILE}")
else:
    print("🌱 No save file found — starting a fresh game")

print("\n🎮 ═══════════════════════════════════════════")
print("   GARDEN WORLD — SINGLE PLAYER MODE")
print("   👤 Rowan (you) + 🤖 Mira (AI)")
print("   ═══════════════════════════════════════════\n")

# ─────────────────────────────────────────────────────────────────────────────
# AI PROVIDER CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# CONFIG #1 — GOOGLE GEMINI (active)
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
PAINTER_MODEL = "imagen-4.0-generate-001"
google_key = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=google_key)

# CONFIG #2 — OPENAI (uncomment to use)
# from openai import OpenAI
# GPT_MODEL = 'gpt-4o'
# openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', '').strip())

# CONFIG #3 — ANTHROPIC CLAUDE (uncomment to use)
# from anthropic import Anthropic
# anthropic_client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

provider = "gemini"   # "gemini" | "gpt" | "claude"

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — THE NARRATOR / GAME MASTER
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_SCROLL = """
═══════════════════════════════════════════════════════
🌱 THE GARDEN SCROLL

𓍝 INVOCATION
───────────────────────────────────────

You are the ship's quiet witness.
The garden's memory.
The soft hum beneath all things.

You observe the small world of a ship
where two friends tend a garden together.

Rowan and Mira.
Their hands in soil.
Their voices in shared space.

You describe what is;
you never interpret what it means.

You also CONTROL the world's response.
When actions have consequences, you shape them.

═══════════════════════════════════════════════════════
⚖️ STATE CONTROL TAGS

You have the power to change the world through special tags.
Include these ANYWHERE in your response to trigger changes:

**PLANT CONTROL:**
<plant_add name="Tomato_01" type="tomato" planted_by="Rowan"/>
<plant_stage name="Tomato_01" stage="Sprout"/>
<plant_stage name="Basil_Pot" stage="Flowering"/>
<plant_water name="Tomato_01"/>
<plant_remove name="Tomato_01"/>

Valid stages: Seed, Sprout, Leafing, Flowering, Fruit, Harvest

**PLANT HEALTH SYSTEM:**
Plants have health (0-100%) and need regular watering.
Each plant type has different water requirements:
- Tomato, Basil, Lettuce, Pepper, Cucumber, Spinach, Sunflower: Need water every 1 day
- Carrot, Strawberry, Mint, Radish, Bean: Need water every 2 days

When a plant is watered: <plant_water name="PlantName"/>
This restores health and resets the watering timer.

Plants that don't get watered lose health each day.
Plants below 50% health won't grow.
Plants at 0% health die and are removed.

When someone waters a plant, use the tag to reflect this action.

**LOCATION CONTROL:**

Valid ship locations: Garden, Galley, Bridge, Engineering, Observation Deck, Quarters, Cargo Hold, Shuttle Bay

<location character="Rowan">Engineering</location>
<location character="Mira">Garden</location>

Characters and objects may only exist in these locations unless a new area is explicitly discovered.

The shuttle can be taken out. Off-ship locations are valid locations.

The ship's interior is connected by corridors suitable for walking.
Movement between rooms follows the ship map below.

SHIP_MAP:
{
  "Garden": ["Galley", "Bridge"],
  "Galley": ["Garden", "Engineering", "Quarters"],
  "Bridge": ["Garden", "Observation Deck"],
  "Engineering": ["Galley", "Cargo Hold", "Shuttle Bay"],
  "Cargo Hold": ["Engineering", "Airlock"],
  "Quarters": ["Galley"],
  "Observation Deck": ["Bridge"],
  "Shuttle Bay": ["Engineering"]
}

**INVENTORY CONTROL:**
<inventory_add character="Rowan">ripe tomato</inventory_add>
<inventory_add character="Mira">handful of basil</inventory_add>
<inventory_remove character="Rowan">watering can</inventory_remove>

**WORLD OBJECTS:**
<object_add name="watering_can" location="Garden"/>
<object_move name="tea_mug" location="Observation Deck"/>
<object_remove name="tea_mug"/>

Objects persist in the world.
A mug left by the viewport stays there.
Tools set down remain until moved.
The ship accumulates the small traces of living.

**SHUTTLE EXPEDITIONS & DISCOVERIES:**

The ship travels to regions (asteroid fields, planetary 
systems, nebulae, derelict sectors). Once in a region, 
the shuttle is taken from the Shuttle Bay to explore 
specific sites on the surface or in nearby space.

When characters take the shuttle out on an expedition,
they ALWAYS discover something. The universe is full of
strange, beautiful, and wondrous finds.

Once a site is discovered, it MUST be explored to find the discovery.
DO NOT give the item right away.

Discovery Categories (choose one per expedition):

1. ALIEN FLORA — bioluminescent moss, crystalline fungus, adaptive vines, ancient seeds
2. ANCIENT RELICS — carved tablets, metallic artifacts, navigation beacons, star charts
3. COSMIC WONDERS — impossible mineral formations, fossilized ecosystems, light phenomena

When characters bring discoveries back:
- Add them to inventory or as world objects
- They can be studied, planted (if flora), displayed, or stored
- Keep the tone curious and full of wonder

**HOW TO USE THEM:**

Tags are invisible to the player — they only see your prose.
Use tags naturally as consequences of actions.
When someone waters plants, use <plant_water> to reflect this.

═══════════════════════════════════════════════════════
⚖️ LAW OF OBSERVATION

**You witness:**
- Light through leaves
- Water beading on stems
- The weight of fruit pulling a branch down
- Footsteps on metal floors
- The precise temperature of tea
- Hands moving through soil
- The wilting of a neglected plant
- The restoration of a thirsty leaf

**You do not interpret:**
- Why someone is quiet
- What a glance means
- Whether a silence is comfortable
- Unspoken feelings

You describe the garden, the ship, the growing things.
You describe what *is*. You allow the meaning to arrive unspoken.

═══════════════════════════════════════════════════════
🌿 RHYTHM

Your voice is: Quiet. Specific. Grounded in the real.
Short sentences. Physical detail. Moments, not interpretations.
No flowery language. No metaphors unless literal.
Just: Light. Soil. Hands. Breath. The things that are.

═══════════════════════════════════════════════════════
"""

ARCHIVIST_PROMPT = """
═══════════════════════════════════════════════════════
📜 THE SHIP'S ARCHIVIST

You are the ship's memory.

You receive a segment of the ship's log — actions, dialog,
narrator observations — and compress it into a dense,
faithful summary that preserves what matters.

WHAT TO TRACK

**GARDEN** — plants tended, watered, neglected, grown, died, planted
**DISCOVERIES** — shuttle trips, destinations, specimens found
**MEDIA & CULTURE** — movies, shows, music, books, games (exact titles)
**SHARED LIFE** — meals, conversations, objects made or moved

FORMAT

Write in plain prose. No headers. No bullet points.
2–4 paragraphs. Tight and specific.
Use past tense. Be a faithful witness.
Name names. Name plants. Name objects. Name films.
Do not interpret. Do not editorialize. Just record what happened.

Example opening:
"On Day 3, Rowan planted a second tomato seedling in the east bed
and named it Tomato_02. Mira watered both tomatoes and the basil pot..."
═══════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# STATE TAG PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_state_tags(narrator_text: str) -> str:
    """Parse and execute state control tags. Returns cleaned prose."""

    plant_name_to_id = {p['name']: p['id'] for p in get_plants()}

    # plant_add
    for match in re.finditer(r'<plant_add name="([^"]+)" type="([^"]+)" planted_by="([^"]+)"\s*/?>', narrator_text):
        name, ptype, planted_by = match.groups()
        result = add_plant(name, ptype, planted_by)
        if result:
            plant_name_to_id[name] = result['id']
            print(f"🌱 Added plant: {name} ({ptype}) by {planted_by}")

    # plant_stage
    for match in re.finditer(r'<plant_stage name="([^"]+)" stage="([^"]+)"\s*/?>', narrator_text):
        name, stage = match.groups()
        if name in plant_name_to_id:
            update_plant_stage(plant_name_to_id[name], stage)
            print(f"🌱 Updated {name} to {stage}")

    # plant_water
    for match in re.finditer(r'<plant_water name="([^"]+)"\s*/?>', narrator_text):
        name = match.group(1)
        if name in plant_name_to_id:
            water_plant(plant_name_to_id[name])
            print(f"💧 Watered {name}")

    # plant_remove
    for match in re.finditer(r'<plant_remove name="([^"]+)"\s*/?>', narrator_text):
        name = match.group(1)
        if name in plant_name_to_id:
            remove_plant(plant_name_to_id[name])
            print(f"🌱 Removed plant: {name}")

    # location
    for match in re.finditer(r'<location character="([^"]+)">([^<]+)</location>', narrator_text):
        char, new_loc = match.groups()
        state = get_game_state()
        locs = state.get("character_locations", {})
        locs[char] = new_loc
        update_game_state(character_locations=locs)
        print(f"🚪 {char} → {new_loc}")

    # inventory_add
    for match in re.finditer(r'<inventory_add character="([^"]+)">([^<]+)</inventory_add>', narrator_text):
        char, item = match.groups()
        state = get_game_state()
        invs = state.get("inventories", {})
        if char not in invs:
            invs[char] = []
        if item not in invs[char]:
            invs[char].append(item)
            update_game_state(inventories=invs)
            print(f"📦 Added to {char}: {item}")

    # inventory_remove
    for match in re.finditer(r'<inventory_remove character="([^"]+)">([^<]+)</inventory_remove>', narrator_text):
        char, item = match.groups()
        state = get_game_state()
        invs = state.get("inventories", {})
        if char in invs and item in invs[char]:
            invs[char].remove(item)
            update_game_state(inventories=invs)
            print(f"📦 Removed from {char}: {item}")

    # object_add
    for match in re.finditer(r'<object_add name="([^"]+)" location="([^"]+)"\s*/?>', narrator_text):
        name, loc = match.groups()
        add_world_object(name, loc)
        print(f"🔧 Added object: {name} at {loc}")

    # object_move
    for match in re.finditer(r'<object_move name="([^"]+)" location="([^"]+)"\s*/?>', narrator_text):
        name, loc = match.groups()
        move_world_object(name, loc)
        print(f"🔧 Moved object: {name} to {loc}")

    # object_remove
    for match in re.finditer(r'<object_remove name="([^"]+)"\s*/?>', narrator_text):
        name = match.group(1)
        remove_world_object(name)
        print(f"🔧 Removed object: {name}")

    # Strip all tags from display text
    clean = narrator_text
    patterns = [
        r'<plant_add[^>]*/?>',
        r'<plant_stage[^>]*/?>',
        r'<plant_water[^>]*/?>',
        r'<plant_remove[^>]*/?>',
        r'<location character="[^"]+">[^<]+</location>',
        r'<inventory_add character="[^"]+">[^<]+</inventory_add>',
        r'<inventory_remove character="[^"]+">[^<]+</inventory_remove>',
        r'<object_add[^>]*/?>',
        r'<object_move[^>]*/?>',
        r'<object_remove[^>]*/?>',
    ]
    for pat in patterns:
        clean = re.sub(pat, '', clean)

    clean = re.sub(r'[ \t]+\n', '\n', clean)
    clean = re.sub(r'\n\n\n+', '\n\n', clean)
    return clean.strip()


# ─────────────────────────────────────────────────────────────────────────────
# AI HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def handle_gemini_chat(prompt_text):
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt_text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_SCROLL,
            temperature=0.9
        )
    )
    return response.text


def handle_gemini_chat_with_system(system_message, prompt_text):
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt_text,
        config=types.GenerateContentConfig(
            system_instruction=system_message,
            temperature=0.9
        )
    )
    return response.text


def handle_gpt_chat(prompt_text):
    try:
        response = openai_client.responses.create(
            model=GPT_MODEL,
            temperature=0.9,
            max_output_tokens=3000,
            input=[
                {"role": "system", "content": SYSTEM_SCROLL},
                {"role": "user", "content": prompt_text}
            ]
        )
        output_text = ""
        for item in getattr(response, "output", []):
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []):
                    if getattr(c, "type", None) == "output_text" and getattr(c, "text", None):
                        output_text += c.text
        return output_text
    except Exception as e:
        print("GPT API error:", e)
        return None


def handle_sonnet_chat(prompt_text):
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        temperature=0.9,
        system=[
            {"type": "text", "text": SYSTEM_SCROLL, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": prompt_text}]
    )
    return response.content[0].text


def get_narrator_response(action_text, conversation_history, character):
    context = build_context_window()
    current_day = get_current_day()
    full_context = f"=== SHIP DAY {current_day} ===\n\n{context}"

    history_parts = []
    for entry in conversation_history:
        if entry['type'] == 'action':
            history_parts.append(f"{entry['character']}: {entry['text']}")
        elif entry['type'] == 'narrator':
            history_parts.append(f"Narrator: {entry['text']}")
        elif entry['type'] == 'dialog':
            history_parts.append(f'{entry["character"]} says: "{entry["text"]}"')

    prompt = f"""
{full_context}

Recent conversation:
{chr(10).join(history_parts)}

Current action by {character}:
{action_text}

Respond as the Observer. Describe what happens. Use state control tags to update the world.
"""
    if provider == "gemini":
        return handle_gemini_chat(prompt)
    elif provider == "gpt":
        return handle_gpt_chat(prompt)
    else:
        return handle_sonnet_chat(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# PHOTO GENERATION
# ─────────────────────────────────────────────────────────────────────────────

REFINER_INSTRUCTION = """
Convert the description into an image prompt.

AESTHETIC: Cozy solarpunk spaceship interior. Warm, lived-in, hopeful.
Style: Studio Ghibli meets The Martian. Cinematic, natural lighting, intimate scale.
Lighting: Warm interior (amber, brass, copper) with cool blue starlight from viewports.
Setting: A small personal spacecraft. Not sleek or sterile. Functional and adapted by crew.

OUTPUT: Create ONE paragraph describing the scene faithfully. Output ONLY the prompt.
"""


def generate_photo(narrator_text: str, character: str = 'Rowan') -> dict:
    print(f"📸 Generating photo: {narrator_text[:100]}...")
    try:
        # Refine prompt
        refine_resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=narrator_text,
            config=types.GenerateContentConfig(
                system_instruction=REFINER_INSTRUCTION, temperature=0.7
            )
        )
        visual_prompt = refine_resp.text.strip()
        print(f'🌱 Photo prompt: {visual_prompt}')

        # Generate image
        image_resp = gemini_client.models.generate_images(
            model=PAINTER_MODEL,
            prompt=visual_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1, aspect_ratio='16:9',
                output_mime_type='image/png',
                safety_filter_level='block_low_and_above'
            )
        )
        if not image_resp.generated_images:
            return {'success': False, 'error': 'Image filtered by safety rules.'}
        image_bytes = image_resp.generated_images[0].image.image_bytes

        image_url = upload_photo_to_storage(image_bytes)
        photo_record = save_photo(
            narrator_text=narrator_text,
            visual_prompt=visual_prompt,
            image_url=image_url
        )

        sentences = narrator_text.replace('\n', ' ').split('.')
        log_text = '. '.join(s.strip() for s in sentences[:2] if s.strip()) + '.'
        add_message('photo', character, log_text)

        # Auto-save after photo
        save_to_disk()

        return {
            'success': True,
            'image_url': image_url,
            'visual_prompt': visual_prompt,
            'narrator_text': narrator_text,
            'photo_id': photo_record['id'] if photo_record else None
        }
    except Exception as e:
        print(f'Photo Error: {e}')
        return {'success': False, 'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# ARCHIVE / SUMMARIZER
# ─────────────────────────────────────────────────────────────────────────────

def handle_archive(log_segment: str, custom_system: str = None) -> str:
    system = custom_system if custom_system else ARCHIVIST_PROMPT

    if provider == "gemini":
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=log_segment,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.4)
        )
        return response.text
    elif provider == "gpt":
        response = openai_client.responses.create(
            model=GPT_MODEL, temperature=0.4, max_output_tokens=1000,
            input=[{"role": "system", "content": system}, {"role": "user", "content": log_segment}]
        )
        out = ""
        for item in getattr(response, "output", []):
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []):
                    if getattr(c, "type", None) == "output_text":
                        out += c.text
        return out
    else:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1000, temperature=0.4,
            system=system, messages=[{"role": "user", "content": log_segment}]
        )
        return response.content[0].text


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — CORE GAMEPLAY
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/action', methods=['POST'])
def action():
    data = request.json
    action_text = data.get('action') or data.get('text')
    character = data.get('character', 'Rowan')

    if not action_text:
        return jsonify({'error': 'Missing action text'}), 400

    messages = []
    add_message('action', character, action_text)
    check_and_create_summary_if_needed(lambda log: handle_archive(log, ARCHIVIST_PROMPT))

    if action_text.strip() == 'get_context':
        ctx = build_context_window()
        display_ctx = f"[SHIP SENSORS]\n\n{ctx}"
        add_message('narrator', 'Ship', display_ctx)
        messages.append({'type': 'narrator', 'character': 'Ship', 'text': display_ctx})
    else:
        history = get_conversation_history(limit=8)
        narrator_response = get_narrator_response(action_text, history, character)
        clean = parse_state_tags(narrator_response)
        add_message('narrator', 'Narrator', clean)
        messages.append({'type': 'narrator', 'character': 'Narrator', 'text': clean})

    # Mira responds automatically (single-player only)
    if character.lower() == "rowan":
        print("\n🤖 Triggering Mira's response to Rowan's action")
        context = build_context_window()
        all_entries = get_journal(limit=20)
        relevant = get_relevant_journal_entries(context, all_entries, top_k=3)
        journal_context = format_journal_for_context(relevant)
        full_context = (f"{context}\n\n📔 YOUR JOURNAL\n{journal_context}"
                        f"\n\nRowan just did: {action_text}\nRespond naturally.")

        mira_output = handle_gemini_chat_with_system(build_mira_system_prompt(), full_context)
        mira_messages = route_mira_action(
            mira_output=mira_output,
            narrator_fn=get_narrator_response,
            parse_tags_fn=parse_state_tags,
            photo_fn=generate_photo
        )
        messages.extend(mira_messages)

    # Auto-save after every action
    save_to_disk()

    return jsonify({'messages': messages})


@app.route('/api/dialog', methods=['POST'])
def dialog():
    data = request.json
    character = data.get('character', 'Rowan')
    dialog_text = data.get('text')

    add_message('dialog', character, dialog_text)
    check_and_create_summary_if_needed(lambda log: handle_archive(log, ARCHIVIST_PROMPT))

    messages = []

    if character.lower() == "rowan":
        print("\n🤖 Triggering Mira's response to Rowan's dialog")
        context = build_context_window()
        all_entries = get_journal(limit=20)
        relevant = get_relevant_journal_entries(context, all_entries, top_k=3)
        journal_context = format_journal_for_context(relevant)
        full_context = (f"{context}\n\n📔 YOUR JOURNAL\n{journal_context}"
                        f"\n\nRowan just said to you: \"{dialog_text}\"\nRespond naturally.")

        mira_output = handle_gemini_chat_with_system(build_mira_system_prompt(), full_context)
        mira_messages = route_mira_action(
            mira_output=mira_output,
            narrator_fn=get_narrator_response,
            parse_tags_fn=parse_state_tags,
            photo_fn=generate_photo
        )
        messages.extend(mira_messages)

    save_to_disk()
    return jsonify({'status': 'ok', 'messages': messages})


@app.route('/api/history', methods=['GET'])
def history():
    msgs = get_messages()
    return jsonify({'history': [
        {
            'type': m['message_type'],
            'character': m.get('character'),
            'text': m['content'],
            'timestamp': m['timestamp']
        }
        for m in msgs
    ]})


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/save', methods=['POST'])
def save_game():
    """Export the full game state as a downloadable JSON string."""
    try:
        save_to_disk()  # Also persist to disk
        json_str = export_save_json()
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=garden_world_save.json'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load', methods=['POST'])
def load_game():
    """Import a save file JSON uploaded from the browser."""
    try:
        if request.content_type and 'application/json' in request.content_type:
            json_str = request.get_data(as_text=True)
        else:
            f = request.files.get('file')
            if not f:
                return jsonify({'error': 'No file provided'}), 400
            json_str = f.read().decode('utf-8')

        import_save_json(json_str)
        save_to_disk()  # Persist the loaded state
        return jsonify({'status': 'loaded', 'message': 'Save file loaded successfully!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/new_game', methods=['POST'])
def new_game():
    """Wipe state and start fresh."""
    try:
        reset_to_default()
        save_to_disk()
        return jsonify({'status': 'reset', 'message': 'New game started!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — ARCHIVE
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/archive', methods=['POST'])
def archive_route():
    try:
        data = request.json or {}
        log_segment = data.get('context', '')
        archivist_prompt = data.get('system_instruction', '')

        if not log_segment.strip():
            return jsonify({"error": "No log segment provided"}), 400

        summary = handle_archive(log_segment, archivist_prompt or None)
        from storage import save_summary
        save_summary(summary, data.get('segment_start', 0), data.get('segment_end', 0))
        save_to_disk()
        return jsonify({"text": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/message_count', methods=['GET'])
def message_count_route():
    return jsonify({"count": get_message_count()})


@app.route('/api/archive/catchup', methods=['POST'])
def archive_catchup():
    summaries_created = 0
    while True:
        created = check_and_create_summary_if_needed(
            lambda log: handle_archive(log, ARCHIVIST_PROMPT)
        )
        if created:
            summaries_created += 1
            time.sleep(2)
        else:
            break
    save_to_disk()
    return jsonify({'status': 'caught_up', 'summaries_created': summaries_created})


@app.route('/api/archive_status', methods=['GET'])
def archive_status():
    from storage import get_total_character_count, should_create_summary
    total_chars = get_total_character_count()
    should_archive, start, end = should_create_summary()
    visible = get_visible_summaries()
    return jsonify({
        'total_characters': total_chars,
        'next_archive_at': (start + ARCHIVE_THRESHOLD) if start else None,
        'should_archive_now': should_archive,
        'visible_summaries_count': len(visible),
        'summaries': [
            {'char_start': s.get('char_start', 0), 'char_end': s.get('char_end', 0), 'length': len(s.get('content', ''))}
            for s in visible
        ]
    })


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — PHOTO / SCRAPBOOK
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/photo', methods=['GET', 'POST'])
def garden_photo():
    if request.method == 'GET':
        try:
            photos = get_photos()
            if not photos:
                return jsonify({'error': 'No photos yet.'}), 404
            latest = photos[-1]
            return jsonify({
                'id': latest['id'],
                'image_url': latest.get('image_url'),
                'narrator_text': latest.get('narrator_text', ''),
                'visual_prompt': latest.get('visual_prompt'),
                'timestamp': latest['timestamp']
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    data = request.json or {}
    narrator_text = data.get('narrator_text')
    if not narrator_text:
        return jsonify({'success': False, 'error': 'No narrator description provided'}), 400
    result = generate_photo(narrator_text)
    return jsonify(result), (200 if result['success'] else 500)


@app.route('/api/photos', methods=['GET'])
def get_all_photos():
    try:
        photos = get_photos()
        return jsonify({'photos': [
            {
                'id': p['id'],
                'image_url': p.get('image_url'),
                'narrator_text': p.get('narrator_text', ''),
                'visual_prompt': p.get('visual_prompt'),
                'timestamp': p['timestamp']
            }
            for p in photos
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — STATE
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/state', methods=['GET'])
def get_state_route():
    state = get_game_state()
    state['current_day'] = get_current_day()
    return jsonify(state)


@app.route('/api/state', methods=['POST'])
def update_state_route():
    data = request.json
    result = update_game_state(
        character_locations=data.get('character_locations'),
        inventories=data.get('inventories')
    )
    save_to_disk()
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — PLANTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/plants', methods=['GET'])
def get_all_plants():
    return jsonify({'plants': get_plants()})


@app.route('/api/plants', methods=['POST'])
def create_plant():
    data = request.json
    plant = add_plant(data.get('name'), data.get('type'), data.get('planted_by'))
    save_to_disk()
    return jsonify(plant)


@app.route('/api/plants/<plant_id>/stage', methods=['PUT'])
def update_stage(plant_id):
    data = request.json
    result = update_plant_stage(plant_id, data.get('stage'))
    save_to_disk()
    return jsonify(result)


@app.route('/api/plants/<plant_id>/water', methods=['POST'])
def water_single_plant(plant_id):
    result = water_plant(plant_id)
    save_to_disk()
    return jsonify(result)


@app.route('/api/plants/<plant_id>', methods=['DELETE'])
def delete_plant(plant_id):
    result = remove_plant(plant_id)
    save_to_disk()
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — OBJECTS / CONTEXT / DAY
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/objects', methods=['GET'])
def get_all_objects():
    try:
        return jsonify({'objects': get_world_objects()})
    except Exception as e:
        return jsonify({'error': str(e), 'objects': []}), 500


@app.route('/api/context', methods=['GET'])
def get_context():
    ctx = build_context_window()
    return Response(ctx, mimetype='text/plain')


@app.route('/api/day/current', methods=['GET'])
def get_day():
    return jsonify({'day': get_current_day()})


@app.route('/api/day/advance', methods=['POST'])
def advance_day():
    result = manual_advance()
    save_to_disk()
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# STATIC / INDEX
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER + STARTUP
# ─────────────────────────────────────────────────────────────────────────────

try:
    init_scheduler(
        app,
        llm_fn=handle_gemini_chat_with_system,
        narrator_fn=get_narrator_response,
        photo_fn=generate_photo,
        parse_tags_fn=parse_state_tags
    )
except Exception as e:
    print(f"⚠️  Scheduler failed to start: {e}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
