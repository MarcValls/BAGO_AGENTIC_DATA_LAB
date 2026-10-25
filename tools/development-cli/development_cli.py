"""Standalone JSON CLI over the same DevelopmentService used by ADL."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.development import DevelopmentService, DevelopmentError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list')
    inspect=sub.add_parser('inspect'); inspect.add_argument('change_id')
    for name in ('apply','rollback'):
        action=sub.add_parser(name); action.add_argument('change_id'); action.add_argument('--expected-sha256',required=True); action.add_argument('--confirmed',action='store_true')
    invoke=sub.add_parser('invoke'); invoke.add_argument('name'); invoke.add_argument('--args-file',required=True); invoke.add_argument('--owner-id',required=True); invoke.add_argument('--conversation-id',required=True); invoke.add_argument('--root',required=True)
    args=parser.parse_args()
    try:
        service=DevelopmentService(args.profile)
        if args.command=='list': result={'changes':service.list_changes()}
        elif args.command=='inspect': result={'change':service.inspect(args.change_id)}
        elif args.command in ('apply','rollback'): result={'change':getattr(service,args.command)(args.change_id,args.expected_sha256,args.confirmed)}
        else:
            result,receipt=service.invoke(args.name,json.loads(Path(args.args_file).read_text(encoding='utf8')),owner_id=args.owner_id,conversation_id=args.conversation_id,root=args.root)
            result={'result':result,'receipt':receipt}
        print(json.dumps(result,ensure_ascii=False)); return 0
    except (DevelopmentError,OSError,ValueError,KeyError) as error:
        print(json.dumps({'ok':False,'reason_code':getattr(error,'code','development_failed')})); return 1

if __name__=='__main__': raise SystemExit(main())
