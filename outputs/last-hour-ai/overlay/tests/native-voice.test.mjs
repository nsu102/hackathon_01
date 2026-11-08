import test from 'node:test';import assert from 'node:assert/strict';import {EventEmitter} from 'node:events';
import createVoice from '../native-voice.cjs';
async function fixture({captureWait=async()=>{},configure=true,extraWindows=()=>[],onCapture=()=>{}}={}){
 let micState='granted',now=0,visible=true,pointVisible=true,pressed;const sent=[],crops=[],order=[],hook=new EventEmitter();hook.start=()=>{};hook.stop=()=>{};
 const image={isEmpty:()=>false,getSize:()=>({width:2880,height:1800}),crop:r=>{crops.push(r);return {getSize:()=>({width:r.width,height:r.height}),toPNG:()=>Buffer.from('fixture')};},toDataURL:()=> 'data:image/png;base64,fixture'};
 const win={isDestroyed:()=>false,isVisible:()=>visible,getBounds:()=>({x:-500,y:0,width:400,height:600}),hide:()=>{visible=false;order.push('hide-overlay');},showInactive:()=>{visible=true;order.push('restore-overlay');},webContents:{send:(_,event)=>sent.push(event)}};
 const pointer={isVisible:()=>pointVisible,hide:()=>{pointVisible=false;order.push('hide-pointer');},isDestroyed:()=>false,showInactive:()=>{pointVisible=true;order.push('restore-pointer');}};
 const apiCalls=[];
 const voice=await createVoice({win:()=>win,display:()=>({id:2,bounds:{x:-1440,y:0,width:1440,height:900},scaleFactor:2}),api:async(...args)=>{apiCalls.push(args);return {message:{content:'fixture'}};},systemPreferences:{getMediaAccessStatus:type=>type==='microphone'?micState:'granted',isTrustedAccessibilityClient:()=>true,askForMediaAccess:async()=>true},globalShortcut:{register:(_,callback)=>{pressed=callback;return true;},unregister:()=>{}},desktopCapturer:{getSources:async()=>{assert.equal(visible,false);assert.equal(pointVisible,false);order.push('capture');return [{display_id:'2',thumbnail:image}];}},pointer:()=>pointer,extraWindows,onCapture,screen:{},keyHook:()=>({uIOhook:hook,UiohookKey:{Enter:28,Escape:1}}),now:()=>now,wait:captureWait});
 if(configure)await voice.configure({enabled:true,consent:true,shortcut:'CommandOrControl+Shift+Enter'});voice.setSession('fixture-session');
 for(let t=0;t<=1000;t+=100){now=t;voice.sample({x:-1000,y:450,at_ms:t,validity:'valid',validated:true,pose_ok:true,calibration_id:'cal-1',display_id:2,validation_error_px:30});}
 return {voice,press:()=>pressed(),hook,sent,apiCalls,crops,order,setMic:s=>micState=s,setTime:t=>now=t};
}
test('native capture freezes gaze, hides owned windows, restores inactive and submits only after key release',async()=>{
 const f=await fixture();await f.press();assert.deepEqual(f.order,['hide-overlay','hide-pointer','capture','restore-overlay','restore-pointer']);const start=f.sent.find(e=>e.type==='start');assert.ok(start);
 await assert.rejects(()=>f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true}),/키 해제/);
 f.setTime(1500);f.voice.sample({x:-300,y:300,validity:'valid',validated:true,pose_ok:true}); // later overlay gaze cannot replace frozen target
 f.hook.emit('keyup',{keycode:28});await f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true});
 assert.equal(f.apiCalls.length,1);assert.equal(f.apiCalls[0][2].target.calibration_id,'cal-1');assert.deepEqual(f.crops[0],{x:400,y:600,width:960,height:600});f.voice.disable();
});
test('release while capture prepares cancels and never creates a sendable recording',async()=>{let resume;const f=await fixture({captureWait:()=>new Promise(r=>resume=r)});const pending=f.press();f.hook.emit('keyup',{keycode:28});resume();await pending;assert.ok(f.sent.some(e=>e.type==='cancel'));assert.ok(!f.sent.some(e=>e.type==='start'));assert.equal(f.apiCalls.length,0);f.voice.disable();});
test('missing gaze asks for a region on the original capture; cancellation discards it',async()=>{const f=await fixture();f.setTime(4000);await f.press();const start=f.sent.find(e=>e.type==='start');f.hook.emit('keyup',{keycode:28});assert.equal((await f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true})).select,true);assert.equal(f.apiCalls.length,0);assert.ok(f.sent.some(e=>e.type==='select'));f.voice.cancel();await assert.rejects(()=>f.voice.select({x:0,y:0,width:100,height:100}));f.voice.disable();});

