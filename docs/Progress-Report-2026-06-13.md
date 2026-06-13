# Egregore 进度报告

**日期**: 2026-06-13
**仓库**: https://github.com/KuaaMU/egregore
**分支**: main (4 commits)

---

## 一、项目定位

```
Egregore = Browser Runtime + Collective Intelligence Engine
```

不是 ChatGPT Clone，是 Collective Intelligence Platform。
当前阶段聚焦 Browser Runtime（V0.5），暂停 Consensus/Debate/Memory。

---

## 二、技术栈

| 层 | 技术 |
|---|------|
| Backend | Python 3.13, FastAPI, asyncio, uv |
| Browser | Playwright (persistent contexts) |
| Frontend | Next.js 16, TypeScript, TailwindCSS |
| CI | GitHub Actions (lint + typecheck + test + build) |

---

## 三、架构总览

```
┌─────────────────────────────────────────────────────┐
│              Collective Intelligence                  │
│     (Round Table → Consensus → Debate → Memory)      │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│            Application Layer                          │
│  ┌──────────────┐  ┌──────────────┐                  │
│  │ Orchestrator  │  │  Event Bus   │                  │
│  └──────┬───────┘  └──────────────┘                  │
└─────────┼────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────┐
│              Domain Layer (zero infra deps)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Transport │ │Provider  │ │ Health   │ │ Session  │ │
│  │ (Port)   │ │ (Port)   │ │(StateMch)│ │ (State)  │ │
│  └────┬─────┘ └──────────┘ └──────────┘ └──────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │StreamEvent│ │Locator   │ │Capability│              │
│  │(13 types)│ │ (Chain)  │ │ (Trait)  │              │
│  └──────────┘ └──────────┘ └──────────┘              │
└─────────┬────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────┐
│         Infrastructure Layer                           │
│                                                       │
│  ┌─────────────────────────────────────────────┐      │
│  │          Browser Runtime                     │      │
│  │  ChromiumRuntime → SessionManager → Pools    │      │
│  │  LocatorResolver → Parsers → HealthMonitor   │      │
│  │  RecoveryManager (escalation-based)          │      │
│  └─────────────────────────────────────────────┘      │
│                                                       │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ BrowserTransport │  │  API Transport   │          │
│  │ (Playwright)     │  │  (httpx/openai)  │          │
│  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │
│  ┌────────▼─────────────────────▼────────┐            │
│  │        BrowserProviderAdapter          │            │
│  │  (BrowserTransport → BaseProvider)     │            │
│  └───────────────────────────────────────┘            │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  OpenAI  │  │ Anthropic│  │  Mock    │            │
│  │ (API)    │  │  (API)   │  │ Adapter  │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└───────────────────────────────────────────────────────┘
```

---

## 四、已完成模块清单

### 4.1 Domain Layer（零基础设施依赖）

| 文件 | 核心类型 | 用途 |
|------|---------|------|
| `domain/transport/base.py` | `BaseTransport` | Port: send() → AsyncIterator[StreamEvent] |
| `domain/providers/base.py` | `BaseProvider` | Port: complete()/stream() → Message |
| `domain/executor/events.py` | `StreamEvent`, `StreamEventType` (13 types) | 事件驱动流式生命周期 |
| `domain/executor/locator.py` | `LocatorChain`, `LocatorDef`, `LocatorStrategy` | 集中化选择器模型，带 fallback |
| `domain/executor/capabilities.py` | `Capabilities` | 能力模型：streaming/thinking/vision/tool_use/artifacts |
| `domain/health/types.py` | `HealthStatus` (9 states), `ProviderHealth` | 健康状态机 |
| `domain/session/types.py` | `SessionState` (9 states), `SessionInfo` | 会话生命周期 |
| `domain/entities/message.py` | `Message`, `Conversation`, `ProviderMeta` | 核心实体（frozen Pydantic） |
| `domain/events/bus.py` | `EventBus`, `Event`, `EventType` | 异步 pub/sub 事件总线 |
| `domain/providers/registry.py` | `ProviderRegistry` | Provider 生命周期管理 |

### 4.2 Infrastructure Layer — Browser Runtime

| 文件 | 核心类型 | 用途 |
|------|---------|------|
| `browser/runtime/chromium.py` | `ChromiumRuntime` | Playwright 生命周期，persistent contexts |
| `browser/sessions/manager.py` | `SessionManager`, `Session` | 长驻会话管理 |
| `browser/locators/chatgpt.py` | LocatorChain 定义 | ChatGPT 集中化选择器（9 组） |
| `browser/locators/claude.py` | LocatorChain 定义 | Claude 集中化选择器（7 组） |
| `browser/locators/resolver.py` | `LocatorResolver` | LocatorChain → Playwright Locator |
| `browser/parsers/base.py` | `BaseParser`, `ParsedContent` | Parser port |
| `browser/parsers/markdown.py` | `MarkdownParser` | 从 DOM 提取 markdown |
| `browser/parsers/thinking.py` | `ThinkingParser` | 提取 thinking/reasoning 块 |
| `browser/health/monitor.py` | `HealthMonitor` | 周期性健康检查 + 状态机 |
| `browser/recovery/manager.py` | `RecoveryManager`, `RecoveryLevel` | 恢复升级：refresh→reopen→recreate→restart |

