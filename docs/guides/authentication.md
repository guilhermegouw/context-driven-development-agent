# Authentication Guide

This guide walks you through setting up authentication for CDD Agent with your preferred LLM provider.

## Quick Start

```bash
# Interactive setup for any provider
cdd-agent auth setup

# OAuth setup for Claude Pro/Max subscribers
cdd-agent auth oauth

# Check current configuration
cdd-agent auth status
```

## User Story: Maria's Setup Journey

Maria is a developer who wants to use CDD Agent with multiple LLM providers. Here's how she sets up her authentication:

### Initial Setup

Maria starts by running the interactive setup:

```bash
cdd-agent auth setup
```

The CLI presents her with provider options:
- `anthropic` - Claude models from Anthropic
- `openai` - GPT models from OpenAI  
- `custom` - Alternative providers (z.ai, local servers, proxies)

She chooses `anthropic` and enters her API key when prompted.

### Adding OAuth for Convenient Setup

Later, Maria wants to try OAuth for easier API key creation:

```bash
cdd-agent auth oauth
```

She chooses "api-key" mode (recommended for third-party apps), authorizes in her browser, and pastes the authorization code back into the terminal. The system creates a permanent API key for her.

**Note:** She initially tried "max" mode hoping for zero-cost access with her Claude Pro subscription, but learned that zero-cost access only works with official Claude Code, not third-party apps like cdd-agent.

### Adding Multiple Providers

Maria also wants to experiment with OpenAI models:

```bash
cdd-agent auth setup
# Choose "openai" when prompted
# Enter OpenAI API key
```

### Managing Providers

```bash
# Check all configured providers
cdd-agent auth status

# Switch default provider
cdd-agent auth set-default openai

# Test authentication
cdd-agent auth test --provider anthropic
```

## Authentication Flows

### 1. Anthropic Authentication

#### API Key Method

```bash
cdd-agent auth setup
# Choose "anthropic"
# Enter API key from https://console.anthropic.com/
```

**Where data is stored:**
- **Config file:** `~/.cdd-agent/settings.json`
- **Key field:** `providers.anthropic.auth_token`
- **Default models:**
  - `small`: `claude-3-5-haiku-20241022`
  - `mid`: `claude-sonnet-4-5-20250929`
  - `big`: `claude-opus-4-20250514`

#### OAuth Method (Not Recommended for Third-Party Apps)

**IMPORTANT:** Zero-cost API access via OAuth "max" mode does NOT work with cdd-agent or any third-party applications. Anthropic restricts this feature to official Claude Code only.

```bash
cdd-agent auth oauth
# Choose "api-key" to create permanent API key via OAuth
# Authorize in browser
# Paste authorization code
```

**Where data is stored:**
- **Config file:** `~/.cdd-agent/settings.json`
- **OAuth fields:** `providers.anthropic.oauth.refresh_token`, `access_token`, `expires_at`
- **Auto-refresh:** Tokens automatically refresh when expired
- **Limitation:** Third-party apps like cdd-agent cannot use zero-cost plan benefits

#### API Key via OAuth

```bash
cdd-agent auth oauth
# Choose "api-key" to create permanent API key
```

**Where data is stored:**
- **Config file:** `~/.cdd-agent/settings.json`
- **Key field:** `providers.anthropic.auth_token` (permanent key)
- **Benefits:** More convenient but counts toward API usage limits

### 2. OpenAI Authentication

```bash
cdd-agent auth setup
# Choose "openai"
# Enter API key from https://platform.openai.com/
```

**Where data is stored:**
- **Config file:** `~/.cdd-agent/settings.json`
- **Key field:** `providers.openai.api_key`
- **Default models:**
  - `small`: `gpt-4o-mini`
  - `mid`: `gpt-4o`
  - `big`: `o1-preview`

### 3. Custom Provider Authentication

For alternative providers like z.ai, local servers, or proxies:

```bash
cdd-agent auth setup
# Choose "custom"
# Enter base URL (e.g., https://api.z.ai/api/anthropic)
# Enter API key/token
# Choose API compatibility: "anthropic" or "openai"
# Configure model mappings
```

