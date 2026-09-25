#!/usr/bin/env python3
"""Sync _data/publications.yml with ORCID, Crossref, Unpaywall and YouTube.

- Adds ORCID works whose DOI (or title, if no DOI) is not yet listed.
  Metadata (authors, venue, year) comes from Crossref when a DOI exists.
- Fills in `youtube` for entries whose title matches a video on the channel.
- Fills in `open_access` / `oa_pdf` from Unpaywall for entries without an own PDF.
- Writes BibTeX for entries missing in _data/bibtex.yml, built from Crossref
  metadata, and reports fields the publisher metadata does not provide.
- Never deletes or overwrites curated fields or existing BibTeX (unless
  --refresh-bibtex). DOIs in _data/publications_ignore.yml are skipped.

Usage: python3 scripts/sync_publications.py [--dry-run] [--refresh-bibtex]
"""
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS = os.path.join(ROOT, "_data", "publications.yml")
BIB = os.path.join(ROOT, "_data", "bibtex.yml")
IGNORE = os.path.join(ROOT, "_data", "publications_ignore.yml")
CONFIG = os.path.join(ROOT, "_config.yml")
EMAIL = "mail@markustatzgern.com"
UA = "mtatz.github.io publication sync (mailto:%s)" % EMAIL
TITLE_MATCH = 0.85
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
PROTECT = {"Fitts", "Christmas", "Carnegie", "Museum", "Natural", "History"}


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def similar(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def ascii_fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def slug(title, year):
    words = [w for w in norm(title).split() if len(w) > 3][:3]
    return "%s_%s" % (year, "_".join(words) or "paper")


# --- remote sources -------------------------------------------------------

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
    return json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]


def unpaywall(doi):
    return json.loads(get("https://api.unpaywall.org/v2/%s?email=%s" % (urllib.parse.quote(doi), EMAIL)))


def youtube_videos(channel):
    xml = get("https://www.youtube.com/feeds/videos.xml?user=" + channel, accept="application/xml")
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(xml)
    return [(e.find("a:title", ns).text, e.find("yt:videoId", ns).text)
            for e in root.findall("a:entry", ns)]


# --- BibTeX ---------------------------------------------------------------

def publisher_name(p):
    if not p:
        return None
    if "Association for Computing Machinery" in p or p.startswith("ACM"):
        return "Association for Computing Machinery"
    if "IEEE" in p or "Institute of Electrical" in p:
        return "IEEE"
    return re.sub(r"\s+(BV|B\.V\.|Ltd|Inc\.?)$", "", p)