### 4.3 Infrastructure Layer — Transport

| 文件 | 核心类型 | 用途 |
|------|---------|------|
| `transport/browser.py` | `BrowserTransport` | 抽象浏览器传输（Template Method） |
| `transport/chatgpt_browser.py` | `ChatGPTBrowserTransport` | ChatGPT 具体实现 |
| `transport/provider_adapter.py` | `BrowserProviderAdapter` | BrowserTransport → BaseProvider 桥接 |
| `providers/openai_provider.py` | `OpenAIProvider` | OpenAI API adapter |
| `providers/anthropic_provider.py` | `AnthropicProvider` | Anthropic API adapter |
| `providers/mock.py` | `MockProvider` | 测试用 mock |

### 4.4 Application Layer

| 文件 | 核心类型 | 用途 |
|------|---------|------|
| `orchestrators/round_table.py` | `RoundTableOrchestrator` | 并行分发到所有 providers |

### 4.5 API Layer

| 文件 | 核心类型 | 用途 |
|------|---------|------|
| `api/app.py` | `create_app()` | Composition Root，依赖注入 |
| `api/routers/chat.py` | `/api/chat/round-table` | REST endpoint |
| `api/schemas/chat.py` | `ChatRequest`, `ChatResponse` | DTO |

### 4.6 Frontend

| 文件 | 用途 |
|------|------|
| `components/ConversationSidebar.tsx` | 左栏：对话历史 |
| `components/RoundTableView.tsx` | 中栏：输入 + 共识 + 响应卡片 |
| `components/ProviderPanel.tsx` | 右栏：Provider 详情 |
| `types/index.ts` | TypeScript 类型 |

---

## 五、关键设计决策

### 5.1 Transport 抽象

```
Provider → Transport → Runtime → BrowserContext
```

Provider 不知道底层是 Browser 还是 API。Transport 可以热替换。

### 5.2 事件流（不是请求-响应）

```python
async for event in transport.send(prompt):
    match event.type:
        case StreamEventType.THINKING_TOKEN: ...
        case StreamEventType.ANSWER_TOKEN: ...
        case StreamEventType.TOOL_CALL: ...
        case StreamEventType.COMPLETED: ...
```

13 种事件类型，支持 thinking/answer/tool 三阶段。

### 5.3 能力模型（不是 Provider 身份）

```python
# 不是
class ChatGPTExecutor: ...

# 而是
Capabilities = {
    streaming: bool,
    thinking: bool,
    vision: bool,
    tool_use: bool,
    artifacts: bool,
    web_search: bool,
    ...
}
```

### 5.4 健康状态机

```
UNKNOWN ⚪
    ↓
READY 🟢 ↔ BUSY 🟡
    ↓
THROTTLED 🟠 / RATE_LIMITED 🟠 / AUTH_EXPIRED 🔐
    ↓
RECOVERING 🔄 → READY 🟢
    ↓
OFFLINE 🔴 → RECOVERING 🔄 → READY 🟢
    ↓
FAILED ❌ → RECOVERING 🔄
```

关键保证：**每个状态都有回到 READY 的路径**（BFS 验证）。

### 5.5 恢复升级

```
Page Refresh (最便宜)
    ↓ 失败
Reopen Page
    ↓ 失败
Recreate Context
    ↓ 失败
Restart Browser (最昂贵)
```

每级尝试后再升级。

### 5.6 Locator Chain

```python
SEND_BUTTON = LocatorChain(locators=[
    LocatorDef(ROLE, "button", name="Send"),          # 最稳定
    LocatorDef(ARIA, "[aria-label='Send message']"),
    LocatorDef(TESTID, "[data-testid='send-button']"),
    LocatorDef(TEXT, "Send"),
    LocatorDef(CSS, ".send-btn"),                     # 最脆弱
])
```

UI 变化时自动 fallback。

### 5.7 Parser 按能力分类（不是按平台）

```python
# 不是
chatgpt_parser.py, claude_parser.py

# 而是
MarkdownParser   — 所有平台通用
ThinkingParser   — 有 thinking 能力的平台
ArtifactParser   — 有 artifacts 能力的平台
```

---

## 六、测试覆盖

```
tests/
├── test_round_table.py          # 3 tests — orchestrator
├── test_browser_runtime.py      # 36 tests — domain models + capabilities
└── chaos/
    ├── test_health_state_machine.py  # 14 tests — 状态机完整性
    └── test_recovery.py              # 11 tests — 恢复路径 + 流中断

Total: 64 tests, 0.58s
```

### Chaos 测试覆盖

