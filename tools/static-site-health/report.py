import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

WORKFLOW = "static-site"
ISSUE_TITLE = "static-site health"
MARKER_STEPS = {
    "Hostinger upload missed": "hostinger_missed",
    "Region setup failed": "region_failed",
}


@dataclass
class Summary:
    finished: int = 0
    succeeded: int = 0
    failed: list[int] = field(default_factory=list)
    hostinger_missed: list[int] = field(default_factory=list)
    region_failed: list[int] = field(default_factory=list)

    @property
    def bad(self) -> bool:
        return bool(self.failed or self.hostinger_missed or self.region_failed)


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def runs_since(repo: str, since: datetime) -> list[dict]:
    listed = json.loads(
        gh("run", "list", "--repo", repo, "--workflow", WORKFLOW, "--limit", "300", "--json", "databaseId,status,conclusion,createdAt")
    )
    return [r for r in listed if r["status"] == "completed" and parse_time(r["createdAt"]) >= since]


def ran_steps(repo: str, run_id: int) -> set[str]:
    jobs = json.loads(gh("run", "view", str(run_id), "--repo", repo, "--json", "jobs"))["jobs"]
    return {s["name"] for j in jobs for s in j.get("steps", []) if s.get("conclusion") == "success"}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def summarize(runs: list[dict], steps_of) -> Summary:
    summary = Summary()
    for run in runs:
        if run["conclusion"] in ("cancelled", "skipped"):
            continue
        summary.finished += 1
        if run["conclusion"] == "success":
            summary.succeeded += 1
        else:
            summary.failed.append(run["databaseId"])
        for step in steps_of(run["databaseId"]) & MARKER_STEPS.keys():
            getattr(summary, MARKER_STEPS[step]).append(run["databaseId"])
    return summary


def report(summary: Summary, repo: str, hours: int) -> str:
    def links(ids: list[int]) -> str:
        return ", ".join(f"[{i}](https://github.com/{repo}/actions/runs/{i})" for i in ids)

    lines = [
        f"Last {hours} h: {summary.succeeded} of {summary.finished} runs succeeded.",
        "",
        f"- Failed runs (site not updated): {len(summary.failed)}" + (f" ({links(summary.failed)})" if summary.failed else ""),
        f"- Hostinger upload missed (synterra.cl/maule kept the previous version): {len(summary.hostinger_missed)}"
        + (f" ({links(summary.hostinger_missed)})" if summary.hostinger_missed else ""),
        f"- Region setup failed (run continued on the restored database): {len(summary.region_failed)}"
        + (f" ({links(summary.region_failed)})" if summary.region_failed else ""),
    ]
    return "\n".join(lines)


def health_issue(repo: str) -> int:
    found = json.loads(
        gh("issue", "list", "--repo", repo, "--state", "all", "--search", f'in:title "{ISSUE_TITLE}"', "--json", "number,title")
    )
    for issue in found:
        if issue["title"] == ISSUE_TITLE:
            return issue["number"]
    url = gh(
        "issue", "create", "--repo", repo, "--title", ISSUE_TITLE,
        "--body", "Daily digest of failed static-site runs. A comment appears only on days with a failure.",
    ).strip()
    return int(url.rsplit("/", 1)[1])


def main() -> int:
    parser = argparse.ArgumentParser(description="Comment on the static-site health issue when the last day had failures")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    summary = summarize(runs_since(args.repo, since), lambda run_id: ran_steps(args.repo, run_id))
    body = report(summary, args.repo, args.hours)
    print(body)
    if summary.bad and not args.dry_run:
        gh("issue", "comment", str(health_issue(args.repo)), "--repo", args.repo, "--body", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
