import argparse
from pathlib import Path

from internal.config import CollectorConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="geo-monitor independent log collector")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="preflight without modifying state")
    parser.add_argument("--once", action="store_true", help="process one available batch and exit")
    args = parser.parse_args()
    try:
        config = CollectorConfig.load(args.config)
    except (ValueError, OSError):
        parser.exit(2, "Invalid collector configuration; check JSON, required fields and HTTP permission.\n")
    from internal.collector.locking import source_lock
    from internal.collector.runtime import run

    try:
        if args.check:
            run(config, check=True)
        else:
            with source_lock(config.state_path):
                run(config, once=args.once)
    except OSError:
        parser.exit(
            2, "Collector state is locked or inaccessible; run only one collector per source.\n"
        )


if __name__ == "__main__":
    main()
