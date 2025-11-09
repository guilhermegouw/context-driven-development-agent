# CDD Agent Implementation Plan: Socrates, Planner, Executor Agents

**Author:** Huyang  
**Date:** 2025-06-17  
**Status:** Design Proposal  
**Target:** Phase 2 - CDD Workflow Integration

---

## Executive Summary

This document outlines a comprehensive plan to implement the three core CDD agents (Socrates, Planner, Executor) in CDD Agent, bringing the structured Context-Driven Development workflow from the original POC into our LLM-agnostic terminal application.

## Vision

Transform CDD Agent from a generic coding assistant into a specialized development workflow tool that guides users through **Spec → Plan → Execute** while maintaining LLM provider freedom and terminal-first philosophy.

## Proposed Architecture

### CLI Commands Approach

```bash
cdd-agent socrates [ticket-path]     # Interactive spec generation
cdd-agent plan [ticket-path]         # Generate implementation plan  
cdd-agent exec [ticket-path]         # Execute implementation
```

### Code Structure

```
src/cdd_agent/
├── agents/
│   ├── __init__.py
│   ├── base.py          # BaseAgent class (shared functionality)
│   ├── socrates.py      # Socrates agent (spec generation)
│   ├── planner.py       # Planner agent (implementation planning)
│   └── executor.py      # Executor agent (implementation)
├── cli.py              # Extended with new commands
├── context.py          # Enhanced context loading
└── tools.py            # Existing tools (reused by agents)
```

## Implementation Phases

### Phase 1: Foundation (Week 1) - 12-15 hours

#### 1.1 BaseAgent Architecture
```python
# src/cdd_agent/agents/base.py
class BaseAgent:
    def __init__(self, provider_config, tool_registry, context_loader):
        self.provider_config = provider_config
        self.tool_registry = tool_registry
        self.context_loader = context_loader
        self.system_prompt = self.load_system_prompt()
        self.conversation_history = []
    
    def load_system_prompt(self):
        """Load persona-specific system prompt from markdown file"""
        pass
    
    def run_interactive(self, target_path):
        """Run interactive session for this agent"""
        pass
    
    def add_message(self, role, content):
        """Track conversation state"""
        self.conversation_history.append({"role": role, "content": content})
```

#### 1.2 CLI Integration
```python
# src/cdd_agent/cli.py (extend existing)

@cli.command()
@click.argument("ticket_path")
def socrates(ticket_path: str):
    """Interactive requirements gathering through Socratic dialogue"""
    # Agent instantiation and execution
    
@cli.command()
@click.argument("ticket_path")  
def plan(ticket_path: str):
    """Generate implementation plan from specification"""
    # Agent instantiation and execution
    
@cli.command()
@click.argument("ticket_path")
def exec(ticket_path: str):
    """Execute implementation from plan"""
    # Agent instantiation and execution
```

#### 1.3 System Prompt Loading
```python
def load_agent_prompt(agent_name: str) -> str:
    """Load agent persona from markdown file"""
    prompt_file = Path(".claude/commands") / f"{agent_name}.md"
    if prompt_file.exists():
        return extract_system_prompt(prompt_file)
    return get_builtin_prompt(agent_name)
```

### Phase 2: Socrates Agent (Week 2) - 15-18 hours

#### 2.1 SocratesAgent Implementation
- **Context Loading**: CLAUDE.md, existing spec, templates
- **Socratic Dialogue**: Progressive clarification, stay in scope
- **State Management**: Track what's clear vs. unclear
- **File Generation**: Complete spec.yaml with approval

#### 2.2 Key Features
- Intelligent context loading (CLAUDE.md → spec → templates → related work)
- Progressive questioning (acknowledge clarity, target vagueness)
- Scope enforcement (requirements only, no implementation)
- Complete summary before file writing

#### 2.3 Tool Access
```python
socrates_tools = [
    "read_file", "list_files", "glob_files", "grep_files"
]
```

### Phase 3: Planner Agent (Week 3) - 15-18 hours

