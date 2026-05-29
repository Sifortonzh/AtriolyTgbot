Atrioly · A quiet interface for modern life.  
序栖｜于纷扰人间，自置一隅静界。

# Atrioly · Wanatring —— 认知的信号掮客

> *Wanatring* 是 **Atrioly / 序栖** 品牌下的 Telegram 自治代理。  
> 它不仅仅是一个机器人，更是一位 **数字掮客（Digital Broker）**：负责过滤 Telegram 群组与私聊中的混沌噪声，提炼高价值信号，并为 Owner 提供一个轻量但完整的操作控制台。
>
> [English Documentation](./README.md)

---

## 💠 核心愿景（Core Vision）

在信息过载的时代，**Wanatring** 充当你的认知过滤器与个人控制台。它采用 **混合智能（Hybrid Intelligence）** 架构：

1. **侦测（Detect）**：识别高价值的流媒体合租机会，例如 Netflix、Disney+、YouTube Premium、HBO Max、Prime Video、Apple TV+、Spotify 等。
2. **防御（Defend）**：通过启发式规则与 AI 分析，拦截垃圾信息、诈骗、Crypto 引流、无效噪声与低可信消息。
3. **操作（Operate）**：在 Telegram 内完成私聊转发、Owner 回复、任务提醒、模式切换与运行时 AI Provider 切换。

Wanatring 面向真实自部署场景：足够轻，可以跑在普通 VPS 上；结构足够清晰，也可以逐步演化为个人数字基础设施的一部分。

---

## ✨ 当前版本亮点

近期版本已经从“可运行的 Bot”升级为更完整的 Telegram 操作台：

- **Inline Console**：`/start` 打开按钮式控制台，而不是只有普通文本提示。
- **运行时 AI Provider 切换**：Owner 可通过 `/ai_provider` 或按钮切换 OpenAI、DeepSeek、Claude 等 Provider。
- **无需重启 Docker**：切换 Provider 不修改 `.env`，也不需要重新构建容器。
- **运行时覆盖配置**：Provider 覆盖配置持久化到 `/app/data/ai_runtime.json`。
- **统一 Provider Router**：OpenAI、DeepSeek、Anthropic / Claude、OpenAI-compatible 共用同一套 AI 调用层。
- **结构化雷达输出**：`/probe <文本>` 会返回标准化的雷达分析结果，方便调试。
- **发信人主页链接**：转发 / 管理员报告中可附带可点击的发信人主页链接。
- **OpenAI-first 快速兜底**：默认优先使用 OpenAI；当前环境不可达时，按请求快速 fallback 到 DeepSeek。
- **中文广告硬拦截**：通过正则与多链接密度规则，优先拦截博彩、注册送、网广、推广等明显垃圾信息。
- **Admin Report Card 2.0**：群组雷达命中后，以可操作卡片转发给 Owner，支持查看发信人、黑名单、备注等按钮入口。
- **Private Service Desk 2.0**：非 Owner 私聊默认进入转发服务台，并向用户返回更温和的送达确认。

---

## 🧠 智能分层（Intelligence Layers）

### 1. 会员雷达（Membership Radar）

Wanatring 会监听指定 Telegram 群组，识别有价值的流媒体合租消息。它不是单纯依赖关键词，而是结合规则触发、AI 分类与 fallback 启发式判断。

- **意图识别**：区分“求 Netflix 车位”和“出一个 Netflix 车位”这类不同意图。
- **信息提取**：解析平台、价格、货币、地区、意图、风险分、置信度与摘要。
- **动作判断**：决定消息应该转发、忽略、警告，还是作为垃圾信息处理。

`/probe` 的输出结构类似：

```json
{
  "is_spam": false,
  "spam_reason": null,
  "is_membership": true,
  "intent": "offer",
  "platform": "Netflix",
  "price": 25,
  "currency": "CNY",
  "region": null,
  "risk_score": 35,
  "confidence": 0.7,
  "summary": "Netflix 车位还有一个，25 元一个月",
  "reason": "这是一条流媒体合租供应消息。",
  "action": "forward"
}
```

