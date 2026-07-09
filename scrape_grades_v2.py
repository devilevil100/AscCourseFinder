#!/usr/bin/env python3
"""Fetch grade stats for EVERY course code (2024 & 2025, sem 2), cache each
response to disk, classify why a course has/hasn't data, and emit:
  - iitb_grade_coverage.csv     (one row per course-year: status)
  - iitb_grade_sectionwise.csv  (one row per course-year-section, raw grade counts, NO avg)
Re-run is cheap: cached HTML on disk is reused instead of re-fetching.
"""
import csv, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

SEMESTER = "1"
YEARS = ["2024", "2025"]
WORKERS = 6
CACHE = "grade_cache"
COOKIE = ("JSESSIONID=B6252B6B19F5F9CEF82ABE1632E042A8; "
          "_ga=GA1.3.1012964073.1782648462")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
REFERER = ("https://asc.iitb.ac.in/academic/Grading/statistics/"
           "gradstatistics.jsp?57XGAhPVwbR53lbQ4FqdRYkAJMCKe6HK3GapesiydmU%3D")

GRADES = ["AA", "AB", "AC", "AD", "AP", "BB", "BC", "BD", "CC", "CD", "DD",
          "PP", "NP", "FF", "FR", "DX", "DR", "II", "W", "AU", "PD", "NC"]
GRADE_RE = re.compile(r"\b(" + "|".join(GRADES) + r")\b\s+(\d+)")


def cache_path(code, year):
    safe = re.sub(r"[^A-Za-z0-9]", "_", code)
    return os.path.join(CACHE, f"{safe}_{year}_s{SEMESTER}.html")


def fetch(code, year):
    p = cache_path(code, year)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        with open(p, encoding="utf-8") as f:
            return f.read()
    url = ("https://asc.iitb.ac.in/academic/Grading/statistics/"
           "gradstatforcrse.jsp?" + urllib.parse.urlencode(
               {"year": year, "semester": SEMESTER,
                "txtcrsecode": code, "submit": "SUBMIT"}))
    req = urllib.request.Request(url, headers={
        "Cookie": COOKIE, "User-Agent": UA, "Referer": REFERER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return html


def classify(txt):
    if "Invalid Access" in txt:
        return "INVALID_ACCESS"
    if "Total Grades Given" in txt:
        return "HAS_DATA"
    if re.search(r"is NOT offered", txt):
        return "NOT_OFFERED"
    if "Course wise Statistics" in txt:
        return "OFFERED_NO_GRADES"
    return "OTHER"


def parse_sections(txt):
    parts = re.split(r"Total Grades Given for(?: section)?\s*"
                     r"([A-Za-z0-9]*)\s*are\s+(\d+)", txt)
    out, seen = [], set()
    i = 1
    while i + 1 < len(parts):
        sec = parts[i].strip() or "ALL"
        total = parts[i + 1]
        body = parts[i + 2] if i + 2 < len(parts) else ""
        grades = {g: int(c) for g, c in GRADE_RE.findall(body)}
        key = (sec, total)
        if key not in seen:
            seen.add(key)
            out.append((sec, total, grades))
        i += 3
    return out


def main():
    os.makedirs(CACHE, exist_ok=True)
    codes = {}
    for r in csv.DictReader(open("iitb_courses_2026_sem1.csv")):
        c = r["Course Code"].replace(" ", "")
        if c not in codes:
            codes[c] = (r["Department Prefix"], r["Department"],
                        r["Course Code"], r["Course Name"])
    jobs = [(c, y) for c in codes for y in YEARS]
    print(f"{len(codes)} codes x {len(YEARS)} yrs = {len(jobs)} lookups",
          file=sys.stderr)

    def work(job):
        code, year = job
        try:
            html = fetch(code, year)
            txt = re.sub(r"\s+", " ", BeautifulSoup(html, "lxml")
                         .get_text(" ", strip=True))
            status = classify(txt)
            secs = parse_sections(txt) if status == "HAS_DATA" else []
            name = None
            m = re.search(r"Course Name\s+(.*?)\s+(?:Total Grades Given|"
                          r"[A-Z]{2,4}\s?\d+[A-Z]* is NOT|Home|\Z)", txt)
            if m:
                name = m.group(1).strip()
            return code, year, status, name, secs, None
        except Exception as e:
            return code, year, "FETCH_ERROR", None, [], str(e)

    results, done = [], 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, j): j for j in jobs}
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 200 == 0:
                print(f"  ...{done}/{len(jobs)}", file=sys.stderr)

    # coverage report
    from collections import Counter
    counts = Counter(r[2] for r in results)
    with open("iitb_grade_coverage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Department Prefix", "Department", "Course Code",
                    "Course Name", "Year", "Semester", "Status", "Sections"])
        for code, year, status, name, secs, err in sorted(
                results, key=lambda x: (x[0], x[1])):
            dp, dept, disp, dname = codes[code]
            w.writerow([dp, dept, disp, name or dname, year, SEMESTER,
                        status, ",".join(s[0] for s in secs)])

    # section-wise grades, long format, NO avg
    grade_cols = GRADES
    with open("iitb_grade_sectionwise.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Department Prefix", "Department", "Course Code",
                    "Course Name", "Year", "Semester", "Section",
                    "Total Graded"] + grade_cols)
        rows = []
        for code, year, status, name, secs, err in results:
            if status != "HAS_DATA":
                continue
            dp, dept, disp, dname = codes[code]
            for sec, total, grades in secs:
                rows.append([dp, dept, disp, name or dname, year, SEMESTER,
                             sec, total] + [grades.get(g, "") for g in grade_cols])
        rows.sort(key=lambda r: (r[2], r[4], r[6]))   # code, year, section
        w.writerows(rows)

    print("\n=== COVERAGE (course-year lookups) ===")
    for k, v in counts.most_common():
        print(f"  {k:18s} {v}")
    codes_with_data = len({r[0] for r in results if r[2] == "HAS_DATA"})
    print(f"\nunique codes with grade data: {codes_with_data}/{len(codes)}")
    print(f"section-wise rows written: {len(rows)}")


if __name__ == "__main__":
    main()
