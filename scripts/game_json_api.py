"""Read or replace catalogue definitions through the maintenance API."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("get", "update"))
    parser.add_argument("--game", required=True)
    parser.add_argument("--variant", default="default")
    parser.add_argument("--file", type=Path, help="Replacement game_json file, required for update.")
    parser.add_argument("--url", default=os.getenv("OBG_CHABANAS_URL", "http://localhost:12000"))
    args = parser.parse_args()
    secret = os.getenv("OBG_ADMIN_SECRET")
    if not secret:
        parser.error("Set OBG_ADMIN_SECRET to the Chabanas administration secret.")
    replacement = None
    if args.action == "update":
        if args.file is None:
            parser.error("update requires --file")
        try:
            replacement = json.loads(args.file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            parser.error(f"Cannot read replacement: {error}")
        if not isinstance(replacement, dict):
            parser.error("game_json must be an object")

    def post(action, body):
        request = Request(
            args.url.rstrip("/") + "/game/json/" + action,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-OBG-Admin-Secret": secret},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    selector = {"game_name": args.game, "variant_name": args.variant}
    try:
        current = post("get", selector)
        if args.action == "get":
            print(json.dumps(current, ensure_ascii=False, indent=2))
        else:
            result = post("update", {
                **selector, "game_json": replacement,
                "expected_updated_at": current["updated_at"],
            })
            print(json.dumps({key: value for key, value in result.items() if key != "game_json"},
                             ensure_ascii=False, indent=2))
    except HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError, KeyError) as error:
        print(f"API request failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
