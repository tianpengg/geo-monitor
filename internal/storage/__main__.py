import argparse
from pathlib import Path

from internal.storage.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="Consistent SQLite maintenance")
    parser.add_argument("action", choices=["backup"])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.database.is_file() or args.output.exists():
        parser.exit(2, "Database must exist and output must be a new backup file.\n")
    Database(args.database).backup(args.output)


if __name__ == "__main__":
    main()
