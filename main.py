"""
LOCAL TESTING ONLY. In production, GitHub Actions (.github/workflows/market_intel.yml)
runs `pipeline.py` once per scheduled trigger — there is no always-on process to pay for.
This loop exists purely so you can watch multiple cycles run locally without
setting up a GitHub Actions schedule first.
"""
import time
from config import Config
from pipeline import run_cycle


def main():
    interval_seconds = Config.POLL_INTERVAL_MINUTES * 60
    print(f"[main] Starting market intelligence agent. Polling every {Config.POLL_INTERVAL_MINUTES} min.")

    while True:
        try:
            run_cycle()
        except Exception as e:
            print(f"[main] Cycle failed: {e}")

        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
