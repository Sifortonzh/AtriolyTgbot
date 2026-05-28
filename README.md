# Atrioly · Wanatring
[简体中文文档](./README-zh.md)

## Introduction

Atrioly · Wanatring is a self-hosted Telegram bot system designed for real operational scenarios rather than demo scripts. It integrates group radar detection, private message forwarding, owner task assistance, and runtime AI Provider switching into a unified Telegram console.

Wanatring is intended to be a compact personal operations layer: it watches noisy Telegram spaces, extracts useful signals, protects attention from spam, and gives the owner a controllable AI-powered workflow.

## Feature Overview

- Inline Console: `/start` opens a button-based control panel for Status, AI Radar, Membership, Tasks, Mode, Help, and Owner Tools.
- Runtime AI Provider Router: supports OpenAI, DeepSeek, Anthropic / Claude, and OpenAI-compatible providers.
- Switch Without Restart: the owner can switch Provider through `/ai_provider` or inline buttons without editing `.env` and without restarting Docker.
- Runtime Override Persistence: runtime override is written to `/app/data/ai_runtime.json`.
- Group Membership Radar: detects and forwards high-value streaming membership or shared-subscription messages.
- Structured Probe Output: `/probe <text>` returns a complete radar schema in JSON-like form for diagnostics.
- Owner Task Assistant: parses natural-language task instructions and manages owner-side tasks.
- Private Reply Bridge: user DMs are forwarded to the owner, and owner replies can be bridged back to the original user.
- Sender Profile Links: forwarded/admin messages can include clickable sender profile links when enabled.
- Owner Permission Boundary: sensitive operations are restricted to configured owner IDs.

## Architecture Overview

| Layer | Responsibility |
| --- | --- |
| `src/main.py` | Application startup, handler registration, scheduler startup |
| `src/config.py` | Environment variable loading and runtime-safe summaries |
| `src/bot/commands.py` | Slash command entry points |
| `src/bot/callbacks.py` | Inline Keyboard callback routing |
| `src/bot/handlers.py` | Group radar flow, private service desk flow, reply bridge |
| `src/services/ai_agent.py` | Unified AI task layer: radar, private analysis, chat, vision, task intent |
| `src/services/ai_runtime.py` | Runtime AI override storage and effective model resolution |
| `src/services/*` | Blacklist, state, membership, task persistence, and scheduler services |

## Quick Start

1. Clone the repository.
2. Create `.env` from `.env.example`.
3. Fill in the core configuration: `TELEGRAM_BOT_TOKEN`, `OWNER_IDS`, and Provider API keys.
4. Start with Docker Compose:

```bash
docker compose up -d --build
```

If your environment still uses the legacy Compose command:

```bash
docker-compose up -d --build
```

5. Check logs to confirm the service is online:

```bash
docker compose logs -f --tail=120
```

## `.env` Configuration

`.env` is the default configuration source and must never be committed to the repository.

Recommended minimal configuration:

```ini
TELEGRAM_BOT_TOKEN=
OWNER_IDS=123456789
FORWARD_TO=123456789

AI_PROVIDER=openai
OPENAI_API_KEY=
DEFAULT_MODEL=gpt-4o
RADAR_MODEL=gpt-4o
PRIVATE_MODEL=gpt-4o
TASK_MODEL=gpt-4o
CHAT_MODEL=gpt-4o
VISION_MODEL=gpt-4o

DATA_DIR=/app/data
LOG_LEVEL=INFO
ENABLE_SENDER_PROFILE_LINK=true
```

Notes:

- Provider availability depends on API key configuration, account status, model availability, and server network connectivity.
- `openai_compatible` requires an API key, a Base URL, and a compatible model name.
- Runtime Provider switching does not modify `.env`; it only writes a runtime override file.

## AI Provider Switching

The owner can switch the runtime Provider directly inside Telegram.

Entrypoints:

- Command: `/ai_provider`
- Console path: `/start` -> `⚙️ AI Provider`

