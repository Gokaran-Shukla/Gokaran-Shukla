"""Rebuild the "Latest releases" table in README.md from the GitHub REST API.

Lists every public, non-archived repository owned by OWNER, takes its latest
published (non-draft, non-prerelease) release, sorts by publication date and
writes a Markdown table between the RELEASES:START / RELEASES:END markers.
Uses only the standard library; GITHUB_TOKEN raises the API rate limit.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get("OWNER", "Gokaran-Shukla")
README = os.environ.get("README", "README.md")
MAX_ROWS = int(os.environ.get("MAX_ROWS", "10"))
SKIP = {OWNER.lower(), f"{OWNER.lower()}.github.io"}
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28",
                                          "User-Agent": "profile-release-updater"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def repos():
    out, page = [], 1
    while True:
        batch = api(f"/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not batch:
            return out
        out += [r for r in batch if not r["private"] and not r["archived"]
                and r["name"].lower() not in SKIP]
        page += 1


def latest_releases():
    rows = []
    for r in repos():
        rel = api(f"/repos/{OWNER}/{r['name']}/releases/latest")
        if not rel or rel.get("draft") or rel.get("prerelease"):
            continue
        rows.append(dict(repo=r["name"], repo_url=r["html_url"], tag=rel["tag_name"],
                         name=(rel.get("name") or rel["tag_name"]).strip(),
                         url=rel["html_url"], date=rel["published_at"][:10],
                         n=len(api(f"/repos/{OWNER}/{r['name']}/releases?per_page=100") or [])))
    rows.sort(key=lambda x: (x["date"], x["repo"]), reverse=True)
    return rows[:MAX_ROWS]


def table(rows):
    if not rows:
        return "_No published releases yet._"
    lines = ["| Software | Latest release | Date | Releases |", "|---|---|---|---|"]
    for x in rows:
        lines.append(f"| **[{x['repo']}]({x['repo_url']})** | [{x['tag']}]({x['url']}) — {x['name']} "
                     f"| {x['date']} | [{x['n']}]({x['repo_url']}/releases) |")
    return "\n".join(lines)


def main():
    text = open(README, encoding="utf-8").read()
    block = ("<!-- RELEASES:START -->\n" + table(latest_releases()) +
             "\n\n<sub>Updated automatically from the GitHub API.</sub>\n<!-- RELEASES:END -->")
    new, k = re.subn(r"<!-- RELEASES:START -->.*?<!-- RELEASES:END -->", block, text, flags=re.S)
    if k == 0:
        sys.exit("markers not found in README")
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated")
    else:
        print("no change")


if __name__ == "__main__":
    main()