def tex(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", "``").replace("”", "''")
    return re.sub(r"([&%#_$])", r"\\\1", s)


def protect_title(t):
    def fix(m):
        w = m.group(0)
        core = re.sub(r"[^A-Za-z0-9]", "", w)
        caps = sum(c.isupper() for c in core[1:])
        if caps or core in PROTECT or (any(c.isdigit() for c in core) and any(c.isalpha() for c in core)):
            return "{%s}" % w
        return w
    return re.sub(r"[A-Za-z0-9][A-Za-z0-9\-]*", fix, tex(t))


def pages(p):
    return re.sub(r"\s*[-–—]+\s*", "--", p) if p else None


def cite_key(authors, year, title, used):
    fam = authors[0].split(",")[0] if authors else "anon"
    fam = re.sub(r"[^a-z]", "", ascii_fold(fam).lower())
    word = next((w for w in norm(ascii_fold(title)).split()
                 if w not in {"a", "an", "the", "on", "of", "for", "towards", "toward", "and"}), "paper")
    key, n = "%s%s%s" % (fam, year, word), 1
    while key in used:
        n += 1
        key = "%s%s%s%s" % (fam, year, word, chr(96 + n))
    used.add(key)
    return key


def render(kind, key, fields):
    order = ["author", "title", "booktitle", "journal", "series", "volume", "number", "pages", "year", "month", "publisher", "address", "location", "isbn", "issn",
             "doi", "url", "note"]
    lines = ["@%s{%s," % (kind, key)]
    for f in order:
        v = fields.get(f)
        if v:
            lines.append("  %s = {%s}," % (f, v) if f != "month" else "  month = %s," % v)
    lines[-1] = lines[-1].rstrip(",")
    return "\n".join(lines + ["}"])


def bibtex_from_crossref(m, pub, used):
    authors = ["%s, %s" % (a["family"], a["given"]) if a.get("given") else a.get("family") or a.get("name")
               for a in m.get("author", [])]
    date = (m.get("issued") or {}).get("date-parts", [[None]])[0]
    year = date[0]
    month = MONTHS[date[1] - 1] if len(date) > 1 and date[1] else None
    event = m.get("event") or {}
    container = (m.get("container-title") or [""])[0]
    kind = "inproceedings" if m.get("type") in ("proceedings-article", "book-chapter") else "article"
    f = {
        "author": " and ".join(tex(a) for a in authors),
        "title": protect_title((m.get("title") or [pub["title"]])[0]),
        "year": year, "month": month,
        "pages": pages(m.get("page")),
        "publisher": tex(publisher_name(m.get("publisher")) or ""),
        "doi": m.get("DOI"), "url": "https://doi.org/" + m.get("DOI", ""),
    }
    if kind == "inproceedings":
        f["booktitle"] = tex(container)
        f["series"] = tex(event.get("acronym", "")) if f["publisher"].startswith("Association") else None
        loc = event.get("location")
        f["location"] = tex(re.sub(r"\s+,", ",", loc)) if loc else None
        f["address"] = "New York, NY, USA" if f["publisher"].startswith("Association") else None
        f["isbn"] = (m.get("ISBN") or [None])[0]
    else:
        f["journal"] = tex(container)
        f["volume"], f["number"] = m.get("volume"), m.get("issue")
        f["issn"] = (m.get("ISSN") or [None])[0]
    need = ["author", "title", "year", "publisher"] + (
        ["booktitle", "pages"] if kind == "inproceedings" else ["journal", "volume", "pages"])
    missing = [x for x in need if not f.get(x)]
    return render(kind, cite_key(authors, year, f["title"], used), f), missing


def bibtex_from_pub(pub, used, extra=None):
    """Fallback for works without Crossref metadata; built from the site data."""
    authors = ["%s, %s" % (n.split()[-1], " ".join(n.split()[:-1])) for n in pub["authors"].split(", ")]
    f = {"author": " and ".join(tex(a) for a in authors), "title": protect_title(pub["title"]),
         "booktitle": tex(pub["venue"]), "year": pub["year"],
         "doi": pub.get("doi"), "url": "https://doi.org/" + pub["doi"] if pub.get("doi") else pub.get("url")}
    f.update(extra or {})
    missing = [x for x in ("pages", "publisher") if not f.get(x)]
    return render("inproceedings", cite_key(authors, pub["year"], pub["title"], used), f), missing


# --- main -----------------------------------------------------------------

def _str(dumper, s):
    style = "|" if "\n" in s else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=style)


yaml.SafeDumper.add_representer(str, _str)


def dump(path, data, header=""):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=200))


