import importlib.util,sys,json
from pathlib import Path
from types import SimpleNamespace
base=Path(__file__).resolve().parent; sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('locator_renderer',base/'make_locators.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import bpy
out=base/'out/_review'; plans=[]
for zid in ('Z04','Z06','Z12'):
    try:
        a=SimpleNamespace(zones=zid,view='eye',out=str(out),samples=8,mask_existing=False,preflight=False,preview=True)
        m.worker(a,bpy)
        plans.append({'zone':zid,'ok':True})
    except Exception as e:
        plans.append({'zone':zid,'ok':False,'error':str(e)}); print('REVIEW_ERROR',zid,str(e),flush=True)
(out/'plans.json').write_text(json.dumps(plans,indent=2)+'\n',encoding='utf8')
