# Atrioly · Wanatring
面向生产环境的 Telegram 智能控制台，用于信号路由、内容治理与 Owner 运维。

[English Documentation](./README.md)

## 项目简介
Atrioly · Wanatring 是一套可自托管的 Telegram 机器人系统，目标是稳定服务真实运营场景，而非演示型脚本。系统将群组雷达识别、私聊转发服务台、Owner 任务助手与运行时 AI Provider 切换整合为统一控制台。

## 功能概览
- 内联控制台: `/start` 打开按钮式控制面板（状态、AI 雷达、会员、任务、模式、帮助、Owner 工具）。
- 运行时 AI Provider 路由: 支持 OpenAI、DeepSeek、Anthropic、OpenAI-compatible。
- 无重启切换: Owner 可通过 `/ai_provider` 或内联按钮切换 Provider，无需修改 `.env`，无需重启 Docker。
- 运行时覆盖持久化: 覆盖配置写入 `/app/data/ai_runtime.json`。
- 群组会员雷达: 识别并转发高价值合租/会员共享信息。
- 结构化探针输出: `/probe <text>` 返回完整雷达 Schema JSON。
- Owner 任务助手: 自然语言解析任务并执行任务管理流程。
- 私聊回复桥: 用户私信转发给 Owner，Owner 回复可桥接回原用户。
- 发送者资料链接: 在开启配置时，转发/管理消息中可带可点击的发送者链接。
- Owner 权限边界: 敏感操作仅对 Owner 开放。

## 架构概览
| 层 | 职责 |
| --- | --- |
| `src/main.py` | 应用启动、Handler 注册、调度器启动 |
| `src/config.py` | 环境变量加载与运行时摘要 |
| `src/bot/commands.py` | Slash 命令入口 |
| `src/bot/callbacks.py` | Inline Keyboard 回调路由 |
| `src/bot/handlers.py` | 群组雷达流程、私聊服务台流程、回复桥 |
| `src/services/ai_agent.py` | AI 任务统一层（雷达、私聊分析、聊天、视觉、任务意图） |
| `src/services/ai_runtime.py` | 运行时 AI 覆盖存储与生效模型解析 |
| `src/services/*` | 黑名单、状态、会员、任务持久化与调度 |

## 快速开始
1. 克隆仓库。
2. 由 `.env.example` 创建 `.env`。
3. 填写核心配置: `TELEGRAM_BOT_TOKEN`、`OWNER_IDS`、Provider API Key。
4. 使用 Docker Compose 启动:

```bash
docker-compose up -d --build
```

5. 查看日志确认服务在线:

```bash
docker-compose logs -f
```

## .env 配置说明
`.env` 是默认配置来源，且绝不能提交到仓库。

建议最小配置:

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
```

说明:
- Provider 是否可用取决于 API Key 配置与网络连通性。
- `openai_compatible` 需同时配置 API Key 与 Base URL。

## AI Provider 切换
Owner 可在 Telegram 内直接切换运行时 Provider:
- 命令入口: `/ai_provider`
- 控制台入口: `/start` -> `⚙️ AI Provider`

支持 Provider:
- OpenAI
- DeepSeek
- Anthropic / Claude
- OpenAI-compatible

Provider 页面展示:
- Runtime Provider / Model
- Runtime Override 是否生效
- `.env` 默认 Provider
- Provider Readiness

## 运行时覆盖机制
- 覆盖文件路径: `/app/data/ai_runtime.json`
- 作用: 在运行中覆盖 Provider 与模型选择。
- 关键行为:
  - 不修改 `.env`
  - 不触发 Docker 重启
  - 可通过 `Clear Runtime Override` 清除覆盖
- 若无覆盖文件，系统自动回退到 `.env` 默认配置。

## Telegram 命令清单
| 命令 | 权限 | 说明 |
| --- | --- | --- |
| `/start` | 公开 | 打开内联控制台主页 |
| `/help` | 公开 | 查看命令帮助 |
| `/status` | 公开 | 查看运行状态与功能摘要 |
| `/ping` | 公开 | 存活检查 |
| `/mode [chat|forward]` | 公开（按用户生效） | 切换聊天/转发模式 |
| `/membership_sharing` | 公开 | 查看活跃会员记录 |
| `/probe <text>` | Owner 或按策略限制 | 返回雷达分析完整 Schema |
| `/ai_test <text>` | 与 probe 同策略 | `/probe` 的兼容别名 |
| `/ai_provider` | Owner 专属 | 打开运行时 Provider 切换器 |
| `/blacklist <uid>` | Owner 专属 | 封禁指定用户 |
| `/whitelist <uid>` | Owner 专属 | 解除封禁 |
| `/listall` | Owner 专属 | 查看任务汇总 |

## Docker 部署说明
推荐生产方式:
- 使用 `docker-compose.yml` 管理服务
- 挂载 `/app/data` 持久化 JSON 数据
- 使用 Compose 的重启策略保障可用性

常用运维检查:

```bash
docker-compose ps
docker-compose logs -f
```

## 截图占位（Placeholder）
- 控制台首页: `docs/screenshots/console-home.png`
- AI Provider 切换页: `docs/screenshots/ai-provider-switcher.png`
- 雷达告警卡片: `docs/screenshots/radar-alert.png`
- 任务摘要页: `docs/screenshots/task-summary.png`

## 安全说明
- 严禁提交 `.env` 或任何真实密钥。
- 敏感能力均为 Owner-only（如 `/ai_provider`、黑白名单、任务总览控制）。
- 运行时切换不会在 Telegram 中暴露 API Key。
- 发送者资料链接受 `ENABLE_SENDER_PROFILE_LINK` 控制，可按需启用。
- 外部 AI Provider 可用性受密钥权限、网络环境与服务商状态影响。

## Roadmap
- 增加 Provider 健康度与错误率可观测面板。
- 增加 Provider 切换前的测试模式与确认流程。
- 提供更细粒度的群组治理策略模板。
- 可选持久化后端升级（JSON -> 数据库）。
- 扩展控制台内联分析视图。

## 许可证
MIT License。

# Atrioly · Wanatring

Production-grade Telegram intelligence console for signal routing, content governance, and owner operations.

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