Supported Providers:

- OpenAI
- DeepSeek
- Anthropic / Claude
- OpenAI-compatible

The Provider panel shows:

- Runtime Provider / Model
- Runtime Override status
- Default `.env` Provider
- Provider readiness

Switching Provider at runtime does not restart Docker and does not edit `.env`. If the override is cleared, Wanatring falls back to the default `.env` configuration.

## Runtime Override Mechanism

Runtime override file:

```text
/app/data/ai_runtime.json
```

Purpose:

- Override Provider and model selection while the bot is running.
- Preserve override state across container restarts when `/app/data` is mounted persistently.
- Keep `.env` as the stable deployment-level fallback.

Key behaviors:

- Does not modify `.env`.
- Does not trigger Docker restart.
- Can be cleared through the AI Provider console.
- Does not expose API keys in Telegram.

If no override exists, the system automatically uses `.env` defaults.

## Telegram Command List

| Command | Permission | Description |
| --- | --- | --- |
| `/start` | Public | Open the Inline Console home page |
| `/help` | Public | Show command help |
| `/status` | Public | Show runtime status and feature summary |
| `/ping` | Public | Health check |
| `/mode [chat\|forward]` | Public / per-user mode | Switch chat or forwarding mode |
| `/membership_sharing` | Public | View active membership records |
| `/probe <text>` | Owner or policy-controlled | Return the full radar analysis schema |
| `/ai_test <text>` | Same as probe policy | Legacy compatibility alias for `/probe` |
| `/ai_provider` | Owner only | Open the runtime Provider switcher |
| `/blacklist <uid>` | Owner only | Ban a user ID |
| `/whitelist <uid>` | Owner only | Unban a user ID |
| `/listall` | Owner only | Show task summary |

Recommended BotFather command list:

```text
start - Open Wanatring console
help - Show help and available commands
status - Show system status and AI runtime
probe - Test AI radar with one message
ai_provider - Switch AI provider, owner only
mode - View or switch bot mode
membership_sharing - Show streaming membership radar info
listall - Show tasks, reminders and anniversaries
ping - Check bot health
```

## Docker Deployment

Recommended production setup:

- Use `docker-compose.yml` to manage the service.
- Mount `/app/data` to persist runtime JSON data.
- Use Compose restart policies for availability.
- Keep `.env` outside version control.

Common operational checks:

```bash
docker compose ps
docker compose logs -f --tail=120
```

Typical update flow:

```bash
git pull origin main
docker compose up -d --build
docker compose logs -f --tail=120
```

If local tracked changes block `git pull`, back up `.env` first and then reset tracked files:

```bash
cp .env .env.backup.$(date +%Y%m%d-%H%M%S)
git reset --hard
git clean -fd
git pull origin main
docker compose up -d --build
```

## Screenshots Placeholder

- Console Home: `docs/screenshots/console-home.png`
- AI Provider Switcher: `docs/screenshots/ai-provider-switcher.png`
- Radar Alert Card: `docs/screenshots/radar-alert.png`
- Owner Task Summary: `docs/screenshots/task-summary.png`

## Security Notes

- Never commit `.env` or any real credentials.
- Never expose Telegram bot tokens, Provider API keys, server credentials, or private user IDs.
- Sensitive capabilities are Owner-only, including `/ai_provider`, blacklist/whitelist controls, and task overview controls.
- Runtime Provider switching does not expose API keys in Telegram messages.
- Sender profile links are controlled by `ENABLE_SENDER_PROFILE_LINK` and can be disabled when needed.
- External AI Provider availability depends on key permissions, network environment, model availability, and provider uptime.

## Roadmap

- Add Provider health and error-rate observability.
- Add a test/confirmation mode before applying Provider switching.
- Improve group governance strategy templates.
- Upgrade optional persistence backend from JSON to database storage.
- Expand Inline Console analytics views.
- Improve membership radar cards and owner reports.
- Add screenshot-backed documentation.

## License

MIT License.