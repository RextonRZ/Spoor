import importlib.util,sys
from pathlib import Path
from types import SimpleNamespace
base=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('locators',base/'make_locators.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import bpy
for view in ('eye','map'):
    m.worker(SimpleNamespace(zones='Z11',view=view,out=str(base/'out'),samples=16,mask_existing=True,preflight=False),bpy)
