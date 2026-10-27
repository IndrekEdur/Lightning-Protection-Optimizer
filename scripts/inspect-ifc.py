"""Local diagnostic runner; reads originals without rewriting them."""
from pathlib import Path
import sys
import argparse
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from lpo.ifc_import import import_ifc
from lpo.optimization import solve
parser=argparse.ArgumentParser()
parser.add_argument('file',type=Path)
parser.add_argument('--verify',action='store_true',help='Run manual/no-rod rolling sphere verification, not placement optimization')
parser.add_argument('--save-project',type=Path,help='Write sensitive derived geometry JSON; use test_models/')
args=parser.parse_args()
try:
    project=import_ifc(args.file)
    if args.save_project:args.save_project.write_text(project.model_dump_json(indent=2),encoding='utf-8')
    summary=project.ifc_metadata.model_dump()
    if args.verify:
        result=solve(project)
        summary['calculation']={key:result[key] for key in ['verification_status','geometry_verified','engineering_verified','duration_seconds','checks']}
        summary['calculation']['diagnostics']=result['verification'].get('diagnostics',{})
    print(json.dumps(summary,indent=2,ensure_ascii=False))
except (ValueError,OSError) as exc:
    print(f'IFC diagnostic error: {exc}',file=sys.stderr)
    sys.exit(2)
