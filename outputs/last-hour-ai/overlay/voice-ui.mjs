import {selectRegion} from './regions.mjs';
const $=id=>document.getElementById(id),bridge=window.studyBridge;
export function setupVoice({getSession,onAnswer,error,onStatus=()=>{}}){
 let enabled=false,recorder=null,stream=null,chunks=[],audioContext=null,analyser=null,raf=null,startAt=0,voicedMs=0,lastAt=0,id=null,discard=true,helping=false,generation=0,phase='idle',control='button';
 function status(text,next=phase){
  phase=next;$('voice-status').textContent=text;$('voice-indicator').hidden=phase!=='recording';
  $('voice-talk').textContent=phase==='recording'?(control==='button'?'말 끝내고 보내기':'단축키를 놓으면 전송'):phase==='preparing'?'화면·마이크 준비 중…':phase==='processing'?'답변 준비 중…':'말하기 시작';
  $('voice-talk').disabled=['preparing','processing','selecting'].includes(phase)||phase==='recording'&&control==='hotkey';
  $('voice-cancel').hidden=!['preparing','recording','selecting'].includes(phase);
  onStatus({text,phase,attachment:!$('voice-attachment').hidden});
 }
 function cleanup(){cancelAnimationFrame(raf);stream?.getTracks().forEach(t=>{t.onended=null;t.stop();});stream=null;audioContext?.close().catch(()=>{});audioContext=null;analyser=null;}
 function cancel(text='음성 질문을 취소했어요.'){
  generation++;discard=true;chunks=[];if(recorder?.state==='recording')recorder.stop();cleanup();helping=false;$('voice-attachment').hidden=true;status(text,'idle');
 }
 async function fail(text){await bridge.window('voice-cancel').catch(()=>{});cancel(text);error(text);}
 async function start(data){
  if(data.control!=='button'&&!enabled||getSession()?.status!=='running'||getSession()?.busy){await bridge.window('voice-cancel');cancel('AI 학습을 시작한 뒤 말해주세요.');return;}
  speechSynthesis.cancel();const current=++generation;helping=true;discard=false;id=data.id;control=data.control||'hotkey';chunks=[];voicedMs=0;$('voice-attachment').hidden=!data.attachment;status('마이크를 준비하고 있어요…','preparing');
  try{
   const acquired=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
   if(discard||current!==generation){acquired.getTracks().forEach(t=>t.stop());return;}stream=acquired;
   if(!MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))throw new Error('WebM/Opus 녹음을 지원하지 않아요.');
   const context=new AudioContext();audioContext=context;await context.resume();if(discard||current!==generation){context.close().catch(()=>{});acquired.getTracks().forEach(t=>t.stop());return;}
   analyser=context.createAnalyser();analyser.fftSize=1024;audioContext.createMediaStreamSource(stream).connect(analyser);
   const bytes=new Float32Array(analyser.fftSize);lastAt=startAt=performance.now();
   function meter(){if(!analyser||current!==generation)return;const at=performance.now();analyser.getFloatTimeDomainData(bytes);const rms=Math.sqrt(bytes.reduce((sum,v)=>sum+v*v,0)/bytes.length);if(rms>.012)voicedMs+=Math.min(100,at-lastAt);lastAt=at;raf=requestAnimationFrame(meter);}meter();
   stream.getAudioTracks()[0].onended=()=>fail('마이크 연결이 끊겨 녹음을 폐기했어요.');
   recorder=new MediaRecorder(stream,{mimeType:'audio/webm;codecs=opus',audioBitsPerSecond:64000});
   recorder.ondataavailable=e=>{if(current===generation&&!discard&&e.data.size)chunks.push(e.data);};
   recorder.onerror=()=>{if(current===generation)fail('녹음 오류로 폐기했어요.');};
   recorder.onstop=async()=>{
    if(discard||current!==generation)return;cleanup();
    const duration=Math.round(performance.now()-startAt);
    if(voicedMs<180){await fail('질문 음성이 들리지 않았어요. 다시 말해주세요.');return;}
    const blob=new Blob(chunks,{type:'audio/webm'});chunks=[];
    if(blob.size>2000000){await fail('녹음이 너무 커서 폐기했어요.');return;}
    const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    if(discard||current!==generation)return;status('질문을 받아 적고, 고정한 화면을 읽고 있어요…','processing');
    try{await bridge.window('voice-submit',{id,audio:btoa(binary),duration_ms:duration,speech_detected:true});}catch(e){await fail(e.message);}
   };
   recorder.start();status(control==='button'?'녹음 중 · 다 말하면 보내기 버튼을 눌러주세요 · 최대 20초':'녹음 중 · 단축키를 놓으면 전송 · 최대 20초','recording');
  }catch(e){if(current===generation)await fail(e.message);}
 }
 async function talk(){
  error();
  if(phase==='recording'&&control==='button'){await bridge.window('voice-button-release');return;}
  if(phase!=='idle')return;
  const session=getSession();
  if(session?.status!=='running'||!session.ai_enabled||session.busy){error('AI 도움을 켠 학습을 시작한 뒤 말해주세요.');return;}
  if(!$('voice-consent').checked){error('음성과 화면 전송에 먼저 체크해주세요.');$('voice-consent').focus();return;}
  speechSynthesis.cancel();helping=true;status('질문 시작 때의 화면을 고정하고 있어요…','preparing');
  try{await bridge.window('gaze-display',{display_id:$('monitor').value});await bridge.window('voice-button-start',{consent:true,target:$('voice-target').value});}
  catch(e){await fail(e.message);}
 }
 $('voice-talk').onclick=()=>talk().catch(e=>fail(e.message));
 $('voice-enable').onclick=async()=>{
  try{await bridge.window('gaze-display',{display_id:$('monitor').value});const result=await bridge.window('voice-configure',{enabled:!enabled,consent:$('voice-consent').checked,target:$('voice-target').value,shortcut:$('voice-shortcut').value,session_id:getSession()?.status==='running'&&getSession()?.ai_enabled?getSession().id:null});enabled=result.enabled;$('voice-enable').textContent=enabled?'전역 음성 단축키 끄기':'전역 음성 단축키 켜기';status(enabled?'단축키를 누른 동안 말하고 놓아주세요':'말하기 시작 버튼으로 질문할 수 있어요.','idle');}
  catch(e){enabled=false;error(e.message);status('말하기 버튼은 손쉬운 사용 권한 없이 쓸 수 있어요.','idle');}
 };
 $('voice-consent').onchange=()=>{if(!$('voice-consent').checked){enabled=false;bridge.window('voice-configure',{enabled:false}).catch(()=>{});cancel('전송 동의를 해제했어요.');$('voice-enable').textContent='전역 음성 단축키 켜기';}};
 const consentSaved=localStorage.getItem('study-voice-consent');if(consentSaved!==null)$('voice-consent').checked=consentSaved==='true';
 $('voice-consent').addEventListener('change',()=>{localStorage.setItem('study-voice-consent',String($('voice-consent').checked));onStatus({phase,text:$('voice-status').textContent,attachment:!$('voice-attachment').hidden});});
 $('voice-target').onchange=()=>{bridge.window('voice-cancel').catch(()=>{});cancel('질문 범위를 바꿨어요. 다시 말해주세요.');if(enabled){enabled=false;bridge.window('voice-configure',{enabled:false}).catch(()=>{});$('voice-enable').textContent='전역 음성 단축키 켜기';}};
 $('voice-cancel').onclick=()=>{bridge.window('voice-cancel').catch(()=>{});cancel();};
 $('read-answer').onchange=()=>{if(!$('read-answer').checked){speechSynthesis.cancel();if(phase==='idle')helping=false;}localStorage.setItem('study-read-answer',String($('read-answer').checked));};
 const readSaved=localStorage.getItem('study-read-answer');if(readSaved!==null)$('read-answer').checked=readSaved==='true';
 bridge.onVoice(async event=>{
  if(event.type==='start')return start(event.data);
  if(event.type==='release'){if(recorder?.state==='recording'&&!discard&&event.data===id)recorder.stop();else await fail('준비 전에 녹음이 끝나 질문을 폐기했어요.');}
  if(event.type==='cancel')cancel(event.data);
  if(event.type==='processing'){helping=true;status('선택한 화면과 질문으로 답변을 준비하고 있어요…','processing');}
  if(event.type==='select'){
   status('질문 시작 때 고정한 화면에서 문단을 선택해주세요.','selecting');
   try{const r=await selectRegion('질문할 부분 선택',{display_id:event.data.display.display_id,preview:event.data.png});await bridge.window('voice-select',{x:r.x,y:r.y,width:r.width,height:r.height});}
   catch(e){await fail(e.message);}
  }
  if(event.type==='answer'){
   helping=false;status('답변했어요. 이어서 궁금한 걸 말해주세요.','idle');await onAnswer(event.data);
   if($('read-answer').checked){speechSynthesis.cancel();const speech=new SpeechSynthesisUtterance(event.data.message.content);speech.lang='ko-KR';helping=true;speech.onend=speech.onerror=()=>{helping=false;};speechSynthesis.speak(speech);}
  }
 });
 return {talk,state:()=>({phase,attachment:!$('voice-attachment').hidden}),isHelping:()=>helping,stop:()=>{bridge.window('voice-cancel').catch(()=>{});cancel();speechSynthesis.cancel();}};
}
