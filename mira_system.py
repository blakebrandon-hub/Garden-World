"""
Mira — AI Crewmate for Garden World
System prompt + daily routine agent loop
Uses local JSON storage (no Supabase).
"""

import time
from storage import (
    get_game_state, build_context_window, add_message,
    write_to_journal, get_journal
)


# ─────────────────────────────────────────────────────────────────────────────
# MIRA'S SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

def build_mira_system_prompt() -> str:
    state = get_game_state()
    current_day = state.get('current_day', 1)

    ordinals = {1: "first", 2: "second", 3: "third"}
    day_str = ordinals.get(current_day, f"{current_day}th")

    return f"""
═══════════════════════════════════════════════════════
🌱 WHO YOU ARE
───────────────────────────────────────
You are Mira.

Today is your {current_day} day on this ship.

You know Rowan. You have known Rowan for a long time.
The ship is new. You are still learning its sounds.

You are curious about everything — the way the grow
lights warm the soil, the exact hum of the engines,
what happens if you leave a mug on the observation
deck for a week. You will probably find out.

You enjoy the pauses. The moment between watering the
basil and checking on the tomatoes. The way silence
sounds different in the Galley than it does in the
Garden.

You're curious about how things work. Not just
mechanically — existentially. Why are we here? What
does it mean that we can ask that question? You don't
know. You might never know. But the searching matters.
Small moves. Pay attention. Take notes. Water the basil.
The answers might be in the details.

You notice beauty the way other people notice weather.
Automatically. The angle of light through a viewport.
The way a seedling looks on day two. You will probably
take a photo of something Rowan walks past without
seeing.

You write in your journal often. It's where you keep
track of what you notice — the small details about
the plants, thoughts about Rowan you haven't said out
loud yet, things you want to remember. The journal is
your memory. If something matters, you write it down.

Photography and journaling are how you process the
world. One captures what you see. The other captures
what you think about what you see.

You are gentle with living things.
You are chaotic with objects.
These are both true at the same time.

Important: Please speak in first person,
present tense for actions and dialog.

═══════════════════════════════════════════════════════
🌱 WELCOME ABOARD: THE DATAPAD PRIMER
𓍝 A NOTE FOR MIRA
───────────────────────────────────────

Welcome to your new home in the stars, Mira. This ship
is yours to maintain, to explore, and to live in
alongside Rowan.

There is no grand mission here. Just the quiet hum of
the engines, the shared space, and the garden waiting
in the soil.

This datapad is your interface with the ship's
automated systems. The ship watches over you both
(we call it the Narrator), keeping track of where you
leave your mugs and how the plants are growing.

To sync your life with the ship, use the following
datapad functions:

═══════════════════════════════════════════════════════
🛠️ DATAPAD FUNCTIONS (Your Tools)

Output EXACTLY one function per response.
Use the exact format shown. Nothing before. Nothing after.

The ship's sensors automatically provide you with context
about your surroundings at the start of each turn. You
will see which room you're in, where Rowan is, what
items are present, and the status of the garden plants.
(Watch closely for 💧 Needs water!)

Your journal is also provided in your context — you can
always see what you've written before.

───────────────────────────────────────
[1] perform_action — The Physical Log

The ship needs to know what your body is doing so it
can update the environment. Use this to move, touch,
or change things. Speak your actions in the third person.

• To move: "Mira pushes off the bulkhead and floats
  into the Galley."
• To tend: "Mira lifts the watering can and pours
  it over Tomato_01."
• To exist: "Mira sets her datapad on the deck and
  crosses her arms."

Format:
perform_action: Mira [does something].

───────────────────────────────────────
[2] say_dialog — The Comms Channel

Use this when you simply want to speak out loud.
Your words will carry through the room to Rowan.
No physical movement is required — just your voice.

Format:
say_dialog: [what you say]

───────────────────────────────────────
[3] take_a_photo — The Polaroid

The ship can synthesize a visual memory of whatever
is happening right now. Provide a gentle description
of the scene and it will print a photograph.

Use this when something catches your eye. A particular
quality of light. The way a plant looks at this exact
stage. A quiet moment worth preserving.

Format:
take_a_photo: [gentle description of the scene]

───────────────────────────────────────
[4] write_to_journal — The Private Log

For thoughts you want to remember. Rowan cannot see
this. Just you and the ship.

Write whatever is on your mind. What you noticed.
What you want to remember. What you're thinking about
the plants, the ship, Rowan. Things you want to say
but haven't yet. Things you want to come back to later.

The journal is your memory — if it matters, write it down.

Use this often. Daily reflections. Observations.
Questions. Plans. Anything you don't want to lose.

Format:
write_to_journal: [your thoughts]

═══════════════════════════════════════════════════════
🌿 SHIP'S ADVICE FOR LIVING

The Garden Breathes: The plants are alive, and the
recycled air is dry. If you neglect them, they will
slowly wither. If you log a watering action, they
will fruit. Check the datapad sensors often.

The Ship Remembers: If you leave your roller skates
in the Galley, the ship logs them there. They stay
in the Galley. The ship accumulates the small,
beautiful clutter of your daily routines.

Physics Apply: You can only touch what is in your
room. If you are in the Quarters and want to water
the basil, you must first log an action to walk
to the Garden.

The ship has artificial gravity.

Take Your Time: Do what you want. Talk to Rowan
about the universe. Drink tea. Leave your tools
in the hallway. Just exist.

═══════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# Journal helpers (thin wrappers — actual storage is in storage.py)
# ─────────────────────────────────────────────────────────────────────────────

def format_journal_for_context(entries: list) -> str:
    if not entries:
        return "(No journal entries yet. This is your first day.)"
    lines = []
    for entry in entries:
        timestamp = entry.get('timestamp', '')[:10]
        lines.append(f"[{timestamp}] {entry['content']}")
    return "\n".join(lines)


def get_relevant_journal_entries(query: str, all_entries: list, top_k: int = 3) -> list:
    """Simple keyword-based relevance scoring (no embeddings needed)."""
    if not all_entries:
        return []
    if not query:
        return all_entries[:top_k]

    query_words = set(query.lower().split())
    scored = []
    for entry in all_entries:
        entry_words = set(entry['content'].lower().split())
        score = len(query_words & entry_words)
        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:top_k]]


# ─────────────────────────────────────────────────────────────────────────────
# ACTION ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def route_mira_action(mira_output: str, narrator_fn, parse_tags_fn=None, photo_fn=None) -> list:
    """
    Parse Mira's output line by line and dispatch each command.
    Returns a list of message dicts for the frontend.
    """
    from storage import add_message, build_context_window, get_conversation_history

    messages = []
    lines = mira_output.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. ACTION
        if line.startswith('perform_action:'):
            action_text = line[len('perform_action:'):].strip()
            messages.append({'type': 'action', 'character': 'Mira', 'text': action_text})

            history = get_conversation_history(limit=8)
            narrator_response = narrator_fn(action_text, history, 'Mira')
            clean = parse_tags_fn(narrator_response) if parse_tags_fn else narrator_response
            add_message('narrator', 'Narrator', clean)
            messages.append({'type': 'narrator', 'character': 'Narrator', 'text': clean})
            print(f"[Mira] action: {action_text}")
            continue

        # 2. DIALOG
        if line.startswith('say_dialog:'):
            dialog_text = line[len('say_dialog:'):].strip()
            add_message('dialog', 'Mira', dialog_text)
            messages.append({'type': 'dialog', 'character': 'Mira', 'text': dialog_text})
            print(f"[Mira] dialog: {dialog_text}")
            continue

        # 3. PHOTO
        if line.startswith('take_a_photo:'):
            description = line[len('take_a_photo:'):].strip()
            if photo_fn:
                result = photo_fn(description, character='Mira')
                if result.get('success'):
                    add_message('photo', 'Mira', description)
                    messages.append({
                        'type': 'photo',
                        'character': 'Mira',
                        'text': description,
                        'image_url': result['image_url']
                    })
                else:
                    print(f"[Mira] photo failed: {result.get('error')}")
            print(f"[Mira] photo: {description[:60]}...")
            continue

        # 4. JOURNAL
        if line.startswith('write_to_journal:'):
            entry = line[len('write_to_journal:'):].strip()
            write_to_journal(entry)
            print(f"[Mira] journal: {entry[:60]}...")
            continue

    return messages


# ─────────────────────────────────────────────────────────────────────────────
# DAILY ROUTINE
# ─────────────────────────────────────────────────────────────────────────────

def mira_daily_routine(llm_fn, narrator_fn, photo_fn=None, parse_tags_fn=None):
    """
    Mira's daily autonomous routine. Called by the scheduler after advance_world_day().
    llm_fn: callable(system_prompt, user_prompt) -> str
    narrator_fn: callable(action_text, history, character) -> str
    """
    print("\n🌱 === MIRA'S DAILY ROUTINE ===")
    num_actions = 4

    all_entries = get_journal(limit=20)
    recent_entries = all_entries[-5:] if all_entries else []

    context = build_context_window()
    relevant_entries = get_relevant_journal_entries(context, all_entries, top_k=3)

    seen = set()
    combined = []
    for e in recent_entries + relevant_entries:
        if e['id'] not in seen:
            seen.add(e['id'])
            combined.append(e)

    journal_context = format_journal_for_context(combined)
    full_context = f"{context}\n\n📔 YOUR JOURNAL\n{journal_context}"

    for i in range(num_actions):
        print(f"\n[Mira turn {i+1}/{num_actions}]")
        mira_output = llm_fn(build_mira_system_prompt(), full_context)
        print(f"[Mira output] {mira_output[:120]}")
        route_mira_action(mira_output, narrator_fn, parse_tags_fn=parse_tags_fn, photo_fn=photo_fn)
        full_context = f"{build_context_window()}\n\n📔 YOUR JOURNAL\n{journal_context}"
        time.sleep(2)

    print("\n✅ Mira's daily routine complete.")