#### 3.1 PlannerAgent Implementation
- **Spec Analysis**: Parse spec.yaml requirements
- **Codebase Analysis**: Pattern detection with depth limits
- **Autonomous Decisions**: 90% decisions from context, 1-3 questions max
- **Plan Generation**: Detailed, actionable implementation steps

#### 3.2 Pattern Analysis Strategy
```
Depth Limits (Strict):
- Maximum 10 files examined for pattern analysis
- Maximum 3 glob searches total
- Maximum 30 seconds for all codebase analysis
- Prioritize quality over quantity
```

#### 3.3 Tool Access
```python
planner_tools = [
    "read_file", "list_files", "glob_files", "grep_files",
    "git_status", "git_log"
]
```

### Phase 4: Executor Agent (Week 4) - 18-20 hours

#### 4.1 ExecutorAgent Implementation
- **Plan Execution**: Step-by-step implementation
- **Progress Tracking**: progress.yaml for resumability
- **Quality Gates**: Black, Ruff, pytest integration
- **Error Handling**: Interactive issue resolution

#### 4.2 Progress Management
```python
# progress.yaml structure
steps:
  - id: "step-1"
    description: "Create CLI command structure"
    status: "completed"
    started_at: "2025-06-17T10:00:00Z"
    completed_at: "2025-06-17T10:30:00Z"
    files_touched: ["src/cdd_agent/cli.py"]
  - id: "step-2"
    description: "Implement Agent base class"
    status: "in_progress"
    started_at: "2025-06-17T10:30:00Z"
    completed_at: null
    files_touched: []

acceptance_criteria:
  - criterion: "CLI commands accept correct arguments"
    status: "passed"
    validated_at: "2025-06-17T11:00:00Z"
```

#### 4.3 Tool Access
```python
executor_tools = registry.list_tools()  # All 16 tools
```

### Phase 5: Polish & Integration (Week 5) - 10-12 hours

#### 5.1 Slash Commands (Optional Enhancement)
```bash
cdd-agent chat
/socrates [ticket-path]    # Alias to CLI command
/plan [ticket-path]        # Alias to CLI command
/exec [ticket-path]        # Alias to CLI command
```

#### 5.2 Error Handling & Edge Cases
- Missing files (CLAUDE.md, spec.yaml, templates)
- Invalid ticket paths
- Permission issues
- Network failures

#### 5.3 Testing & Documentation
- Unit tests for each agent
- Integration tests for complete workflow
- User documentation and examples

## Why This Approach is Brilliant

### 1. **Leverages Existing Strengths**
- **Tool System**: Reuses 16 production tools
- **Provider Architecture**: Works with any LLM provider
- **Configuration System**: Existing settings management
- **Terminal UI**: Rich, beautiful interface

### 2. **Clean Separation of Concerns**
- **Socrates**: Requirements gathering specialist
- **Planner**: Architecture and implementation planning
- **Executor**: Code implementation and quality
- **BaseAgent**: Shared functionality

### 3. **Maintains CDD Agent Philosophy**
- **LLM-Agnostic**: Works with Anthropic, OpenAI, custom endpoints
- **Terminal-First**: Beautiful CLI experience
- **Local Control**: Configuration stays on user's machine
- **No Vendor Lock-in**: Freedom to choose LLM provider

### 4. **Practical Implementation Path**
- **Incremental**: Each phase delivers value
- **Testable**: Each agent can be unit tested
- **Extensible**: Easy to add new agents (Reviewer, Docs, etc.)
- **Backward Compatible**: Doesn't break existing functionality

### 5. **Addresses Original CDD Limitations**
- **Claude Code Dependency**: No longer requires Claude Code
- **Vendor Lock-in**: Works with any LLM provider
- **Installation**: Simple pip install vs complex setup
- **Portability**: Works anywhere Python runs

## Trade-offs and Considerations

### 1. **Development Complexity**
**Trade-off**: More complex than single-agent approach
**Mitigation**: 
- Clean architecture with BaseAgent
- Incremental implementation phases
- Comprehensive testing

