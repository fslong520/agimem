#!/usr/bin/env python3
"""superseded_by 写入通道排查（隔离库 store_s1，端口 17121）。"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lexicon_i18n as lx
ISO="/tmp/agimem-i18n/stores/store_s1"; PW="/tmp/agimem-i18n/pass_s1.txt"
ENV=dict(os.environ, RSRS_DATA_DIR=ISO, RSRS_M3_DIR=os.path.expanduser("~/.rsrs/models/bge-m3"),
         RSRS_RPC_PORT="17121", RSRS_RETRIEVAL="bge", RSRS_UPDATE_CHECK="0")
def J(args,t=300):
    p=subprocess.run(args,capture_output=True,text=True,env=ENV,timeout=t)
    raw=p.stdout; i=raw.find("{")
    return p.returncode,(json.loads(raw[i:]) if i>=0 else {}),raw[:300]
os.makedirs(ISO,exist_ok=True)
rc,d,_=J(["rsrs","keygen","--json"]); pw=d["summary"]["super"]; open(PW,"w").write(pw); os.chmod(PW,0o600)
ENV["RSRS_SUPER"]=pw; ENV["RSRS_PASS"]=pw
f=lx.FACTS[0]
rc,d,_=J(["rsrs","remember","--importance","important","--title",f["title"]["zh"],f["body"]["zh"],"--json"])
old=d["summary"]["id"]; print("A write:",d.get("status"),d["summary"].get("action"),old[:8])
new_body="【日记】2026-11-09 更正：灰度回滚结论已修订，先回滚再定位，回滚后 500 率恢复。"
rc,d,raw=J(["rsrs","remember","--importance","important","--supersedes",old,"--title","灰度回滚结论修订","--json",new_body])
print("B supersedes:",d.get("status"),(d.get("summary") or {}).get("action"),(d.get("summary") or {}).get("id","")[:8])
print("B errors:",d.get("errors"),raw[:200] if rc else "")
new=(d.get("summary") or {}).get("id")
if new:
    rc,d,_=J(["rsrs","show",old,"--json"],)
    e=(d.get("details") or {})
    ent=e.get("entry") or {}
    print("show old: status",d.get("status"),"superseded_by=",repr(ent.get("superseded_by"))[:40])
    rc,d,_=J(["rsrs","show",new,"--json"])
    ent=(d.get("details") or {}).get("entry") or {}
    print("show new: supersedes=",repr(ent.get("supersedes"))[:40],"superseded_by=",repr(ent.get("superseded_by"))[:40])
    rc,d,_=J(["rsrs","recall","灰度回滚 5% 500 率 先回滚","--json","--limit","3","--titles"])
    det=d.get("details") or []
    print("recall hits:",[(str(h.get('id'))[:8], round(h.get('score') or 0,2), h.get("superseded_by")) for h in det])
J(["rsrs","runtime","stop","--json"])
