#!/usr/bin/env python3
"""Scrape credit structure (credits + L-T-P-S) for every course code."""
import csv, json, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

CACHE="credit_cache"; WORKERS=6
COOKIE="JSESSIONID=A626A683DD6F7A80B3CAEA64819627EF; _ga=GA1.3.1012964073.1782648462"
UA=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36")
REFERER="https://asc.iitb.ac.in/academic/utility/RunningCourses.jsp?deptcd=AE,AES&year=2026&semester=1"
WANT=["Total Credits","Type","Lecture","Tutorial","Practical","Selfstudy","Half Semester","Description"]

def cache_path(code): return os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]","_",code)+".html")

def fetch(code):
    p=cache_path(code)
    if os.path.exists(p) and os.path.getsize(p)>0:
        return open(p,encoding="utf-8",errors="replace").read()
    url="https://asc.iitb.ac.in/academic/CourseRegistration/Common/crsedetail.jsp?"+ \
        urllib.parse.urlencode({"ccd":code,"view":""})
    req=urllib.request.Request(url,headers={"Cookie":COOKIE,"User-Agent":UA,"Referer":REFERER,
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req,timeout=60) as r:
        html=r.read().decode("utf-8","replace")
    open(p,"w",encoding="utf-8").write(html)
    return html

def parse(html):
    soup=BeautifulSoup(html,"lxml")
    kv={}
    for t in soup.find_all("table"):
        for r in t.find_all("tr"):
            cells=r.find_all(["td","th"])
            if len(cells)==2:
                k=cells[0].get_text(" ",strip=True)
                if k in WANT:
                    kv[k]=cells[1].get_text("\n" if k=="Description" else " ",strip=True)
    if "Total Credits" not in kv: return None
    def num(x):
        x=(kv.get(x) or "").strip()
        return float(x) if re.fullmatch(r"\d+(\.\d+)?",x) else None
    desc=re.sub(r"\n{3,}","\n\n",(kv.get("Description") or "").replace("�","")).strip()
    return {"credits":num("Total Credits"),"type":kv.get("Type","").strip(),
            "L":num("Lecture"),"T":num("Tutorial"),"P":num("Practical"),
            "S":num("Selfstudy"),"half":(kv.get("Half Semester","").strip().upper()=="Y"),
            "desc":desc}

def main():
    codes=sorted({r["Course Code"].strip() for r in csv.DictReader(open("iitb_courses_2026_sem1.csv"))})
    os.makedirs(CACHE,exist_ok=True)
    print(f"{len(codes)} course codes",file=sys.stderr)
    out={}; done=0; miss=0
    def work(code):
        try: return code, parse(fetch(code)), None
        except Exception as e: return code, None, str(e)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(work,c):c for c in codes}
        for f in as_completed(futs):
            code,rec,err=f.result(); done+=1
            if done%150==0: print(f"  ...{done}/{len(codes)}",file=sys.stderr)
            if rec: out[code]=rec
            else: miss+=1
    json.dump(out,open("credits.json","w"),separators=(",",":"))
    print(f"\ngot credits for {len(out)}/{len(codes)} codes ({miss} missing) -> credits.json")
    from collections import Counter
    print("credit values:",dict(Counter(round(v['credits']) for v in out.values() if v['credits'] is not None)))

if __name__=="__main__": main()