### 2. Atrioly Shield（反垃圾防线）

这是一套保护注意力的防御系统：

- **第一层：启发式过滤**：对明显的垃圾、诈骗、推广、可疑链接等进行零延迟拦截。
- **第二层：认知过滤**：对模棱两可的消息调用 AI 进行语义分析。
- **黑名单持久化**：被封禁的用户 ID 会保存在本地，并在中间件层直接丢弃，不再消耗后续资源。

### 3. Owner Task Console（个人任务控制台）

对于 Owner 来说，Wanatring 也可以作为一个轻量的生活管理代理。

它可以理解类似这样的自然语言：

```text
提醒我这周六下午 3 点考六级
帮我记一个 TODO：整理 Config4Streaming 的 README
```

任务数据会保存到本地，可通过 `/listall` 查看。目前任务层支持 Todo、Reminder、Special Day 与 Anniversary 等类型。

---

## 🪐 Telegram Inline Console

`/start` 会打开 Wanatring 控制台。

典型入口包括：

```text
📊 Status
🧠 AI Radar
⚙️ AI Provider
🎬 Membership
🗂 Tasks
🔁 Mode
🛡 Owner Tools
📖 Help
```

敏感控制项，例如 AI Provider 切换、Owner Tools、黑白名单等，应始终只对 `OWNER_IDS` 中配置的 Owner 开放。

---

## 🧬 运行时 AI Provider Router

Wanatring 支持多个 AI Provider，并通过统一路由层处理不同任务。

| Provider | 典型用途 | 必要配置 |
| --- | --- | --- |
| OpenAI | 默认通用 Provider | `OPENAI_API_KEY` |
| DeepSeek | 成本更低的 Chat / Radar 备选 | `DEEPSEEK_API_KEY` |
| Anthropic / Claude | Claude 模型族 | `ANTHROPIC_API_KEY` |
| OpenAI-compatible | 自定义代理或兼容端点 | API Key + Base URL + Model |

当前推荐的 OpenAI 配置：

```ini
AI_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
RADAR_MODEL=gpt-4o
PRIVATE_MODEL=gpt-4o
TASK_MODEL=gpt-4o
CHAT_MODEL=gpt-4o
VISION_MODEL=gpt-4o
```

Provider 是否可用取决于 API Key、账号状态、服务器网络与模型可用性。当前策略为 **OpenAI-first**：默认优先尝试 OpenAI；当当前服务器环境无法连接 OpenAI 时，会在本次请求内快速 fallback 到 DeepSeek，并在结果中保留 `_provider_used`、`_provider_fallback_used` 与 `_provider_failures` 等诊断字段。若所有 Provider 都不可用，部分雷达流程会退回到启发式 fallback 判断。

---

## 🔁 运行时覆盖配置

`.env` 是默认配置来源，而运行时切换会单独保存。

```text
/app/data/ai_runtime.json
```

重要行为：

- `/ai_provider` 修改的是运行时覆盖配置，不会改 `.env`。
- 切换 Provider 不需要重启 Docker。
- 清除运行时覆盖后，Bot 会回到 `.env` 默认配置。
- API Key 不会显示在 Telegram 消息里。
- `/app/data` 应作为持久化数据目录挂载。

这让你可以在 Telegram 里安全测试不同 Provider，同时保持部署配置稳定。

---

## 📨 私聊服务台（Private Service Desk）

Wanatring 可以充当私聊消息桥：

1. 非 Owner 用户私聊 Bot。
2. Wanatring 默认强制进入 **Forward / Service Desk** 流程，不会把普通用户误判为 Chat 模式。
3. Bot 对消息进行分析、分类或摘要，并生成私聊服务台卡片转发给 Owner。
4. 用户会收到送达确认，例如「消息已悄悄递给主人啦」。
5. Owner 在 Telegram 中直接回复被转发的消息。
6. Wanatring 将回复回传给原用户，Owner 的工作流仍然停留在 Telegram 内。

