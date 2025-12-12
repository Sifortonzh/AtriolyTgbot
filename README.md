# Atrioly · Wanatring — The Cognitive Signal Broker

> *Wanatring* is the autonomous agent under the **Atrioly / 序栖** brand.  
> It serves not merely as a bot, but as a **Digital Broker**—filtering the chaotic noise of Telegram groups and private chats to distill high‑value signals: streaming memberships, rental opportunities, personal reminders and trusted interactions.
>
> [中文文档 (Chinese Version)](./README-zh.md)

---

## 💠 Core Vision

In an era of information overload, **Wanatring** acts as a cognitive filter and personal console. It employs a **Hybrid Intelligence** architecture to:

1. **Detect** high‑value streaming membership opportunities (Netflix, Disney+, YouTube, etc.).
2. **Defend** against spam, crypto scams, and noise using a dual‑layer immune system.
3. **Manage** your digital life via natural language: todos, reminders, special days and anniversaries.

---

## 🧠 Intelligence Layers

### 1. Membership Radar (Signal Detection)

The Agent constantly monitors specific groups. Unlike simple keyword searchers, it uses **gpt‑5‑mini** to understand context.

- **Intent Recognition** – Distinguishes between a *request* (“I need a Netflix slot”) and an *offer* (“I have a Netflix slot”).
- **Data Extraction** – Automatically parses price, platform, and restrictions into a structured “Opportunity Card”.
- **Supported Platforms** – Netflix, Disney+, YouTube Premium, HBO Max, Prime Video, Apple TV+, Spotify.

### 2. Atrioly Shield (Spam Defense)

A ruthless, efficient defense system protecting your attention.

- **Layer 1 (Heuristic)** – Zero‑latency blocking of obvious patterns (crypto scams, referral links, NSFW, excessive caps).
- **Layer 2 (Cognitive)** – AI analysis of ambiguous messages to detect “hidden” spam or irrelevant noise.
- **Three‑Strike Protocol** – Users who trigger the AI spam filter 3 times are **permanently blacklisted** (UID ban). Their future messages are dropped at the middleware level, consuming zero resources.

### 3. Owner Task Console (Personal Agent)

For the owner, Wanatring becomes a private **life‑management agent**:

- Understands natural language such as “提醒我这周六下午 3 点考六级” and auto‑classifies it as:
  - `/todo` – general tasks.
  - `/reminder` – one‑off reminders with a precise time.
  - `/days` – special countdown days.
  - `/anniversary` – recurring anniversaries / meaningful dates.
- Persists tasks to a local JSON database and schedules notifications.
  - Reminders are fired **15 minutes before** the event time (UTC+8).
  - Special Days & Anniversaries are greeted at **07:00 (UTC+8)** on the day.
- Provides an overview via `/listall`, grouped by **Todos**, **Reminders**, **Special Days** and **Anniversaries**.

---

## 📨 Private Service Desk

Wanatring acts as a comprehensive **Customer Support Agent** for private chats.

### Workflow

1. **User DM** – When a user messages the bot privately, the **AI Classifier** analyzes the text.
2. **Tagging** – It assigns categories (e.g. `#billing`, `#membership`, `#support`) and generates a short summary.
3. **Forwarding** – The processed message is forwarded to the owner with a structured header.
4. **Reply Bridge** – The owner simply **replies** to the forwarded message in Telegram; the bot relays the reply back to the original user, keeping the owner identity hidden.

### Modes (`/mode`)

- **Forward Mode** (default) – Messages are forwarded to the owner for human handling (plus optional AI analysis).
- **Chat Mode** – For the owner only. The bot behaves as an AI chat assistant (powered by `gpt‑5‑mini`) while still keeping task understanding available.

---

## 📷 Image Intelligence

Wanatring can also understand images sent in private chats:

- Downloads the photo, runs it through an **AI Vision** pipeline (GPT‑4o family).
- Generates a **Chinese summary**, risk level (`safe` / `sensitive` / `nsfw`) and 2‑3 hashtag‑style tags (e.g. `#screenshot`, `#contract`, `#ui`).
- For non‑owners, forwards both the **analysis header** and the **original image** to the owner, attaching a reply bridge as with text messages.

