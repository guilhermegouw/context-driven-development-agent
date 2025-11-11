# Task 2: Port `create_new_ticket()` and `create_new_documentation()` from CDD POC

**Estimated Time:** 2 hours
**Status:** Planning Complete, Ready to Implement
**Prerequisites:** Task 1 complete ✅

---

## Overview

Port the ticket and documentation creation functions from CDD POC to CDD Agent. These functions create structured files from templates for the CDD workflow.

**Source:** `/home/guilherme/code/context-driven-documentation/src/cddoc/new_ticket.py`
**Destination:** `/home/guilherme/code/cdd-agent-cli/src/cdd_agent/mechanical/new_ticket.py`

---

## Key Changes from CDD POC

### 1. Simplified for English-Only (For Now)

**CDD POC:**
```python
# Language-aware template loading
template_path = git_root / ".cdd" / "templates" / f"{language}-{ticket_type}-ticket-template.yaml"
```

**CDD Agent (v0.2.0):**
```python
# English-only (templates have no language prefix)
template_path = git_root / ".cdd" / "templates" / f"{ticket_type}-ticket-template.yaml"
```

### 2. Same Core Functionality

- ✅ Name normalization ("User Auth" → "user-auth")
- ✅ Git root detection
- ✅ Template validation
- ✅ Overwrite prompts
- ✅ Date population ([auto-generated])
- ✅ Ticket types: feature, bug, spike, enhancement
- ✅ Documentation types: guide, feature

### 3. No Major Architectural Changes

Most functions can be ported directly with minimal modifications.

---

## Functions to Port

From CDD POC `new_ticket.py`, port these functions:

### Core Functions (8 functions)

1. ✅ **`normalize_ticket_name(name: str) -> str`**
   - **Status:** Port unchanged
   - Converts any string to lowercase-with-dashes
   - Examples: "User Auth" → "user-auth", "payment_processing" → "payment-processing"

2. ✅ **`get_git_root() -> Path`**
   - **Status:** Port unchanged
   - Finds git repository root
   - Raises TicketCreationError if not in git repo

3. ✅ **`get_template_path(git_root: Path, ticket_type: str) -> Path`**
   - **Status:** Minor modification
   - Locates ticket template file
   - **Change:** No language parameter (English-only)

4. ✅ **`populate_template_dates(template_content: str) -> str`**
   - **Status:** Port unchanged
   - Replaces [auto-generated] with current date
   - Format: YYYY-MM-DD

5. ✅ **`check_ticket_exists(ticket_path: Path) -> bool`**
   - **Status:** Port unchanged
   - Checks if ticket directory already exists