| 场景 | 测试 |
|------|------|
| 所有合法状态转换 | ✅ 验证 VALID_TRANSITIONS |
| 所有非法状态转换被拒绝 | ✅ 全对组合测试 |
| 无自环 | ✅ 没有状态→自身 |
| 恢复路径始终存在 | ✅ BFS 验证每个状态→READY |
| 终态约束 | ✅ FAILED 只能→RECOVERING |
| 恢复升级顺序 | ✅ refresh→reopen→recreate→restart |
| Stream 中断类型 | ✅ ERROR/CANCELLED/TIMEOUT |
| 事件不可变性 | ✅ frozen Pydantic |

---

## 七、文件结构

```
Egregore/
├── .github/workflows/ci.yml
├── README.md
├── docs/
│   ├── Architecture.md
│   ├── Roadmap.md
│   ├── Progress-Report-2026-06-13.md
│   └── ADR/
│       ├── ADR-001-hexagonal-architecture.md
│       └── ADR-002-browser-runtime-first.md
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/egregore/
│   │   ├── domain/
│   │   │   ├── entities/message.py
│   │   │   ├── providers/base.py, registry.py
│   │   │   ├── transport/base.py
│   │   │   ├── executor/events.py, locator.py, capabilities.py
│   │   │   ├── health/types.py
│   │   │   ├── session/types.py
│   │   │   └── events/bus.py
│   │   ├── application/
│   │   │   └── orchestrators/round_table.py
│   │   ├── infrastructure/
│   │   │   ├── browser/
│   │   │   │   ├── runtime/chromium.py
│   │   │   │   ├── sessions/manager.py
│   │   │   │   ├── locators/chatgpt.py, claude.py, resolver.py
│   │   │   │   ├── parsers/base.py, markdown.py, thinking.py
│   │   │   │   ├── health/monitor.py
│   │   │   │   └── recovery/manager.py
│   │   │   ├── transport/
│   │   │   │   ├── browser.py
│   │   │   │   ├── chatgpt_browser.py
│   │   │   │   └── provider_adapter.py
│   │   │   └── providers/
│   │   │       ├── openai_provider.py
│   │   │       ├── anthropic_provider.py
│   │   │       └── mock.py
│   │   ├── api/
│   │   │   ├── app.py
│   │   │   ├── routers/chat.py
│   │   │   └── schemas/chat.py
│   │   └── config/settings.py
│   └── tests/
│       ├── test_round_table.py
│       ├── test_browser_runtime.py
│       └── chaos/
│           ├── test_health_state_machine.py
│           └── test_recovery.py
└── frontend/
    └── src/
        ├── app/layout.tsx, page.tsx
        ├── components/
        │   ├── ConversationSidebar.tsx
        │   ├── RoundTableView.tsx
        │   └── ProviderPanel.tsx
        └── types/index.ts
```

---

## 八、Git 提交历史

```
23657c6  refactor(V0.5): five corrections from reliability review
78b702c  feat(V0.5): Browser Runtime infrastructure layer
c224ebb  feat: add CI workflow and orchestrator tests
ee0a6f4  feat: initial Egregore project scaffolding
```

---

## 九、设计模式使用

| Pattern | 位置 | 原因 |
|---------|------|------|
| Hexagonal Architecture | 全局 | Provider 可热替换 |
| Strategy | BaseTransport | Browser/API/Mock 传输切换 |
| Template Method | BrowserTransport | 子类提供平台特定步骤 |
| Chain of Responsibility | LocatorChain | UI 变化时自动 fallback |
| State Machine | HealthStatus, SessionState | 防止非法状态转换 |
| Escalation | RecoveryManager | 便宜修复先试 |
| Adapter | BrowserProviderAdapter | 事件流 ↔ Message 桥接 |
| Event Stream | StreamEvent generator | 实时、可组合、可取消 |
| Capability | Capabilities | 按能力分类，不是按平台 |
| Repository | LocatorRepository | 集中化选择器 |
| Composition Root | create_app() | 唯一知道所有具体类型的地方 |
| DTO | API schemas | API 契约独立于领域 |

---

## 十、当前状态 & 下一步

### 当前状态

- ✅ 架构骨架完整
- ✅ Domain 层零依赖
- ✅ Browser Runtime 基础设施就绪
- ✅ ChatGPT BrowserTransport 第一个实现
- ✅ 64 测试全通过
- ⚠️ 尚未对真实 ChatGPT UI 测试

### 下一步（按优先级）

1. **安装 Playwright Chromium** — `playwright install chromium`
2. **真实 ChatGPT 测试** — 验证 locators 是否匹配当前 UI
3. **证明可靠性** — 一个 provider 运行 7 天，成功率 >99%
4. **Claude BrowserTransport** — 第二个实现证明模式可复用
5. **前端健康仪表盘** — 🟢🟡🔴 状态显示

### 核心原则

> **Stop adding providers. Start proving reliability.**
>
> Provider 数量不产生护城河。可靠性才是护城河。