---

## 📂 Project Structure

The project follows a modular “Service‑Oriented” architecture suitable for scaling.

```text
AtriolyTgbot/
├── src/
│   ├── main.py                 # Application entry point
│   ├── config.py               # Pydantic configuration & env loading
│   ├── bot/
│   │   ├── handlers.py         # Gatekeeper, group logic, private desk, image pipeline
│   │   └── commands.py         # User & owner command interface
│   └── services/
│       ├── ai_agent.py         # Unified LLM layer (spam, membership, tasks, chat, vision)
│       ├── safety.py           # Layer 1 heuristic filter
│       ├── blacklist_manager.py# JSON‑based ban persistence
│       ├── membership.py       # Subscription state manager
│       ├── state_manager.py    # Session / mode tracking (CHAT vs FORWARD)
│       ├── task_manager.py     # Todos, reminders, days & anniversaries (JSON DB)
│       ├── scheduler.py        # APScheduler integration for timed jobs
│       └── calendar_utils.py   # Holiday & calendar helpers (lunar + western)
├── Dockerfile                  # Deployment image
├── docker-compose.yml          # Orchestration
├── requirements.txt            # Dependencies
└── data/                       # Persistent JSON data (mounted volume)
```

---

## 🚀 Deployment (Docker)

**Wanatring** is designed to be self‑hosted (VPS, Raspberry Pi, or cloud) to ensure data sovereignty.

### 1. Configuration

Create a `.env` file in the root directory:

```ini
# --- Credentials ---
TELEGRAM_BOT_TOKEN=123456:ABC-YourTokenHere
OPENAI_API_KEY=sk-proj-YourOpenAIKey

# --- Access Control ---
# Your numeric Telegram ID(s), comma‑separated
OWNER_IDS=123456789
# Who receives membership / support alerts? (comma‑separated chat IDs)
FORWARD_TO=123456789

# --- System ---
DEFAULT_MODEL=gpt-5-mini
LOG_LEVEL=INFO
# Optional: where to store JSON DB & logs inside the container
DATA_DIR=/app/data
```

### 2. Launch

Run with Docker Compose to handle dependencies and persistence automatically.

```bash
docker-compose up -d --build
```

### 3. Verification

Check the logs to ensure the system is online:

```bash
docker-compose logs -f
```

---

## 🕹 Command Interface

| Command | Permission | Description |
| :------ | :--------- | :---------- |
| `/start` | Public | Wake the agent and show a short status banner. |
| `/help` | Public | Show the command manual. |
| `/status` | Public | Check system health, current mode and model, and basic DB stats. |
| `/membership_sharing` | Public | View active membership offers and tracked subscriptions. |
| `/ai_test <text>` | Public | **Diagnostic tool** – force the AI to analyze arbitrary text and show the JSON output. |
| `/mode [chat\|forward]` | **Owner** | Switch between AI chat mode and pure forwarding mode. |
| `/listall` | **Owner** | List all stored **Todos**, **Reminders**, **Special Days** and **Anniversaries** in a single grouped view. |
| `/blacklist <uid>` | **Owner** | Manually ban a user ID from the system. |
| `/whitelist <uid>` | **Owner** | Unban a user ID. |

---

## 🛡️ Anti‑Spam Logic Flow

1. **Incoming Message** → `gatekeeper_middleware` checks the blacklist DB.  
   - *If banned* → **DROP** (end).
2. **Safety Check** → `safety.py` runs regex rules.  
   - *If pattern match* → **DROP** (end).
3. **Relevance Trigger** → Checks for membership‑related keywords (e.g. “Netflix”, “车位”, “合租”).  
   - *If irrelevant* → **IGNORE**.
4. **AI Analysis** → `ai_agent.py` sends to `gpt‑4o` for deeper inspection.  
   - *If spam* → **WARN USER** (strike +1). If strike ≥ 3, **BAN**.  
   - *If valid membership* → **FORWARD** a detailed opportunity card to the owner.

---

## 📜 License & Brand

**Atrioly / 序栖** — *Geometry of Flowing Voices.*  
This project is open‑source under the **MIT License**.

> “Code is not just utility; it is the architecture of one’s digital life.”
