# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.4] - 2025-11-11

### Added

#### OAuth Authentication
- **OAuth 2.0 support** for Anthropic authentication with PKCE flow
- New `cdd-agent auth oauth` command for OAuth setup
- Two OAuth modes:
  - `api-key`: Creates permanent API key via OAuth (recommended for third-party apps)
  - `max`: OAuth tokens (restricted to official Claude Code only)
- Automatic token refresh mechanism with 5-minute expiration buffer
- Custom HTTP transport for proper OAuth Bearer token handling
- OAuth token storage in settings.json with auto-refresh capability

#### Background Execution
- Enhanced background execution with real-time monitoring
- `--background` flag for all agent commands (chat, ticket, etc.)
- Background process management commands:
  - `cdd-agent bg list` - List all background processes
  - `cdd-agent bg show <id>` - Show specific process output
  - `cdd-agent bg kill <id>` - Kill running background process
  - `cdd-agent bg clear` - Clear completed processes
- Process status tracking (running, completed, failed)
- Persistent process storage across CLI sessions

#### Documentation
- Comprehensive OAuth implementation documentation (OAUTH_IMPLEMENTATION.md)
- OAuth limitation documentation explaining third-party app restrictions (OAUTH_LIMITATION.md)
- OAuth testing guide with all fixes documented (OAUTH_TESTING.md)
- User-facing authentication guide (docs/guides/authentication.md)
- Technical authentication documentation (docs/features/authentication.md)
- Updated README with v0.0.4 features and honest OAuth limitations
- Tools guide documentation (docs/guides/TOOLS_GUIDE.md)

#### Agent System Improvements
- Multi-agent architecture with specialized agents:
  - **Planner Agent**: Analyzes tickets and creates implementation plans
  - **Executor Agent**: Executes planned tasks with tool usage
  - **Socrates Agent**: Handles CDD file analysis and spec writing
- Agent coordination and task delegation
- Enhanced logging for agent operations

#### Tool System
- Tool schema filtering for OAuth API compatibility
- Automatic removal of custom `risk_level` field when using OAuth
- Enhanced tool registry with configurable schema output

### Changed

- **pyproject.toml**: Added `authlib = "^1.3.2"` dependency for OAuth support
- **Agent initialization**: Now detects OAuth and adjusts tool schemas automatically
- **Authentication flow**: Enhanced to support both API key and OAuth methods
- **CLI structure**: Improved command organization and help text
- **Logging system**: More detailed OAuth-related logging
- **Settings format**: Extended to include OAuth token storage

### Fixed

- **OAuth 401 Error**: Implemented custom HTTP transport to properly handle Bearer tokens
  - Removes incorrect `x-api-key` header
  - Adds correct `Authorization: Bearer` header
  - Includes required `anthropic-beta` header for OAuth features

- **OAuth 400 Tool Schema Error**: Implemented automatic schema filtering
  - Detects OAuth authentication mode
  - Removes custom `risk_level` field from tool schemas
  - Maintains backward compatibility with API key authentication

- **Token refresh mechanism**: Proper expiration checking with buffer time
- **Error handling**: Better error messages for OAuth-related issues
- **Configuration validation**: Enhanced validation for OAuth settings

### Security

- File permissions recommendations for settings.json (chmod 600)
- Environment variable support for sensitive credentials
- Proper token storage and refresh handling
- Security considerations documented in authentication guides

### Known Limitations

- **OAuth Zero-Cost Access**: Does NOT work with third-party applications like cdd-agent
  - Anthropic restricts OAuth "max" mode to official Claude Code only
  - Third-party apps receive error: "This credential is only authorized for use with Claude Code"
  - Workaround: Use OAuth "api-key" mode or manual API key setup (regular pricing applies)
  - Zero-cost API access is exclusive to official Claude Code application

### Documentation Improvements

- Honest and transparent documentation about OAuth limitations
- Clear guidance on when to use OAuth vs manual API keys
- Comparison table between official Claude Code and cdd-agent capabilities
- User stories and examples for authentication setup
- Comprehensive troubleshooting guides

### Technical Details

**OAuth Implementation:**
- PKCE flow with S256 code challenge
- Automatic token refresh 5 minutes before expiration
- Custom httpx.HTTPTransport for OAuth-specific headers
- Support for both token-based and API-key-via-OAuth modes

**Architecture Changes:**
- Modular OAuth handler (oauth.py)
- Enhanced ConfigManager with OAuth support
- Agent auto-detection of authentication mode
- Tool registry schema filtering capability

---

## [0.0.3] - Previous Release

(Previous release notes would go here)

---

## Release Notes Format

Each release includes:
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

---

**Note**: This project is in active development. Features and APIs may change between releases.
