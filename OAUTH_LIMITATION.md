# Important OAuth Limitation

## TL;DR

**❌ Zero-cost Claude Pro/Max API access does NOT work with third-party applications like cdd-agent.**

Anthropic restricts OAuth tokens to work **only with the official Claude Code application**. This is a fundamental limitation that cannot be worked around.

## What Happened

We successfully implemented OAuth authentication for cdd-agent, but discovered that Anthropic's OAuth tokens carry a critical restriction:

```
Error 400: This credential is only authorized for use with Claude Code
and cannot be used for other API requests.
```

## Why This Limitation Exists

Anthropic designed their OAuth system with two distinct use cases:

### 1. Claude Code OAuth (Restricted)
- **Purpose:** Enable zero-cost API access for Claude Pro/Max subscribers
- **Restriction:** Tokens only work with official Claude Code application
- **Detection:** Anthropic's API validates the client making requests
- **Benefit:** Free API usage for plan subscribers
- **Limitation:** Cannot be used by third-party apps

### 2. API Key via OAuth (Unrestricted)
- **Purpose:** Convenient API key creation through OAuth flow
- **Restriction:** None - works with all applications
- **Cost:** Regular API pricing applies
- **Benefit:** Easier than manually creating API keys in console
- **Use Case:** Third-party applications like cdd-agent

## What This Means for cdd-agent

### What Works ✅
- OAuth flow for creating API keys
- Browser-based authorization
- Automatic token management
- All the OAuth infrastructure we built

### What Doesn't Work ❌
- Zero-cost API access via Claude Pro/Max plan
- Using plan-based OAuth tokens for API calls
- Getting "free" API requests like official Claude Code

## Comparison with Official Claude Code

| Feature | Official Claude Code | cdd-agent (via OAuth) | cdd-agent (via API Key) |
|---------|---------------------|----------------------|------------------------|
| OAuth Authentication | ✅ Yes | ✅ Yes | ❌ No |
| Zero-Cost API Access | ✅ Yes (for Pro/Max) | ❌ No | ❌ No |
| Third-Party App Support | ❌ Official only | ✅ Yes | ✅ Yes |
| API Costs | Free (with plan) | Regular pricing | Regular pricing |
| Token Refresh | ✅ Auto | ✅ Auto | N/A |

## What About OpenCode?

OpenCode faces the **exact same limitation**. Despite having OAuth support, they cannot provide zero-cost API access to third-party users because:

1. OpenCode is a third-party application (not official Claude Code)
2. Anthropic restricts OAuth tokens to official Claude Code
3. OpenCode's OAuth creates API keys (which have costs), not zero-cost access

**From OpenCode's perspective:**
- They implemented OAuth for **convenience**, not zero-cost access
- Their OAuth flow creates API keys, just like we implemented
- The "max" mode in their plugin exists but won't work for third-party apps
- Zero-cost benefit only applies when using official Anthropic tools

## Recommended Approach

For cdd-agent users who want to use OAuth:

```bash
# Run OAuth setup
poetry run cdd-agent auth oauth

# When prompted for mode:
# Choose: api-key ✅ (creates permanent API key)
# Avoid: max ❌ (restricted to Claude Code)
```

This will:
1. Open browser for OAuth authorization
2. Create a permanent API key via OAuth
3. Save the API key to settings.json
4. Work with all API requests

**Cost:** Regular Anthropic API pricing applies (not zero-cost)

## Alternative: Manual API Key

If OAuth seems unnecessary, you can simply:

```bash
# Traditional API key setup
poetry run cdd-agent auth setup

# Manually enter API key from:
# https://console.anthropic.com/settings/keys
```

This is simpler and achieves the same result as "API Key via OAuth" mode.

## Technical Details

### How Anthropic Detects Third-Party Apps

Anthropic's API likely uses one or more of these methods to restrict OAuth tokens:

1. **Client ID Validation:** Checks the OAuth client_id in requests
2. **Application Fingerprinting:** Validates SDK version, user-agent, etc.
3. **Token Metadata:** OAuth tokens contain metadata about intended use
4. **Request Origin:** May validate request patterns/signatures

### Why We Can't Bypass This

- This is a **server-side restriction** enforced by Anthropic's API
- No amount of client-side code can bypass it
- Attempting to spoof official Claude Code would violate ToS
- The restriction is intentional to protect plan benefits

## Lessons Learned

### What We Built (Still Valuable)
1. ✅ Complete OAuth 2.0 implementation with PKCE
2. ✅ Custom HTTP transport for OAuth headers
3. ✅ Automatic token refresh mechanism
4. ✅ Tool schema filtering for OAuth compatibility
5. ✅ Comprehensive documentation

### What We Can't Achieve
1. ❌ Zero-cost API access for third-party apps
2. ❌ Claude Pro/Max plan benefits in cdd-agent
3. ❌ Bypassing Anthropic's restriction

### What We Recommend
- Use OAuth **for convenient API key creation**
- Don't expect **zero-cost access** in third-party apps
- Understand that **plan benefits ≠ third-party benefits**
- Use official **Claude Code** if zero-cost access is critical

## Conclusion

The OAuth implementation is **technically correct and fully functional**, but Anthropic's business decision to restrict zero-cost access to official applications means:

**For Claude Pro/Max Subscribers:**
- Use official Claude Code CLI for zero-cost access
- Use cdd-agent with API key for third-party features
- Accept that these are separate use cases

**For cdd-agent Users:**
- OAuth provides convenient API key creation
- All API usage incurs costs (same as manual API keys)
- This is normal for third-party applications

**For Developers:**
- Our OAuth implementation works correctly
- The restriction is external (Anthropic's policy)
- Cannot be "fixed" without Anthropic changing their policy
- Implementation still valuable for future use cases

## References

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [OAuth 2.0 Specification](https://oauth.net/2/)
- [OpenCode OAuth Plugin](https://github.com/sst/opencode-anthropic-auth)
- Error message: "This credential is only authorized for use with Claude Code"

---

**Last Updated:** 2025-11-11
**Status:** ⚠️ Fundamental Limitation Discovered
**Recommendation:** Use "API Key via OAuth" mode or manual API key setup
