#!/usr/bin/env python3
"""Detailed startup profiling for CDD Agent CLI.

This script measures import times for all modules to identify bottlenecks.
"""

import importlib
import sys
import time
from typing import Dict


def profile_module_import(module_name: str, clear_cache: bool = True) -> float:
    """Profile the import time of a specific module.

    Args:
        module_name: Name of module to import
        clear_cache: Whether to clear cached imports first

    Returns:
        Import time in milliseconds
    """
    if clear_cache:
        # Clear the module and its dependencies from cache
        modules_to_clear = [
            name for name in sys.modules.keys() if name.startswith(module_name)
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

    start = time.perf_counter()
    try:
        importlib.import_module(module_name)
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed
    except ImportError as e:
        print(f"ERROR importing {module_name}: {e}")
        return -1


def profile_third_party_imports() -> Dict[str, float]:
    """Profile import times for third-party dependencies."""
    dependencies = [
        "anthropic",
        "openai",
        "click",
        "yaml",
        "rich",
        "httpx",
        "pydantic",
        "textual",
    ]

    results = {}
    for dep in dependencies:
        # Clear all cached modules
        modules_to_clear = [name for name in list(sys.modules.keys())]
        for mod in modules_to_clear:
            if dep in mod:
                del sys.modules[mod]

        import_time = profile_module_import(dep, clear_cache=False)
        results[dep] = import_time

    return results


def profile_cdd_agent_modules() -> Dict[str, float]:
    """Profile import times for CDD Agent modules."""
    modules = [
        "cdd_agent.config",
        "cdd_agent.tools",
        "cdd_agent.auth",
        "cdd_agent.context",
        "cdd_agent.approval",
        "cdd_agent.agent",
        "cdd_agent.cli",
        "cdd_agent.tui",
        "cdd_agent.ui",
    ]

    results = {}
    for module in modules:
        # Clear CDD Agent modules but keep third-party cached
        modules_to_clear = [
            name for name in sys.modules.keys() if name.startswith("cdd_agent")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]

        import_time = profile_module_import(module, clear_cache=False)
        results[module] = import_time

    return results


def check_eager_loading():
    """Check which provider SDKs are loaded at import time."""
    # Clear everything
    modules_to_clear = list(sys.modules.keys())
    for mod in modules_to_clear:
        if "anthropic" in mod or "openai" in mod or "cdd_agent" in mod:
            if mod in sys.modules:
                del sys.modules[mod]

    print("\n" + "=" * 70)
    print("EAGER LOADING CHECK")
    print("=" * 70)

    # Import CLI
    import cdd_agent.cli  # noqa: F401

    # Check what got loaded
    anthropic_modules = [name for name in sys.modules.keys() if "anthropic" in name]
    openai_modules = [name for name in sys.modules.keys() if "openai" in name]

    if anthropic_modules:
        print("\n⚠️  ANTHROPIC SDK LOADED AT IMPORT TIME")
        print(f"   Modules: {len(anthropic_modules)}")
        print(f"   First 5: {anthropic_modules[:5]}")
    else:
        print("\n✅ Anthropic SDK NOT loaded at import (good!)")

    if openai_modules:
        print("\n⚠️  OPENAI SDK LOADED AT IMPORT TIME")
        print(f"   Modules: {len(openai_modules)}")
        print(f"   First 5: {openai_modules[:5]}")
    else:
        print("\n✅ OpenAI SDK NOT loaded at import (good!)")


def main():
    """Run full performance profiling."""
    print("=" * 70)
    print("CDD AGENT CLI STARTUP PERFORMANCE PROFILING")
    print("=" * 70)

    # 1. Profile third-party imports
    print("\n" + "=" * 70)
    print("THIRD-PARTY LIBRARY IMPORT TIMES")
    print("=" * 70)

    third_party_times = profile_third_party_imports()
    total_third_party = 0

    for lib, time_ms in sorted(
        third_party_times.items(), key=lambda x: x[1], reverse=True
    ):
        if time_ms > 0:
            print(f"{lib:20s} {time_ms:8.1f}ms")
            total_third_party += time_ms
        else:
            print(f"{lib:20s} {'FAILED':>8s}")

    print(f"{'-' * 70}")
    print(f"{'TOTAL':20s} {total_third_party:8.1f}ms")

    # 2. Profile CDD Agent modules
    print("\n" + "=" * 70)
    print("CDD AGENT MODULE IMPORT TIMES")
    print("=" * 70)

    module_times = profile_cdd_agent_modules()
    total_module_time = 0

    for module, time_ms in sorted(
        module_times.items(), key=lambda x: x[1], reverse=True
    ):
        if time_ms > 0:
            print(f"{module:30s} {time_ms:8.1f}ms")
            total_module_time += time_ms
        else:
            print(f"{module:30s} {'FAILED':>8s}")

    print(f"{'-' * 70}")
    print(f"{'TOTAL':30s} {total_module_time:8.1f}ms")

    # 3. Check for eager loading
    check_eager_loading()

    # 4. Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Third-party imports: {total_third_party:.1f}ms")
    print(f"CDD Agent modules:   {total_module_time:.1f}ms")
    print(f"Total measured:      {total_third_party + total_module_time:.1f}ms")
    print("\nTarget: <200ms (ideal: <100ms)")
    print(f"Current: {total_third_party + total_module_time:.1f}ms")

    if total_third_party + total_module_time > 200:
        overhead = total_third_party + total_module_time - 200
        print(f"Overhead: {overhead:.1f}ms ({overhead/2:.0f}% over target)")
    else:
        print("✅ Within target!")

    # 5. Recommendations
    print("\n" + "=" * 70)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("=" * 70)

    # Find top bottlenecks
    all_times = {**third_party_times, **module_times}
    top_bottlenecks = sorted(all_times.items(), key=lambda x: x[1], reverse=True)[:5]

    print("\nTop 5 bottlenecks:")
    for i, (name, time_ms) in enumerate(top_bottlenecks, 1):
        if time_ms > 0:
            percentage = (time_ms / (total_third_party + total_module_time)) * 100
            print(f"{i}. {name}: {time_ms:.1f}ms ({percentage:.1f}%)")

    print("\nActions:")
    if any("anthropic" in name for name, _ in top_bottlenecks):
        print("  - Implement lazy loading for Anthropic SDK")
    if any("openai" in name for name, _ in top_bottlenecks):
        print("  - Implement lazy loading for OpenAI SDK")
    if any("textual" in name for name, _ in top_bottlenecks):
        print("  - Consider deferring Textual import until TUI is used")
    if any("cdd_agent.cli" in name for name, _ in top_bottlenecks):
        print("  - Optimize CLI module structure (reduce dependencies)")


if __name__ == "__main__":
    main()
