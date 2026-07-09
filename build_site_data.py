#!/usr/bin/env python3
"""Merge the running-courses CSV and the grade-stats CSV into a single compact
JSON payload used by the course-explorer website."""
import csv, json, re
from collections import defaultdict

GP = {"AA": 10, "AB": 9, "BB": 8, "BC": 7, "CC": 6, "CD": 5, "DD": 4,
      "FF": 0, "FR": 0}
GRADE_COLS = ["AA", "AB", "AC", "AD", "AP", "BB", "BC", "BD", "CC", "CD", "DD",
              "PP", "NP", "FF", "FR", "DX", "DR", "II", "W", "AU", "PD", "NC"]


def clean_instructors(raw):
    """'I - A B  I - C D' -> ['A B', 'C D'] (strip I-/A-/C- role prefixes)."""
    if not raw:
        return []
    parts = re.split(r"\s(?=[IAC]\s*-\s)", raw)
    out = []
    for p in parts:
        p = re.sub(r"^[IAC]\s*-\s*", "", p).strip()
        p = re.sub(r"\s+", " ", p)
        if p and p not in out:
            out.append(p)
    return out


def clean_slot(raw):
    """Compress the timetable blob to 'slot • Day-code-HH:MM' pieces."""
    if not raw:
        return ""
    raw = re.sub(r"Class Room :|Room No\.?|:", " ", raw)
    raw = re.sub(r"-\d{2}:\d{2}:\d{2}", lambda m: m.group(0), raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


_CELL = re.compile(r"\b(?:1[0-2]|[1-9])[ABC]\b")
_XCELL = re.compile(r"\bX[1-3ABE]\b")
_LCELL = re.compile(r"\bL[1-6X]\b")


def parse_cells(raw):
    """Extract atomic slot-cells (1A, 11B, X3, L2, ...) from a timetable blob."""
    if not raw:
        return []
    cells = set(_CELL.findall(raw)) | set(_XCELL.findall(raw)) | set(_LCELL.findall(raw))
    return sorted(cells)


def level_of(code):
    m = re.search(r"(\d)\d{2,}", code)
    return int(m.group(1)) * 100 if m else 0


def main():
    # ---- courses ----
    courses = {}
    for r in csv.DictReader(open("iitb_courses_2026_sem1.csv")):
        code = r["Course Code"].strip()
        c = courses.get(code)
        if not c:
            c = courses[code] = {
                "code": code, "name": r["Course Name"].strip(),
                "deptPrefix": r["Department Prefix"], "dept": r["Department"],
                "type": r["Course Type"], "category": r["Course content category"],
                "level": level_of(code.replace(" ", "")),
                "instructors": [], "offerings": [],
            }
        instr = clean_instructors(r["Instructor(s)"])
        for i in instr:
            if i not in c["instructors"]:
                c["instructors"].append(i)
        c["offerings"].append({
            "row": r["Type"], "instructors": instr,
            "slot": clean_slot(r["Slot"]),
            "cells": parse_cells(r["Slot"]),
            "div": r["Division"], "limit": r["Registration Limit"],
            "biometric": bool(r["Biometric Attendance Enabled?"].strip()),
        })

    # ---- grades ----
    grades = defaultdict(list)
    for r in csv.DictReader(open("iitb_grade_sectionwise.csv")):
        dist = {g: int(r[g]) for g in GRADE_COLS if r.get(g)}
        pts = sum(GP[g] * n for g, n in dist.items() if g in GP)
        gpn = sum(n for g, n in dist.items() if g in GP)
        passed = sum(n for g, n in dist.items()
                     if g in GP and g not in ("FF", "FR"))
        graded = sum(n for g, n in dist.items() if g in GP)
        grades[r["Course Code"].strip()].append({
            "year": r["Year"], "sec": r["Section"],
            "total": int(r["Total Graded"] or 0), "dist": dist,
            "avg": round(pts / gpn, 2) if gpn else None,
            "passRate": round(100 * passed / graded) if graded else None,
        })

    # ---- merge + course-level summary ----
    out = []
    for code, c in courses.items():
        g = grades.get(code, [])
        c["grades"] = g
        wpts = wn = 0
        for row in g:
            if row["avg"] is not None:
                n = sum(v for k, v in row["dist"].items() if k in GP)
                wpts += row["avg"] * n
                wn += n
        c["avgGP"] = round(wpts / wn, 2) if wn else None
        c["gradedN"] = wn
        c["nInstr"] = len(c["instructors"])
        out.append(c)

    out.sort(key=lambda x: (x["deptPrefix"], x["code"]))
    depts = sorted({(c["deptPrefix"], c["dept"]) for c in out},
                   key=lambda x: x[1])
    payload = {
        "courses": out,
        "depts": [{"prefix": p, "name": n} for p, n in depts],
        "types": sorted({c["type"] for c in out if c["type"]}),
        "gradeCols": [g for g in GRADE_COLS if g in GP] +
                     ["PP", "NP", "II", "AU", "AP"],
    }
    with open("site_data.json", "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"{len(out)} courses, "
          f"{sum(len(c['grades']) for c in out)} grade rows -> site_data.json")
    print(f"with grade history: {sum(1 for c in out if c['grades'])}")


if __name__ == "__main__":
    main()