test('20s watchdog discards and a late key release cannot authorize a send',async t=>{t.mock.timers.enable({apis:['setTimeout']});const f=await fixture();await f.press();const start=f.sent.find(e=>e.type==='start');t.mock.timers.tick(20000);f.hook.emit('keyup',{keycode:28});await assert.rejects(()=>f.voice.submit({id:start.data.id,audio:'x',duration_ms:19000,speech_detected:true}));assert.equal(f.apiCalls.length,0);assert.ok(f.sent.some(e=>e.type==='cancel'&&e.data.includes('20초')));f.voice.disable();});
test('microphone permission revocation discards a released recording',async()=>{const f=await fixture();await f.press();const start=f.sent.find(e=>e.type==='start');f.hook.emit('keyup',{keycode:28});f.setMic('denied');await assert.rejects(()=>f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true}),/권한/);assert.equal(f.apiCalls.length,0);f.voice.disable();});
test('neural processing latency cannot make old camera frames look current at the hotkey',async()=>{
 const f=await fixture();
 for(let t=2000;t<=2600;t+=200){f.setTime(t);f.voice.sample({x:-1000,y:450,at_ms:t-400,latency_ms:400,validity:'valid',validated:true,pose_ok:true,calibration_id:'cal-1',display_id:2,validation_error_px:30});}
 await f.press();const start=f.sent.find(e=>e.type==='start');f.hook.emit('keyup',{keycode:28});
 assert.equal((await f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true})).select,true);
 assert.equal(f.apiCalls.length,0);f.voice.disable();
});
test('typed screen help needs no voice configuration and uploads only a user-confirmed frozen crop',async()=>{
 const f=await fixture({configure:false});
 const frame=await f.voice.screenPrepare({message:'분모는 왜 4야?',consent:true});
 assert.ok(frame.initial);assert.equal(frame.display.display_id,2);assert.equal(f.apiCalls.length,0);
 assert.deepEqual(f.order,['hide-overlay','hide-pointer','capture','restore-overlay','restore-pointer']);
 await f.voice.screenSubmit({x:-1400,y:100,width:600,height:400});
 assert.equal(f.apiCalls[0][1],'/study/sessions/fixture-session/screen-help');
 const body=f.apiCalls[0][2];assert.equal(body.message,'분모는 왜 4야?');assert.equal(body.target.selection,'manual');assert.ok(!('audio' in body));
 assert.deepEqual(f.crops[0],{x:80,y:200,width:1200,height:800});f.voice.disable();
});
test('typed preparation never sends on cancellation, missing consent, or session change',async()=>{
 const f=await fixture({configure:false});
 await assert.rejects(()=>f.voice.screenPrepare({message:'질문',consent:false}));assert.equal(f.order.length,0);
 await f.voice.screenPrepare({message:'질문',consent:true});
 await assert.rejects(()=>f.voice.screenPrepare({message:'중복',consent:true}));
 f.voice.setSession(null);
 await assert.rejects(()=>f.voice.screenSubmit({x:-1400,y:100,width:600,height:400}));assert.equal(f.apiCalls.length,0);f.voice.disable();
});
test('cancellation while a typed screen capture is preparing cannot revive the frozen frame',async()=>{
 let resume;const f=await fixture({configure:false,captureWait:()=>new Promise(r=>resume=r)});
 const preparing=f.voice.screenPrepare({message:'설명',consent:true});f.voice.cancel();resume();
 await assert.rejects(()=>preparing,/취소/);await assert.rejects(()=>f.voice.screenSubmit({x:-1400,y:100,width:600,height:400}));assert.equal(f.apiCalls.length,0);f.voice.disable();
});
test('button voice records a frozen monitor without calibration or global-key configuration; only explicit send releases it',async()=>{
 const f=await fixture({configure:false});f.setTime(4000);
 await f.voice.buttonStart({consent:true,target:'screen'});const start=f.sent.find(e=>e.type==='start');assert.equal(start.data.control,'button');assert.equal(f.hook.listenerCount('keyup'),0);
 await assert.rejects(()=>f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true}),/키 해제/);
 f.voice.buttonRelease();await f.voice.submit({id:start.data.id,audio:'x',duration_ms:1000,speech_detected:true});
 assert.equal(f.apiCalls.length,1);assert.equal(f.apiCalls[0][2].target.selection,'screen');assert.equal(f.apiCalls[0][2].target.calibration_id,null);assert.deepEqual(f.crops[0],{x:0,y:0,width:2880,height:1800});f.voice.disable();
});
test('button recording cancellation and twenty-second timeout discard, and missing consent captures nothing',async t=>{
 t.mock.timers.enable({apis:['setTimeout']});const f=await fixture({configure:false});
 await assert.rejects(()=>f.voice.buttonStart({consent:false,target:'screen'}));assert.equal(f.order.length,0);
 await f.voice.buttonStart({consent:true,target:'screen'});t.mock.timers.tick(20000);
 assert.throws(()=>f.voice.buttonRelease());assert.equal(f.apiCalls.length,0);f.voice.disable();
});
test('turning off optional keyboard hooks preserves the active session for button voice',async()=>{
 const f=await fixture({configure:false});await f.voice.configure({enabled:false});
 await f.voice.buttonStart({consent:true,target:'screen'});assert.ok(f.sent.some(e=>e.type==='start'));f.voice.disable();
});

test('chat bubbles are hidden during the captured frame and restored without focus',async()=>{
 let visible=true;const guarded=[];const bubble={isDestroyed:()=>false,isVisible:()=>visible,getBounds:()=>({x:-400,y:650,width:350,height:200}),hide:()=>{visible=false;},showInactive:()=>{visible=true;}};
 const f=await fixture({configure:false,extraWindows:()=>[bubble],onCapture:v=>guarded.push(v),captureWait:async()=>{assert.equal(visible,false);}});
 await f.voice.buttonStart({consent:true,target:'screen'});assert.deepEqual(guarded,[true,false]);assert.equal(visible,true);f.voice.disable();
});
