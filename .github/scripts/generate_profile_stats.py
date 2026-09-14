#!/usr/bin/env python3
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = "EnroXD1"
API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
OUT = Path("profile")

BG = "#0d1117"
CARD = "#0d1117"
BORDER = "#30363d"
TEXT = "#f0f6fc"
MUTED = "#8b949e"
CYAN = "#00BDF1"
ORANGE = "#FE4408"
EMPTY = "#161b22"
LEVELS = ["#063443", "#07566d", "#0087ad", CYAN, ORANGE]
LANG_COLORS = [CYAN, ORANGE, "#58a6ff", "#a371f7", "#3fb950", "#d29922"]


def request_json(url, *, data=None):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "EnroXD1-profile-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "EnroXD1-profile-stats",
    }
    req = urllib.request.Request(GRAPHQL, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]


def write_svg(name, body, width, height):
    OUT.mkdir(parents=True, exist_ok=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<style>
text {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
.title {{ fill:{TEXT}; font-size:18px; font-weight:700; }}
.label {{ fill:{MUTED}; font-size:13px; }}
.value {{ fill:{TEXT}; font-size:22px; font-weight:700; }}
.small {{ fill:{MUTED}; font-size:11px; }}
</style>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="10" fill="{CARD}" stroke="{BORDER}"/>
{body}
</svg>'''
    (OUT / name).write_text(svg, encoding="utf-8")


def get_repositories():
    repos = []
    for page in range(1, 5):
        batch = request_json(f"{API}/users/{USERNAME}/repos?type=owner&sort=updated&per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            break
    return repos


def contribution_data():
    query = '''
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                weekday
              }
            }
          }
        }
      }
    }
    '''
    data = graphql(query, {"login": USERNAME})
    return data["user"]["contributionsCollection"]["contributionCalendar"]


def make_stats(profile, repos, contributions):
    own = [r for r in repos if not r.get("fork")]
    stars = sum(r.get("stargazers_count", 0) for r in own)
    forks = sum(r.get("forks_count", 0) for r in own)
    total_contrib = contributions.get("totalContributions", 0)
    items = [
        ("Followers", profile.get("followers", 0)),
        ("Public repos", profile.get("public_repos", 0)),
        ("Total stars", stars),
        ("Year contributions", total_contrib),
    ]

    body = [f'<text x="24" y="34" class="title">GitHub Statistics</text>',
            f'<rect x="24" y="47" width="72" height="3" rx="1.5" fill="{CYAN}"/>',
            f'<rect x="98" y="47" width="26" height="3" rx="1.5" fill="{ORANGE}"/>']
    positions = [(24, 82), (230, 82), (24, 137), (230, 137)]
    for (label, value), (x, y) in zip(items, positions):
        body.append(f'<text x="{x}" y="{y}" class="label">{escape(str(label))}</text>')
        body.append(f'<text x="{x}" y="{y+27}" class="value">{escape(str(value))}</text>')
    body.append(f'<text x="404" y="164" text-anchor="end" class="small">auto-updated</text>')
    write_svg("stats.svg", "\n".join(body), 430, 180)


def make_languages(repos):
    totals = Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = request_json(repo["languages_url"])
        except Exception as exc:
            print(f"languages failed for {repo.get('name')}: {exc}")
            continue
        totals.update(langs)

    top = totals.most_common(6)
    total_bytes = sum(v for _, v in top) or 1
    body = [f'<text x="24" y="34" class="title">Top Languages</text>',
            f'<rect x="24" y="47" width="72" height="3" rx="1.5" fill="{CYAN}"/>',
            f'<rect x="98" y="47" width="26" height="3" rx="1.5" fill="{ORANGE}"/>']

    bar_x, bar_y, bar_w, bar_h = 24, 66, 382, 10
    current = bar_x
    for i, (name, value) in enumerate(top):
        width = bar_w * value / total_bytes
        body.append(f'<rect x="{current:.1f}" y="{bar_y}" width="{max(width, 1):.1f}" height="{bar_h}" fill="{LANG_COLORS[i % len(LANG_COLORS)]}"/>')
        current += width

    for i, (name, value) in enumerate(top):
        col = i % 2
        row = i // 2
        x = 24 + col * 205
        y = 103 + row * 24
        pct = value / total_bytes * 100
        color = LANG_COLORS[i % len(LANG_COLORS)]
        body.append(f'<circle cx="{x+5}" cy="{y-4}" r="5" fill="{color}"/>')
        body.append(f'<text x="{x+17}" y="{y}" class="label">{escape(name)} {pct:.1f}%</text>')

    if not top:
        body.append('<text x="24" y="110" class="label">No language data yet</text>')
    write_svg("top-langs.svg", "\n".join(body), 430, 180)


def contribution_color(count, max_count):
    if count <= 0:
        return EMPTY
    if max_count <= 1:
        return LEVELS[3]
    ratio = count / max_count
    if ratio <= 0.20:
        return LEVELS[0]
    if ratio <= 0.40:
        return LEVELS[1]
    if ratio <= 0.65:
        return LEVELS[2]
    if ratio <= 0.85:
        return LEVELS[3]
    return LEVELS[4]


def make_activity(contributions):
    weeks = contributions.get("weeks", [])[-53:]
    days = [d for w in weeks for d in w.get("contributionDays", [])]
    max_count = max((d.get("contributionCount", 0) for d in days), default=1)
    total = contributions.get("totalContributions", 0)

    body = [
        f'<text x="24" y="34" class="title">Contribution Activity</text>',
        f'<text x="896" y="34" text-anchor="end" class="label">{total} contributions in the last year</text>',
        f'<rect x="24" y="47" width="72" height="3" rx="1.5" fill="{CYAN}"/>',
        f'<rect x="98" y="47" width="26" height="3" rx="1.5" fill="{ORANGE}"/>',
    ]

    x0, y0, cell, gap = 71, 70, 11, 3
    body.extend([
        f'<text x="24" y="{y0+cell}" class="small">Sun</text>',
        f'<text x="24" y="{y0+2*(cell+gap)+cell}" class="small">Tue</text>',
        f'<text x="24" y="{y0+4*(cell+gap)+cell}" class="small">Thu</text>',
        f'<text x="24" y="{y0+6*(cell+gap)+cell}" class="small">Sat</text>',
    ])

    for wi, week in enumerate(weeks):
        for day in week.get("contributionDays", []):
            weekday = int(day.get("weekday", 0))
            count = int(day.get("contributionCount", 0))
            x = x0 + wi * (cell + gap)
            y = y0 + weekday * (cell + gap)
            color = contribution_color(count, max_count)
            date = escape(day.get("date", ""))
            body.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}"><title>{date}: {count} contributions</title></rect>')

    legend_x, legend_y = 763, 190
    body.append(f'<text x="{legend_x-42}" y="{legend_y}" class="small">Less</text>')
    for i, color in enumerate([EMPTY] + LEVELS):
        body.append(f'<rect x="{legend_x+i*16}" y="{legend_y-10}" width="11" height="11" rx="2" fill="{color}"/>')
    body.append(f'<text x="{legend_x+103}" y="{legend_y}" class="small">More</text>')
    write_svg("activity.svg", "\n".join(body), 920, 210)


def main():
    profile = request_json(f"{API}/users/{USERNAME}")
    repos = get_repositories()
    try:
        contributions = contribution_data()
    except Exception as exc:
        print(f"GraphQL contribution query failed: {exc}")
        contributions = {"totalContributions": 0, "weeks": []}

    make_stats(profile, repos, contributions)
    make_languages(repos)
    make_activity(contributions)
    print("Generated profile/stats.svg, profile/top-langs.svg, profile/activity.svg")


if __name__ == "__main__":
    main()
