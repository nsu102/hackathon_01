"""Build a standalone Apple Silicon .app/DMG from the local Electron runtime.

Run with Python containing playwright. The existing .gaze-venv needs PyInstaller.
Uses ad-hoc signatures; does not load credentials or run notarization.
"""
from pathlib import Path
import argparse,json,os,plistlib,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.build'

def run(args,**kwargs):subprocess.run([str(a) for a in args],check=True,**kwargs)

def icon():
 from playwright.sync_api import sync_playwright
 source=(ROOT/'overlay/assets/StudySignalTemplate.svg').read_text()
 inner=source[source.index('>')+1:source.rindex('</svg>')]
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><rect width="1024" height="1024" rx="224" fill="#c6f24e"/><svg x="180" y="180" width="664" height="664" viewBox="0 0 24 24">{inner}</svg></svg>'
 (ROOT/'overlay/assets/StudySignalApp.svg').write_text(svg)
 folder=BUILD/'StudySignal.iconset';folder.mkdir(exist_ok=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
  for size in (16,32,128,256,512):
   for scale in (1,2):
    page=browser.new_page(viewport={'width':size,'height':size},device_scale_factor=scale)
    page.set_content('<style>html,body{margin:0;width:100%;height:100%;background:transparent}svg{display:block;width:100%;height:100%}</style>'+svg)
    page.screenshot(path=str(folder/f'icon_{size}x{size}{"@2x" if scale==2 else ""}.png'),omit_background=True);page.close()
  browser.close()
 run(['/usr/bin/iconutil','-c','icns',folder,'-o',BUILD/'StudySignal.icns'])

def service():
 command=[ROOT/'.gaze-venv/bin/python','-m','PyInstaller','--noconfirm','--clean','--onedir','--target-arch','arm64','--name','study-service','--distpath',BUILD/'service-dist','--workpath',BUILD/'pyinstaller','--specpath',BUILD,'--paths',ROOT,'--additional-hooks-dir',ROOT/'scripts/pyinstaller_hooks','--add-data',str(ROOT/'last_hour/prompts.md')+':last_hour','--collect-data','timm','--collect-data','torch','--copy-metadata','timm','--copy-metadata','torch','--collect-submodules','timm.models','--hidden-import','torchvision','--hidden-import','certifi']
 for module in ['matplotlib','scipy','pandas','tensorflow','tkinter','IPython','pytest','openai','playwright','onnx','onnxruntime']:command+=['--exclude-module',module]
 command+=[ROOT/'scripts/bundled_service.py']
 with (BUILD/'service-build.log').open('w') as log:run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYINSTALLER_CONFIG_DIR':str(BUILD/'pyinstaller-cache'),'HF_HUB_OFFLINE':'1'})

def build_app():
 staging=BUILD/'dmg';staging.mkdir(exist_ok=True)
 app=staging/'Study Signal.app'
 if app.exists():shutil.rmtree(app)
 shutil.copytree(ROOT/'overlay/node_modules/electron/dist/Electron.app',app,symlinks=True)
 contents=app/'Contents';resources=contents/'Resources'
 default=resources/'default_app.asar'
 if default.exists():default.unlink()
 front=resources/'app';front.mkdir()
 for p in (ROOT/'overlay').iterdir():
  if p.name in {'node_modules','tests','package-lock.json'}:continue
  if p.is_dir():shutil.copytree(p,front/p.name)
  elif p.suffix in {'.cjs','.mjs','.js','.html','.css','.json'}:shutil.copy2(p,front/p.name)
 modules=front/'node_modules';modules.mkdir()
 # Current UI dependencies; experimental ONNX modules have no role in this build.
 for name in ['@mediapipe','@fontsource','uiohook-napi','node-gyp-build']:
  shutil.copytree(ROOT/'overlay/node_modules'/name,modules/name,symlinks=True)
 shutil.copytree(BUILD/'service-dist/study-service',resources/'service',symlinks=True)
 models=resources/'models/unigaze';models.mkdir(parents=True)
 shutil.copy2(ROOT/'data/models/unigaze/unigaze_l16_joint.safetensors',models/'unigaze_l16_joint.safetensors')
 shutil.copytree(ROOT/'last_hour/neural_assets',resources/'model-notices')
 shutil.copy2(ROOT/'.env.example',resources/'defaults.env')
 shutil.copy2(BUILD/'StudySignal.icns',resources/'StudySignal.icns')
 version=json.loads((ROOT/'overlay/package.json').read_text())['version']
 with (contents/'Info.plist').open('rb') as f:info=plistlib.load(f)
 executable=contents/'MacOS'/info['CFBundleExecutable'];executable.rename(contents/'MacOS'/'StudySignal')
 info.update(CFBundleExecutable='StudySignal',CFBundleName='Study Signal',CFBundleDisplayName='Study Signal',CFBundleIdentifier='dev.studysignal.mac',CFBundleShortVersionString=version,CFBundleVersion=version,CFBundleIconFile='StudySignal.icns',LSMinimumSystemVersion='15.0',LSApplicationCategoryType='public.app-category.education',NSCameraUsageDescription='화면 응시와 이탈을 이 Mac에서 감지합니다. 얼굴 영상은 서버로 전송하지 않습니다.',NSMicrophoneUsageDescription='버튼이나 단축키로 녹음한 학습 질문을 전사합니다.',NSScreenCaptureUsageDescription='질문을 시작할 때의 선택 모니터 화면을 AI 설명에 사용합니다.',NSCameraUseContinuityCameraDeviceType=True)
 with (contents/'Info.plist').open('wb') as f:plistlib.dump(info,f)
 for p in (contents/'Frameworks').glob('Electron Helper*.app/Contents/Info.plist'):
  with p.open('rb') as f:helper=plistlib.load(f)
  helper['CFBundleIdentifier']='dev.studysignal.mac.helper'+p.parts[-3].replace('Electron Helper','').replace('.app','').replace(' ','').replace('(','-').replace(')','').lower()
  helper['CFBundleDisplayName']=helper['CFBundleName']='Study Signal Helper'
  with p.open('wb') as f:plistlib.dump(helper,f)
 # No user configuration/data or development paths are copied into the image.
 assert not list(app.rglob('.env'))
 assert not (resources/'data').exists()
 entitlements=BUILD/'entitlements.plist'
 with entitlements.open('wb') as f:plistlib.dump({'com.apple.security.cs.allow-jit':True,'com.apple.security.cs.allow-unsigned-executable-memory':True,'com.apple.security.cs.disable-library-validation':True,'com.apple.security.device.audio-input':True,'com.apple.security.device.camera':True},f)
 run(['/usr/bin/codesign','--force','--deep','--sign','-','--entitlements',entitlements,app])
 run(['/usr/bin/codesign','--verify','--deep','--strict',app])
 link=staging/'Applications'
 if not link.exists():link.symlink_to('/Applications')
 (staging/'설치 안내.txt').write_text('Study Signal.app을 Applications 폴더로 옮겨 실행하세요.\nApple Silicon / macOS 15 이상용 개발 빌드입니다. Apple 공증은 포함하지 않습니다.\n상단 눈 모양 아이콘 → 설정에서 OpenRouter API 키를 입력하세요.\n⌘⇧Space 창 표시/숨김 · ⌘, 설정 · ⌘⇧Enter 음성(설정에서 별도 켜기)\n시선 모델은 연구·비상업용 라이선스입니다.\n')
 return app,version

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--reuse-service',action='store_true');parser.add_argument('--app-only',action='store_true');args=parser.parse_args()
 BUILD.mkdir(exist_ok=True)
 if not args.reuse_service:service()
 icon();app,version=build_app()
 print('App built:',app,flush=True)
 if not args.app_only:
  output=ROOT.parent/f'Study-Signal-{version}-arm64.dmg'
  run(['/usr/bin/hdiutil','create','-ov','-format','UDZO','-volname','Study Signal','-srcfolder',BUILD/'dmg',output])
  run(['/usr/bin/hdiutil','verify',output]);print('DMG built:',output,flush=True)
if __name__=='__main__':main()
