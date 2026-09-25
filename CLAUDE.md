# Website of Markus Tatzgern

Single-page Jekyll site, deployed to GitHub Pages (custom domain markustatzgern.com) by
`.github/workflows/pages.yml` on every push to `main`. No subpages.

## Structure
- `index.html` – bio, publications, theses, patents. Bio text is edited here.
- `_data/publications.yml` – all publications, newest first. The page groups them by `year`
  and keeps file order within a year.
- `_data/theses.yml`, `_data/patents.yml`, `_data/links.yml` – other sections and sidebar links.
- `_data/publications_ignore.yml` – ORCID DOIs that must not be added to the site.
- `_data/news.yml` – news items, newest first; one line each, Markdown links allowed, `date: YYYY-MM`.
- `_data/bibtex.yml` – BibTeX per publication id (Cite button). Generated from Crossref by the sync
  script; hand edits are kept. Entries without Crossref record (DataCite DOIs, no DOI) were completed by hand.
- `_includes/publication.html` – markup of one publication entry.
- `assets/css/site.css` – all styles (do not name it `style.css`; the default GitHub Pages theme overwrites that path).
- `papers/` – teaser images (`<id>.webp`, max 800 px wide) and author PDFs (`<id>.pdf`). Keep PDF file names:
  external links point to them. `papers/<old-id>.html` are redirect stubs for URLs of the old site; keep them.
- `assets/fonts/` – self-hosted Oswald and Source Sans 3 (no Google Fonts requests, GDPR).
- `_layouts/default.html` – head with Open Graph tags and schema.org Person JSON-LD; update `jobTitle`/`affiliation` there when the position changes.
- `scripts/sync_publications.py` – adds new ORCID works (metadata via Crossref), links matching videos
  from the YouTube channel `mtatzgern`, marks open-access papers via Unpaywall, and writes missing BibTeX.
  Runs weekly via `.github/workflows/sync-publications.yml` and opens a PR. Reports missing BibTeX fields.
- `scripts/optimize_images.py papers/<file>` – converts a new teaser image to 800 px WebP and updates the data file.

## Publication entry format
```yaml
- id: 2025_arkward               # YEAR_shortname, unique, used as anchor and file name
  title: ...
  authors: A, B, Markus Tatzgern  # comma-separated, full names
  venue: Full Venue Name (ABBR)   # no pages, no year
  year: 2025
  badge: MobileHCI                # short venue label shown before the title
  image: papers/2025_arkward.png  # optional; without it papers/placeholder.svg is shown
  doi: 10.1145/3743740            # without https://doi.org/
  pdf: papers/2025_arkward.pdf    # optional, author version
  youtube: Y_DVrMH3XDs            # optional, video ID only
  award: Honorable Mention for Best Paper   # optional, shown as badge
  url: https://...                # optional project page
  open_access: true               # set by sync script (Unpaywall)
  oa_pdf: https://...             # set by sync script; used as PDF link when no own pdf
```
Venue style: `ACM CHI Conference on Human Factors in Computing Systems (CHI)`,
`IEEE International Symposium on Mixed and Augmented Reality (ISMAR)`, etc. Reuse existing venue strings.

## Common tasks
- **Add a paper:** run `python3 scripts/sync_publications.py` (needs network access to pub.orcid.org,
  api.crossref.org, youtube.com), or add the entry by hand from the DOI via Crossref. Normalize the venue.
  Save the teaser image as `papers/<id>.<ext>` and run `scripts/optimize_images.py` on it.
  Ask the user for the image, video and award if not given. Set `badge`. Check the generated BibTeX.
  Add a news line if the user wants one.
- **Paper in ORCID but unwanted on site:** add its DOI to `_data/publications_ignore.yml`.
- **Check the build:** `bundle install && LANG=C.UTF-8 bundle exec jekyll build` (Gemfile uses the `github-pages` gem, same as CI).
- Develop on a feature branch and open a PR to `main`; merging deploys the site.

## Future ideas (agreed to postpone; would need subpages)
- Research topics section with representative images.
- Students/team and open positions.
- Projects section fed from ORCID fundings.
- Selected publications with "show all", and filters by year/type.
