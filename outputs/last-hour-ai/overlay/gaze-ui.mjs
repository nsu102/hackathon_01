import {GazeTracker} from './gaze.mjs';
import {selectRegion} from './regions.mjs';
import {CalibrationStore,calibrationContext} from './calibration-store.mjs';
const $=id=>document.getElementById(id),bridge=window.studyBridge;
export function setupGaze(aggregate,error){
 let calibrationDisplay=null,calibrationActive=false,savedCalibration=null;
 const store=new CalibrationStore(localStorage);
 const tracker=new GazeTracker($('camera'),v=>{
  $('gaze-label').textContent=v.label;$('camera-dot').classList.toggle('on',tracker.running);
  $('camera-preview').hidden=v.status==='off';$('gaze-map-section').hidden=!tracker.running;
  $('camera-instruction').textContent=v.label;$('camera-toggle').textContent=tracker.running||v.status==='loading'?'감지 끄기':'감지 켜기';
  if(v.status==='calibrating'){
   $('calibration-target').hidden=false;$('calibration-target').style.left=v.target.x*100+'%';$('calibration-target').style.top=v.target.y*100+'%';
   $('calibration-progress').textContent=`${v.stage==='train'?'보정':'검증'} ${v.index+1} / ${v.stage==='train'?9:5} · ${v.samples}/12`;
   $('calibration-hint').textContent=v.hint||'머리는 편하게 고정하고 점을 계속 바라봐 주세요.';
  }
  if(v.status==='calibration-result'||v.status==='calibration-failed'){
   $('calibration-target').hidden=true;$('calibration-done').hidden=!v.accepted;$('calibration-retry').hidden=Boolean(v.accepted);
   $('calibration-progress').textContent=v.status==='calibration-failed'?v.error:`${v.label} · 중앙 ${Math.round(v.median_error_px)} / 최대 ${Math.round(v.max_error_px)} DIP px · 유효율 ${Math.round(v.valid_ratio*100)}%`;
   $('calibration-hint').textContent=v.accepted?'정밀 좌표 검증을 통과했어요. 기본 화면 방향 감지는 이 보정과 별도로 동작해요.':'정밀 좌표 검증을 통과하지 못했어요. 기본 화면 방향 감지는 별도로 사용할 수 있어요.';
   if(v.accepted){try{store.save(calibrationContext(tracker,calibrationDisplay),tracker.mapping);$('calibration-storage').textContent='보정 저장됨 · 다음 실행에는 5점 확인만 해요';$('calibration-hint').textContent+=' 보정을 이 Mac에 저장했어요.';}catch(e){error('보정은 통과했지만 저장하지 못했어요. '+e.message);}}
  }
  if(v.engine){const size=v.engine.model.includes('l16')?'L':'B';$('calibration-model').textContent=`UniGaze-${size} · 신경망 시선 보정`;$('gaze-accuracy').textContent=`UniGaze-${size} · ${v.engine.device==='mps'?'이 Mac의 Metal GPU':'이 Mac의 CPU'} · 화면 보정 전`;}
  if(v.error&&!calibrationActive)error(v.error);
 },aggregate,p=>{
  const inScreen=p&&p.nx>=0&&p.nx<=1&&p.ny>=0&&p.ny<=1;
  $('map-dot').hidden=!inScreen;$('map-empty').hidden=Boolean(inScreen);
  if(p){if(inScreen){$('map-dot').style.left=p.nx*100+'%';$('map-dot').style.top=p.ny*100+'%';}$('gaze-coordinates').textContent=`x ${Math.round(p.x)} · y ${Math.round(p.y)} DIP${inScreen?'':' · 화면 밖'}`;$('gaze-accuracy').textContent=`검증 중앙 오차 ${Math.round(p.error_px)} DIP px`;}else $('gaze-coordinates').textContent='측정 불가 또는 미검증';
  bridge.window('gaze-point',p?{x:p.x,y:p.y,error_px:p.error_px}:null).catch(()=>{});
 });
 tracker.regions={study:null,notes:null};
 function regionStatus(){$('region-status').textContent=(tracker.regions.study?'학습 영역 설정됨':'학습 영역 미지정')+' · '+(tracker.regions.notes?'필기 영역 허용':'필기 영역 미지정');}
 async function displays(){const list=await bridge.window('displays'),previous=$('monitor').value||localStorage.getItem('study-monitor');$('monitor').replaceChildren(...list.map(d=>{const o=document.createElement('option');o.value=d.id;o.textContent=`${d.label} · ${d.width}×${d.height} · ${d.scale}x`;return o;}));if(list.some(d=>String(d.id)===previous))$('monitor').value=previous;}
 displays().catch(e=>error(e.message));
 navigator.mediaDevices.addEventListener('devicechange',async()=>{
  if(!tracker.running||!tracker.cameraId)return;
  try{const devices=await navigator.mediaDevices.enumerateDevices();
   if(tracker.running&&!devices.some(d=>d.kind==='videoinput'&&d.deviceId===tracker.cameraId)){tracker.stop();error('사용하던 카메라 연결이 끊겼어요.');}
  }catch{/* The active video track's ended handler remains authoritative. */}
 });
 const selected=()=>({display_id:$('monitor').value});
 $('monitor').onchange=()=>{localStorage.setItem('study-monitor',$('monitor').value);bridge.window('voice-cancel').catch(()=>{});bridge.window('gaze-display',selected()).catch(e=>error(e.message));tracker.stop();tracker.display=null;tracker.regions={study:null,notes:null};regionStatus();};
 async function openCalibration(){
  if(!tracker.running)return;
  calibrationDisplay=await bridge.window('calibration-open',selected());calibrationActive=true;
  $('show-gaze').checked=false;await bridge.window('gaze-visible',false);tracker.cancelCalibration();tracker.setDisplay(calibrationDisplay);
  $('gaze-map').style.aspectRatio=calibrationDisplay.width+'/'+calibrationDisplay.height;
  $('calibration').hidden=false;$('calibration-intro').hidden=false;$('calibration-target').hidden=true;$('calibration-done').hidden=true;$('calibration-retry').hidden=true;$('calibration-progress').textContent='';
  savedCalibration=store.load(calibrationContext(tracker,calibrationDisplay),calibrationDisplay);
  $('calibration-heading').textContent=savedCalibration?'저장된 보정을 불러왔어요':'눈으로 점을 따라가 주세요';
  $('calibration-description').textContent=savedCalibration?'같은 모니터·카메라의 보정이 있어요. 9점 보정은 건너뛰고 5개 점에서 현재 자세와 오차만 확인해요.':'UniGaze 신경망으로 시선을 추정해요. 머리는 편하게 두고 9개 점을 바라봐 주세요. 별도 5점 검증을 통과하면 보정을 자동 저장해요.';
  $('calibration-start').textContent=savedCalibration?'저장된 보정으로 5점 확인':'보정 시작';$('calibration-full').hidden=!savedCalibration;
  $('calibration-storage').textContent=savedCalibration?'저장된 보정 있음 · 5점 확인 대기':'현재 모니터·카메라의 저장된 보정 없음';
  $('calibration-hint').textContent=savedCalibration?'보정 계수는 이 Mac에만 저장해요. 재검증을 통과하기 전에는 자동 알림이 켜지지 않아요.':'9점 학습 + 별도 5점 검증. 각 점에서 안정화 후 12개의 유효 샘플을 수집해요.';
 }
 async function closeCalibration(cancel=false){if(cancel)tracker.cancelCalibration();calibrationActive=false;$('calibration').hidden=true;await bridge.window('calibration-close');}
 tracker.closeCalibration=()=>closeCalibration(true);
 function startCalibration(reuse=true){$('calibration-intro').hidden=true;$('calibration-done').hidden=true;$('calibration-retry').hidden=true;if(reuse&&savedCalibration)tracker.beginSavedValidation(calibrationDisplay,savedCalibration);else tracker.beginCalibration(calibrationDisplay);}
 tracker.startMonitoring=async()=>{if(tracker.running||tracker.loading)return;tracker.setDisplay(await bridge.window('gaze-display',selected()));await tracker.start();};
 $('camera-toggle').onclick=async()=>{error();if(tracker.running||tracker.loading){tracker.stop();$('show-gaze').checked=false;await bridge.window('gaze-visible',false);return;}try{await tracker.startMonitoring();}catch(e){error(e.message);}};
 $('recalibrate').onclick=()=>openCalibration().catch(e=>error(e.message));$('calibration-start').onclick=()=>startCalibration();$('calibration-retry').onclick=()=>startCalibration(false);$('calibration-full').onclick=()=>startCalibration(false);
 $('calibration-clear').onclick=()=>{try{store.clear();savedCalibration=null;$('calibration-storage').textContent='저장된 보정을 지웠어요. 다음 실행에는 새로 보정해요.';}catch(e){error(e.message);}};
 $('calibration-done').onclick=()=>closeCalibration().catch(e=>error(e.message));$('calibration-cancel').onclick=()=>closeCalibration(true).catch(e=>error(e.message));
 window.addEventListener('keydown',e=>{if(e.key==='Escape'&&calibrationActive)closeCalibration(true).catch(()=>{});});
 $('show-gaze').onchange=async()=>{if($('show-gaze').checked&&!tracker.mapping){$('show-gaze').checked=false;error('먼저 보정과 검증을 통과해주세요.');return;}await bridge.window('gaze-visible',$('show-gaze').checked);};
 for(const kind of ['study','notes'])$(kind+'-region').onclick=async()=>{try{tracker.regions[kind]=await selectRegion(kind==='study'?'학습 영역':'허용할 필기 영역',selected());await bridge.window('gaze-display',selected());regionStatus();}catch(e){error(e.message);}};
 $('notes-clear').onclick=()=>{tracker.regions.notes=null;regionStatus();};
 bridge.onDisplayChanged(()=>{tracker.stop();tracker.display=null;tracker.regions={study:null,notes:null};regionStatus();displays().catch(()=>{});if(calibrationActive)closeCalibration(true).catch(()=>{});$('show-gaze').checked=false;error('화면 구성이 바뀌었어요. 사용할 모니터를 다시 선택하고 보정해주세요.');});
 const opacity=Math.min(98,Math.max(72,Number(localStorage.getItem('study-opacity'))||90));
 function setOpacity(n){document.documentElement.style.setProperty('--overlay-alpha',n/100);$('opacity-value').textContent=n+'%';localStorage.setItem('study-opacity',String(n));}
 $('opacity').value=opacity;setOpacity(opacity);$('opacity').oninput=()=>setOpacity(Number($('opacity').value));
 return tracker;
}
