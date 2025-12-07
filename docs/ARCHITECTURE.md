# CDD Agent Architecture

This document provides a visual overview of the CDD Agent architecture and explains how each component works together.

## High-Level Architecture

```mermaid
graph TB
    subgraph UI["User Interface Layer"]
        CLI["cli.py<br/>Click Commands"]
        TUI["tui.py<br/>Textual Split-Pane"]
        StreamUI["ui.py<br/>Rich Streaming"]
    end

    subgraph Slash["Slash Commands"]
        Socrates_Cmd["/socrates<br/>Refine"]
        Plan_Cmd["/plan<br/>Planning"]
        Exec_Cmd["/exec<br/>Execute"]
        New_Cmd["/new<br/>Ticket"]
        Init_Cmd["/init<br/>Project"]
        Help_Cmd["/help & /clear<br/>Utilities"]
    end

    subgraph Agents["Specialized Agents (LLM-powered)"]
        Socrates["SocratesAgent<br/>Refine specs via dialogue"]
        Planner["PlannerAgent<br/>Generate impl plans"]
        Executor["ExecutorAgent<br/>Autonomous coding"]
    end

    subgraph Mechanical["Mechanical Operations (No LLM)"]
        MechOps["mechanical/<br/>Templates & Scaffolding"]
        Writer["WriterAgent<br/>File I/O Helper"]
    end

    subgraph Core["Core Agent Loop"]
        Agent["agent.py<br/>Agentic Loop"]
    end

    subgraph Support["Support Systems"]
        Tools["tools.py<br/>Tool Registry"]
        Approval["approval.py<br/>Risk-based Approval"]
        Context["context.py<br/>Context Loading"]
        BG["background_executor.py<br/>Background Processes"]
    end

    subgraph Infra["Infrastructure Layer"]
        Config["config.py<br/>Settings & Providers"]
        Auth["auth.py<br/>API Key Setup"]
        OAuth["oauth.py<br/>OAuth 2.0 Flow"]
        Logging["logging.py<br/>Structured Logs"]
    end

    CLI --> TUI
    CLI --> StreamUI
    TUI --> Slash
    StreamUI --> Slash

    Socrates_Cmd --> Socrates
    Plan_Cmd --> Planner
    Exec_Cmd --> Executor
    New_Cmd --> MechOps
    Init_Cmd --> MechOps

    Socrates --> Agent
    Planner --> Agent
    Executor --> Agent
    Socrates --> Writer

    Agent --> Tools
    Agent --> Approval
    Agent --> Context
    Tools --> BG

    Agent --> Config
    Config --> Auth
    Auth --> OAuth
    Agent --> Logging
```

---

## The CDD Workflow

The core value proposition: **Spec → Plan → Execute**

```mermaid
flowchart LR
    subgraph Spec["1. SPECIFICATION"]
        S[Socrates Agent]
        S --> SR[Refined<br/>Requirements]
    end

    subgraph Plan["2. PLANNING"]
        P[Planner Agent]
        P --> PR[Implementation<br/>Plan]
    end

    subgraph Exec["3. EXECUTION"]
        E[Executor Agent]
        E --> ER[Working<br/>Code]
    end

    SR --> P
    PR --> E

    style Spec fill:#e1f5fe
    style Plan fill:#fff3e0
    style Exec fill:#e8f5e9
```

---

## Core Agent Loop

The agentic loop that powers all interactions:

```mermaid
flowchart TD
    Start([User Message]) --> LLM[Send to LLM<br/>with Tools]
    LLM --> Decision{Tool Use<br/>Needed?}

    Decision -->|No| Response([Final Response])
    Decision -->|Yes| Approve{Approval<br/>Required?}

    Approve -->|Auto-approved| Execute[Execute Tool]
    Approve -->|Ask User| UserApproval{User<br/>Approves?}

    UserApproval -->|Yes| Execute
    UserApproval -->|No| Reject[Tool Rejected]
    Reject --> LLM

    Execute --> Result[Tool Result]
    Result --> LLM

    style Start fill:#4caf50,color:#fff
    style Response fill:#2196f3,color:#fff
    style Execute fill:#ff9800,color:#fff
```

---

## Tool System

### Risk Levels

```mermaid
graph LR
    subgraph Safe["SAFE (Auto-approved)"]
        read_file[read_file]
        glob_files[glob_files]
        grep_files[grep_files]
        git_status[git_status]
    end

    subgraph Medium["MEDIUM (Ask in balanced)"]
        write_file[write_file]
        edit_file[edit_file]
    end

    subgraph High["HIGH (Always ask)"]
        run_bash[run_bash]
        run_bash_bg[run_bash_background]
    end

    style Safe fill:#c8e6c9
    style Medium fill:#fff9c4
    style High fill:#ffcdd2
```

### Background Execution

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant BG as Background Executor
    participant Process

    User->>Agent: "Run tests in background"
    Agent->>BG: run_bash_background("pytest")
    BG->>Process: Start process
    BG-->>Agent: process_id: "abc123"
    Agent-->>User: "Tests running (id: abc123)"

    Note over User,Agent: User continues chatting...

    User->>Agent: "Check test status"
    Agent->>BG: get_background_status("abc123")
    BG-->>Agent: status: "running", output: "..."
    Agent-->>User: "Tests still running..."

    User->>Agent: "Get test results"
    Agent->>BG: get_background_output("abc123")
    BG->>Process: Read stdout/stderr
    BG-->>Agent: Full output
    Agent-->>User: "Tests complete: 42 passed"
