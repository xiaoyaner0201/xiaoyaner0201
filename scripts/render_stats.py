#!/usr/bin/env python3
"""Redraw the upstream-contribution cards from live GitHub data.

Counts merged pull requests authored by the profile owner in repositories
the owner does not own, groups them by repository, and writes:
  assets/stats.json
  assets/stats-{light,dark}.svg
Runs in GitHub Actions with GITHUB_TOKEN, or locally with `gh auth token`.
Standard library only.
"""
import json
import os
import pathlib
import subprocess
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

USER = "xiaoyaner0201"
OWN = {USER.lower(), "xiaoyaner-home"}
ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


TOKEN = token()


def get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def merged_prs():
    q = urllib.parse.quote(f"author:{USER} is:pr is:merged")
    items, page = [], 1
    while True:
        d = get(f"https://api.github.com/search/issues?q={q}&per_page=100&page={page}")
        items += d["items"]
        if len(items) >= d["total_count"] or not d["items"] or page >= 10:
            return items
        page += 1


def short(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def search_count(q):
    return get("https://api.github.com/search/issues?q=" + urllib.parse.quote(q) + "&per_page=1")["total_count"]


def main():
    prs = merged_prs()
    by_repo = {}
    for p in prs:
        full = p["repository_url"].split("/repos/")[1]
        if full.split("/")[0].lower() in OWN:
            continue
        by_repo.setdefault(full, 0)
        by_repo[full] += 1
    repos = []
    for full, n in by_repo.items():
        meta = get(f"https://api.github.com/repos/{full}")
        repos.append({"repo": meta["full_name"], "merged": n, "stars": meta["stargazers_count"]})
    repos.sort(key=lambda r: (-r["merged"], -r["stars"]))
    stats = {
        "merged_upstream": sum(r["merged"] for r in repos),
        "repos": len(repos),
        "open_upstream": search_count(f"author:{USER} is:pr is:open " + " ".join(f"-user:{o}" for o in sorted(OWN))),
        "top": repos[:6],
    }
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    for theme in ("light", "dark"):
        (ASSETS / f"stats-{theme}.svg").write_text(render(stats, theme))
    print(json.dumps({k: v for k, v in stats.items() if k != "top"}))


THEMES = {
    "light": dict(bg="#fdf9fc", line="#ead9ee", ink="#3b2f45", soft="#7d6d89", accent="#9b6fb3", bar="#e9d8f1"),
    "dark": dict(bg="#1d1823", line="#3a2f44", ink="#f1e8f6", soft="#b6a6c3", accent="#c9a0e0", bar="#3a2d47"),
}


def render(s, theme):
    c = THEMES[theme]
    font = "-apple-system,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif"
    w, h = 1000, 300
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="18" fill="{c["bg"]}" stroke="{c["line"]}" stroke-width="2"/>']
    nums = [(s["merged_upstream"], "merged PRs"), (s["repos"], "projects"), (s["open_upstream"], "open, in review")]
    for i, (v, label) in enumerate(nums):
        x = 48 + i * 152
        out.append(f'<text x="{x}" y="92" font-family="{font}" font-size="44" font-weight="700" fill="{c["accent"]}">{v}</text>')
        out.append(f'<text x="{x}" y="120" font-family="{font}" font-size="14" fill="{c["soft"]}">{escape(label)}</text>')
    out.append(f'<text x="48" y="196" font-family="{font}" font-size="15" fill="{c["soft"]}">Pull requests to projects I don\'t own.</text>')
    out.append(f'<text x="48" y="220" font-family="{font}" font-size="15" fill="{c["soft"]}">在别人的项目里被合并的 PR · 每天从 GitHub API 刷新</text>')
    out.append(f'<path d="M520 36 V264" stroke="{c["line"]}" stroke-width="2"/>')
    top = s["top"]
    mx = max((r["merged"] for r in top), default=1)
    for i, r in enumerate(top):
        y = 58 + i * 38
        bw = max(10, int(110 * (r["merged"] / mx) ** 0.5))
        out.append(f'<text x="552" y="{y}" font-family="{font}" font-size="15" fill="{c["ink"]}">{escape(r["repo"])}</text>')
        out.append(f'<text x="552" y="{y+17}" font-family="{font}" font-size="12" fill="{c["soft"]}">★ {short(r["stars"])}</text>')
        out.append(f'<rect x="830" y="{y-12}" width="{bw}" height="14" rx="7" fill="{c["bar"]}"/>')
        out.append(f'<text x="{838+bw}" y="{y}" font-family="{font}" font-size="14" font-weight="600" fill="{c["accent"]}">{r["merged"]}</text>')
    out.append("</svg>\n")
    return "\n".join(out)


if __name__ == "__main__":
    main()