### 2. **User Experience**
**Trade-off**: Less "magical" than Claude Code slash commands
**Mitigation**:
- CLI commands are familiar to developers
- Can add slash commands as aliases later
- Better discoverability and documentation

### 3. **Conversation State Management**
**Trade-off**: Must manually track conversation state
**Mitigation**:
- BaseAgent provides conversation tracking
- Context loading from existing infrastructure
- Progress files for persistence

### 4. **Performance Considerations**
**Trade-off**: Multiple agent instances vs single agent
**Mitigation**:
- Lazy loading of agent-specific components
- Efficient context caching
- Tool registry reuse

### 5. **Maintenance Overhead**
**Trade-off**: More code to maintain
**Mitigation**:
- Shared BaseAgent reduces duplication
- Clear interfaces and responsibilities
- Comprehensive test coverage

## Technical Challenges and Solutions

### 1. **File Access Restrictions**
**Challenge**: Agents can't directly read/write files like Claude Code
**Solution**: Use existing tool system with appropriate tool subsets per agent

### 2. **System Prompt Management**
**Challenge**: Loading complex personas from markdown files
**Solution**: Extract system prompts from original CDD command files

### 3. **Context Loading Complexity**
**Challenge**: Intelligent context loading across multiple sources
**Solution**: Enhance existing context.py with agent-specific logic

### 4. **Progress Persistence**
**Challenge**: Tracking implementation state across sessions
**Solution**: progress.yaml files with resumable execution

### 5. **Error Handling**
**Challenge**: Graceful handling of various failure modes
**Solution**: Comprehensive error handling with user guidance

## Success Metrics

### Phase 1 Success Criteria
- [ ] BaseAgent class implemented and tested
- [ ] CLI commands (socrates, plan, exec) added
- [ ] System prompt loading from markdown files
- [ ] Basic conversation state management

### Phase 2 Success Criteria
- [ ] SocratesAgent generates complete spec.yaml files
- [ ] Context loading works (CLAUDE.md → spec → templates)
- [ ] Socratic dialogue flows naturally
- [ ] Progressive clarification implemented

### Phase 3 Success Criteria
- [ ] PlannerAgent analyzes codebase with depth limits
- [ ] Autonomous decision making (90% decisions)
- [ ] Detailed plan.md generation
- [ ] Pattern analysis working

### Phase 4 Success Criteria
- [ ] ExecutorAgent implements code step-by-step
- [ ] Progress tracking with progress.yaml
- [ ] Quality gates (Black, Ruff, pytest)
- [ ] Interactive error handling

### Phase 5 Success Criteria
- [ ] Complete end-to-end workflow working
- [ ] Comprehensive test coverage (>80%)
- [ ] Documentation and examples
- [ ] Slash commands as aliases (optional)

## Resource Requirements

### Development Time
- **Phase 1**: 12-15 hours
- **Phase 2**: 15-18 hours  
- **Phase 3**: 15-18 hours
- **Phase 4**: 18-20 hours
- **Phase 5**: 10-12 hours
- **Total**: 70-83 hours (2-3 weeks)

### Dependencies
- Existing CDD Agent infrastructure
- Original CDD command files (.claude/commands/*.md)
- Standard Python development tools

### Testing Requirements
- Unit tests for each agent class
- Integration tests for complete workflows
- Mock LLM responses for reproducibility
- End-to-end testing with real workflows

## Conclusion

This implementation plan provides a clear path to bringing the structured CDD workflow to CDD Agent while maintaining our core advantages of LLM-agnostic architecture and terminal-first experience. The phased approach allows for incremental value delivery and risk mitigation.

The CLI commands approach is practical, testable, and extensible, providing a solid foundation for future enhancements while delivering immediate value to users seeking structured development workflows.

### Next Steps
1. **Review and approve** this implementation plan
2. **Begin Phase 1** with BaseAgent architecture
3. **Set up development environment** with original CDD command files
4. **Create project tracking** for implementation phases
5. **Start implementation** with Socrates agent

---

*This plan represents a significant step forward in making CDD Agent the premier LLM-agnostic development workflow tool while maintaining our commitment to user freedom and terminal excellence.*