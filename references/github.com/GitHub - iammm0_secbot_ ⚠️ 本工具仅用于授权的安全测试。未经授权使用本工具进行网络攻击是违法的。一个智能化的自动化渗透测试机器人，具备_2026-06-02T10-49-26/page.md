# GitHub - iammm0/secbot: ⚠️ 本工具仅用于授权的安全测试。未经授权使用本工具进行网络攻击是违法的。一个智能化的自动化渗透测试机器人，具备AI驱动的安全测试能力。

> 来源: https://github.com/iammm0/secbot

---

[![npm version](images/img_000.svg)](https://www.npmjs.com/package/@opensec/secbot)
[![npm downloads](images/img_001.svg)](https://www.npmjs.com/package/@opensec/secbot)
[![Node.js](images/img_002.svg)](https://nodejs.org/)
[![License](images/img_003.svg)](https://github.com/iammm0/secbot/blob/release/LICENSE)


Secbot is an AI-powered TypeScript security automation workspace with a NestJS backend and an Ink-based terminal UI.


> Security notice: this package is for authorized security testing, research, and education only. Do not run scans or exploitation tasks against targets without explicit permission.


[*[图片未能下载: Secbot main UI]*](https://raw.githubusercontent.com/iammm0/secbot/main-ts-version/assets/secbot-main.png)


- End-to-end TypeScript architecture (`NestJS + Ink + SQLite`).
- `secbot` binary that starts terminal UI with local spawned backend by default.
- `secbot-server` binary for backend-only API scenarios.
- `secbot-mcp` binary that exposes Secbot tools as a stdio MCP server.
- Shared skills management across REST, TUI slash commands, CLI subcommands, and internal tools.
- Multi-agent orchestration with planning, tool execution, MCP bridging, and summarization.
- Built-in security tool modules for web, network, OSINT, defense, and reporting workflows.


From the repository checkout, `ChatService` routes each turn through **`IntentRouter`** (single LLM classify), optionally **`ExploreAgent`** (ReAct with `vuln_db_query` / `browser_session`, no sensitive tools), then **`ContextAssemblerService`** + **`ContextStore`** under a per-model context budget. SSE events include `intent_decision`, `explore_*`, and **`context_usage`** for the TUI token meter. **`task_simple`** skips the planner; **`SummaryAgent`** runs only when `needs_report` is true. Contributor-oriented details live in **[`CLAUDE.md`](https://github.com/iammm0/secbot/blob/release/CLAUDE.md)**; longer user docs: [`README_CN.md`](https://github.com/iammm0/secbot/blob/release/README_CN.md) / [`README_EN.md`](https://github.com/iammm0/secbot/blob/release/README_EN.md).


- Node.js `>= 24`
- npm `>= 10` (recommended)
- Optional: Ollama for local model serving


```
npm install -g @opensec/secbot
```


```
npx @opensec/secbot
```


Create a `.env` file in your working directory:


```
# Cloud model backend (recommended)
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_MODEL=deepseek-chat

# Optional local backend (Ollama)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.2

# Optional: explore iterations, context debug SSE, adaptive replan, NVD rate limits
# SECBOT_EXPLORE_MAX_ITERS=12
# SECBOT_CONTEXT_DEBUG=1
# SECBOT_ADAPTIVE_REPLAN=false
# NVD_API_KEY=your-nvd-key
```


```
secbot
```


```
secbot-server
```


```
secbot-mcp
```


Set `SECBOT_MCP_ALLOW_SENSITIVE=true` only when you intentionally want MCP clients to see sensitive tools.


```
# Recommended explicit service mode
SECBOT_TUI_BACKEND=service SECBOT_API_URL=http://127.0.0.1:8000 secbot

# Backward-compatible alias
SECBOT_TUI_BACKEND=remote SECBOT_API_URL=http://127.0.0.1:8000 secbot
```


| Binary | Description || --- | --- |


| `secbot` | Start terminal UI (default: spawn local backend; optional service mode) |

| `secbot-server` | Start NestJS backend only |

| `secbot-mcp` | Expose Secbot tools through stdio MCP |


Secbot now exposes one shared skills layer for product and automation surfaces.


```
/skills
/skill <name>
/create-skill <name> [--description ...] [--trigger ...] [--tag ...] [--prerequisite ...] [--author ...]

```


```
secbot skills list
secbot skills view <name>
secbot skills create <name> --description "..." --trigger recon --tag web
```


```
GET  /api/skills
GET  /api/skills/:name
POST /api/skills

```


Created skills are scaffolded under `skills/custom/<slug>/SKILL.md` and can also be reached through the internal `list_skills`, `get_skill`, and `create_skill` tools.


Secbot supports MCP in both directions.


```
secbot-mcp
```


This exposes the current `ToolsService` catalog over stdio MCP. Sensitive tools stay hidden by default unless `SECBOT_MCP_ALLOW_SENSITIVE=true` is set.


Use the built-in `mcp_call` tool to connect to another stdio MCP server, list its tools, or invoke one of them from Secbot workflows.


```
git clone https://github.com/iammm0/secbot.git
cd secbot
npm ci

# Backend dev
npm run dev

# Backend dev with file watching
npm run dev:watch

# TUI (in another terminal, default: spawn local backend)
npm run start:tui

# TUI service mode (connect existing backend only)
SECBOT_TUI_BACKEND=service SECBOT_API_URL=http://127.0.0.1:8000 npm run start:tui
```


| Script | Description || --- | --- |


| `npm run build` | Build the NestJS backend |

| `npm run build:terminal-ui` | Build the Ink terminal UI |

| `npm run build:web` | Build the web frontend bundle |

| `npm run typecheck` | Type-check server code |

| `npm run lint` | Run ESLint |

| `npm run format:check` | Check Prettier formatting |

| `npm test` | Run tests |

| `npm run release:pack` | Build and create npm package tarball |

| `npm run release:verify` | Verify packaged npm release contents |


- **[CLAUDE.md](https://github.com/iammm0/secbot/blob/release/CLAUDE.md)** — contributor / AI coding agent guide (orchestration, SSE, env vars)
- [Quickstart](https://github.com/iammm0/secbot/blob/main-ts-version/docs/QUICKSTART.md)
- [API Reference](https://github.com/iammm0/secbot/blob/main-ts-version/docs/API.md)
- [LLM Providers](https://github.com/iammm0/secbot/blob/main-ts-version/docs/LLM_PROVIDERS.md)
- [Ollama Setup](https://github.com/iammm0/secbot/blob/main-ts-version/docs/OLLAMA_SETUP.md)
- [UI Interaction Design](https://github.com/iammm0/secbot/blob/main-ts-version/docs/UI-DESIGN-AND-INTERACTION.md)
- [Tool Extension](https://github.com/iammm0/secbot/blob/main-ts-version/docs/TOOL_EXTENSION.md)
- [Release Guide](https://github.com/iammm0/secbot/blob/main-ts-version/docs/RELEASE.md)
- [Security Warning](https://github.com/iammm0/secbot/blob/main-ts-version/docs/SECURITY_WARNING.md)


- npm: https://www.npmjs.com/package/@opensec/secbot
- GitHub Packages: https://github.com/iammm0/secbot/packages
- Repository: https://github.com/iammm0/secbot
- Issues: https://github.com/iammm0/secbot/issues


This project is licensed under MIT. See [LICENSE](https://github.com/iammm0/secbot/blob/release/LICENSE) for details.