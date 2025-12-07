"""Tests for hierarchical context loading."""

from cdd_agent.context import ContextLoader


class TestProjectRootDetection:
    """Test project root detection."""

    def test_detects_git_root(self, tmp_path):
        """Should detect .git directory as project root."""
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Create subdirectory
        sub_dir = project_dir / "src" / "components"
        sub_dir.mkdir(parents=True)

        # From subdirectory, should detect project root
        loader = ContextLoader(cwd=sub_dir)
        root = loader.detect_project_root()

        assert root == project_dir

    def test_detects_pyproject_toml(self, tmp_path):
        """Should detect pyproject.toml as project root."""
        project_dir = tmp_path / "python_project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").touch()

        sub_dir = project_dir / "src"
        sub_dir.mkdir()

        loader = ContextLoader(cwd=sub_dir)
        root = loader.detect_project_root()

        assert root == project_dir

    def test_detects_package_json(self, tmp_path):
        """Should detect package.json as project root."""
        project_dir = tmp_path / "node_project"
        project_dir.mkdir()
        (project_dir / "package.json").touch()

        loader = ContextLoader(cwd=project_dir)
        root = loader.detect_project_root()

        assert root == project_dir

    def test_no_project_root_found(self, tmp_path):
        """Should return None if no project markers found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = ContextLoader(cwd=empty_dir)
        root = loader.detect_project_root()

        assert root is None

    def test_priority_order(self, tmp_path):
        """Should detect closest project root (not parent project)."""
        # Outer project with .git
        outer = tmp_path / "outer_project"
        outer.mkdir()
        (outer / ".git").mkdir()

        # Inner project with pyproject.toml
        inner = outer / "inner_project"
        inner.mkdir()
        (inner / "pyproject.toml").touch()

        # From inner project, should detect inner root (not outer)
        loader = ContextLoader(cwd=inner)
        root = loader.detect_project_root()

        assert root == inner


class TestGlobalContextLoading:
    """Test global context loading."""

    def test_loads_cdd_md_priority(self, tmp_path, monkeypatch):
        """Should load ~/.cdd/CDD.md as first priority."""
        # Create both global context files
        cdd_dir = tmp_path / ".cdd"
        cdd_dir.mkdir()
        (cdd_dir / "CDD.md").write_text("CDD global context")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("Claude global context")

        # Mock home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader()
        context = loader.load_global_context()

        assert context == "CDD global context"

    def test_fallback_to_claude_md(self, tmp_path, monkeypatch):
        """Should fallback to ~/.claude/CLAUDE.md if CDD.md not found."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("Claude global context")

        # Mock home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader()
        context = loader.load_global_context()

        assert context == "Claude global context"

    def test_no_global_context(self, tmp_path, monkeypatch):
        """Should return None if no global context found."""
        # Mock home directory with no context files
        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader()
        context = loader.load_global_context()

        assert context is None


class TestProjectContextLoading:
    """Test project context loading."""

    def test_loads_cdd_md_priority(self, tmp_path):
        """Should load CDD.md as first priority at project root."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        (project_dir / "CDD.md").write_text("CDD project context")
        (project_dir / "CLAUDE.md").write_text("CLAUDE project context")

        loader = ContextLoader(cwd=project_dir)
        context = loader.load_project_context()

        assert context == "CDD project context"

    def test_fallback_to_claude_md(self, tmp_path):
        """Should fallback to CLAUDE.md if CDD.md not found."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        (project_dir / "CLAUDE.md").write_text("CLAUDE project context")

        loader = ContextLoader(cwd=project_dir)
        context = loader.load_project_context()

        assert context == "CLAUDE project context"

    def test_no_project_context(self, tmp_path):
        """Should return None if no project context found."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        # No CDD.md or CLAUDE.md

        loader = ContextLoader(cwd=project_dir)
        context = loader.load_project_context()

        assert context is None

    def test_no_project_root(self, tmp_path):
        """Should return None if no project root detected."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = ContextLoader(cwd=empty_dir)
        context = loader.load_project_context()

        assert context is None


