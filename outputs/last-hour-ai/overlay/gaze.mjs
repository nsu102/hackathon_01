import {NeuralGaze} from './neural-gaze.mjs';
import {ScreenPresence} from './screen-presence.mjs';
import { ObservationWindow, features } from './study-signals.mjs';
const facePose=p=>p?.[33]&&p?.[263]?[(p[33].x+p[263].x)/2,(p[33].y+p[263].y)/2,Math.hypot(p[33].x-p[263].x,p[33].y-p[263].y)]:null;
import { ScreenGazeModel, center, calibrationTargets, validationTargets } from './screen-gaze.mjs';
export class GazeTracker {
 constructor(video,update,aggregate,point){Object.assign(this,{video,update,aggregate,point});this.window=new ObservationWindow();this.presence=new ScreenPresence();this.running=false;this.generation=0;this.loading=false;this.mapping=null;this.calibration=null;this.display=null;this.calibrationId=null;this.poseDriftAt=null;this.lastVideoTime=null;this.sample=()=>{};}
 async start(){
  if(this.running||this.loading)return;
  const generation=++this.generation,current=()=>generation===this.generation;this.loading=true;let stream,model;
  this.update({status:'loading',label:'로컬 모델 준비 중'});
  try{
   const permission=await window.studyBridge.window('camera-permission');if(!current())return;
   if(!permission.granted)throw new Error('카메라 권한을 시스템 설정에서 확인해주세요.');
   stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720},frameRate:{ideal:30,max:30},facingMode:'user'},audio:false});if(!current())return;
   this.stream=stream;this.cameraId=stream.getVideoTracks()[0].getSettings().deviceId;stream.getVideoTracks()[0].onended=()=>{this.stop();this.update({status:'error',label:'카메라 연결 변경 · 재보정 필요'});};this.video.srcObject=stream;await this.video.play();if(!current())return;this.videoSize=[this.video.videoWidth,this.video.videoHeight].join('x');
   const {FaceLandmarker,FilesetResolver}=await import('./node_modules/@mediapipe/tasks-vision/vision_bundle.mjs');if(!current())return;
   const vision=await FilesetResolver.forVisionTasks(new URL('./node_modules/@mediapipe/tasks-vision/wasm',location.href).href);if(!current())return;
   model=await FaceLandmarker.createFromOptions(vision,{baseOptions:{modelAssetPath:new URL('./assets/face_landmarker.task',location.href).href,delegate:'CPU'},runningMode:'VIDEO',numFaces:1,minFaceDetectionConfidence:.6,minFacePresenceConfidence:.6,minTrackingConfidence:.6});if(!current())return;
   this.model=model;model=null;this.update({status:'loading',label:'UniGaze 신경망 준비 중'});this.neural=new NeuralGaze(this.video);this.engineInfo=await this.neural.start();if(!current())return;this.running=true;this.presence.reset();this.update({status:'tracking',label:'화면 가운데를 2초 바라봐 주세요',engine:this.engineInfo});this.tick();
  }catch(error){if(current()){this.stop();this.update({status:'error',label:'측정 시작 실패',error:error.message});throw error;}}
  finally{if(!current()){stream?.getTracks().forEach(t=>t.stop());model?.close();}else this.loading=false;}
 }
 setDisplay(display){if(JSON.stringify(display)!==JSON.stringify(this.display)){this.invalidate();this.presence.reset();}this.display=display;}
 invalidate(){this.mapping=null;this.calibrationId=null;this.smoothed=null;this.poseDriftAt=null;this.point(null);this.sample({at_ms:performance.now(),validity:'unknown',validated:false,pose_ok:false});}
 beginCalibration(display){
  if(!this.running)throw new Error('먼저 카메라를 켜주세요.');this.invalidate();
  this.calibration={display,stage:'train',index:0,rows:[],validation:[],samples:[],poses:[],attempts:0,valid:0,validationAttempts:0,validationValid:0,started:performance.now()};this.window.reset();this.calibrationUpdate();
 }
 beginSavedValidation(display,profile){
  if(!this.running)throw new Error('먼저 카메라를 켜주세요.');
  const model=ScreenGazeModel.restore(profile.model,display);this.beginCalibration(display);
  Object.assign(this.calibration,{stage:'validation',model,reused:true});this.calibrationUpdate();
 }
 calibrationUpdate(extra={}){const c=this.calibration;if(!c)return;this.update({status:'calibrating',label:c.stage==='train'?'화면 위치 보정 중':'시선 오차 확인 중',stage:c.stage,index:c.index,target:(c.stage==='train'?calibrationTargets:validationTargets)[c.index],samples:c.samples.length,...extra});}
 collect(value,at,pose=null){
  const c=this.calibration;if(!c)return;
  if(at-c.started<900)return;
  c.attempts++;if(c.stage==='validation')c.validationAttempts++;
  if(!value){this.calibrationUpdate({hint:'얼굴과 눈이 카메라에 보이도록 해주세요.'});return;}
  c.valid++;if(c.stage==='validation')c.validationValid++;if(pose)c.poses.push(pose);c.samples.push(value);this.calibrationUpdate();if(c.samples.length<12)return;
  const screenTarget=(c.stage==='train'?calibrationTargets:validationTargets)[c.index],vp=c.display.viewport||c.display;
  const target={x:(vp.x+screenTarget.x*vp.width-c.display.x)/c.display.width,y:(vp.y+screenTarget.y*vp.height-c.display.y)/c.display.height},f=center(c.samples);
  const spread=Math.max(...f.map((v,i)=>Math.sqrt(c.samples.reduce((s,r)=>s+(r[i]-v)**2,0)/c.samples.length)));
  if(spread>.05){c.samples=[];c.started=at;this.calibrationUpdate({hint:'같은 점을 조금 더 편하게 바라봐 주세요.'});return;}
  (c.stage==='train'?c.rows:c.validation).push({features:f,target});c.index++;c.samples=[];c.started=at;
  if(c.stage==='train'&&c.index===calibrationTargets.length){
   try{c.model=new ScreenGazeModel().fit(c.rows,c.display);}catch(error){this.calibration=null;this.update({status:'calibration-failed',label:'시선 신호 확인 필요',error:error.message});return;}
   c.stage='validation';c.index=0;
  }else if(c.stage==='validation'&&c.index===validationTargets.length){
   const result=c.model.validate(c.validation,Math.min(c.valid/c.attempts,c.validationValid/c.validationAttempts));if(result.accepted){this.mapping=c.model;this.calibrationId=crypto.randomUUID();this.baseline=center((c.rows.length?c.rows:c.validation).map(r=>r.features));this.baselinePose=c.poses.length?center(c.poses):null;}
   this.calibration=null;this.update({status:'calibration-result',label:result.accepted?(c.reused?'저장된 보정 확인 완료':'시선 위치 보정 완료'):'보정 오차가 커요',reused:Boolean(c.reused),...result});return;
  }this.calibrationUpdate();
 }
 cancelCalibration(){this.calibration=null;this.invalidate();this.update({status:this.running?'tracking':'off',label:this.running?'화면 방향 감지 중':'카메라 꺼짐'});}
 async tick(){
  if(!this.running)return;const generation=this.generation;
  try{
   const at=performance.now();this.lastTickAt=at;
   const size=[this.video.videoWidth,this.video.videoHeight].join('x');
   if(this.videoSize&&size!==this.videoSize){this.videoSize=size;this.calibration=null;this.invalidate();this.presence.reset();this.update({status:'tracking',label:'해상도 변경 · 화면 기준 다시 확인 중'});}
   if(this.video.readyState<2||this.video.currentTime===this.lastVideoTime){
    this.sample({at_ms:at,validity:'unknown',validated:false,pose_ok:false,presence:this.presence.unknown('stale')});
    if(this.calibration)this.calibrationUpdate({hint:'새 카메라 프레임을 기다리고 있어요.'});
    this.timer=setTimeout(()=>this.tick(),120);return;
   }
   this.lastVideoTime=this.video.currentTime;
   const frame=this.neural?this.neural.freeze():this.video;
   const result=this.model.detectForVideo(frame,at),quality=features(result.faceLandmarks?.[0]);
   const neuralResult=quality&&this.neural?await this.neural.estimate(result.faceLandmarks[0]):null;
   if(!this.running||generation!==this.generation)return;
   const latency=performance.now()-at;
   const value=latency>600?null:(this.neural?(neuralResult?.features??null):quality);
   if(this.calibration){this.collect(value,performance.now(),facePose(result.faceLandmarks?.[0]));this.sample({at_ms:at,validity:'unknown',validated:false,pose_ok:false});}
   else if(this.display){
    const pose=facePose(result.faceLandmarks?.[0]);
    const geometryOK=!this.baselinePose||pose&&Math.abs(pose[0]-this.baselinePose[0])<.10&&Math.abs(pose[1]-this.baselinePose[1])<.10&&pose[2]/this.baselinePose[2]>.75&&pose[2]/this.baselinePose[2]<1.3;
    const poseOK=Boolean(geometryOK&&value&&this.baseline&&Math.abs(value[3]-this.baseline[3])<(this.neural ? .25 : .09)&&Math.abs(value[4]-this.baseline[4])<(this.neural ? .25 : .09));
    if(this.mapping&&value&&!poseOK){this.poseDriftAt??=at;if(at-this.poseDriftAt>1800){this.invalidate();this.update({status:'uncalibrated',label:'자세가 바뀌었어요. 재보정 필요'});}}
    else this.poseDriftAt=null;
    const p=value&&this.mapping?this.mapping.predict(value):null;
    const offscreen=p&&(p.nx<0||p.nx>1||p.ny<0||p.ny>1);
    const presence=latency>600?this.presence.unknown('stale'):this.presence.update(value,at,pose);
    if(quality&&this.neural&&!value&&latency<=600)presence.reason='model_quality';
    this.sample({display_id:this.display.display_id,calibration_id:this.calibrationId,at_ms:at,latency_ms:latency,x:p?.x??null,y:p?.y??null,validity:p?(offscreen?'offscreen':'valid'):'unknown',validated:Boolean(this.mapping),pose_ok:poseOK,validation_error_px:this.mapping?.errorPx??null,presence});
    this.point(p);
    this.update({status:'tracking',label:presence.state==='on_screen'?'화면 응시 중':presence.state==='away'?'화면 이탈 방향 감지':['reference','unstable_reference'].includes(presence.reason)?'화면 가운데를 2초 바라봐 주세요':presence.reason==='position_changed'?'화면 기준 다시 잡기':presence.reason==='model_quality'?'시선 추정 불가':'눈 측정 불가'});
    this.window.add(p?(offscreen?'away':'on'):'unknown',at);
    if(this.window.started!==null&&at-this.window.started>=10000){this.aggregate(this.window.summary(at,Boolean(this.mapping)));this.window.reset();}
   }
  }catch(error){if(!this.running||generation!==this.generation)return;this.stop();this.update({status:'error',label:'카메라 신호 확인 필요',error:error.message});return;}
  this.timer=setTimeout(()=>this.tick(),Math.max(0,120-(performance.now()-this.lastTickAt)));
 }
 stop(){++this.generation;this.loading=false;this.running=false;this.lastVideoTime=null;clearTimeout(this.timer);this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.neural?.close();this.neural=null;this.video.srcObject=null;this.model?.close();this.model=null;this.calibration=null;this.presence.reset();this.invalidate();this.window.reset();this.update({status:'off',label:'카메라 꺼짐'});}
}
