"""Install public inference dependencies and hash-verified UniGaze research weights."""
from pathlib import Path
import argparse
import os
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import venv
ROOT=Path(__file__).resolve().parents[1]

def install(model):
    if sys.version_info<(3,13):raise SystemExit('신경망 시선 환경에는 Python 3.13 이상이 필요해요.')
    env=ROOT/'.gaze-venv';python=env/'bin/python'
    if not python.exists():venv.EnvBuilder(with_pip=True).create(env)
    marker=env/'study-gaze-installed.json'
    requirements=ROOT/'scripts/gaze-requirements.txt'
    stamp=hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not marker.exists() or json.loads(marker.read_text()).get('requirements')!=stamp:
        subprocess.run([str(python),'-m','pip','install','-r',str(requirements)],check=True)
        marker.write_text(json.dumps({'requirements':stamp})+'\n')
    manifest=json.loads((ROOT/'last_hour/neural_assets/model-manifest.json').read_text())
    item=next(x for x in manifest['models'] if x['filename']==model+'.safetensors')
    destination=ROOT/'data/models/unigaze'/item['filename'];destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists() and destination.stat().st_size==item['bytes'] and hashlib.file_digest(destination.open('rb'),'sha256').hexdigest()==item['sha256']:
        print('UniGaze 모델 검증 완료:',model);return
    print('공식 UniGaze 모델 다운로드:',model,round(item['bytes']/1024**2),'MiB',flush=True)
    url=f"https://huggingface.co/{manifest['repo']}/resolve/{manifest['revision']}/{item['filename']}?download=true"
    temp=destination.with_suffix('.download');digest=hashlib.sha256();count=0;next_progress=100*1024**2
    with urllib.request.urlopen(url,timeout=120) as response,temp.open('wb') as target:
        while chunk:=response.read(4*1024**2):
            count+=len(chunk);digest.update(chunk);target.write(chunk)
            if count>=next_progress:print(round(count/item['bytes']*100),'%',flush=True);next_progress+=100*1024**2
    if count!=item['bytes'] or digest.hexdigest()!=item['sha256']:raise SystemExit('모델 해시가 다릅니다. 설치를 중단했어요.')
    temp.replace(destination);print('UniGaze 설치 완료. 얼굴 영상은 이 Mac 안에서만 처리해요.')

if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    from last_hour.config import load_env
    load_env(ROOT/'.env')
    p=argparse.ArgumentParser();p.add_argument('--model',choices=['unigaze_l16_joint','unigaze_b16_joint'],default=os.getenv('STUDY_GAZE_MODEL','unigaze_l16_joint'))
    install(p.parse_args().model)