**Where data is stored:**
- **Config file:** `~/.cdd-agent/settings.json`
- **Key field:** `providers.custom.auth_token`
- **Base URL:** `providers.custom.base_url`
- **API format:** `providers.custom.provider_type`

#### Example Custom Provider Setup

For z.ai (Anthropic-compatible):

```
Base URL: https://api.z.ai/api/anthropic
API compatibility: anthropic
Model mappings:
  small: glm-4.5-air
  mid: glm-4.6
  big: glm-4.6
```

## Configuration File Structure

All authentication data is stored in `~/.cdd-agent/settings.json`:

```json
{
  "version": "1.0",
  "default_provider": "anthropic",
  "providers": {
    "anthropic": {
      "auth_token": "sk-ant-api03-...",
      "base_url": "https://api.anthropic.com",
      "models": {
        "small": "claude-3-5-haiku-20241022",
        "mid": "claude-sonnet-4-5-20250929",
        "big": "claude-opus-4-20250514"
      },
      "oauth": {
        "type": "oauth",
        "refresh_token": "refresh_token_here",
        "access_token": "access_token_here",
        "expires_at": 1730419200
      }
    },
    "openai": {
      "api_key": "sk-proj-...",
      "base_url": "https://api.openai.com/v1",
      "models": {
        "small": "gpt-4o-mini",
        "mid": "gpt-4o", 
        "big": "o1-preview"
      }
    },
    "custom": {
      "auth_token": "your-api-key",
      "base_url": "https://api.z.ai/api/anthropic",
      "provider_type": "anthropic",
      "models": {
        "small": "glm-4.5-air",
        "mid": "glm-4.6",
        "big": "glm-4.6"
      }
    }
  }
}
```

## Environment Variable Overrides

You can override settings using environment variables (Claude Code style):

```bash
# Override Anthropic authentication
export ANTHROPIC_AUTH_TOKEN="sk-ant-api03-..."
export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Override OpenAI authentication
export OPENAI_API_KEY="sk-proj-..."

# Generic overrides (work for any provider)
export CDD_AUTH_TOKEN="your-token"
export CDD_BASE_URL="https://your-provider.com"
export CDD_APPROVAL_MODE="paranoid"
```

**Priority order (highest to lowest):**
1. Environment variables
2. Configuration file settings
3. Default values

## Security Considerations

### File Permissions

The configuration file `~/.cdd-agent/settings.json` contains sensitive API keys and tokens:

```bash
# Recommended permissions (read/write by owner only)
chmod 600 ~/.cdd-agent/settings.json

# Check current permissions
ls -la ~/.cdd-agent/settings.json
```

### API Key Security

- **Never commit** `settings.json` to version control
- **Use environment variables** in CI/CD environments
- **Rotate keys regularly** for production deployments
- **Secure file permissions** - `settings.json` should be readable only by you (chmod 600)

### OAuth Token Security

**Note:** OAuth provides convenience but not enhanced security for third-party apps:

- OAuth tokens are stored in plain JSON (same as API keys)
- Access tokens have limited lifetime (auto-refresh)
- Refresh tokens are long-lived but can be revoked
- Browser-based flow is convenient but doesn't prevent interception
- **Zero-cost access does NOT work** - third-party apps use regular API pricing

## OAuth Limitations

### Why Zero-Cost Access Doesn't Work

If you're a Claude Pro or Max subscriber, you might expect OAuth authentication to provide zero-cost API access like it does with official Claude Code. Unfortunately, **this doesn't work with third-party applications** like cdd-agent.

**The Reality:**
- ❌ OAuth "max" mode does NOT provide zero-cost access for third-party apps
- ❌ Anthropic restricts zero-cost tokens to official Claude Code only
- ✅ OAuth "api-key" mode creates permanent API keys (regular pricing applies)
- ✅ Zero-cost benefit is exclusive to official Claude Code application

