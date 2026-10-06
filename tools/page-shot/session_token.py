import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.auth import issue_token
from app.db import row, transaction


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a session token for a local user, for headless page checks")
    parser.add_argument("email")
    args = parser.parse_args()
    with transaction() as conn:
        user = row(conn, "select id, role, municipality_id from app_user where lower(email) = lower(:e)", e=args.email)
    if not user:
        print(f"no user {args.email}", file=sys.stderr)
        return 1
    print(issue_token(user))
    return 0


if __name__ == "__main__":
    sys.exit(main())