6. ✅ **`prompt_overwrite() -> bool`**
   - **Status:** Port unchanged
   - Asks user to confirm overwrite
   - Safe default: 'n' (don't overwrite)

7. ✅ **`prompt_new_name(ticket_type: str) -> str | None`**
   - **Status:** Port unchanged
   - Prompts for alternative name
   - Allows cancellation

8. ✅ **`create_ticket_file(ticket_path: Path, template_path: Path)`**
   - **Status:** Port unchanged
   - Creates directory and spec.yaml from template
   - Populates dates

### Main Functions (2 functions)

9. ✅ **`create_new_ticket(ticket_type: str, name: str) -> dict`**
   - **Status:** Minor modification
   - Main orchestration for ticket creation
   - **Change:** No language parameter
   - Returns: `{ticket_path, normalized_name, ticket_type, overwritten}`

10. ✅ **`create_new_documentation(doc_type: str, name: str) -> dict`**
    - **Status:** Minor modification
    - Main orchestration for documentation creation
    - **Change:** No language parameter
    - Returns: `{file_path, normalized_name, doc_type, overwritten}`

### Documentation Functions (3 functions)

11. ✅ **`get_documentation_directory(git_root: Path, doc_type: str) -> Path`**
    - **Status:** Port unchanged
    - Returns docs/guides/ or docs/features/

12. ✅ **`get_documentation_template_path(git_root: Path, doc_type: str) -> Path`**
    - **Status:** Minor modification
    - Locates documentation template
    - **Change:** No language parameter

13. ✅ **`create_documentation_file(file_path: Path, template_path: Path)`**
    - **Status:** Port unchanged
    - Creates markdown file from template
    - **Note:** No date population for docs (they're living documents)

### Exception Class

14. ✅ **`TicketCreationError`**
    - **Status:** Port unchanged
    - Custom exception for ticket creation failures

---

## Implementation Details

### File Structure Created

#### Tickets:
```python
def create_new_ticket(ticket_type: str, name: str) -> dict:
    """
    Input:  create_new_ticket("feature", "User Auth")
    Output: specs/tickets/feature-user-auth/spec.yaml

    Folder naming: {type}-{normalized-name}
    Examples:
      - feature-user-auth
      - bug-login-error
      - spike-oauth-research
      - enhancement-improve-performance
    """
```

#### Documentation:
```python
def create_new_documentation(doc_type: str, name: str) -> dict:
    """
    Input:  create_new_documentation("guide", "Getting Started")
    Output: docs/guides/getting-started.md

    Input:  create_new_documentation("feature", "Authentication")
    Output: docs/features/authentication.md

    File naming: {normalized-name}.md (no type prefix)
    """
```

---

## Name Normalization Algorithm

```python
def normalize_ticket_name(name: str) -> str:
    """
    1. Convert to lowercase
    2. Replace spaces, underscores, special chars with dashes
    3. Remove duplicate consecutive dashes
    4. Strip leading/trailing dashes

    Examples:
      "User Auth System"    → "user-auth-system"
      "payment_processing"  → "payment-processing"
      "Feature__Name"       → "feature-name"
      "  dash-test  "       → "dash-test"
      "user@auth!"          → "user-auth"
      ""                    → "" (invalid, will error)
    """
    # Convert to lowercase
    normalized = name.lower()

    # Replace special characters and whitespace with dash
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)

    # Remove duplicate dashes
    normalized = re.sub(r"-+", "-", normalized)

    # Strip leading/trailing dashes
    normalized = normalized.strip("-")

    return normalized
```

---

## Template Date Population

```python
def populate_template_dates(template_content: str) -> str:
    """
    Replaces [auto-generated] with current date.

    Template example (feature-ticket-template.yaml):
      created: [auto-generated]
      updated: [auto-generated]

    Result:
      created: 2025-11-09
      updated: 2025-11-09
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    return template_content.replace("[auto-generated]", current_date)
```

**Note:** Documentation templates do NOT use date population (docs are living, continuously updated).

---

## Overwrite Handling Flow

```python
def create_new_ticket(ticket_type: str, name: str) -> dict:
    normalized_name = normalize_ticket_name(name)
    ticket_path = git_root / "specs" / "tickets" / f"{ticket_type}-{normalized_name}"

    overwritten = False

    # Loop until we have a valid path
    while check_ticket_exists(ticket_path):
        console.print(f"⚠️  Ticket already exists: {ticket_path}")

        if prompt_overwrite():  # "Overwrite? [y/N]"
            overwritten = True
            break  # Use this path, overwrite
        else:
            # Prompt for new name
            new_name = prompt_new_name(ticket_type)

            if new_name is None:  # User cancelled
                raise TicketCreationError("Ticket creation cancelled by user")

            # Re-normalize and try again
            normalized_name = normalize_ticket_name(new_name)

            if not normalized_name:  # Empty after normalization
                console.print("[red]❌ Invalid name - must contain alphanumeric[/red]")
                continue  # Try again

            # Update path and loop
            ticket_path = git_root / "specs" / "tickets" / f"{ticket_type}-{normalized_name}"

    # Create the ticket
    create_ticket_file(ticket_path, template_path)

    return {
        "ticket_path": ticket_path,
        "normalized_name": normalized_name,
        "ticket_type": ticket_type,
        "overwritten": overwritten
    }
```

---

## Return Values

### `create_new_ticket()`:
```python
{
    "ticket_path": Path("/path/to/specs/tickets/feature-user-auth"),
    "normalized_name": "user-auth",
    "ticket_type": "feature",
    "overwritten": False
}
```

### `create_new_documentation()`:
```python
{
    "file_path": Path("/path/to/docs/guides/getting-started.md"),
    "normalized_name": "getting-started",
    "doc_type": "guide",
    "overwritten": False
}
```

---

## Template Files Expected

### Ticket Templates:
```
.cdd/templates/
├── feature-ticket-template.yaml
├── bug-ticket-template.yaml
├── spike-ticket-template.yaml
└── enhancement-ticket-template.yaml
```

### Plan Templates (not used by this task, but present):
```
.cdd/templates/
├── feature-plan-template.md
├── bug-plan-template.md
├── spike-plan-template.md
└── enhancement-plan-template.md
```

### Documentation Templates:
```
.cdd/templates/
├── guide-doc-template.md
└── feature-doc-template.md
```

**Note:** All templates were copied in Task 1 ✅

---

## Error Cases

### 1. Not in Git Repository
```python
try:
    git_root = get_git_root()
except TicketCreationError:
    # Error: "Not a git repository"
    # Message: "CDD requires git. Run: git init"
```

### 2. Template Not Found
```python
template_path = get_template_path(git_root, ticket_type)
if not template_path.exists():
    # Error: "Template not found: feature-ticket-template.yaml"
    # Message: "Run: cdd-agent init"
```

### 3. Invalid Name (Empty After Normalization)
```python
normalized_name = normalize_ticket_name("@#$%")
# Result: "" (empty string)
# Error: "Invalid ticket name - must contain alphanumeric characters"
```

### 4. User Cancellation
```python
new_name = prompt_new_name(ticket_type)
if new_name is None:
    # User typed 'cancel' or pressed Ctrl+C
    raise TicketCreationError("Ticket creation cancelled by user")
```

---

## Dependencies

```python
import re
import subprocess
from datetime import datetime
from pathlib import Path

import click  # For prompt helpers
from rich.console import Console

console = Console()
```

**All dependencies already available in CDD Agent** ✅

---

## Implementation Checklist

### Step 1: Create new_ticket.py
- [ ] Create `src/cdd_agent/mechanical/new_ticket.py`
- [ ] Add module docstring
- [ ] Import dependencies

### Step 2: Port Exception and Helper Functions
- [ ] Port `TicketCreationError` class
- [ ] Port `normalize_ticket_name()`
- [ ] Port `get_git_root()` (or reuse from init.py)
- [ ] Port `populate_template_dates()`
- [ ] Port `check_ticket_exists()`
- [ ] Port `prompt_overwrite()`
- [ ] Port `prompt_new_name()`

### Step 3: Port Ticket Functions
- [ ] Port `get_template_path()` (remove language parameter)
- [ ] Port `create_ticket_file()`
- [ ] Port `create_new_ticket()` (remove language parameter)

### Step 4: Port Documentation Functions
- [ ] Port `get_documentation_directory()`
- [ ] Port `get_documentation_template_path()` (remove language parameter)
- [ ] Port `create_documentation_file()`
- [ ] Port `create_new_documentation()` (remove language parameter)

### Step 5: Update Module Exports
- [ ] Update `src/cdd_agent/mechanical/__init__.py` to export new functions

### Step 6: Testing
- [ ] Test `create_new_ticket()` for each type (feature, bug, spike, enhancement)
- [ ] Test `create_new_documentation()` for each type (guide, feature)
- [ ] Test name normalization with various inputs
- [ ] Test overwrite handling
- [ ] Test error cases (no git, missing template, etc.)

---

## Test Cases

### TC-1: Create Feature Ticket
```python
result = create_new_ticket("feature", "User Authentication")

assert result["ticket_path"].exists()
assert result["normalized_name"] == "user-authentication"
assert (result["ticket_path"] / "spec.yaml").exists()
assert result["overwritten"] == False

# Verify dates populated
content = (result["ticket_path"] / "spec.yaml").read_text()
assert "[auto-generated]" not in content
assert "2025-11-09" in content  # Today's date
```

### TC-2: Create Bug Ticket
```python
result = create_new_ticket("bug", "Login Error 500")

assert result["normalized_name"] == "login-error-500"
assert result["ticket_type"] == "bug"
```

### TC-3: Create Spike Ticket
```python
result = create_new_ticket("spike", "OAuth Provider Comparison")

assert result["normalized_name"] == "oauth-provider-comparison"
assert result["ticket_type"] == "spike"
```

### TC-4: Create Enhancement Ticket
```python
result = create_new_ticket("enhancement", "Improve Error Messages")

assert result["normalized_name"] == "improve-error-messages"
assert result["ticket_type"] == "enhancement"
```

### TC-5: Create Guide Documentation
```python
result = create_new_documentation("guide", "Getting Started")

assert result["file_path"] == Path("docs/guides/getting-started.md")
assert result["normalized_name"] == "getting-started"
assert result["doc_type"] == "guide"
assert result["file_path"].exists()

# Verify NO date population for docs
content = result["file_path"].read_text()
# Templates don't have [auto-generated] for docs
```

### TC-6: Create Feature Documentation
```python
result = create_new_documentation("feature", "Authentication System")

assert result["file_path"] == Path("docs/features/authentication-system.md")
assert result["doc_type"] == "feature"
```

### TC-7: Name Normalization
```python
assert normalize_ticket_name("User Auth System") == "user-auth-system"
assert normalize_ticket_name("payment_processing") == "payment-processing"
assert normalize_ticket_name("Feature__Name") == "feature-name"
assert normalize_ticket_name("  dash-test  ") == "dash-test"
assert normalize_ticket_name("user@auth!") == "user-auth"
assert normalize_ticket_name("") == ""
assert normalize_ticket_name("@#$%") == ""
```

### TC-8: Overwrite Detection (Manual)
```python
# Create ticket first time
result1 = create_new_ticket("feature", "auth")
assert result1["overwritten"] == False

# Try to create again (requires user interaction)
# User responds 'y' to overwrite
result2 = create_new_ticket("feature", "auth")
assert result2["overwritten"] == True
```

### TC-9: Git Root Detection
```python
# In git subdirectory
os.chdir("project/src/components")
result = create_new_ticket("feature", "test")

# Should create at git root, not in subdirectory
assert "project/specs/tickets/" in str(result["ticket_path"])
assert "project/src/components/specs/" not in str(result["ticket_path"])
```

### TC-10: Error - Not in Git Repo
```python
# In non-git directory
try:
    create_new_ticket("feature", "test")
    assert False, "Should have raised TicketCreationError"
except TicketCreationError as e:
    assert "Not a git repository" in str(e)
```

### TC-11: Error - Missing Template
```python
# Remove templates directory
shutil.rmtree(".cdd/templates")

try:
    create_new_ticket("feature", "test")
    assert False, "Should have raised TicketCreationError"
except TicketCreationError as e:
    assert "Template not found" in str(e)
```

---

## Success Criteria

- ✅ All 13 functions ported successfully
- ✅ `create_new_ticket()` works for all 4 ticket types
- ✅ `create_new_documentation()` works for both doc types
- ✅ Name normalization handles all edge cases
- ✅ Overwrite handling works correctly
- ✅ Date population works for tickets
- ✅ No date population for documentation
- ✅ Git root detection works
- ✅ Error cases handled gracefully
- ✅ All test cases pass
- ✅ Module exports updated

---

## Integration with Slash Commands (Future)

Once slash command router is ready (Task 3):

```python
# In src/cdd_agent/slash_commands.py

class NewCommand(BaseSlashCommand):
    async def execute(self, args: str) -> str:
        # Parse: /new feature user-auth
        #        /new bug login-error
        #        /new documentation guide getting-started

        parts = args.split(maxsplit=2)

        if len(parts) < 2:
            return self._usage_error()

        ticket_type = parts[0]
        name = parts[1]

        if ticket_type == "documentation":
            # /new documentation guide getting-started
            doc_type = parts[1]
            doc_name = parts[2] if len(parts) > 2 else ""

            from cdd_agent.mechanical.new_ticket import create_new_documentation
            result = create_new_documentation(doc_type, doc_name)

            return self._format_doc_success(result)
        else:
            # /new feature user-auth
            from cdd_agent.mechanical.new_ticket import create_new_ticket
            result = create_new_ticket(ticket_type, name)

            return self._format_ticket_success(result)
```

---

## Estimated Breakdown

- **Step 1-2:** Port helpers and exception (30 min)
- **Step 3:** Port ticket functions (30 min)
- **Step 4:** Port documentation functions (20 min)
- **Step 5:** Update exports (5 min)
- **Step 6:** Testing (35 min)

**Total:** ~2 hours

---

## Files to Create/Modify

### Created:
- ✅ `src/cdd_agent/mechanical/new_ticket.py` (~460 lines estimated)
- ✅ `test_new_ticket.py` (temporary test file)

### Modified:
- ✅ `src/cdd_agent/mechanical/__init__.py` (add exports)

---

## Next Steps After Task 2

1. Task 3: Implement slash command router
2. Task 4: Integrate with chat session
3. Integration testing of `/init` and `/new` commands together

---

**Task 2 Status:** Ready to implement
**Dependencies:** Task 1 complete ✅
**Blocks:** Task 3 (slash commands need these functions)
