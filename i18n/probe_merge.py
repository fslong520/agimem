#!/usr/bin/env python3
"""零合并定性（二）：① --importance important 走判重；② d3 库 96 条跨语言相似度矩阵。"""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon_i18n as lx

M3=os.path.expanduser("~/.rsrs/models/bge-m3")
title2fl={}
for f in lx.FACTS:
    for lang in lx.LANGS: title2fl[f["title"][lang]]=(f["fid"],lang)

def env(d,pw,port):
    e=dict(os.environ, RSRS_DATA_DIR=d, RSRS_M3_DIR=M3, RSRS_RPC_PORT=str(port),
           RSRS_RETRIEVAL="bge", RSRS_UPDATE_CHECK="0")
    if pw: e["RSRS_SUPER"]=pw; e["RSRS_PASS"]=pw
    return e

def J(e,args,t=300):
    p=subprocess.run(args,capture_output=True,text=True,env=e,timeout=t)
    raw=p.stdout; i=raw.find("{")
    return p.returncode, (json.loads(raw[i:]) if i>=0 else {})

# ---------- ① importance=important 实测
ISO="/tmp/agimem-i18n/stores/store_p5"; PW="/tmp/agimem-i18n/pass_p5.txt"
os.makedirs(ISO,exist_ok=True)
rc,d=J(env(ISO,None,17112),["rsrs","keygen","--json"]); pw=d["summary"]["super"]
open(PW,"w").write(pw); os.chmod(PW,0o600)
E=env(ISO,pw,17112)
f=lx.FACTS[0]
out=[]
def w(lang,kw):
    args=["rsrs","remember","--title",f["title"][lang],f["body"][lang],"--importance","important","--json"]
    rc,d=J(E,args); s=(d.get("summary") or {})
    rec={"lang":lang,"status":d.get("status"),"state":s.get("state"),"action":s.get("action"),
         "written":s.get("written"),"merge_count":s.get("merge_count"),"parent_count":s.get("parent_count"),
         "items":[(i.get("name"),i.get("value")) for i in (d.get("items") or [])][:3],
         "actions":(d.get("actions") or [])[:2]}
    out.append(rec); print(kw, json.dumps(rec,ensure_ascii=False)); return rec
w("zh","A) zh important")
w("en","B) en important")
w("zh","C) zh duplicate important")
# 索引就绪后再试 ja
for _ in range(30):
    rc,d=J(E,["rsrs","status","--json"]); idx=(d.get("summary") or {}).get("retrieval_index",{})
    if not idx.get("running") and not idx.get("scheduled"): break
    time.sleep(3)
J(E,["rsrs","model","activate","m3","--json"])
w("ja","D) ja important after index")
J(E,["rsrs","runtime","stop","--json"])

# ---------- ② d3 库相似度矩阵
D3="/tmp/agimem-i18n/stores/d3"; pw3=open("/tmp/agimem-i18n/pass_d3.txt").read().strip()
E3=env(D3,pw3,17106)
pairs=[]
for f in lx.FACTS:
    for lang in lx.LANGS:
        rc,d=J(E3,["rsrs","candidates",f["body"][lang],"--json"])
        det=d.get("details") or {}
        for tier in ("merge","parent"):
            for c in det.get(tier,[]) or []:
                e=c.get("entry") or {}
                t=e.get("title","")
                tl=title2fl.get(t)
                if not tl: continue
                fid2,l2=tl
                pairs.append({"fid":f["fid"],"lang":lang,"cand_fid":fid2,"cand_lang":l2,
                              "score":round(float(c.get("score") or 0),4),
                              "same_fact":fid2==f["fid"],"same_lang":l2==lang,
                              "tier":tier})
J(E3,["rsrs","runtime","stop","--json"])
json.dump({"importance_probe":out,"pairs":pairs},open("/tmp/agimem-i18n/probe_merge2.json","w"),ensure_ascii=False,indent=1)
print("pairs",len(pairs))