当 `ENABLE_SENDER_PROFILE_LINK=true` 时，转发 / 管理员报告中可以附带发信人的可点击主页链接。

- 有用户名的用户：使用 `https://t.me/{username}`。
- 没有用户名的用户：使用 `tg://user?id={user_id}`，具体表现取决于 Telegram 客户端支持。

当前私聊卡片支持：

```text
📨 Private Message
👤 Sender: clickable profile
🆔 User ID: xxx
🏷 Category: membership / support / billing / general / spam
🧠 Priority: normal / high / urgent
📝 Summary: ...
💬 Message: ...
```

卡片按钮包括：`↩️ Reply Guide`、`👁 View Sender`、`🚫 Blacklist`、`✅ Mark Resolved`。

---

## 📷 图像理解（Image Intelligence）

当配置了支持视觉能力的模型后，Wanatring 可以分析私聊中的图片。

典型流程：

- 下载图片；
- 调用 Vision 模型；
- 生成简短中文摘要；
- 判断风险等级，例如 `safe`、`sensitive`、`nsfw`；
- 在需要时将分析结果与原图转发给 Owner。

图像能力取决于当前 Provider 与模型是否支持 Vision。

---

## 📂 项目结构

```text
AtriolyTgbot/
├── src/
│   ├── main.py                  # 应用入口，注册 Handler 与调度器
│   ├── config.py                # Pydantic 配置、环境变量加载、运行时摘要
│   ├── bot/
│   │   ├── callbacks.py         # Inline Keyboard 渲染与回调路由
│   │   ├── commands.py          # Slash Command 指令接口
│   │   └── handlers.py          # 群组雷达、私聊服务台、转发桥、媒体流程
│   └── services/
│       ├── ai_agent.py          # Provider 无关的 AI 任务层
│       ├── ai_runtime.py        # 运行时 Provider 覆盖与有效模型解析
│       ├── safety.py            # 启发式反垃圾过滤器
│       ├── blacklist_manager.py # 基于 JSON 的封禁持久化
│       ├── membership.py        # 合租信号状态管理
│       ├── state_manager.py     # 用户 / 会话模式管理
│       ├── task_manager.py      # Todo、Reminder、Special Day、Anniversary
│       ├── scheduler.py         # APScheduler 定时任务
│       └── calendar_utils.py    # 日历工具函数
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── README-zh.md
└── data/                        # Docker 挂载的持久化运行数据
```

---

## 🚀 Docker 部署

Wanatring 面向 VPS 或类似服务器的自托管部署。

### 1. 准备 `.env`

复制示例配置文件，并填入自己的凭证。

```bash
cp .env.example .env
```

最低推荐配置：

