# CDD Agent Tools Guide

**Updated**: 2025-11-07 (v0.0.3 development)

Your CDD Agent now has **10 professional tools** that enable Claude Code-level capabilities!

---

## 🔍 Search Tools

### glob_files
Find files matching glob patterns.

**Syntax:**
```python
glob_files(pattern: str, max_results: int = 100)
```

**Examples:**
```python
# Find all Python files
glob_files("**/*.py")

# Find all test files
glob_files("**/test_*.py")

# Find React components
glob_files("src/components/**/*.tsx")

# Find config files (limit to 10)
glob_files("**/*.{json,yaml,toml}", max_results=10)
```

**Features:**
- Recursive pattern matching (`**`)
- Respects `.gitignore` automatically
- Sorted by modification time (most recent first)
- Shows file size and relative time

---

### grep_files
Search for regex patterns across files.

**Syntax:**
```python
grep_files(pattern: str, file_pattern: str = "**/*", context_lines: int = 0, max_results: int = 100)
```

**Examples:**
```python
# Find all TODO comments
grep_files("TODO")

# Find class definitions in Python files
grep_files("class\\s+\\w+", "**/*.py")

# Find React imports with 2 lines of context
grep_files("import.*from 'react'", "**/*.tsx", context_lines=2)

# Find function definitions
grep_files("def\\s+\\w+\\(", "src/**/*.py")
```

**Features:**
- Full regex support
- File pattern filtering (glob)
- Context lines (before/after matches)
- Shows file:line for each match
- Skips binary files automatically

---

## ✏️ Edit Tools

### edit_file
Perform surgical edits (not full rewrites).

**Syntax:**
```python
edit_file(path: str, old_text: str, new_text: str)
```

**Examples:**
```python
# Change a config value
edit_file("config.py", "DEBUG = False", "DEBUG = True")

# Refactor a function
edit_file(
    "auth.py",
    "def login(username, password):\\n    pass",
    "def login(username: str, password: str) -> bool:\\n    return validate_credentials(username, password)"
)

# Update import
edit_file("main.py", "from auth import login", "from auth.core import login")
```

**Safety Features:**
- Text must exist in file (fails if not found)
- Text must be unique (fails if appears multiple times)
- Prevents accidental bulk replacements
- Shows line diff after edit

**Tip:** Use `read_file()` first to see exact content!

---

## 📊 Git Tools

### git_status
Show current repository status.

**Syntax:**
```python
git_status()
```

**Output:**
```
Git status:
M src/cdd_agent/tools.py
M ROADMAP.md
?? new_file.py
```

---

### git_diff
Show changes for a file or entire repository.

**Syntax:**
```python
git_diff(file_path: str = "")
```

**Examples:**
```python
# Diff entire repository
git_diff()

# Diff specific file
git_diff("src/cdd_agent/tools.py")
```

---

### git_log
Show recent commit history.

**Syntax:**
```python
git_log(max_commits: int = 10)
```

**Examples:**
```python
# Show last 10 commits (default)
git_log()

# Show last 5 commits
git_log(5)
```

**Output:**
```
Recent commits:
58b46be (HEAD -> master) feat: release v0.0.2
eb6f2e4 (tag: v0.0.1) feat: initial release
```

---

## 📁 Basic File Tools

### read_file
Read file contents.

```python
read_file("path/to/file.py")
```

### write_file
Write content to a file.

```python
write_file("path/to/file.py", content)
```

### list_files
List directory contents.

```python
list_files("src/")
```

---

## 🐚 Shell Tools

### run_bash
Execute shell commands.

```python
run_bash("pytest tests/")
```

**Security:** 30-second timeout, captures stdout/stderr

---

## 🎯 Real-World Workflows

### Workflow 1: Find and Fix TODOs

```python
# 1. Find all TODO comments
grep_files("TODO", "**/*.py")

# Output:
# src/auth.py:42
# > # TODO: Add rate limiting

# 2. Read the file
read_file("src/auth.py")

# 3. Fix the TODO
edit_file(
    "src/auth.py",
    "    # TODO: Add rate limiting\\n    pass",
    "    # Rate limiting implemented\\n    check_rate_limit(user)"
)

# 4. Verify changes
git_diff("src/auth.py")
```

---

### Workflow 2: Refactor Class Name

```python
# 1. Find all Python files
glob_files("**/*.py")

# 2. Find class definition
grep_files("class Agent", "**/*.py")

# Output: src/cdd_agent/agent.py:22

# 3. Find all imports
grep_files("from.*Agent", "**/*.py", context_lines=1)

# 4. Edit class definition
edit_file("src/cdd_agent/agent.py", "class Agent:", "class CddAgent:")

# 5. Edit imports
edit_file("src/cdd_agent/cli.py", "from .agent import Agent", "from .agent import CddAgent")

# 6. Check status
git_status()
git_diff()
```

---

### Workflow 3: Understand Project Structure

```python
# 1. Find all Python source files
glob_files("src/**/*.py")

# 2. Find all test files
glob_files("tests/**/*.py")

# 3. Find all documentation
glob_files("**/*.md")

# 4. Find main entry points
grep_files("if __name__ == '__main__'", "**/*.py")

# 5. Find CLI commands
grep_files("@cli\\.command", "**/*.py", context_lines=3)
```

---

## 🚀 Performance Tips

1. **Use specific patterns**: `src/**/*.py` is faster than `**/*.py`
2. **Limit results**: Add `max_results=10` for large searches
3. **Combine tools**: Use `glob` then `grep` for targeted searches
4. **Check git first**: Use `git_status()` to see what changed

---

## 🎨 Coming Soon (Phase 1, Week 2)

- **Tool approval system** (ask before destructive operations)
- **Security warnings** (dangerous commands highlighted)
- **Context loading** (auto-load CLAUDE.md)
- **Background bash** (long-running commands)

---

**Your agent is now production-ready for daily coding!** 🎉
