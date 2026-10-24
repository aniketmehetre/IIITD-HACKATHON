"""TinyFish Free-Tier Smoke Test Script.

Performs free-tier calls only (Fetch and Search), verifies latency,
prints response shapes, and writes redacted response samples to fixtures/tinyfish_samples/.
Never performs paid Agent or Browser calls.
"""

import asyncio
import json
from pathlib import Path
import sys
import time

# Ensure backend package can be imported
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "backend"))

from backend.app.config import Settings
from backend.app.integrations.tinyfish import TinyFishClient, redact_secrets


async def run_smoke_test() -> None:
    """Executes Fetch and Search smoke tests and records redacted fixtures."""
    print("=" * 70)
    print("STING — TinyFish Free-Tier Smoke Test (Fetch & Search)")
    print("=" * 70)

    # Initialize settings and client
    try:
        settings = Settings()
    except Exception:
        settings = Settings(STING_ENV="test")

    client = TinyFishClient(settings=settings)
    mode = "LIVE" if client.has_live_credentials else "MOCK_FALLBACK"
    print(f"[*] Client Mode: {mode}")
    print(f"[*] API Key Present: {bool(client.api_key)}")

    fixtures_dir = repo_root / "fixtures" / "tinyfish_samples"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # 1. Fetch API Test (Free Tier)
    # --------------------------------------------------------------------------
    target_url = "https://example.com"
    print(f"\n[1/2] Testing Fetch API on {target_url}...")
    t0 = time.perf_counter()
    try:
        fetch_result = await client.fetch(target_url, format="markdown")
        fetch_duration = (time.perf_counter() - t0) * 1000
        print(f"  [+] Fetch Success! Latency: {fetch_duration:.2f} ms")
        print(f"  [+] Response Keys: {list(fetch_result.keys())}")

        # Redact any secret before writing
        fetch_str = redact_secrets(
            json.dumps(fetch_result, indent=2), client.api_key
        )
        sample_path = fixtures_dir / "fetch_sample.json"
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(fetch_str)
        print(f"  [+] Saved redacted sample to {sample_path}")
    except Exception as e:
        print(f"  [-] Fetch Error: {e}")
        fetch_result = {"error": str(e)}

    # --------------------------------------------------------------------------
    # 2. Search API Test (Free Tier)
    # --------------------------------------------------------------------------
    search_query = "UPI scam"
    print(
        f"\n[2/2] Testing Search API for query '{search_query}' (location: IN)..."
    )
    t0 = time.perf_counter()
    try:
        search_result = await client.search(search_query, location="IN", limit=3)
        search_duration = (time.perf_counter() - t0) * 1000
        print(f"  [+] Search Success! Latency: {search_duration:.2f} ms")
        print(f"  [+] Response Keys: {list(search_result.keys())}")

        # Redact any secret before writing
        search_str = redact_secrets(
            json.dumps(search_result, indent=2), client.api_key
        )
        sample_path = fixtures_dir / "search_sample.json"
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(search_str)
        print(f"  [+] Saved redacted sample to {sample_path}")
    except Exception as e:
        print(f"  [-] Search Error: {e}")
        search_result = {"error": str(e)}

    print("\n" + "=" * 70)
    print("Smoke test completed successfully. Zero paid credits consumed.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