def main():
    dry = "--dry-run" in sys.argv
    refresh = "--refresh-bibtex" in sys.argv
    cfg = yaml.safe_load(open(CONFIG))
    text = open(PUBS, encoding="utf-8").read()
    header = "".join(l for l in text.splitlines(True) if l.startswith("#"))
    pubs = yaml.safe_load(text) or []
    bib = {} if refresh or not os.path.exists(BIB) else (yaml.safe_load(open(BIB, encoding="utf-8")) or {})
    ignore = set()
    if os.path.exists(IGNORE):
        ignore = {d.lower() for d in (yaml.safe_load(open(IGNORE)) or [])}
    known_dois = {p["doi"].lower() for p in pubs if p.get("doi")}
    report, warnings = [], []

    # 1. new works from ORCID
    for w in orcid_works(str(cfg["orcid"])):
        doi = (w["doi"] or "").lower()
        if doi and (doi in known_dois or doi in ignore):
            continue
        if any(similar(w["title"], p["title"]) >= TITLE_MATCH for p in pubs):
            continue
        entry = {"title": w["title"], "authors": "", "venue": w["venue"] or "", "year": w["year"]}
        if doi:
            try:
                m = crossref(doi)
                date = (m.get("issued") or {}).get("date-parts", [[None]])[0]
                entry.update({k: v for k, v in {
                    "title": (m.get("title") or [""])[0],
                    "authors": ", ".join(" ".join(x for x in (a.get("given"), a.get("family")) if x)
                                         for a in m.get("author", [])),
                    "venue": (m.get("container-title") or [""])[0],
                    "year": date[0]}.items() if v})
            except Exception as e:  # keep ORCID data if Crossref fails
                warnings.append("Crossref lookup failed for %s: %s" % (doi, e))
        new = {"id": slug(entry["title"], entry["year"]), "title": entry["title"],
               "authors": entry["authors"], "venue": entry["venue"], "year": int(entry["year"] or 0)}
        abbr = re.findall(r"\(([^()]+)\)", new["venue"])
        if abbr:
            new["badge"] = abbr[-1]
        if doi:
            new["doi"] = doi
        pos = next((i for i, p in enumerate(pubs) if int(p["year"]) <= new["year"]), len(pubs))
        pubs.insert(pos, new)
        known_dois.add(doi)
        report.append("Added: %s (%s) %s. Needs image, badge and venue check" % (new["title"], new["year"], doi or "no DOI"))

    # 2. YouTube videos
    try:
        videos = youtube_videos(cfg["youtube_channel"])
    except Exception as e:
        videos = []
        warnings.append("YouTube feed failed: %s" % e)
    for p in pubs:
        if p.get("youtube"):
            continue
        best = max(videos, key=lambda v: similar(v[0], p["title"]), default=None)
        if best and similar(best[0], p["title"]) >= TITLE_MATCH:
            p["youtube"] = best[1]
            report.append("Video linked: %s -> https://youtu.be/%s" % (p["title"], best[1]))

    # 3. Open access via Unpaywall
    for p in pubs:
        if not p.get("doi") or p.get("pdf") or p.get("open_access"):
            continue
        try:
            u = unpaywall(p["doi"])
        except Exception:
            continue
        loc = u.get("best_oa_location")
        if u.get("is_oa") and loc:
            p["open_access"] = True
            if loc.get("url_for_pdf"):
                p["oa_pdf"] = loc["url_for_pdf"]
            report.append("Open access: %s" % p["title"])

    # 4. BibTeX
    used = {re.match(r"@\w+\{([^,]+),", b).group(1) for b in bib.values()}
    for p in pubs:
        if p["id"] in bib:
            continue
        try:
            if not p.get("doi"):
                raise LookupError
            b, missing = bibtex_from_crossref(crossref(p["doi"]), p, used)
        except Exception:
            b, missing = bibtex_from_pub(p, used)
            missing.append("built from site data, no Crossref record")
        bib[p["id"]] = b
        report.append("BibTeX created: %s" % p["id"])
        if missing:
            warnings.append("BibTeX %s: missing %s" % (p["id"], ", ".join(missing)))

    out = "\n".join(report + ["WARNING " + w for w in warnings]) or "No changes."
    print(out)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write("\n".join("- " + r for r in out.splitlines()))
    if report and not dry:
        dump(PUBS, pubs, header)
        ordered = {p["id"]: bib[p["id"]] for p in pubs if p["id"] in bib}
        dump(BIB, ordered, "# BibTeX per publication id. Generated from Crossref; manual edits are kept.\n")


if __name__ == "__main__":
    main()