```

---

## Data Flow

```mermaid
flowchart TB
    subgraph Input["Input Sources"]
        CLI_Input[CLI Prompt]
        TUI_Input[TUI Chat]
    end

    subgraph Context["Context Loading"]
        Global["~/.cdd/CDD.md<br/>(Global)"]
        Project["./CDD.md<br/>(Project)"]
        System["System Prompt<br/>(Built-in)"]
    end

    subgraph Processing["Agent Processing"]
        Agent[Agent Loop]
        LLM[LLM Provider<br/>Anthropic/OpenAI/Custom]
        Tools[Tool Execution]
    end

    subgraph Output["Output"]
        Stream[Streaming Response]
        FileChanges[File Changes]
        BashOutput[Bash Output]
    end

    CLI_Input --> Agent
    TUI_Input --> Agent

    Global --> Agent
    Project --> Agent
    System --> Agent

    Agent <--> LLM
    Agent <--> Tools

    Agent --> Stream
    Tools --> FileChanges
    Tools --> BashOutput
```

---

## Configuration Hierarchy

```mermaid
graph TB
    subgraph Priority["Priority (Highest to Lowest)"]
        CLI["1. CLI Flags<br/>--provider, --model"]
        ENV["2. Environment Variables<br/>ANTHROPIC_API_KEY"]
        Settings["3. Settings File<br/>~/.cdd-agent/settings.json"]
        Defaults["4. Defaults<br/>anthropic, mid, balanced"]
    end

    CLI --> ENV --> Settings --> Defaults

    style CLI fill:#4caf50,color:#fff
    style ENV fill:#8bc34a,color:#fff
    style Settings fill:#cddc39
    style Defaults fill:#ffeb3b
```

---

## Component Breakdown

### User Interface Layer

| File | Purpose |
|------|---------|
| `cli.py` | Click-based CLI entry point. Commands: `chat`, `auth`, `tui` |
| `tui.py` | Textual-based split-pane chat interface |
| `ui.py` | Rich streaming output for simpler terminal interactions |

### Slash Commands (`slash_commands/`)

| Command | File | Uses | Purpose |
|---------|------|------|---------|
| `/socrates` | `socrates_command.py` | SocratesAgent | Refine requirements through dialogue |
| `/plan` | `plan_command.py` | PlannerAgent | Generate implementation plans |
| `/exec` | `exec_command.py` | ExecutorAgent | Execute autonomous coding |
| `/new` | `new_command.py` | mechanical/ | Create new tickets (templates) |
| `/init` | `init_command.py` | mechanical/ | Initialize project structure |
| `/help` | `help_command.py` | - | Show available commands |
| `/clear` | `clear_command.py` | - | Clear conversation history |

### Specialized Agents (`agents/`)

| Agent | Type | Purpose |
|-------|------|---------|
| `SocratesAgent` | LLM | Uses Socratic method to refine specs through questioning |
| `PlannerAgent` | LLM | Generates step-by-step implementation plans from specs |
| `ExecutorAgent` | LLM | Autonomously executes code changes using tools |
| `WriterAgent` | I/O Helper | Simple file persistence (no LLM), used by other agents |

### Mechanical Operations (`mechanical/`)

Template-based operations that don't require LLM interaction:

| Module | Purpose |
|--------|---------|
| `init.py` | Project scaffolding (creates CDD.md, directories, configs) |
| `new_ticket.py` | Create tickets/docs from templates |
| `templates/` | Markdown templates for tickets, plans, docs |

### Core Agent Loop (`agent.py`)

The heart of the system implementing the ReAct pattern:
1. **Reason**: LLM decides what to do
2. **Act**: Execute tool if needed
3. **Observe**: Feed result back
4. **Repeat**: Until task complete

### Tool System (`tools.py`)

| Tool | Risk Level | Purpose |
|------|------------|---------|
| `read_file` | SAFE | Read file contents |
| `write_file` | MEDIUM | Write/modify files |
| `run_bash` | HIGH | Execute shell commands |
| `glob_files` | SAFE | Pattern-based file search |
| `grep_files` | SAFE | Regex search in files |

### Infrastructure Layer

| File | Purpose |
|------|---------|
| `config.py` | Settings management, provider configs, model tiers |
| `auth.py` | Authentication setup, API key validation |
| `oauth.py` | OAuth flow for Claude Pro/Max plans |
| `approval.py` | Tool execution approval (paranoid/balanced/trusting) |
| `context.py` | Load project context from CDD.md/CLAUDE.md |
| `logging.py` | Structured logging system |

---

## Design Patterns

### 1. Provider Pattern
```mermaid
graph LR
    Agent[Agent] --> Provider{Provider Interface}
    Provider --> Anthropic[AnthropicProvider]
    Provider --> OpenAI[OpenAIProvider]
    Provider --> Custom[CustomProvider]
```

### 2. Tool Registry Pattern
Decorator-based registration with auto-schema generation.

### 3. Configuration-Driven Design
Settings file with environment variable overrides and model tier abstraction.

---

## See Also

- [README.md](../README.md) - Installation and usage
- [ROADMAP.md](Roadmaps/ROADMAP.md) - Development roadmap
- [TOOLS_GUIDE.md](guides/TOOLS_GUIDE.md) - Tool documentation
- [USER_GUIDE.md](../USER_GUIDE.md) - User guide
