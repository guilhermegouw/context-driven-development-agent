# OAuth Testing Guide

## Critical Fixes Applied

### Fix #1: 401 Authentication Error

**Issue Found:** The initial implementation returned `401 - invalid x-api-key` error.

**Root Cause:** Anthropic's OAuth API requires:
1. `Authorization: Bearer {token}` header (not `x-api-key`)
2. Special `anthropic-beta` header with OAuth feature flags
3. The Python Anthropic SDK always adds `x-api-key` header by default

**Solution:** Implemented custom `OAuthTransport` class that:
- Intercepts HTTP requests before they're sent
- Removes `x-api-key` header
- Adds `Authorization: Bearer {token}` header
- Adds required `anthropic-beta` header

### Fix #2: 400 Invalid Request Error

**Issue Found:** After fixing authentication, got `400 - tools.0.custom.risk_level: Extra inputs are not permitted`

**Root Cause:**
- cdd-agent tools include custom `risk_level` field for approval system
- Anthropic's OAuth API is stricter and rejects custom tool fields
- Regular API key auth tolerates custom fields, but OAuth does not

**Solution:** Modified `ToolRegistry.get_schemas()` to:
- Accept `include_risk_level` parameter
- When `include_risk_level=False`, filter out `risk_level` field from all tool schemas
- Agent automatically detects OAuth and calls `get_schemas(include_risk_level=False)`
- Files modified:
  - `src/cdd_agent/tools.py` - Added filtering logic
  - `src/cdd_agent/agent.py` - Auto-detect OAuth and filter schemas
  - `src/cdd_agent/utils/filtered_tools.py` - Pass-through parameter

### Fix #3: 400 Credential Restriction Error

**Issue Found:** After fixing tools, got `400 - This credential is only authorized for use with Claude Code and cannot be used for other API requests`

**Root Cause:**
- **Anthropic restricts Claude Pro/Max OAuth tokens to official Claude Code app only**
- Third-party applications cannot use zero-cost plan-based API access
- This is a fundamental limitation of Anthropic's OAuth design
- Zero-cost access is a benefit exclusive to the official Claude Code CLI

**Solution:** Use "API Key via OAuth" mode instead:
- Choose `api-key` mode when running `cdd-agent auth oauth`
- This creates a permanent API key through OAuth authorization
- Works with all applications (not restricted to Claude Code)
- **Note:** This uses regular API pricing, not zero-cost

**Reality Check:**
- ❌ Third-party apps cannot get zero-cost Claude Pro/Max API access
- ✅ OAuth can create API keys for convenient authentication
- ✅ OpenCode also cannot provide zero-cost access (same limitation)
- ✅ Zero-cost benefit only applies to official Claude Code application

## Testing Steps

### 1. Install Dependencies
```bash
cd /home/guilherme/code/cdd-agent-cli
poetry install
```

### 2. Run OAuth Setup
```bash
poetry run cdd-agent auth oauth
```

**Expected Flow:**
1. Browser opens to claude.ai OAuth page
2. You authorize with your Claude Pro/Max account
3. You receive an authorization code
4. Paste code back to CLI
5. CLI exchanges code for tokens
6. Tokens saved to `~/.cdd-agent/settings.json`

**Example Output:**
```
Anthropic OAuth Setup
This will authenticate with your Claude Pro or Max plan for zero-cost API access.

Choose authentication mode (max/api-key) [max]: max

Mode: OAuth (Claude Pro/Max)
Uses OAuth tokens that auto-refresh. Best for plan subscribers.

Step 1: Authorize in browser
Opening: https://claude.ai/oauth/authorize?...
✓ Browser opened

Step 2: Paste authorization code
After authorizing, you'll receive a code. Paste it here:
Authorization code: abc123#xyz789

Exchanging code for OAuth tokens...

✓ OAuth setup successful!
Your Claude Pro/Max plan is now connected.
Tokens will auto-refresh when needed.
```

### 3. Verify Token Storage
```bash
cat ~/.cdd-agent/settings.json | python -m json.tool | grep -A 5 oauth
```

**Expected Output:**
```json
"oauth": {
    "type": "oauth",
    "refresh_token": "rt_...",
    "access_token": "ey...",
    "expires_at": 1731389456
}
```

### 4. Test Chat with OAuth
```bash
poetry run cdd-agent chat "Hello, Claude! Confirm you're using OAuth."
```

**Expected:**
- ✅ No authentication errors
- ✅ Claude responds normally
- ✅ Zero API cost (if you have Claude Pro/Max)

**Check logs for confirmation:**
```bash
poetry run cdd-agent logs show | grep -i oauth
```

Should see:
```
Using OAuth authentication
Anthropic client initialized with OAuth authentication
```

### 5. Test Token Refresh

**Option A: Wait for natural expiration** (~55 minutes after setup)
```bash
# After 55+ minutes
poetry run cdd-agent chat "Are you still there?"
```

Should see in logs:
```
OAuth token expiring soon, refreshing...
OAuth token refreshed successfully
```

**Option B: Force refresh by mocking expiration**
```bash
# Edit settings.json and change expires_at to current timestamp
python -c "import time; print(int(time.time()))"
# Update expires_at in settings.json to this value

# Then run chat
poetry run cdd-agent chat "Test refresh"
```

