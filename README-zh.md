Atrioly · A quiet interface for modern life.  
序栖｜于纷扰人间，自置一隅静界。

# Atrioly · Wanatring —— 认知的信号掮客

> *Wanatring* 是 **Atrioly / 序栖** 品牌下的自治代理（Autonomous Agent）。  
> 它不仅仅是一个机器人，更是一位 **数字掮客（Digital Broker）**——负责过滤 Telegram 群组与私聊中的混沌噪声，提炼高价值信号：流媒体合租机会、租赁情报、个人待办与可信的双向交互。
>
> [English Documentation](./README.md)

---

## 💠 核心愿景（Core Vision）

在信息过载的时代，**Wanatring** 充当你的认知过滤器与个人控制台。它采用 **混合智能（Hybrid Intelligence）** 架构来：

1. **侦测（Detect）**：识别高价值的流媒体合租机会（Netflix、Disney+、YouTube 等）。
2. **防御（Defend）**：通过双层免疫系统拦截垃圾信息、诈骗与无效噪声。
3. **管理（Manage）**：用自然语言管理你的 ToDo、提醒、特殊日与纪念日。

---

## 🧠 智能分层（Intelligence Layers）

### 1. 会员雷达（Signal Detection）

代理持续监听特定群组。与简单的关键词搜索不同，它使用 **gpt-5-mini** 理解语境：

- **意图识别**：区分 *需求*（“求 Netflix 车位”）与 *供应*（“出一个 Netflix 车位”）。
- **数据提取**：自动将价格、平台、名额、限制条件等解析为结构化的「机会卡片」。
- **支持平台**：Netflix、Disney+、YouTube Premium、HBO Max、Prime Video、Apple TV+、Spotify 等。

### 2. Atrioly 护盾（Spam Defense）

一套无情且高效的防御系统，用来保护你的注意力：

- **第一层（启发式）**：零延迟拦截明显垃圾模式（Crypto 骗局、推广链接、NSFW、全大写刷屏等）。
- **第二层（认知层）**：通过 AI 深度分析模棱两可的消息，识别伪装成正常聊天的营销 / 垃圾内容。
- **三振出局协议**：触发 AI 垃圾过滤器 ≥ 3 次的用户将被 **永久拉黑（UID Ban）**。后续消息在中间件层直接丢弃，不再消耗运算资源。

### 3. Owner Task Console（个人任务控制台）

对于 Owner 来说，Wanatring 变成一名可靠的 **生活管理代理（Personal Agent）**：

- 通过自然语言理解你的指令，例如：
  - “提醒我这周六下午 3 点考六级。”
  - “帮我记一个 TODO：整理 Config4Streaming 的 README。”
- 自动归类为：
  - **`todo`** —— 一般待办事项；
  - **`reminder`** —— 具有明确时间的一次性提醒；
  - **`days`** —— 特殊日 / 倒计时事件；
  - **`anniversary`** —— 每年重复的纪念日或重要日期。
- 所有任务以 JSON 的形式持久化到本地数据库，并由调度器负责触发：
  - Reminders：在事件时间前 **15 分钟（UTC+8）** 提醒；
  - Days / Anniversary：在当天 **07:00（UTC+8）** 发送一条问候与提醒。
- 使用 `/listall` 可以一次性查看所有 **Todo / Reminders / Special Days / Anniversaries**，按分组展示。

---

## 📨 私聊服务台（Private Service Desk）

Wanatring 在私聊中充当全功能的 **客户支持 / 私人管家**。

### 工作流

1. **用户私信**：当用户私聊机器人时，**AI 分类器** 会分析文本内容。
2. **标签标注**：为消息分配类别标签（如 `#billing`、`#membership`、`#support`），并生成一句话摘要。
3. **转发给 Owner**：处理后的消息会带着结构化抬头转发给 Owner。
4. **回复桥接**：Owner 只需在 Telegram 中 **回复** 这条转发消息，机器人会匿名把回复回传给原用户。

### 模式（`/mode`）

- **转发模式（Forward Mode，默认）**  
  - 普通用户消息 → 经过 AI 分析与标签 → 转发给 Owner。  
  - 适合 Owner 进行人工判断与操作，AI 主要做「分类 + 总结」。

- **聊天模式（Chat Mode）**  
  - **对 Owner 生效**：Owner 在私聊中可将 Wanatring 作为 AI 助手直接对话。  
  - 使用 `gpt-5-mini` 进行对话，支持 Markdown 排版（列表、粗体等）。  
  - 同时仍保留任务理解能力，可根据需要扩展为「边聊边记 ToDo」。

---

## 📷 图像理解（Image Intelligence）

Wanatring 能理解私聊中发送的图片：

- 对非 Owner 用户：
  - 机器人会下载图片并通过 **GPT-4o Vision** 流水线进行分析；
  - 生成：
    - 一段简短的中文摘要；
    - 风险等级：`safe` / `sensitive` / `nsfw`；
    - 2–3 个主题标签（在转发时渲染为 `#tag` 形式，如 `#screenshot`、`#contract`、`#ui`）；
  - 最终向 Owner 转发一条「图像分析抬头 + 原始图片」，并接入回复桥。

