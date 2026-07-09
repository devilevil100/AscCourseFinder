#!/usr/bin/env python3
"""Merge the running-courses CSV and the grade-stats CSV into a single compact
JSON payload used by the course-explorer website."""
import csv, json, re
from collections import defaultdict

GP = {"AA": 10, "AB": 9, "BB": 8, "BC": 7, "CC": 6, "CD": 5, "DD": 4,
      "FF": 0, "FR": 0}
GRADE_COLS = ["AA", "AB", "AC", "AD", "AP", "BB", "BC", "BD", "CC", "CD", "DD",
              "PP", "NP", "FF", "FR", "DX", "DR", "II", "W", "AU", "PD", "NC"]


def median_gp(dist):
    """Median grade point over the graded population (AA=10 … DD=4, F=0)."""
    vals = []
    for g, n in dist.items():
        if g in GP:
            vals.extend([GP[g]] * n)
    if not vals:
        return None
    vals.sort()
    k, m = len(vals), len(vals) // 2
    return vals[m] if k % 2 else (vals[m - 1] + vals[m]) / 2


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
        passed = sum(n for g, n in dist.items()
                     if g in GP and g not in ("FF", "FR"))
        graded = sum(n for g, n in dist.items() if g in GP)
        grades[r["Course Code"].strip()].append({
            "year": r["Year"], "sec": r["Section"],
            "total": int(r["Total Graded"] or 0), "dist": dist,
            "median": median_gp(dist),
            "passRate": round(100 * passed / graded) if graded else None,
        })

    # ---- credits + historical section instructors (optional) ----
    credits = {}
    try:
        credits = json.load(open("credits.json"))
    except FileNotFoundError:
        pass
    hist_instr = {}
    try:
        hist_instr = json.load(open("hist_instructors.json"))
    except FileNotFoundError:
        pass

    # ---- prerequisites / equivalents (from Prerequisite.csv) ----
    prereq_map = {}
    try:
        for r in csv.DictReader(open("Prerequisite.csv", encoding="utf-8", errors="replace")):
            pcode = r["CourseCode"].strip()
            typ = (r["Type"] or "").strip()
            expr = " ".join((r["Courses"] or "").split())
            consent = (r["InstructorConsent"] or "").strip()
            remark = " ".join((r["Remark"] or "").split())
            e = prereq_map.setdefault(pcode, {"prereq": [], "equiv": [], "consent": False, "remarks": []})
            if typ.startswith("prereq") and expr and expr not in e["prereq"]:
                e["prereq"].append(expr)
            if typ == "equivalent" and expr and expr not in e["equiv"]:
                e["equiv"].append(expr)
            if consent in ("Required", "Conditional"):
                e["consent"] = True
            if remark and remark not in e["remarks"]:
                e["remarks"].append(remark)
    except FileNotFoundError:
        pass

    # ---- merge + course-level summary ----
    out = []
    for code, c in courses.items():
        # drop IDC design studio courses that have no timetable slot
        if c["deptPrefix"] == "ID,DE,DEP" and not any(o["cells"] for o in c["offerings"]):
            continue
        cr = credits.get(code)
        c["credits"] = cr["credits"] if cr else None
        c["ltps"] = [cr["L"], cr["T"], cr["P"], cr["S"]] if cr else None
        c["half"] = bool(cr["half"]) if cr else False
        c["desc"] = (cr.get("desc") or "") if cr else ""
        pr = prereq_map.get(code)
        c["prereq"] = pr["prereq"] if pr else []
        c["equiv"] = pr["equiv"] if pr else []
        c["consent"] = bool(pr and pr["consent"])
        c["remarks"] = pr["remarks"] if pr else []
        c["histInstr"] = hist_instr.get(code, {})
        g = grades.get(code, [])
        c["grades"] = g
        agg = {}
        for row in g:
            for k, v in row["dist"].items():
                agg[k] = agg.get(k, 0) + v
        c["medGP"] = median_gp(agg)                          # course-wide median
        c["gradedN"] = sum(v for k, v in agg.items() if k in GP)
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
