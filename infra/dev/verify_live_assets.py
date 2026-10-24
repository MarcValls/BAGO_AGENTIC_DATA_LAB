"""Verify public live edits against an explicitly selected own development container."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
from urllib.request import urlopen

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',required=True);p.add_argument('--public-dir',required=True,type=Path);p.add_argument('--container',required=True);p.add_argument('--receipt',required=True,type=Path);a=p.parse_args()
 public=a.public_dir.resolve(strict=True)
 if not public.is_relative_to(Path(__file__).resolve().parent):raise ValueError('Public fixture must belong to this identified bundle')
 if not a.container.startswith('bago-'):raise ValueError('Explicit own BAGO container required')
 def identity():
  c=json.loads(subprocess.check_output(['docker','inspect',a.container],text=True))[0]
  top=subprocess.check_output(['docker','top',a.container,'-eo','pid,ppid,args'],text=True)
  return {'id':c['Id'],'pid':c['State']['Pid'],'started_at':c['State']['StartedAt'],'processes':top}
 before=identity();rows=[];existing=public/'bago-live-existing.txt';new=public/'bago-live-new.txt'
 if existing.exists() or new.exists():raise ValueError('Preserve previous fixtures: chosen filenames already exist')
 def observe(name,value):
  for attempt in range(60):
   with urlopen(a.url.rstrip('/')+'/'+name,timeout=3) as response:body=response.read()
   if body==value:return {'name':name,'attempt':attempt,'sha256':hashlib.sha256(body).hexdigest()}
   time.sleep(.25)
  raise AssertionError('Exact HTTP effect absent: '+name)
 try:
  existing.write_bytes(b'PUBLIC_A');rows.append(observe(existing.name,b'PUBLIC_A'))
  existing.write_bytes(b'PUBLIC_B');rows.append(observe(existing.name,b'PUBLIC_B'))
  new.write_bytes(b'PUBLIC_NEW');rows.append(observe(new.name,b'PUBLIC_NEW'))
  new.unlink()
  for attempt in range(60):
   with urlopen(a.url.rstrip('/')+'/'+new.name,timeout=3) as response:body=response.read()
   if body!=b'PUBLIC_NEW':break
   time.sleep(.25)
  else:raise AssertionError('Deleted asset still served')
  rows.append({'name':new.name,'unlink_observed':True});existing.write_bytes(b'PUBLIC_A');rows.append(observe(existing.name,b'PUBLIC_A'))
  after=identity();assert before==after,'Container/process identity changed'
  a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps({'result':'PASS','rows':rows,'before':before,'after':after,'scope':'Public HTTP effects; browser HMR requires separate observation'},indent=2)+'\n')
 finally:
  existing.unlink(missing_ok=True);new.unlink(missing_ok=True)
if __name__=='__main__':main()
