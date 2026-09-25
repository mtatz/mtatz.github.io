#!/usr/bin/env python3
"""Sync _data/publications.yml with ORCID and the YouTube channel.

- Adds ORCID works whose DOI (or title, if no DOI) is not yet listed.
  Metadata (authors, venue, year) comes from Crossref when a DOI exists.
- Fills in `youtube` for entries whose title matches a video on the channel.
- Never deletes or overwrites curated fields. DOIs in
  _data/publications_ignore.yml are skipped.

Usage: python3 scripts/sync_publications.py [--dry-run]
"""
import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS = os.path.join(ROOT, "_data", "publications.yml")
IGNORE = os.path.join(ROOT, "_data", "publications_ignore.yml")
CONFIG = os.path.join(ROOT, "_config.yml")
UA = "mtatz.github.io publication sync (mailto:mail@markustatzgern.com)"
TITLE_MATCH = 0.85


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def similar(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def slug(title, year):
    words = [w for w in norm(title).split() if len(w) > 3][:3]
    return "%s_%s" % (year, "_".join(words) or "paper")


def orcid_works(orcid):
    data = json.loads(get("https://pub.orcid.org/v3.0/%s/works" % orcid))
    works = []
    for g in data.get("group", []):
        s = g["work-summary"][0]
        ids = {e["external-id-type"]: e["external-id-value"]
               for e in (g.get("external-ids") or {}).get("external-id") or []}
        date = s.get("publication-date") or {}
        works.append({
            "title": s["title"]["title"]["value"],
            "doi": ids.get("doi"),
            "year": int((date.get("year") or {}).get("value") or 0),
            "venue": (s.get("journal-title") or {}).get("value"),
        })
    return works


def crossref(doi):
    m = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]
    authors = ", ".join(
        " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
        for a in m.get("author", []))
    year = (m.get("issued") or {}).get("date-parts", [[None]])[0][0]
    return {
        "title": (m.get("title") or [""])[0],
        "authors": authors,
        "venue": (m.get("container-title") or [""])[0],
        "year": year,
    }


def youtube_videos(channel):
    xml = get("https://www.youtube.com/feeds/videos.xml?user=" + channel, accept="application/xml")
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(xml)
    return [(e.find("a:title", ns).text, e.find("yt:videoId", ns).text)
            for e in root.findall("a:entry", ns)]


def main():
    dry = "--dry-run" in sys.argv
    cfg = yaml.safe_load(open(CONFIG))
    text = open(PUBS, encoding="utf-8").read()
    header = "".join(l for l in text.splitlines(True) if l.startswith("#"))
    pubs = yaml.safe_load(text) or []
    ignore = set()
    if os.path.exists(IGNORE):
        ignore = {d.lower() for d in (yaml.safe_load(open(IGNORE)) or [])}
    known_dois = {p["doi"].lower() for p in pubs if p.get("doi")}
    report = []

    for w in orcid_works(str(cfg["orcid"])):
        doi = (w["doi"] or "").lower()
        if doi and (doi in known_dois or doi in ignore):
            continue
        if any(similar(w["title"], p["title"]) >= TITLE_MATCH for p in pubs):
            continue
        entry = {"title": w["title"], "authors": "", "venue": w["venue"] or "", "year": w["year"]}
        if doi:
            try:
                entry.update({k: v for k, v in crossref(doi).items() if v})
            except Exception as e:  # keep ORCID data if Crossref fails
                print("Crossref lookup failed for %s: %s" % (doi, e), file=sys.stderr)
        new = {"id": slug(entry["title"], entry["year"]), "title": entry["title"],
               "authors": entry["authors"], "venue": entry["venue"], "year": int(entry["year"] or 0)}
        if doi:
            new["doi"] = doi
        pos = next((i for i, p in enumerate(pubs) if int(p["year"]) <= new["year"]), len(pubs))
        pubs.insert(pos, new)
        known_dois.add(doi)
        report.append("Added: %s (%s) %s — needs image" % (new["title"], new["year"], doi or "no DOI"))

    try:
        videos = youtube_videos(cfg["youtube_channel"])
    except Exception as e:
        videos = []
        print("YouTube feed failed: %s" % e, file=sys.stderr)
    for p in pubs:
        if p.get("youtube"):
            continue
        best = max(videos, key=lambda v: similar(v[0], p["title"]), default=None)
        if best and similar(best[0], p["title"]) >= TITLE_MATCH:
            p["youtube"] = best[1]
            report.append("Video linked: %s -> https://youtu.be/%s" % (p["title"], best[1]))

    print("\n".join(report) or "No changes.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("\n".join("- " + r for r in report) or "No changes.")
    if report and not dry:
        with open(PUBS, "w", encoding="utf-8") as f:
            f.write(header + yaml.safe_dump(pubs, sort_keys=False, allow_unicode=True, width=200))


if __name__ == "__main__":
    main()