```ini
TELEGRAM_BOT_TOKEN=123456:ABC-YourTokenHere
OWNER_IDS=123456789
FORWARD_TO=123456789

AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
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

不要提交 `.env`。

### 2. 启动服务

```bash
docker compose up -d --build
```

如果你的环境仍使用旧版 Compose 命令，也可以使用：

```bash
docker-compose up -d --build
```

### 3. 查看日志

```bash
docker compose logs -f --tail=120
```

正常情况下，日志会显示当前 Provider、模型、Owner 数量、数据目录与功能开关等运行时摘要。

### 4. 服务器更新

```bash
git pull origin main
docker compose up -d --build
docker compose logs -f --tail=120
```

如果服务器上存在本地 tracked 文件改动，导致无法 pull，先备份 `.env`，再重置 tracked 文件：

```bash
cp .env .env.backup.$(date +%Y%m%d-%H%M%S)
git reset --hard
git clean -fd
git pull origin main
docker compose up -d --build
```

---

## 🕹 指令接口（Commands）

| 指令 | 权限 | 说明 |
| :--- | :--- | :--- |
| `/start` | 公开 | 打开 Wanatring Inline Console。 |
| `/help` | 公开 | 查看帮助与可用指令。 |
| `/status` | 公开 | 查看运行状态、功能开关与 AI Provider 摘要。 |
| `/ping` | 公开 | 基础健康检查。 |
| `/membership_sharing` | 公开 | 查看合租记录与雷达信息。 |
| `/mode [chat\|forward]` | Owner / 依配置 | 切换 Chat / Forward 模式。 |
| `/probe <文本>` | Owner / 依配置 | 分析一条消息并返回结构化雷达结果。 |
| `/ai_test <文本>` | 兼容旧指令 | probe 类测试的兼容别名。 |
| `/ai_provider` | Owner only | 打开运行时 AI Provider 切换器。 |
| `/listall` | Owner only | 查看 Todo、Reminder、Special Day、Anniversary。 |
| `/blacklist <uid>` | Owner only | 将某个用户 ID 加入黑名单。 |
| `/whitelist <uid>` | Owner only | 从黑名单中移除某个用户 ID。 |

推荐的 BotFather 默认命令列表：

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

中文命令说明可使用：

```text
start - 打开 Wanatring 控制台
help - 查看帮助与可用命令
status - 查看系统状态与 AI 运行状态
probe - 测试一条消息的 AI 雷达判断
ai_provider - 切换 AI 提供商，仅限管理员
mode - 查看或切换机器人模式
membership_sharing - 查看流媒体合租雷达信息
listall - 查看待办、提醒与纪念日
ping - 检查机器人在线状态
```

---

## 🛡️ 反垃圾逻辑流

1. **入站消息** → 黑名单中间件检查发送者是否已被封禁。
2. **启发式安全检查** → 明显的垃圾、诈骗、推广、中文博彩广告、多链接网广内容会被提前丢弃。
3. **关联性触发** → 与会员 / 合租相关的消息进入雷达分析。
4. **AI 分析** → 模棱两可的消息交给当前 Provider 进行语义判断。
5. **动作执行** → 有效信号转发给 Owner，无效噪声忽略，垃圾内容警告或封禁。

---

## 🖼 截图

截图暂未提交，后续可补充：

```text
docs/screenshots/console-home.png
docs/screenshots/ai-provider-switcher.png
docs/screenshots/radar-alert.png
docs/screenshots/task-summary.png
```

---

## 🔐 安全说明

- 不要提交 `.env`、API Key、Bot Token、私人 Chat ID 或服务器凭证。
- 敏感功能必须由 `OWNER_IDS` 限制访问。
- 运行时 Provider 切换不会在 Telegram 中展示 API Key。
- 发信人主页链接由 `ENABLE_SENDER_PROFILE_LINK` 控制，可按需关闭。
- 外部 AI 能力取决于 Provider Key、模型可用性、服务器网络与服务商状态。
- 生产环境建议将运行数据持久化挂载到 `/app/data`。

---

## 🗺 Roadmap

- Reply Bridge 2.0：为 Owner 回复增加明确的送达确认与失败提示。
- Private Contact Memory：为私聊用户建立轻量联系人档案与历史记录。
- Quick Reply：为私聊服务台增加常用快捷回复按钮。
- Spam Log：记录最近被启发式规则拦截的广告与命中原因。
- Provider 诊断：更清晰地展示 OpenAI / DeepSeek 的连接状态、fallback 原因与耗时。
- Atrioly 操作台 Web Dashboard 或 Mini Admin Panel。
- 更完整的中英文控制台文案与截图文档。

---

## 📜 许可与品牌

**Atrioly / 序栖** — *Geometry of Flowing Voices.*  
本项目基于 **MIT License** 开源。

> “代码不仅是工具，更是数字生活的架构。”
