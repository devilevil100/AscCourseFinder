#!/usr/bin/env python3
"""Scrape section-wise instructor names for 2024 & 2025 (Sem 1) from RunningCourses.
Output: hist_instructors.json = {code: {year: {section: "Name, Name"}}}
Section key uses 'ALL' for the blank-division main lecture (matches grade data)."""
import json, os, re, sys, time, urllib.parse, urllib.request
from bs4 import BeautifulSoup
from scrape_courses import DEPTS

YEARS = ["2024", "2025"]; SEM = "1"; CACHE = "histinstr_cache"
COOKIE = "JSESSIONID=A626A683DD6F7A80B3CAEA64819627EF; _ga=GA1.3.1012964073.1782648462"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/150.0.0.0 Safari/537.36")

def clean_instr(raw):
    if not raw: return ""
    out = []
    for p in re.split(r"\s(?=[IAC]\s*-\s)", raw):
        p = re.sub(r"^[IAC]\s*-\s*", "", p).strip()
        p = re.sub(r"\s+", " ", p)
        if p and p not in out: out.append(p)
    return ", ".join(out)

def fetch(deptcd, year):
    p = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]", "_", deptcd) + f"_{year}.html")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, encoding="utf-8", errors="replace").read()
    url = ("https://asc.iitb.ac.in/academic/utility/RunningCourses.jsp?"
           + urllib.parse.urlencode({"deptcd": deptcd, "year": year, "semester": SEM}))
    req = urllib.request.Request(url, headers={"Cookie": COOKIE, "User-Agent": UA,
        "Referer": "https://asc.iitb.ac.in/academic/utility/allDept.jsp",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(html)
    return html

def parse_rows(html):
    """course rows: [Sr,Type,Code,Name,CType,Cat,Instr,Venue,Slot,Div,...] (14 cols)."""
    tables = BeautifulSoup(html, "lxml").find_all("table")
    if not tables: return []
    rows = []
    for r in tables[0].find_all("tr"):
        cells = r.find_all(["td", "th"], recursive=False)
        if len(cells) != 14: continue
        txt = [c.get_text(" ", strip=True) for c in cells]
        if txt[0].isdigit(): rows.append(txt)
    return rows

def main():
    os.makedirs(CACHE, exist_ok=True)
    hist = {}
    for year in YEARS:
        for deptcd, name in DEPTS:
            try:
                rows = parse_rows(fetch(deptcd, year))
            except Exception as e:
                print(f"  !! {deptcd} {year}: {e}", file=sys.stderr); continue
            for row in rows:
                code = row[2].strip()
                sec = row[9].strip() or "ALL"
                instr = clean_instr(row[6])
                typ = row[1].strip()
                if not instr: continue
                d = hist.setdefault(code, {}).setdefault(year, {})
                # prefer the 'timetable' (lecture) row's instructor for each section
                if sec not in d or typ == "timetable":
                    d[sec] = instr
            time.sleep(0.4)
        print(f"  {year}: {sum(1 for c in hist if year in hist[c])} courses", file=sys.stderr)
    json.dump(hist, open("hist_instructors.json", "w"), separators=(",", ":"))
    tot = sum(len(sec) for c in hist.values() for sec in c.values())
    print(f"\n{len(hist)} courses, {tot} (year,section) instructor entries -> hist_instructors.json")

if __name__ == "__main__":
    main()
