# markustatzgern.com

Personal website of Markus Tatzgern, built with Jekyll and hosted on GitHub Pages.

- Content: `index.html` (bio) and `_data/*.yml` (publications, theses, patents, links).
- New publications can be pulled from [ORCID 0000-0002-3900-4944](https://orcid.org/0000-0002-3900-4944)
  with `scripts/sync_publications.py` (run manually; no schedule). Curate the result before merging.
- Local preview: `bundle install && bundle exec jekyll serve`.

See `CLAUDE.md` for the data format and maintenance conventions.
