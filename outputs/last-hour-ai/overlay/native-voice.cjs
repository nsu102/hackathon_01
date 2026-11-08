const {Hold}=require('./hold.cjs');
module.exports=async function createVoice({win,display,api,systemPreferences,globalShortcut,desktopCapturer,pointer,screen,extraWindows=()=>[],onCapture=()=>{},keyHook=()=>require('uiohook-napi'),now=()=>performance.now(),wait=ms=>new Promise(r=>setTimeout(r,ms))}){
 const {GazeBuffer,dipToPixels,inside}=await import('./focus.mjs');
 const buffer=new GazeBuffer();let enabled=false,session=null,hook=null,shortcut=null,keycode=null,frozen=null,timer=null,manual=null,uploading=false,epoch=0,screenPending=null,control='hotkey',targetMode='gaze';
 const send=(type,data)=>{const w=win();if(w&&!w.isDestroyed())w.webContents.send('voice:event',{type,data});};
 const hold=new Hold((type,data)=>{if(type==='cancel'){clearTimeout(timer);frozen=null;manual=null;}send(type,data);});
 function cancel(reason='녹음을 취소했어요.'){epoch++;clearTimeout(timer);const idle=hold.state==='idle'&&(manual||uploading);hold.cancel(reason);frozen=null;manual=null;screenPending=null;if(idle)send('cancel',reason);}
 async function capture(){
  const d=display();if(!d)throw new Error('학습 모니터를 먼저 선택해주세요.');
  if(process.platform==='darwin'&&['denied','restricted'].includes(systemPreferences.getMediaAccessStatus('screen')))throw new Error('시스템 설정 → 개인정보 보호 및 보안 → 화면 및 시스템 오디오 녹음에서 Study Signal/Electron 화면 권한을 허용하고 앱을 다시 시작해주세요.');
  const w=win(),p=pointer(),wv=w.isVisible(),pv=p?.isVisible(),extras=extraWindows().filter(x=>x&&!x.isDestroyed()&&x.isVisible());
  onCapture(true);
  try{
   w.hide();p?.hide();extras.forEach(x=>x.hide());await wait(180);
   const sources=await desktopCapturer.getSources({types:['screen'],thumbnailSize:{width:Math.round(d.bounds.width*d.scaleFactor),height:Math.round(d.bounds.height*d.scaleFactor)}});
   const image=sources.find(s=>String(s.display_id)===String(d.id))?.thumbnail;
   if(!image||image.isEmpty())throw new Error('선택한 모니터를 캡처하지 못했어요.');
   if(process.platform==='darwin'&&systemPreferences.getMediaAccessStatus('screen')!=='granted')throw new Error('화면 권한을 허용한 뒤 앱을 다시 시작해주세요.');
   return {image,display:{...d.bounds,display_id:d.id},captured_at_ms:now()};
  }finally{if(wv&&!w.isDestroyed())w.showInactive();if(pv&&p&&!p.isDestroyed())p.showInactive();extras.forEach(x=>{if(!x.isDestroyed())x.showInactive();});onCapture(false);}
 }
 async function start(input='hotkey',target=targetMode){
  if(input==='hotkey'&&!enabled||!session||uploading||manual||frozen||screenPending)return false;
  const id=hold.start();if(id===null)return false;control=input;
  timer=setTimeout(()=>cancel('20초 제한 또는 키 해제 신호 누락으로 녹음을 폐기했어요.'),20000);
  const candidate=buffer.freeze(now()),gaze=candidate&&String(candidate.display_id)===String(display()?.id)?candidate:null;
  try{const frame=await capture();if(hold.id!==id||!hold.ready(id))return false;frozen={...frame,gaze,id,target};send('start',{id,control:input,attachment:{display_id:frame.display.display_id,...frame.image.getSize()}});return true;}
  catch(e){cancel(e.message);return false;}
 }
 async function buttonStart(data){
  if(data?.consent!==true)throw new Error('음성과 선택 모니터 화면을 OpenRouter로 보내는 데 동의해주세요.');
  if(!['screen','manual'].includes(data.target))throw new Error('질문할 화면 범위를 확인해주세요.');
  if(!session||hold.state!=='idle'||uploading||manual||screenPending)throw new Error('진행 중인 AI 학습에서 질문을 하나씩 보내주세요.');
  const current=epoch;
  if(process.platform==='darwin'&&!await systemPreferences.askForMediaAccess('microphone'))throw new Error('마이크 권한을 허용해주세요.');
  if(current!==epoch)throw new Error('음성 질문을 취소했어요.');
  if(!await start('button',data.target))throw new Error('녹음을 시작하지 못했어요. 화면 권한과 학습 상태를 확인해주세요.');
  return {started:true};
 }
 function buttonRelease(){if(control!=='button'||hold.state!=='recording')throw new Error('진행 중인 버튼 녹음이 없어요.');hold.release();}
 function disable(){cancel();enabled=false;session=null;if(shortcut)globalShortcut.unregister(shortcut);shortcut=null;if(hook){hook.removeAllListeners('keyup');hook.removeAllListeners('error');try{hook.stop();}catch{}hook=null;}buffer.clear();}
 async function configure(data){
  const previousSession=session;disable();session=previousSession;
  if(!data.enabled)return {enabled:false};
  if(data.consent!==true)throw new Error('음성과 선택 화면의 서버 전송에 동의해주세요.');
  if(data.target!==undefined&&!['screen','manual','gaze'].includes(data.target))throw new Error('질문할 화면 범위를 확인해주세요.');targetMode=data.target||'gaze';
  if(process.platform==='darwin'&&!systemPreferences.isTrustedAccessibilityClient(true))throw new Error('시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용에서 Study Signal/Electron을 허용한 뒤 다시 켜주세요. 키 해제 감지에는 입력 모니터링 권한도 필요할 수 있어요.');
  if(process.platform==='darwin'&&!await systemPreferences.askForMediaAccess('microphone'))throw new Error('마이크 권한을 허용해주세요.');
  const accelerator=data.shortcut||'CommandOrControl+Shift+Enter';
  if(typeof accelerator!=='string'||! /^(CommandOrControl|Command|Control|Alt)(\+(Shift|Alt|Control))*\+(Enter|Space|F[1-9]|F1[0-2])$/.test(accelerator))throw new Error('단축키는 CommandOrControl+Shift+Enter 같은 조합을 사용해주세요.');
  const {uIOhook,UiohookKey}=keyHook();keycode=UiohookKey[accelerator.split('+').at(-1)];
  if(!keycode)throw new Error('지원하지 않는 단축키예요.');
  if(!globalShortcut.register(accelerator,()=>start('hotkey')))throw new Error('단축키가 이미 사용 중이에요. 다른 조합을 선택해주세요.');
  shortcut=accelerator;hook=uIOhook;
  hook.on('keyup',e=>{if(e.keycode===UiohookKey.Escape){cancel();return;}if(e.keycode===keycode&&control==='hotkey')hold.release();});
  hook.on('error',()=>cancel('키 해제 감지가 중단되어 녹음을 폐기했어요.'));
  try{hook.start();}catch{disable();throw new Error('입력 모니터링 권한을 확인하고 앱을 다시 시작해주세요.');}
  enabled=true;return {enabled:true,shortcut};
 }
 function payloadFrame(frame,rect,selection){
  let cropped=frame.image.crop(dipToPixels(rect,frame.display,frame.image.getSize())),bytes=cropped.toPNG();
  if(bytes.length>6000000&&typeof cropped.resize==='function'){const size=cropped.getSize();cropped=cropped.resize({width:Math.min(2048,size.width),quality:'best'});bytes=cropped.toPNG();}
  const size=cropped.getSize();
  if(size.width<32||size.height<32)throw new Error('문단 전체가 보이도록 더 넓게 선택해주세요.');
  if(bytes.length>6000000)throw new Error('화면이 너무 커요. 설정에서 질문 범위를 영역 선택으로 바꿔주세요.');
  return {capture:{png:bytes.toString('base64'),width:size.width,height:size.height,display_id:frame.display.display_id,captured_at_ms:frame.captured_at_ms},target:{selection,calibration_id:selection==='gaze'?frame.gaze.calibration_id:null}};
 }
 async function submit(data){
  if(!frozen||data.id!==frozen.id||hold.state!=='released'||uploading)throw new Error('키 해제가 확인되지 않아 전송하지 않았어요.');
  clearTimeout(timer);hold.done();
  if(data.speech_detected!==true){frozen=null;throw new Error('질문 음성이 들리지 않았어요.');}
  if(process.platform==='darwin'&&(systemPreferences.getMediaAccessStatus('microphone')!=='granted'||systemPreferences.getMediaAccessStatus('screen')!=='granted'||control==='hotkey'&&!systemPreferences.isTrustedAccessibilityClient(false))){frozen=null;throw new Error('마이크·화면 또는 키 감지 권한이 철회되어 녹음을 폐기했어요.');}
  if(typeof data.audio!=='string'||data.audio.length>2700000||!Number.isFinite(data.duration_ms)||data.duration_ms>20000){frozen=null;throw new Error('녹음 형식을 확인해주세요.');}
  const frame=frozen;frozen=null;
  if(frame.target==='screen')return upload({...payloadFrame(frame,frame.display,'screen'),audio:data.audio,duration_ms:data.duration_ms,speech_detected:true,consent:true},session);
  if(frame.target==='manual'||!frame.gaze||!inside(frame.gaze,frame.display)){
   manual={frame,data,session,expires:Date.now()+60000};
   send('select',{png:frame.image.toDataURL(),display:frame.display});
   timer=setTimeout(()=>{manual=null;send('cancel','영역 선택 시간이 지나 녹음을 폐기했어요.');},60000);
   return {select:true};
  }
  const radius=Math.max(240,frame.gaze.error_px*2);
  return upload({...payloadFrame(frame,{x:frame.gaze.x-radius,y:frame.gaze.y-Math.max(150,frame.gaze.error_px*1.5),width:radius*2,height:Math.max(300,frame.gaze.error_px*3)},'gaze'),audio:data.audio,duration_ms:data.duration_ms,speech_detected:true,consent:true},session);
 }
 async function upload(body,id){const current=epoch;uploading=true;send('processing');try{const result=await api('POST',`/study/sessions/${id}/context-help`,body);if(current===epoch)send('answer',result);return {ok:true};}finally{uploading=false;}}
 async function select(rect){
  if(!manual||Date.now()>manual.expires)throw new Error('다시 단축키를 눌러 질문해주세요.');
  const pending=manual;manual=null;clearTimeout(timer);
  return upload({...payloadFrame(pending.frame,rect,'manual'),audio:pending.data.audio,duration_ms:pending.data.duration_ms,speech_detected:true,consent:true},pending.session);
 }
 // Text questions share the same local capture boundary, without microphone/key-hook access.
 async function screenPrepare(data){
  if(!session||uploading||manual||frozen||screenPending||hold.state!=='idle')throw new Error('진행 중인 AI 학습에서 질문을 하나씩 보내주세요.');
  if(data?.consent!==true)throw new Error('선택 화면을 OpenRouter로 보내는 데 동의해주세요.');
  if(typeof data.message!=='string'||!data.message.trim()||data.message.length>4000)throw new Error('질문은 1~4,000자로 입력해주세요.');
  const current=epoch,id=session,candidate=buffer.freeze(now());
  const pending={message:data.message.trim(),session:id};screenPending=pending;
  try{
   const frame=await capture();
   if(current!==epoch||screenPending!==pending||session!==id)throw new Error('질문 준비가 취소됐어요.');
   pending.frame=frame;pending.expires=Date.now()+60000;
   const gaze=candidate&&String(candidate.display_id)===String(frame.display.display_id)&&inside(candidate,frame.display)?candidate:null;
   const radius=gaze?Math.max(240,gaze.error_px*2):0;
   const initial=gaze?{x:Math.max(frame.display.x,gaze.x-radius),y:Math.max(frame.display.y,gaze.y-150),width:radius*2,height:300}:null;
   timer=setTimeout(()=>{if(screenPending===pending)screenPending=null;},60000);
   return {png:frame.image.toDataURL(),display:frame.display,initial};
  }catch(e){if(screenPending===pending)screenPending=null;throw e;}
 }
 async function screenSubmit(rect){
  const pending=screenPending;
  if(!pending?.frame||Date.now()>pending.expires||session!==pending.session||uploading)throw new Error('화면 질문을 다시 시작해주세요.');
  screenPending=null;clearTimeout(timer);
  if(process.platform==='darwin'&&systemPreferences.getMediaAccessStatus('screen')!=='granted')throw new Error('화면 권한이 철회되어 캡처를 폐기했어요.');
  const body={...payloadFrame(pending.frame,rect,'manual'),message:pending.message,consent:true};
  const current=epoch;uploading=true;
  try{
   const result=await api('POST',`/study/sessions/${pending.session}/screen-help`,body);
   if(current!==epoch)throw new Error('학습 상태가 바뀌어 답변 표시를 취소했어요.');
   return result;
  }finally{uploading=false;}
 }
 return {configure,submit,select,cancel,disable,buttonStart,buttonRelease,screenPrepare,screenSubmit,sample:s=>{const onOverlay=[win(),...extraWindows()].some(w=>w&&!w.isDestroyed()&&w.isVisible()&&inside(s,w.getBounds()));const age=Number.isFinite(s.latency_ms)?Math.max(0,Math.min(2000,s.latency_ms)):0;buffer.add({...s,at_ms:now()-age,validity:onOverlay?'unknown':s.validity});},setSession:id=>{if(session!==id)cancel('학습 상태가 바뀌어 녹음을 폐기했어요.');session=id;},busy:()=>uploading};
};
