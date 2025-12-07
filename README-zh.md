# Atrioly · Wanatring —— 认知的信号掮客

> *Wanatring* 是 **Atrioly / 序栖** 品牌下的自治代理 (Autonomous Agent)。
> 它不仅仅是一个机器人，更是一位**数字掮客 (Digital Broker)**——负责过滤 Telegram 群组中的混沌噪声，提炼高价值信号：流媒体合租机会、租赁情报与可信的交互。
>
> [English Documentation](./README.md)

---

## 💠 核心愿景 (Core Vision)

在信息过载的时代，**Wanatring** 充当着认知过滤器的角色。它采用 **混合智能 (Hybrid Intelligence)** 架构来实现：
1.  **侦测 (Detect)**：高价值的流媒体合租机会（Netflix, Disney+, YouTube 等）。
2.  **防御 (Defend)**：利用双层免疫系统拦截垃圾信息、加密货币诈骗与无效噪声。
3.  **管理 (Manage)**：通过自然语言交互管理数字资产与提醒。

---

## 🧠 智能分层 (Intelligence Layers)

### 1. 会员雷达 (信号侦测)
代理持续监听特定群组。与简单的关键词搜索不同，它使用 **gpt-5-mini** 理解语境。
* **意图识别**：精准区分 *需求* ("求租 Netflix 车位") 与 *供应* ("有一个 Netflix 车位")。
* **数据提取**：自动将价格、平台及限制条件解析为结构化的“机会卡片”。
* **支持平台**：Netflix, Disney+, YouTube Premium, HBO Max, Prime Video, Apple TV+, Spotify。

### 2. Atrioly 护盾 (垃圾防御)
一套无情且高效的防御系统，旨在保护你的注意力。
* **第一层 (启发式)**：零延迟拦截明显的垃圾模式（加密货币诈骗、推广链接、NSFW 内容、全大写刷屏）。
* **第二层 (认知层)**：AI 深度分析模棱两可的消息，识别“隐形”的垃圾广告或无关噪声。
* **三振出局协议**：触发 AI 垃圾过滤器 3 次的用户将被 **永久拉黑 (UID Ban)**。其未来的消息将在中间件层级直接被丢弃，不再消耗任何资源。

---

## 📂 项目结构

本项目遵循适合扩展的模块化“面向服务”架构。

```text
AtriolyTgbot/
├── src/
│   ├── main.py                 # 应用程序入口
│   ├── config.py               # Pydantic 配置管理
│   ├── bot/
│   │   ├── handlers.py         # 守门人 (Gatekeeper) 与消息逻辑
│   │   └── commands.py         # 用户与管理员指令接口
│   └── services/
│       ├── ai_agent.py         # 统一 LLM 提示词 (垃圾判定 + 会员分析)
│       ├── safety.py           # 第一层启发式过滤器
│       ├── blacklist_manager.py# 基于 JSON 的持久化封禁管理
│       └── membership.py       # 订阅状态管理器
├── Dockerfile                  # 部署镜像
├── docker-compose.yml          # 容器编排
└── requirements.txt            # 依赖列表
````

-----

## 🚀 部署指南 (Docker)

**Wanatring** 设计为自托管运行（VPS, 树莓派或云服务器），以确保数据主权。

### 1\. 配置环境

在项目根目录创建 `.env` 文件：

```ini
# --- 凭证 ---
TELEGRAM_BOT_TOKEN=123456:ABC-YourTokenHere
OPENAI_API_KEY=sk-proj-YourOpenAIKey

# --- 访问控制 ---
# 你的 Telegram 数字 ID (可通过 @userinfobot 获取)
OWNER_IDS=123456789
# 接收合租情报提醒的 ID
FORWARD_TO=123456789

# --- 系统配置 ---
DEFAULT_MODEL=gpt-5-mini
LOG_LEVEL=INFO
```

### 2\. 启动服务

使用 Docker Compose 自动处理依赖与持久化存储。

```bash
docker-compose up -d --build
```

### 3\. 验证状态

检查日志以确保系统已上线：

```bash
docker-compose logs -f
```

-----

## 🕹 指令接口

| 指令 | 权限 | 说明 |
| :--- | :--- | :--- |
| `/start` | 公开 | 唤醒代理并检查连接状态。 |
| `/membership_sharing` | 公开 | 查看活跃的合租情报及当前追踪的订阅。 |
| `/status` | 公开 | 检查系统健康度及当前 AI 模型。 |
| `/ai_test <文本>` | 公开 | **诊断工具**：强制 AI 分析一段文本并显示 JSON 输出结果。 |
| `/blacklist <uid>` | **管理员** | 手动将某用户 ID 拉入系统黑名单。 |
| `/whitelist <uid>` | **管理员** | 解除某用户 ID 的封禁。 |
| `/help` | 公开 | 显示指令操作手册。 |

-----

## 🛡️ 反垃圾逻辑流

1.  **入站消息** → `gatekeeper_middleware` 检查黑名单数据库。
      * *若已封禁*：**丢弃 (DROP)** (结束)。
2.  **安全检查** → `safety.py` 运行正则规则。
      * *若匹配模式*：**丢弃 (DROP)** (结束)。
3.  **关联性触发** → 检查关键词（如 "Netflix", "合租"）。
      * *若无关*：**忽略 (IGNORE)**。
4.  **AI 分析** → `ai_agent.py` 发送至 gpt-5-mini。
      * *若是垃圾信息*：**警告用户 (WARN)** (打击数 +1)。若打击数 ≥ 3，**封禁 (BAN)**。
      * *若是有效合租*：**转发 (FORWARD)** 详细摘要给管理员。

-----

## 📜 许可与品牌

**Atrioly / 序栖** — *流动之声的几何学。*
本项目基于 **MIT 协议** 开源。

> “代码不仅是工具，更是数字生活的架构。”
