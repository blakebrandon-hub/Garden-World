# 🌱 Garden World

**A cozy, text adventure about tending a garden in deep space.** In **Garden World**, you play as Rowan, a crewmate living aboard a small personal spacecraft alongside your companion Mira. There are no galaxy-ending threats, no intense combat, and no strict win states. Instead, the game is about sharing quiet moments, exploring your ship, and keeping your hydroponic garden alive.

Think *Studio Ghibli* meets *The Martian*.

---

## ✨ Features

- **🧠 Multi-Provider AI Architecture:** Play using your preferred AI ecosystem. Seamlessly switch between Google (Gemini), OpenAI (GPT), or Anthropic (Claude) via a simple configuration toggle in the backend.
- **🤝 Two-Player Dynamic:** Play as Rowan and Mira where Mira is brought to life by AI.
- **🌿 A Living, Breathing Garden:** Your plants aren't just set dressing — they're alive. Plant seeds, watch them sprout, and harvest them. But be careful: different plants have different watering schedules. If you forget to water your basil, it will wither and die.
- **☕ A Persistent World:** The ship remembers what you do. If you make tea in the Galley and leave your mug by the viewport on the Observation Deck, it will stay exactly where you left it until someone moves it.
- **🤖 An Invisible "Game Master" AI:** Type out your actions naturally (e.g., *"Rowan grabs the watering can and tends to the tomatoes"*). An AI narrator describes the world reacting to you, acting as an impartial observer that focuses on the physical details — hands in the dirt, condensation on a leaf, the hum of the ship. It never tells you how to feel; it just sets the scene.
- **📸 Memory Snapshots:** Share a beautiful, quiet moment? Use the photo system to take a "snapshot" of the scene. The AI will generate a cozy, cinematic image and save it permanently to the ship's Supabase-powered Scrapbook.

---

**Conversation Pipeline:**

| Trigger | Response Chain |
|---|---|
| Rowan performs an **action** | Narrator → Mira Action/Dialog → *(if Mira acts)* → Narrator |
| Rowan speaks **dialog** | Mira Action/Dialog → *(if Mira acts)* → Narrator |

**Daily Autonomous Routine:** In addition to reacting to Rowan, Mira takes **2–3 independent actions each day** — checking on plants, tidying the ship, or simply going about her life. These are triggered automatically at midnight alongside the world's daily advancement.

---

## 🌿 How to Play

Playing is as simple as typing what you want to do or say. The game engine works behind the scenes to track your inventory, your location on the ship, and the health of your garden.

- **Move around the ship:** Visit the Galley, Bridge, Engineering, Quarters, Observation Deck, Cargo Hold, Shuttle Bay, or the Garden.
- **Interact with everything:** Pick up tools, move objects, or just sit and watch the stars.
- **Tend the garden:** Water your plants before they get thirsty. Each plant species has its own watering schedule — neglect them and they'll wither.
- **Advance the clock:** Each new day makes your plants grow one stage — from Seed to Sprout to Leafing to Flowering to Fruit to Harvest. But it also means they get one day thirstier.

---

## 🛠️ Tech Stack

- **Backend:** Python 3, Flask, Flask-CORS
- **Database & Storage:** Supabase (tracks game state, item locations, plant health, and saves scrapbook photos)
- **AI Engine:** Google Gemini, OpenAI GPT, or Anthropic Claude — for natural language parsing, narrator responses, Mira's AI behavior, and scrapbook image generation
- **Scheduler:** APScheduler (runs daily world advancement and Mira's autonomous routine at midnight)

---

## 🚀 Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/blakebrandon-hub/garden-world.git
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Ensure `flask`, `flask-cors`, `google-genai`, `openai`, `anthropic`, `apscheduler`, and `supabase` are included.

3. **Configure your `.env` file:**
   ```bash
   # Choose one AI provider
   GEMINI_API_KEY="your_gemini_key_here"
   OPENAI_API_KEY="your_openai_key_here"
   ANTHROPIC_API_KEY="your_anthropic_key_here"

   # Supabase credentials
   SUPABASE_URL="your_supabase_url"
   SUPABASE_KEY="your_supabase_key"
   ```

4. **Set your active AI provider** by changing the `provider` variable at the top of `app.py` (e.g., `provider = "gemini"`).

5. **Run the server:**
   ```bash
   python app.py
   ```



<img width="2560" height="1440" alt="Garden World Screenshot" src="https://github.com/user-attachments/assets/1271b26c-3acd-4de1-a7a4-58028a944310" />
