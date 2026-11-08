import { setupGaze } from './gaze-ui.mjs';
import {FocusController} from './focus.mjs';
import {setupVoice} from './voice-ui.mjs';
import {setupConnection} from './connection-ui.mjs';
import {setupMaterials} from './materials-ui.mjs';
const $=id=>document.getElementById(id),bridge=window.studyBridge;
let voice=null,session=null,ready=false,busy=false,anchor=null,heartReading=false,lastMessageIds=new Set(),manualCheckin=false,materials=null,bubbleConfigured=false,lastUserText='',nagBubbleVisible=false;
const sample='조건부 확률은 어떤 사건 B가 일어났다는 조건 아래 사건 A가 일어날 확률이다.\nP(A|B) = P(A∩B) / P(B), 단 P(B)>0.\n예를 들어 카드 10장 중 빨간 카드가 4장이고, 그중 별 표시 카드가 2장이면 빨간 카드를 뽑았을 때 별 표시일 확률은 2/4이다.\n서로 독립인 사건에서는 P(A|B)=P(A)이다.';
function showBubble(value){bridge.window('bubble-update',{...value,configured:bubbleConfigured,consent:$('voice-consent').checked,materials:materials?.count()||0}).catch(()=>{});}
function error(text=''){$('error').textContent=text;$('error').hidden=!text;if(text)showBubble({kind:'error',text,...(voice?.state()||{phase:'idle'}),show:true});}
setupConnection(error);
function clock(){const elapsed=anchor?anchor.seconds+(anchor.running?(performance.now()-anchor.at)/1000:0):0;const n=Math.floor(elapsed),text=String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');$('timer').textContent=text;$('mini-clock').textContent=text;}
function heart(value){heartReading=value.reading;$('heart-bpm').replaceChildren(document.createTextNode(value.bpm===null?'— ':`${value.bpm} `));const unit=document.createElement('small');unit.textContent='bpm';$('heart-bpm').append(unit);$('heart-status').textContent=value.message+(value.age_seconds===null?'':` · ${Math.round(value.age_seconds)}초 전`);$('heart-toggle').textContent=heartReading?'연결 끊기':'서버 연결';$('signal-note').textContent=value.source==='demo'&&value.connected?'현재 심박은 데모 서버 데이터예요. 실제 워치 측정값이 아니에요.':'시선과 심박은 상태를 확인하는 참고 신호예요.';}
function addMessage(m){if(lastMessageIds.has(m.id))return;lastMessageIds.add(m.id);if(m.role==='user')lastUserText=m.content;else if(m.role==='assistant')showBubble({kind:'answer',text:[m.content,m.question].filter(Boolean).join('\n\n'),question:lastUserText,phase:'idle',attachment:m.mode==='context',show:true});const row=document.createElement('div');row.className=`message ${m.role}`;const label=document.createElement('span');label.className='author';label.textContent=m.role==='user'?'나':m.source==='demo'?'Study Signal · 데모':'Study Signal';row.append(label,document.createTextNode(m.content));if(m.question){const p=document.createElement('p');p.textContent=m.question;row.append(p);}if(m.answer){const d=document.createElement('details');d.className='answer';const title=document.createElement('summary');title.textContent='답 확인하기';const a=document.createElement('p');a.textContent=m.answer;d.append(title,a);row.append(d);}if(m.role==='assistant'){const f=document.createElement('div');f.className='feedback';for(const [name,helpful]of[['도움됐어요',true],['다르게 도와줘',false]]){const b=document.createElement('button');b.textContent=name;b.onclick=async()=>{try{const v=await bridge.request('POST',`/study/sessions/${session.id}/feedback`,{response_id:m.id,helpful,consent_for_training:$('training-consent').checked});f.replaceChildren(document.createTextNode(helpful?'피드백을 기록했어요':'다음 도움 방식을 바꿔볼게요'));render(v);}catch(e){error(e.message);}};f.append(b);}row.append(f);}$('chat').append(row);$('chat').scrollTop=$('chat').scrollHeight;}
function render(v){session=v;anchor={seconds:v.elapsed_seconds,at:performance.now(),running:v.status==='running'};$('goal-display').textContent=v.goal;$('setup').hidden=true;$('learning').hidden=v.status==='ended';$('summary').hidden=v.status!=='ended';$('timer-label').textContent=v.status==='paused'?'쉬는 중':v.status==='ended'?'학습 기록':'함께 공부한 시간';$('minutes').disabled=true;$('pause').textContent=v.status==='paused'?'다시 공부하기':'잠깐 쉬기';$('checkin').hidden=!(v.suggestion||manualCheckin);for(const m of v.messages)addMessage(m);heart(v.heart);$('personalization').textContent=`불필요한 알림 ${v.personalization.dismissals}회 조정 · 도움이 된 답변 ${v.personalization.helpful}개`;
if(v.summary)$('summary-text').textContent=`공부한 시간 ${Math.floor(v.summary.studied_seconds/60)}분 ${v.summary.studied_seconds%60}초\n도움 요청 ${v.summary.help_requests}회 · 도움이 된 답변 ${v.summary.helpful_feedback}개\n\n${v.summary.note}`;clock();}
const focus=new FocusController(event=>{if(session&&session.status!=='ended')bridge.request('POST',`/study/sessions/${session.id}/focus-events`,event).catch(e=>error(e.message));});
voice=setupVoice({onStatus:state=>showBubble({kind:'voice',...state,question:'',show:true}),getSession:()=>session?{...session,busy:busy||session.busy}:null,error,onAnswer:async()=>{try{render(await bridge.request('GET',`/study/sessions/${session.id}`));}catch(e){error(e.message);}}});
materials=setupMaterials({error,busy:()=>Boolean(busy||session?.busy||voice.isHelping()),onChange:async(text,count)=>{if(session&&session.status!=='ended')render(await bridge.request('POST',`/study/sessions/${session.id}/materials`,{material:text}));showBubble({kind:'info',text:`자료 ${count}개를 준비했어요. 질문할 때 현재 화면과 함께 참고할게요.`,phase:'idle',show:true});}});
let overlayBounds=null,lastSampleAt=-Infinity,nagVoice=null;
const tracker=setupGaze(async value=>{if(!session||session.status!=='running')return;try{render(await bridge.request('POST',`/study/sessions/${session.id}/observations`,value));}catch(e){error(e.message);}},error);
function grace(correction){const at=performance.now();focus.grace(at);speechSynthesis.cancel();$('focus-notice').hidden=true;if(session)bridge.request('POST',`/study/sessions/${session.id}/focus-events`,{from:focus.state,to:'paused',reason:'user_correction',at_ms:Math.round(at),duration_ms:60000,correction}).catch(e=>error(e.message));}
$('focus-grace').onclick=()=>grace('notes');$('focus-correction').onclick=()=>grace('false_alarm');
const names={attending:'화면 응시 중',away_pending:'이탈 확인 중',away:'화면 이탈 감지',unknown:'측정 불가',paused:'휴식·유예 중',helping:'질문·답변 중'};
const reasons={reference:'화면 가운데를 2초 바라봐 주세요.',unstable_reference:'화면 가운데를 편하게 바라봐 주세요. 기준을 다시 확인 중이에요.',missing_eyes:'눈이나 얼굴이 잘 보이지 않아요. 조명과 카메라를 확인해주세요.',model_quality:'얼굴은 감지했지만 시선 모델이 유효한 방향을 추정하지 못했어요. 자세·조명을 확인해주세요.',position_changed:'자리나 거리가 바뀌었어요. 화면 기준을 다시 잡아주세요.',stale:'새 카메라 신호를 기다리고 있어요.'};
let latestPresence=null,lastTray='';
function applyFocus(sample){
 const editing=!$('calibration').hidden||!$('region-editor').hidden;
 if(editing)sample={...sample,validity:'unknown',validated:false,presence:{ready:false,state:'unknown'}};
 focus.enabled=$('focus-enabled').checked;
 const mode=$('focus-mode').value;
 const result=focus.update(sample,{mode,running:session?.status==='running',helping:busy||session?.busy||voice.isHelping(),study:tracker.regions.study,notes:tracker.regions.notes,overlay:overlayBounds});
 let title=names[result.state],detail=mode==='screen'?'화면 방향으로 감지하고 있어요. 딴생각이나 이해도를 판단하지 않아요.':'보정된 학습·필기 영역을 확인해요.';
 if(result.state==='unknown'){
  if(!tracker.running){title=tracker.loading?'카메라 준비 중':'감지 꺼짐';detail=tracker.loading?'로컬 시선 모델을 준비하고 있어요.':'감지 켜기를 눌러 화면 응시·이탈을 확인해요.';}
  else if(editing){title='화면 선택·보정 중';detail='학습 화면으로 돌아오면 감지를 이어가요.';}
  else if(mode==='region'&&!tracker.mapping){title='정밀 보정 필요';detail='설정에서 기본 화면 방향 감지로 바꾸면 9점 보정 없이 사용할 수 있어요.';}
  else if(mode==='region'&&!tracker.regions.study){title='학습 영역 미지정';detail='정밀 모드에서는 학습 영역을 선택해주세요.';}
  else{title=sample.presence?.reason==='reference'||sample.presence?.reason==='unstable_reference'?'화면 기준 확인 중':'측정 불가';detail=reasons[sample.presence?.reason]||'측정이 불확실해서 알림을 유예해요.';}
 }else if(result.state==='paused'){
  title=!session||session.status==='ended'?'학습 시작 대기':!focus.enabled?'이탈 알림 꺼짐':'휴식·생각 유예 중';detail=!session?'학습을 시작하면 화면 방향 감지를 켜요.':!focus.enabled?'설정이나 메뉴 막대에서 이탈 알림을 켤 수 있어요.':'복귀하면 감지를 이어가요.';
 }else if(result.state==='helping')detail='질문을 듣거나 답변하는 동안은 잔소리하지 않아요.';
 else if(result.state==='away_pending')detail=`화면 밖 방향 ${Math.max(0,Math.floor((sample.at_ms-focus.awayAt)/1000))} / 8초 · 잠깐 움직임은 기다려요.`;
 else if(result.state==='away')detail='8초 이상 화면 밖 방향이 이어졌어요. 필기·생각 중이면 유예해주세요.';
 $('focus-state').textContent=title;$('focus-evidence').textContent=detail;$('focus-state').closest('.focus-panel').dataset.state=result.state;$('focus-reference').disabled=!tracker.running;
 $('focus-notice').hidden=!result.notice;
 if(!result.notice&&nagBubbleVisible){nagBubbleVisible=false;bridge.window('bubble-clear-nag').catch(()=>{});}
 if(!result.notice&&nagVoice){nagVoice=null;speechSynthesis.cancel();}
 if(result.notice){const line=$('nag-tone').value==='firm'?'화면 밖을 향한 지 꽤 됐어요. 자료로 돌아와 다음 한 줄을 읽어봐요.':'눈동자 출장이 길어졌네. 화면으로 돌아와서 한 줄만 더 읽자.';$('nag-text').textContent=line;if(!nagBubbleVisible){nagBubbleVisible=true;showBubble({kind:'nag',text:line,question:'',phase:'idle',show:true});}
  if(result.nag&&!$('nag-mute').checked&&$('nag-tone').value!=='notice'){speechSynthesis.cancel();const speech=new SpeechSynthesisUtterance(line);nagVoice=speech;speech.onend=speech.onerror=()=>{if(nagVoice===speech)nagVoice=null;};speech.lang='ko-KR';speechSynthesis.speak(speech);}}
 const trayFocus=!tracker.running?'감지 꺼짐':title==='화면 기준 확인 중'?'기준 확인 중':({attending:'화면 응시 중',away_pending:'이탈 확인 중',away:'화면 이탈',unknown:'측정 불가',paused:'휴식 중',helping:'질문 중'})[result.state];
 const tray={running:Boolean(session&&session.status!=='ended'),paused:session?.status==='paused',camera:tracker.running,focus_enabled:focus.enabled,muted:$('nag-mute').checked,focus:trayFocus};
 const signature=JSON.stringify(tray);if(signature!==lastTray){lastTray=signature;bridge.window('tray-state',tray).catch(()=>{});}
}
tracker.sample=sample=>{lastSampleAt=sample.at_ms;latestPresence=sample.presence;applyFocus(sample);bridge.window('gaze-sample',sample).catch(()=>{});};
setInterval(()=>{bridge.window('overlay-bounds').then(b=>{overlayBounds=b;}).catch(()=>{});if(performance.now()-lastSampleAt>650)applyFocus({at_ms:performance.now(),validity:'unknown',validated:false,pose_ok:false,presence:{ready:Boolean(latestPresence?.ready),state:'unknown',reason:'stale'}});},250);
$('focus-reference').onclick=()=>{focus.reset();tracker.presence.reset();speechSynthesis.cancel();};
for(const id of ['focus-enabled','focus-mode','focus-sensitivity','nag-tone','nag-mute','voice-target']){
 const element=$(id),key='study-setting-'+id,saved=localStorage.getItem(key);
 if(saved!==null){if(element.type==='checkbox')element.checked=saved==='true';else if([...element.options].some(o=>o.value===saved))element.value=saved;}
 element.addEventListener('change',()=>{localStorage.setItem(key,element.type==='checkbox'?String(element.checked):element.value);if(id==='focus-enabled'||id==='focus-mode')focus.reset();if(id==='focus-sensitivity')tracker.presence.sensitivity=element.value;speechSynthesis.cancel();});
}
tracker.presence.sensitivity=$('focus-sensitivity').value;
bridge.onAppAction?.(async event=>{
 if(event.action==='settings'||event.action==='materials'){
  if(!$('region-editor').hidden)$('region-cancel').click();
  if(!$('calibration').hidden)await tracker.closeCalibration();
  if(document.body.classList.contains('collapsed'))document.body.classList.toggle('collapsed',await bridge.window('collapse'));
  $('settings').hidden=false;$(event.action==='materials'?'materials-manage':'settings').scrollIntoView({block:'start'});
 }
 if(event.action==='history'){$('settings').hidden=true;if(session)$('learning').hidden=false;$('chat').scrollIntoView({block:'center'});}
 if(event.action==='bubble-talk'){
  try{if(!bubbleConfigured){await bridge.window('show-main',{section:'settings'});return;}if(!session||session.status==='ended')await startStudy();if(session.status==='paused')render(await bridge.request('POST',`/study/sessions/${session.id}/pause`,{paused:false}));await voice.talk();}catch(e){error(e.message);}
 }
 if(event.action==='bubble-start'){try{await startStudy();}catch(e){error(e.message);}}
 if(event.action==='bubble-add-material')await materials.add();
 if(event.action==='bubble-cancel')voice.stop();
 if(event.action==='bubble-consent'){$('voice-consent').checked=Boolean(event.value);$('voice-consent').dispatchEvent(new Event('change'));}
 if(event.action==='bubble-grace'){grace('notes');showBubble({kind:'info',text:'필기·생각할 동안 1분은 조용히 있을게요.',phase:'idle',show:true});}
 if(event.action==='bubble-false-alarm'){grace('false_alarm');showBubble({kind:'info',text:'오탐으로 기록했어요. 필요하면 감도를 여유롭게 바꿔주세요.',phase:'idle',show:true});}
 if(event.action==='monitor')$('camera-toggle').click();
 if(event.action==='pause')$('pause').click();
 if(event.action==='focus-enabled'||event.action==='nag-mute'){$(event.action).checked=Boolean(event.value);$(event.action).dispatchEvent(new Event('change'));}
});
$('heart-toggle').onclick=async()=>{try{error();heart(await bridge.request('POST',`/study/heart/${heartReading?'disconnect':'connect'}`,{}));}catch(e){error(e.message);}};
$('sample').onclick=()=>{$('goal').value='조건부 확률을 예시로 설명하기';$('material').value=sample;};
async function startStudy(){
 if(session&&session.status!=='ended')return;
 error();render(await bridge.request('POST','/study/sessions',{goal:$('goal').value.trim()||'화면과 첨부 자료 이해하기',material:materials.text(),minutes:Number($('minutes').value),ai_enabled:$('ai').checked}));
 if($('focus-enabled').checked)tracker.startMonitoring().catch(e=>error(e.message));
}
$('start').onclick=()=>startStudy().catch(e=>error(e.message));
async function checkin(state){manualCheckin=false;render(await bridge.request('POST',`/study/sessions/${session.id}/checkins`,{state}));}
$('self-check').onclick=()=>{manualCheckin=true;$('checkin').hidden=false;};$('need-help').onclick=async()=>{try{await checkin('stuck');await voice.talk();}catch(e){error(e.message);}};$('thinking').onclick=()=>{grace('thinking');checkin('thinking').catch(e=>error(e.message));};
$('rest').onclick=async()=>{try{voice.stop();await checkin('tired');render(await bridge.request('POST',`/study/sessions/${session.id}/pause`,{paused:true}));}catch(e){error(e.message);}};
$('pause').onclick=async()=>{try{voice.stop();render(await bridge.request('POST',`/study/sessions/${session.id}/pause`,{paused:session.status==='running'}));}catch(e){error(e.message);}};
$('end').onclick=async()=>{try{voice.stop();tracker.stop();focus.reset();$('show-gaze').checked=false;await bridge.window('gaze-visible',false);render(await bridge.request('POST',`/study/sessions/${session.id}/end`,{}));}catch(e){error(e.message);}};
$('new-session').onclick=()=>{voice.stop();focus.reset();session=null;anchor=null;manualCheckin=false;lastMessageIds.clear();$('chat').replaceChildren();$('setup').hidden=false;$('summary').hidden=true;$('minutes').disabled=false;$('goal-display').textContent='작은 목표부터 시작해요';$('timer-label').textContent='오늘의 학습';clock();};
$('settings-toggle').onclick=()=>{$('settings').hidden=!$('settings').hidden;};$('close').onclick=()=>bridge.window('close');$('collapse').onclick=async()=>document.body.classList.toggle('collapsed',await bridge.window('collapse'));
bridge.onLost(()=>{ready=false;$('start').disabled=true;tracker.stop();error('학습 서버 연결이 끊겼어요. 앱을 다시 실행해주세요.');});
(async()=>{try{const v=await bridge.ready();if(!v?.ok)throw new Error(v?.message||'연결 실패');ready=true;$('start').disabled=false;$('connection').textContent='v0.8 · 로컬 처리 · '+(v.health.study_model.configured?'모델 설정됨':'데모 사용 가능');bubbleConfigured=Boolean(v.health.study_model.configured);if(!bubbleConfigured)$('ai').checked=false;showBubble({kind:'welcome',text:bubbleConfigured?'궁금한 부분이 생기면 말로 물어봐요. 현재 화면과 첨부 자료를 함께 볼게요.':'먼저 설정에서 OpenRouter API 키를 입력해주세요.',phase:'idle',show:true});}catch(e){error(e.message);}})();
setInterval(async()=>{clock();if(!ready)return;try{if(session&&session.status!=='ended')render(await bridge.request('GET',`/study/sessions/${session.id}`));else heart(await bridge.request('GET','/study/heart'));}catch{}},2000);
window.addEventListener('beforeunload',()=>{voice.stop();tracker.stop();});
