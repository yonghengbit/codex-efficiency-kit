#!/usr/bin/env python3
"""Context Guardian v3.2.

PostCompact is the source of truth for compaction counting.
Stop is the model-facing continuation gate.
Context handoff is same-model new-root continuation, never subagent delegation.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from pathlib import Path
from typing import Any

DEFAULTS={
    "soft_compactions":2,
    "hard_compactions":3,
    "repeat_threshold":3,
    "track_repetition_after_compaction":True,
}

def home_dir()->Path:
    x=os.environ.get("CODEX_CONTEXT_GUARDIAN_DIR")
    return Path(x).expanduser() if x else Path.home()/'.codex'/'context-guardian'

def load_config(base:Path)->dict[str,Any]:
    cfg=dict(DEFAULTS); p=base/'config.json'
    if p.exists():
        try:
            v=json.loads(p.read_text())
            if isinstance(v,dict): cfg.update(v)
        except Exception: pass
    return cfg

def state_path(base:Path,sid:str)->Path:
    safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in sid)
    return base/'state'/f'{safe}.json'

def load_state(base:Path,sid:str)->dict[str,Any]:
    p=state_path(base,sid)
    if p.exists():
        try:
            v=json.loads(p.read_text())
            if isinstance(v,dict): return v
        except Exception: pass
    return {"session_id":sid,"compactions":0,"last_model":None,"last_cwd":None,
            "handoff_prompted_at":None,"tool_fingerprints":{},"path_reads":{}}

def save_state(base:Path,state:dict[str,Any])->None:
    p=state_path(base,str(state.get('session_id','unknown'))); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix('.tmp'); t.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n'); t.replace(p)

def stable_json(v:Any)->str:
    try:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    except Exception:return repr(v)

def fingerprint(name:str,inp:Any)->str:
    return hashlib.sha256(f'{name}\0{stable_json(inp)}'.encode()).hexdigest()[:20]

PATH_KEYS={"path","file_path","filepath","file","filename"}
def extract_paths(v:Any)->list[str]:
    out=[]
    def walk(x):
        if isinstance(x,dict):
            for k,c in x.items():
                if k.lower() in PATH_KEYS and isinstance(c,str) and c: out.append(c)
                else: walk(c)
        elif isinstance(x,list):
            for c in x: walk(c)
    walk(v); return list(dict.fromkeys(out))

def emit_context(event:str,ctx:str,msg:str|None=None)->None:
    o={"hookSpecificOutput":{"hookEventName":event,"additionalContext":ctx}}
    if msg:o["systemMessage"]=msg
    print(json.dumps(o,ensure_ascii=False))

def post_compact(payload,base,cfg):
    sid=str(payload.get('session_id') or 'unknown'); st=load_state(base,sid)
    st['compactions']=int(st.get('compactions',0))+1
    st['last_model']=payload.get('model'); st['last_cwd']=payload.get('cwd')
    save_state(base,st); print('{}')

def stop(payload,base,cfg):
    if payload.get('stop_hook_active') is True:
        print('{}'); return
    sid=str(payload.get('session_id') or 'unknown'); st=load_state(base,sid)
    n=int(st.get('compactions',0)); soft=int(cfg['soft_compactions']); hard=int(cfg['hard_compactions'])
    if n<soft or st.get('handoff_prompted_at')==n:
        print('{}'); return
    st['handoff_prompted_at']=n; save_state(base,st)
    level='HARD' if n>=hard else 'SOFT'; model=st.get('last_model') or payload.get('model') or 'current primary model'
    reason=(
      f"CONTEXT GUARDIAN {level} HANDOFF GATE: this root has compacted {n} times. "
      "If the original task is already fully complete and required validation passed, finalize normally. "
      "Otherwise do not stop yet: execute the context-handoff workflow now. Write/refresh "
      ".codex/CODEX_HANDOFF.md from known facts, preserve PRIMARY_MODEL="+str(model)+", then create a "
      "BRAND-NEW same-directory root/thread with empty conversation history using first-party "
      "create_thread/thread-start controls. Do NOT use fork_thread/thread-fork because it copies history. "
      "Do NOT use spawn_agent, multi-agent, Terra, Luna, side chat, or $sub-agent as a handoff substitute. "
      "Start the target turn immediately and verify that the target turn actually started and that its "
      "effective model matches PRIMARY_MODEL before this old root stops. A checkpoint or successful message "
      "dispatch alone is not a completed handoff. If first-party fresh-root controls are unavailable or the "
      "target model/turn cannot be verified, fail closed and report handoff blocked."
    )
    print(json.dumps({"decision":"block","reason":reason},ensure_ascii=False))

def post_tool(payload,base,cfg):
    if not cfg.get('track_repetition_after_compaction',True): return
    sid=str(payload.get('session_id') or 'unknown'); st=load_state(base,sid)
    if int(st.get('compactions',0))<1:return
    name=str(payload.get('tool_name') or 'unknown'); inp=payload.get('tool_input'); th=int(cfg['repeat_threshold'])
    fps=st.setdefault('tool_fingerprints',{}); fp=fingerprint(name,inp); fps[fp]=int(fps.get(fp,0))+1
    prs=st.setdefault('path_reads',{}); hits=[]
    for path in extract_paths(inp):
        k=f'{name}:{path}'; prs[k]=int(prs.get(k,0))+1; hits.append((path,prs[k]))
    save_state(base,st)
    exact=fps[fp]==th; repeated=[p for p,c in hits if c==th]
    if not exact and not repeated:return
    detail=[]
    if exact:detail.append(f'the same successful {name} action has been executed {th} times')
    if repeated:detail.append('the same path has been read repeatedly: '+', '.join(repeated[:3]))
    emit_context('PostToolUse','CONTEXT GUARDIAN drift signal: '+'; '.join(detail)+
      '. Do not repeat it unless new state requires it. If this is post-compaction re-investigation, finish only '
      'the current bounded step; the Stop handoff gate will move unfinished work to a fresh same-model root.',
      'Context Guardian: repeated post-compaction work detected.')

def status(base):
    d=base/'state'
    if not d.exists(): print('No Context Guardian session state found.'); return 0
    rows=[]
    for p in sorted(d.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
        try:v=json.loads(p.read_text())
        except Exception:continue
        rows.append({"session":v.get('session_id'),"compactions":v.get('compactions',0),"last_model":v.get('last_model'),
                     "handoff_prompted_at":v.get('handoff_prompted_at'),"cwd":v.get('last_cwd')})
    print(json.dumps(rows[:20],indent=2,ensure_ascii=False)); return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--status',action='store_true'); a=ap.parse_args()
    base=home_dir(); base.mkdir(parents=True,exist_ok=True); cfg=load_config(base)
    if a.status:return status(base)
    try:payload=json.load(sys.stdin)
    except Exception:return 0
    if not isinstance(payload,dict):return 0
    e=payload.get('hook_event_name')
    if e=='PostCompact':post_compact(payload,base,cfg)
    elif e=='Stop':stop(payload,base,cfg)
    elif e=='PostToolUse':post_tool(payload,base,cfg)
    return 0
if __name__=='__main__': raise SystemExit(main())
