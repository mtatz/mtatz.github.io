# Website of Markus Tatzgern

Single-page Jekyll site, deployed to GitHub Pages (custom domain markustatzgern.com) by
`.github/workflows/pages.yml` on every push to `main`. No subpages.

## Structure
- `index.html` – bio, publications, theses, patents. Bio text is edited here.
- `_data/publications.yml` – all publications, newest first. The page groups them by `year`
  and keeps file order within a year.
- `_data/theses.yml`, `_data/patents.yml`, `_data/links.yml` – other sections and sidebar links.
- `_data/publications_ignore.yml` – ORCID DOIs that must not be added to the site.
- `_includes/publication.html` – markup of one publication entry.
- `assets/css/site.css` – all styles (do not name it `style.css`; the default GitHub Pages theme overwrites that path).
- `papers/` – teaser images (`<id>.png|jpg|webp`) and author PDFs (`<id>.pdf`). Keep old file names: external links point to them.
- `scripts/sync_publications.py` – adds new ORCID works (metadata via Crossref) and links matching videos
  from the YouTube channel `mtatzgern`. Runs weekly via `.github/workflows/sync-publications.yml` and opens a PR.

## Publication entry format
```yaml
- id: 2025_arkward               # YEAR_shortname, unique, used as anchor and file name
  title: ...
  authors: A, B, Markus Tatzgern  # comma-separated, full names
  venue: Full Venue Name (ABBR)   # no pages, no year
  year: 2025
  image: papers/2025_arkward.png  # optional; without it papers/placeholder.svg is shown
  doi: 10.1145/3743740            # without https://doi.org/
  pdf: papers/2025_arkward.pdf    # optional, author version
  youtube: Y_DVrMH3XDs            # optional, video ID only
  award: Honorable Mention for Best Paper   # optional, shown as badge
  url: https://...                # optional project page
```
Venue style: `ACM CHI Conference on Human Factors in Computing Systems (CHI)`,
`IEEE International Symposium on Mixed and Augmented Reality (ISMAR)`, etc. Reuse existing venue strings.

## Common tasks
- **Add a paper:** run `python3 scripts/sync_publications.py` (needs network access to pub.orcid.org,
  api.crossref.org, youtube.com), or add the entry by hand from the DOI via Crossref. Normalize the venue.
  Save the teaser image as `papers/<id>.<ext>`, max ~1000 px wide, preferably < 300 KB.
  Ask the user for the image, video and award if not given.
- **Paper in ORCID but unwanted on site:** add its DOI to `_data/publications_ignore.yml`.
- **Check the build:** `bundle install && LANG=C.UTF-8 bundle exec jekyll build` (Gemfile uses the `github-pages` gem, same as CI).
- Develop on a feature branch and open a PR to `main`; merging deploys the site.
