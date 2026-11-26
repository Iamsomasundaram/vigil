"""Run the demo shop:  python -m projects.autonomous_tester.demo_shop --profile all_bugs --port 8100"""

from __future__ import annotations

import argparse

import uvicorn

from projects.autonomous_tester.demo_shop.app import create_app
from projects.autonomous_tester.demo_shop.config import profile_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Vigil demo shop with seeded bugs")
    parser.add_argument("--profile", default="clean", choices=profile_names())
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--host", default="127.0.0.1", help="keep 127.0.0.1 (the shop is deliberately buggy); Docker uses 0.0.0.0 but publishes the port on localhost only")
    args = parser.parse_args()
    uvicorn.run(create_app(args.profile), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