class TestContextMerging:
    """Test context merging."""

    def test_merge_both_contexts(self):
        """Should merge global and project contexts in correct order."""
        global_ctx = "Global preferences"
        project_ctx = "Project specifics"

        loader = ContextLoader()
        merged = loader.merge_contexts(global_ctx, project_ctx)

        # Global should appear first, project second (for recency bias)
        assert "Global Context" in merged
        assert "Project Context" in merged
        assert merged.index("Global Context") < merged.index("Project Context")
        assert "Global preferences" in merged
        assert "Project specifics" in merged

    def test_merge_only_global(self):
        """Should handle case with only global context."""
        global_ctx = "Global preferences"

        loader = ContextLoader()
        merged = loader.merge_contexts(global_ctx, None)

        assert "Global Context" in merged
        assert "Global preferences" in merged
        assert "Project Context" not in merged

    def test_merge_only_project(self):
        """Should handle case with only project context."""
        project_ctx = "Project specifics"

        loader = ContextLoader()
        merged = loader.merge_contexts(None, project_ctx)

        assert "Project Context" in merged
        assert "Project specifics" in merged
        assert "Global Context" not in merged

    def test_merge_empty(self):
        """Should return None if both contexts are empty."""
        loader = ContextLoader()
        merged = loader.merge_contexts(None, None)

        assert merged is None


class TestContextLoading:
    """Test full context loading integration."""

    def test_load_complete_hierarchy(self, tmp_path, monkeypatch):
        """Should load and merge complete context hierarchy."""
        # Create global context
        cdd_dir = tmp_path / ".cdd"
        cdd_dir.mkdir()
        (cdd_dir / "CDD.md").write_text("Global: Use type hints")

        # Create project
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        (project_dir / "CDD.md").write_text("Project: Flask app with SQLAlchemy")

        # Mock home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader(cwd=project_dir)
        context = loader.load_context()

        # Should contain both contexts
        assert "Global: Use type hints" in context
        assert "Project: Flask app with SQLAlchemy" in context

        # Project should come after global (recency bias)
        assert context.index("Global:") < context.index("Project:")

    def test_load_with_cache(self, tmp_path, monkeypatch):
        """Should cache loaded contexts."""
        # Create global context
        cdd_dir = tmp_path / ".cdd"
        cdd_dir.mkdir()
        (cdd_dir / "CDD.md").write_text("Cached content")

        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader()

        # First load
        context1 = loader.load_context()
        assert "Cached content" in context1

        # Modify file
        (cdd_dir / "CDD.md").write_text("Modified content")

        # Second load (should use cache)
        context2 = loader.load_context(use_cache=True)
        assert context2 == context1  # Should be cached
        assert "Cached content" in context2

        # Third load (without cache)
        context3 = loader.load_context(use_cache=False)
        assert "Modified content" in context3  # Should be fresh

    def test_clear_cache(self, tmp_path, monkeypatch):
        """Should clear cached contexts."""
        cdd_dir = tmp_path / ".cdd"
        cdd_dir.mkdir()
        (cdd_dir / "CDD.md").write_text("Original content")

        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader()

        # Load and cache
        context1 = loader.load_context()
        assert "Original content" in context1

        # Modify and clear cache
        (cdd_dir / "CDD.md").write_text("New content")
        loader.clear_cache()

        # Load again (should read fresh)
        context2 = loader.load_context()
        assert "New content" in context2


class TestContextInfo:
    """Test context information reporting."""

    def test_get_context_info(self, tmp_path, monkeypatch):
        """Should provide information about loaded contexts."""
        # Create contexts
        cdd_dir = tmp_path / ".cdd"
        cdd_dir.mkdir()
        (cdd_dir / "CDD.md").write_text("Global")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        (project_dir / "CLAUDE.md").write_text("Project")

        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ContextLoader(cwd=project_dir)
        info = loader.get_context_info()

        assert info["project_root"] == str(project_dir)
        assert ".cdd/CDD.md" in info["global_context"]
        assert "CLAUDE.md" in info["project_context"]
        assert info["has_context"] is True

    def test_get_context_info_no_context(self, tmp_path):
        """Should report when no context is found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = ContextLoader(cwd=empty_dir)
        info = loader.get_context_info()

        assert info["project_root"] is None
        assert info["global_context"] is None
        assert info["project_context"] is None
        assert info["has_context"] is False
