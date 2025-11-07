# Changelog

All notable changes to CDD Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.3] - 2025-11-07

### Added
- **glob_files** tool - Advanced file pattern matching with gitignore respect
  - Supports recursive patterns (`**/*.py`)
  - Shows file metadata (size, modification time)
  - Automatically respects .gitignore patterns
- **grep_files** tool - Regex search across files with context lines
  - Full regex pattern support
  - Configurable context lines before/after matches
  - File pattern filtering
  - Line number reporting
- **edit_file** tool - Surgical file editing with safety checks
  - Exact string replacement (prevents accidental bulk changes)
  - Uniqueness validation (fails if text appears multiple times)
  - Clear success/failure feedback
  - Line change reporting
- **git_status** tool - Repository status display
- **git_diff** tool - Change tracking and verification
- **git_log** tool - Commit history exploration
- **TOOLS_GUIDE.md** - Comprehensive documentation for all tools with examples
- **ROADMAP.md v2.0** - Updated 12-week plan to v1.0 release

### Changed
- Increased max_iterations from 25 to 50 for complex tasks
- Enhanced system prompts for better tool usage guidance
- Improved error messages across all tools

### Fixed
- Fixed TUI multi-line input handling (Ctrl+J support)
- Implemented `/save` command (previously TODO)

### Performance
- Faster search operations on large codebases
- Better memory management
- Optimized file handling

### Documentation
- Comprehensive self-assessment documentation
- Real-world workflow examples
- Tool usage patterns and best practices

## [0.0.2] - 2025-11-06

### Added
- Full Textual TUI with split-pane interface
- Token-by-token streaming responses
- Simple streaming UI fallback mode
- Animated status indicators

### Changed
- Enhanced UI with better visual feedback
- Improved streaming performance

## [0.0.1] - 2025-11-04

### Added
- Initial release
- Multi-provider architecture (Anthropic, OpenAI, custom)
- Authentication and configuration system
- Basic agent loop with tool execution
- Basic tool suite (read_file, write_file, list_files, run_bash)
- CLI interface with auth commands
- Model tier abstraction (small/mid/big)

[0.0.3]: https://github.com/guilhermegouw/context-driven-development-agent/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/guilhermegouw/context-driven-development-agent/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/guilhermegouw/context-driven-development-agent/releases/tag/v0.0.1