- 对 Owner 自己：
  - 行为可根据个人习惯扩展为「图片 → ToDo / Reminder」等（目前保持轻量，不做强制解析）。

---

## 📂 项目结构

本项目遵循适合扩展的模块化「面向服务」架构。

```text
AtriolyTgbot/
├── src/
│   ├── main.py                  # 应用入口，注册 Handler 与调度器
│   ├── config.py                # Pydantic 配置 & 环境变量加载
│   ├── bot/
│   │   ├── handlers.py          # 守门人、群组逻辑、私聊服务台、图像管线
│   │   └── commands.py          # 用户 & Owner 指令接口
│   └── services/
│       ├── ai_agent.py          # 统一 LLM 层（垃圾判定 / 合租分析 / 任务 / Chat / Vision）
│       ├── safety.py            # 第一层启发式过滤器
│       ├── blacklist_manager.py # 基于 JSON 的封禁管理
│       ├── membership.py        # 订阅状态管理器
│       ├── state_manager.py     # 用户模式（CHAT / FORWARD）与会话状态
│       ├── task_manager.py      # Todo / Reminder / Days / Anniversary 的 JSON 数据库
│       ├── scheduler.py         # APScheduler 调度器，负责定时任务
│       └── calendar_utils.py    # 农历与西方节日工具函数
├── Dockerfile                   # 容器构建文件
├── docker-compose.yml           # 服务编排
├── requirements.txt             # 依赖列表
└── data/                        # 持久化 JSON 数据（通过卷挂载）
```

---

## 🚀 部署指南（Docker）

**Wanatring** 被设计为自托管运行（VPS、树莓派或云服务器），以确保数据私有与可控。

### 1. 配置环境

在项目根目录创建 `.env` 文件：

```ini
# --- 凭证 ---
TELEGRAM_BOT_TOKEN=123456:ABC-YourTokenHere
OPENAI_API_KEY=sk-proj-YourOpenAIKey

# --- 访问控制 ---
# 你的 Telegram 数字 ID（可通过 @userinfobot 获取）
OWNER_IDS=123456789
# 接收合租 / 支持工单提醒的 ID（可为多个，逗号分隔）
FORWARD_TO=123456789

# --- 系统配置 ---
DEFAULT_MODEL=gpt-5-mini
LOG_LEVEL=INFO
# JSON 数据库存储路径（容器内路径）
DATA_DIR=/app/data
```

> ⚠️ 注意：`OWNER_IDS` 与 `FORWARD_TO` 采用逗号分隔的列表形式，例如：
> `OWNER_IDS=111111111,222222222`

### 2. 启动服务

使用 Docker Compose 自动处理依赖与持久化存储：

```bash
docker-compose up -d --build
```

### 3. 验证状态

检查日志以确保系统已正常运行：

```bash
docker-compose logs -f
```

---

## 🕹 指令接口（Commands）

| 指令 | 权限 | 说明 |
| :--- | :--- | :--- |
| `/start` | 公开 | 唤醒代理并展示简要状态信息。 |
| `/help` | 公开 | 显示指令帮助与使用说明。 |
| `/status` | 公开 | 查看系统健康状态、当前模式、使用模型与基础任务统计。 |
| `/membership_sharing` | 公开 | 查看当前捕捉到的合租机会与订阅概览。 |
| `/ai_test <文本>` | 公开 | **诊断工具**：强制 AI 分析一段文本并以 JSON 输出原始判定结果。 |
| `/mode [chat|forward]` | Owner | 切换 Chat / Forward 模式。 |
| `/listall` | Owner | 以分组形式列出所有 Todo、Reminders、Special Days 与 Anniversaries。 |
| `/blacklist <uid>` | Owner | 手动将某用户 ID 加入黑名单。 |
| `/whitelist <uid>` | Owner | 将某用户 ID 从黑名单中移除。 |

---

## 🛡️ 反垃圾逻辑流

1. **入站消息** → `gatekeeper_middleware` 检查黑名单数据库。  
   - *若已封禁* → **DROP**（结束）。
2. **安全检查** → `safety.py` 运行启发式正则规则。  
   - *若匹配明显垃圾模式* → **DROP**（结束）。
3. **关联性触发** → 检查是否包含与会员相关的关键词（如 "Netflix"、"Disney"、"车位"、"合租" 等）。  
   - *若无关* → **IGNORE**（忽略）。
4. **AI 深度分析** → `ai_agent.py` 调用 GPT-4o 系列模型进行语义判定。  
   - *若判定为垃圾* → **WARN 用户**（打击数 +1；≥3 次则 **BAN**）。  
   - *若判定为有效合租 / 重要信号* → 生成「机会卡片」并 **FORWARD** 给 Owner。

---

## 📜 许可与品牌

**Atrioly / 序栖** — *Geometry of Flowing Voices.*  
本项目基于 **MIT License** 开源。

> “代码不仅是工具，更是数字生活的架构。”
