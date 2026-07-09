# ASC Course Explorer — IIT Bombay (Autumn 2026)

A single-file, offline-capable web app to explore running courses, per-section
grade-distribution history (2024–2025 Sem 1), and plan a clash-free timetable.

**Live site:** https://devilevil100.github.io/asc-courses/

- `index.html` — the whole app (data embedded, no dependencies)
- `scrape_courses.py`, `scrape_grades_v2.py` — scrapers for ASC
- `build_site_data.py` + `course_template.html` — rebuild `index.html`
