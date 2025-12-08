# Atrioly · Wanatring — The Cognitive Signal Broker

> *Wanatring* is the autonomous agent under the **Atrioly / 序栖** brand.
> It serves not merely as a bot, but as a **Digital Broker**—filtering the chaotic noise of telegram groups to distill high-value signals: streaming memberships, rental opportunities, and trusted interactions.
>
> [中文文档 (Chinese Version)](./README-zh.md)

---

## 💠 Core Vision

In an era of information overload, **Wanatring** acts as a cognitive filter. It employs a **Hybrid Intelligence** architecture to:
1.  **Detect** high-value streaming membership opportunities (Netflix, Disney+, YouTube).
2.  **Defend** against spam, crypto scams, and noise using a dual-layer immune system.
3.  **Manage** digital assets via natural language interaction.

---

## 🧠 Intelligence Layers

### 1. The Membership Radar (Signal Detection)
The Agent constantly monitors specific groups. Unlike simple keyword searchers, it uses **gpt-5-mini** to understand context.
* **Intent Recognition**: Distinguishes between a *request* ("I need a Netflix slot") and an *offer* ("I have a Netflix slot").
* **Data Extraction**: Automatically parses price, platform, and restrictions into a structured "Opportunity Card."
* **Supported Platforms**: Netflix, Disney+, YouTube Premium, HBO Max, Prime Video, Apple TV+, Spotify.

### 2. Atrioly Shield (Spam Defense)
A ruthless, efficient defense system protecting your attention.
* **Layer 1 (Heuristic)**: Zero-latency blocking of obvious patterns (crypto scams, referral links, NSFW, excessive caps).
* **Layer 2 (Cognitive)**: AI analysis of ambiguous messages to detect "hidden" spam or irrelevant noise.
* **Three-Strike Protocol**: Users who trigger the AI spam filter 3 times are **permanently blacklisted** (UID Ban). Their future messages are dropped at the middleware level, consuming zero resources.

---

## 📂 Project Structure

The project follows a modular "Service-Oriented" architecture suitable for scaling.

```text
AtriolyTgbot/
├── src/
│   ├── main.py                 # Application Entry Point
│   ├── config.py               # Pydantic Configuration
│   ├── bot/
│   │   ├── handlers.py         # The Gatekeeper & Message Logic
│   │   └── commands.py         # User & Admin Command Interface
│   └── services/
│       ├── ai_agent.py         # Unified LLM Prompt (Spam + Membership)
│       ├── safety.py           # Layer 1 Heuristic Filter
│       ├── blacklist_manager.py# JSON-based Ban persistence
│       └── membership.py       # Subscription State Manager
├── Dockerfile                  # Deployment Image
├── docker-compose.yml          # Orchestration
└── requirements.txt            # Dependencies
````

-----

## 🚀 Deployment (Docker)

**Wanatring** is designed to be self-hosted (VPS, Raspberry Pi, or Cloud) to ensure data sovereignty.

### 1\. Configuration

Create a `.env` file in the root directory:

```ini
# --- Credentials ---
TELEGRAM_BOT_TOKEN=123456:ABC-YourTokenHere
OPENAI_API_KEY=sk-proj-YourOpenAIKey

# --- Access Control ---
# Your numeric Telegram ID (get from @userinfobot)
OWNER_IDS=[123456789]
# Who receives the membership alerts?
FORWARD_TO=[123456789]

# --- System ---
DEFAULT_MODEL=gpt-5-mini
LOG_LEVEL=INFO
```

### 2\. Launch

Run with Docker Compose to handle dependencies and persistence automatically.

```bash
docker-compose up -d --build
```

### 3\. Verification

Check the logs to ensure the system is online:

```bash
docker-compose logs -f
```

-----

## 🕹 Command Interface

| Command | Permission | Description |
| :--- | :--- | :--- |
| `/start` | Public | Wake the agent and check connection. |
| `/membership_sharing` | Public | View active membership offers and tracked subscriptions. |
| `/status` | Public | Check system health and current AI model. |
| `/ai_test <text>` | Public | **Diagnostic Tool**: Force the AI to analyze a text string and show the JSON output. |
| `/blacklist <uid>` | **Admin** | Manually ban a user ID from the system. |
| `/whitelist <uid>` | **Admin** | Unban a user ID. |
| `/help` | Public | Show the command manual. |

-----

## 🛡️ Anti-Spam Logic Flow

1.  **Incoming Message** → `gatekeeper_middleware` checks Blacklist DB.
      * *If Banned*: **DROP** (End).
2.  **Safety Check** → `safety.py` runs Regex rules.
      * *If Pattern Match*: **DROP** (End).
3.  **Relevance Trigger** → Checks for keywords (e.g., "Netflix", "Share").
      * *If Irrelevant*: **IGNORE**.
4.  **AI Analysis** → `ai_agent.py` sends to GPT-4o.
      * *If Spam*: **WARN USER** (Strike +1). If Strike ≥ 3, **BAN**.
      * *If Valid Membership*: **FORWARD** detailed summary to Admin.

-----

## 📜 License & Brand

**Atrioly / 序栖** — *Geometry of Flowing Voices.*
This project is open-source under the **MIT License**.

> "Code is not just utility; it is the architecture of one's digital life."
