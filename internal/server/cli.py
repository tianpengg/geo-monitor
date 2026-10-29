import argparse
import os
import sys

from internal.config import ServerConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="geo-monitor API service")
    parser.add_argument("--host", default=os.environ.get("GEO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GEO_PORT", "8000")))
    args = parser.parse_args()
    try:
        config = ServerConfig.from_environment()
    except ValueError:
        parser.exit(
            2,
            "Invalid configuration: set GEO_ADMIN_PASSWORD (12+ characters) and GEO_PUBLIC_URL.\n",
        )
    import uvicorn

    from internal.server.app import create_app

    uvicorn.run(create_app(config), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    sys.exit(main())