**What This Means:**
- Use official Claude Code CLI if zero-cost API access is critical for you
- Use cdd-agent with regular API keys (manual or via OAuth) - both have the same cost
- Accept that plan benefits don't extend to third-party applications

**Why This Limitation Exists:**
Anthropic's API validates the client application making requests and rejects OAuth tokens from third-party apps with the error: "This credential is only authorized for use with Claude Code and cannot be used for other API requests."

This is a server-side restriction that cannot be bypassed. See [OAUTH_LIMITATION.md](../../OAUTH_LIMITATION.md) for full technical details.

## Troubleshooting

### Common Issues

#### Invalid API Key

```bash
# Test authentication
cdd-agent auth test --provider anthropic

# Check configuration
cdd-agent auth status
```

#### OAuth Authorization Failed

**If you see "This credential is only authorized for use with Claude Code":**
- This is expected for OAuth "max" mode with third-party apps
- Solution: Use "api-key" mode instead when running `cdd-agent auth oauth`
- This creates a permanent API key that works with cdd-agent (regular pricing applies)

**Other OAuth issues:**
1. Ensure you copied the full authorization code
2. Check that your Claude subscription is active
3. Try the OAuth flow again
4. Use manual API key method as fallback (`cdd-agent auth setup`)

#### Permission Denied

```bash
# Fix file permissions
chmod 600 ~/.cdd-agent/settings.json
chown $USER:$USER ~/.cdd-agent/settings.json
```

#### Environment Variable Not Working

```bash
# Check if variable is set
echo $CDD_AUTH_TOKEN

# Verify it's being used
cdd-agent auth status  # Shows effective config with overrides
```

### Debug Mode

Enable detailed logging to troubleshoot authentication issues:

```bash
# Show recent logs
cdd-agent logs show

# Follow logs in real-time
cdd-agent logs show -f

# Show log file location
cdd-agent logs path
```

## Advanced Configuration

### Custom Model Mappings

Override default model mappings during setup:

```bash
cdd-agent auth setup
# Choose "Use default model mappings? No"
# Enter custom models for each tier
```

### Multiple Provider Configurations

You can configure multiple providers simultaneously:

```bash
# Setup Anthropic
cdd-agent auth setup  # Choose anthropic

# Setup OpenAI as additional provider  
export CDD_AUTH_TOKEN="sk-proj-openai-key"
cdd-agent auth setup  # Choose openai, enter different name

# Switch between providers
cdd-agent chat --provider anthropic
cdd-agent chat --provider openai
```

### Provider-Specific Settings

Each provider can have unique configurations:

```json
{
  "providers": {
    "anthropic": {
      "timeout_ms": 300000,
      "models": {...}
    },
    "openai": {
      "timeout_ms": 60000,
      "models": {...}
    },
    "local-llm": {
      "base_url": "http://localhost:8000/v1",
      "timeout_ms": 120000,
      "models": {...}
    }
  }
}
```

## Migration Guide

### From Claude Code

If you're migrating from Claude Code, you can reuse existing environment variables:

```bash
# Claude Code variables (compatible)
export ANTHROPIC_AUTH_TOKEN="your-key"
export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# CDD Agent specific
export CDD_APPROVAL_MODE="balanced"
```

### Backup and Restore

```bash
# Backup configuration
cp ~/.cdd-agent/settings.json ~/cdd-agent-backup.json

# Restore configuration  
cp ~/cdd-agent-backup.json ~/.cdd-agent/settings.json
```

## Next Steps

After authentication is configured:

1. **Test the setup:**
   ```bash
   cdd-agent chat "Hello, can you help me?"
   ```

2. **Explore tools:**
   ```bash
   cdd-agent chat --simple
   # Type /help to see available commands
   ```

3. **Configure approval mode:**
   ```bash
   export CDD_APPROVAL_MODE="paranoid"  # Ask for all tool approvals
   export CDD_APPROVAL_MODE="trusting"  # Remember approvals
   ```

4. **Read the tools guide:** See [Tools Guide](TOOLS_GUIDE.md) for advanced usage.

---

**Need help?** Check the [logs](#debug-mode) or open an issue on GitHub.