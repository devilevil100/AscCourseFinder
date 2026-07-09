#!/usr/bin/env python3
"""Scrape running courses for every department from ASC IITB into a CSV."""
import csv, sys, time, urllib.parse, urllib.request
from bs4 import BeautifulSoup

YEAR, SEMESTER = "2026", "1"
COOKIE = ("JSESSIONID=B6252B6B19F5F9CEF82ABE1632E042A8; "
          "_ga=GA1.3.1012964073.1782648462")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

# (deptcd sent to server, human-readable department name)
DEPTS = [
    ("AE,AES", "Aerospace Engineering"),
    ("BS,BT,BM,BB,BBS", "Biosciences and Bioengineering"),
    ("CE,CES", "Civil Engineering"),
    ("CH,CHS", "Chemistry"),
    ("CL,CLS", "Chemical Engineering"),
    ("CM,CMS", "Centre for Climate Studies"),
    ("CS,CSS", "Computer Science and Engineering"),
    ("DH", "Koita Centre for Digital Health"),
    ("DS", "Centre for Machine Intelligence and Data Science"),
    ("EC", "Economics"),
    ("EE,EES", "Electrical Engineering"),
    ("EN,ENS", "Energy Science and Engineering"),
    ("ENT", "Desai Sethi School of Entrepreneurship"),
    ("ES,ESS", "Environmental Science and Engineering"),
    ("ET,ETS", "Centre for Educational Technology"),
    ("GNR,NR", "Centre of Studies in Resources Engineering"),
    ("GP", "Applied Geophysics"),
    ("GS,GP,GSS", "Earth Sciences"),
    ("HS,HSS", "Humanities and Social Sciences"),
    ("ID,DE,DEP", "IDC School of Design"),
    ("IE,IES", "Industrial Engineering and Operations Research"),
    ("MA,SI,MAS", "Mathematics/ASI"),
    ("ME,MES", "Mechanical Engineering"),
    ("MG,MGT,MNG,SOM,IWE,MGS", "Shailesh J. Mehta School of Management"),
    ("MM,MMS", "Metallurgical Engineering and Materials Science"),
    ("MS", "Makerspace"),
    ("PH,PHS", "Physics"),
    ("PS,PSS", "Ashank Desai Centre for Policy Studies"),
    ("SC,SCS", "Centre for Systems and Control"),
    ("TD,TDE,TDO", "Centre for Technology Alternatives for Rural Areas"),
]

COLS = ["Sr no.", "Type", "Course Code", "Course Name", "Course Type",
        "Course content category", "Instructor(s)", "Venue", "Slot",
        "Division", "Biometric Attendance Enabled?", "Registration Limit",
        "Restrictions", "Division Definition"]


def fetch(deptcd):
    url = ("https://asc.iitb.ac.in/academic/utility/RunningCourses.jsp?"
           + urllib.parse.urlencode({"deptcd": deptcd, "year": YEAR,
                                     "semester": SEMESTER}))
    req = urllib.request.Request(url, headers={
        "Cookie": COOKIE, "User-Agent": UA,
        "Referer": "https://asc.iitb.ac.in/academic/utility/allDept.jsp",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def parse(html):
    """Return list of course rows (each a list of 14 cell strings)."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        return []
    rows = []
    for r in tables[0].find_all("tr"):
        cells = r.find_all(["td", "th"], recursive=False)
        if len(cells) != 14:
            continue
        txt = [c.get_text(" ", strip=True) for c in cells]
        if txt[0].isdigit():          # a real course row (skip header/others)
            rows.append(txt)
    return rows


def main():
    out = "iitb_courses_2026_sem1.csv"
    total = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Department Prefix", "Department"] + COLS)
        for deptcd, name in DEPTS:
            try:
                rows = parse(fetch(deptcd))
            except Exception as e:
                print(f"  !! {deptcd} FAILED: {e}", file=sys.stderr)
                continue
            for row in rows:
                w.writerow([deptcd, name] + row)
            total += len(rows)
            print(f"  {deptcd:24s} {name[:40]:40s} {len(rows):4d} courses")
            time.sleep(1.0)           # be polite to the server
    print(f"\nDone: {total} courses -> {out}")


if __name__ == "__main__":
    main()