### 6. Test Backward Compatibility

**Verify API key auth still works:**
```bash
# Backup OAuth config
cp ~/.cdd-agent/settings.json ~/.cdd-agent/settings.json.oauth-backup

# Remove OAuth from config
python -c "
import json
with open('/home/guilherme/.cdd-agent/settings.json', 'r') as f:
    config = json.load(f)
if 'anthropic' in config['providers']:
    config['providers']['anthropic']['oauth'] = None
with open('/home/guilherme/.cdd-agent/settings.json', 'w') as f:
    json.dump(config, f, indent=2)
"

# Test with API key
poetry run cdd-agent chat "Hello via API key"

# Restore OAuth config
cp ~/.cdd-agent/settings.json.oauth-backup ~/.cdd-agent/settings.json
```

## Debugging

### Enable Debug Logging
```bash
export CDD_LOG_LEVEL=DEBUG
poetry run cdd-agent chat "Debug test"
```

### Check HTTP Headers Being Sent

Add this to agent.py temporarily to see headers:
```python
def handle_request(self, request: httpx.Request) -> httpx.Response:
    print(f"Headers: {dict(request.headers)}")
    # ... rest of implementation
```

Expected headers:
```python
{
    'authorization': 'Bearer ey...',
    'anthropic-beta': 'oauth-2025-04-20,claude-code-20250219,...',
    'content-type': 'application/json',
    'anthropic-version': '2023-06-01',
    # NO x-api-key!
}
```

### Verify OAuth Token Format

```bash
# Check token structure (don't share this!)
python -c "
import json
with open('/home/guilherme/.cdd-agent/settings.json') as f:
    config = json.load(f)
    oauth = config['providers']['anthropic']['oauth']
    print(f'Refresh token starts with: {oauth[\"refresh_token\"][:10]}...')
    print(f'Access token starts with: {oauth[\"access_token\"][:10]}...')
    print(f'Expires at: {oauth[\"expires_at\"]}')
"
```

**Expected format:**
- Refresh token: starts with `rt_`
- Access token: JWT format (starts with `ey`)
- Expires at: Unix timestamp (10 digits)

## Testing Checklist

- [ ] Dependencies installed (`poetry install`)
- [ ] OAuth setup completes successfully
- [ ] Tokens saved to settings.json
- [ ] Token format is correct (rt_ and ey prefixes)
- [ ] Chat works with OAuth (no 401 errors)
- [ ] Logs show "Using OAuth authentication"
- [ ] Token auto-refreshes when expiring
- [ ] Backward compatibility with API keys
- [ ] Help text is clear (`cdd-agent auth oauth --help`)

## Common Test Failures

### ❌ "401 - invalid x-api-key"
**Problem:** Custom HTTP transport not working
**Fix:** Check that `OAuthTransport` class is defined and used in agent.py:253-294
**Status:** ✅ Fixed

### ❌ "400 - tools.0.custom.risk_level: Extra inputs are not permitted"
**Problem:** OAuth API rejects custom tool schema fields
**Fix:** Check that agent.py filters risk_level field when using OAuth
**Status:** ✅ Fixed - Auto-detects OAuth and removes risk_level field

### ❌ "400 - This credential is only authorized for use with Claude Code"
**Problem:** Anthropic restricts OAuth tokens to official Claude Code app only
**Solution:** Use "API Key via OAuth" mode instead:
```bash
poetry run cdd-agent auth oauth
# Choose: api-key (not max)
```
**Important:** Zero-cost API access is ONLY available through official Claude Code application, not third-party apps
**Status:** ⚠️ Fundamental Limitation - Cannot be fixed

### ❌ "Failed to exchange authorization code"
**Problem:** Invalid code or network issue
**Solution:** Try again, ensure code is pasted immediately after receiving it

### ❌ "No module named 'authlib'"
**Problem:** Dependencies not installed
**Solution:** `poetry install`

### ❌ Chat works but shows API key warning
**Problem:** OAuth not being detected
**Check:**
1. Verify `oauth` field exists in settings.json
2. Check logs: should see "Using OAuth authentication"
3. Verify provider is "anthropic" (not "custom")

## Success Criteria

✅ **OAuth setup completes without errors**
✅ **Tokens saved correctly to settings.json**
✅ **Chat requests work (HTTP 200 responses)**
✅ **No "invalid x-api-key" errors**
✅ **Logs show OAuth authentication being used**
✅ **Token refresh works automatically**
✅ **API key auth still works (backward compatible)**

## Next Steps After Testing

1. **Document any issues found**
2. **Update OAUTH_IMPLEMENTATION.md with real-world learnings**
3. **Create unit tests for oauth.py**
4. **Add integration tests for auth flow**
5. **Consider adding `--debug` flag to show OAuth details**

## Support

If you encounter issues:
1. Check logs: `poetry run cdd-agent logs show`
2. Enable debug mode: `export CDD_LOG_LEVEL=DEBUG`
3. Review settings.json structure
4. Check OAUTH_IMPLEMENTATION.md for troubleshooting
5. File issue with full error message and logs

---

**Last Updated:** 2025-11-11 (after fixing 401 error)
**Status:** ✅ Fix Applied, Ready for Testing
