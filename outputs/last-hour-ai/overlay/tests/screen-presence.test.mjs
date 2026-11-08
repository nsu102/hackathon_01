import test from 'node:test';import assert from 'node:assert/strict';
import {ScreenPresence} from '../screen-presence.mjs';import {FocusController} from '../focus.mjs';
const face=[.5,.5,.25],eye=(yaw=0,pitch=0,head=0)=>[Math.tan(yaw*Math.PI/180),Math.tan(pitch*Math.PI/180),0,head*Math.PI/180,0];
function ready(){const presence=new ScreenPresence();for(let at=0;at<=1500;at+=100)presence.update(eye(),at,face);return presence;}
test('coarse direction needs fresh stable reference but no 9-point mapping or study rectangle',()=>{
 const p=new ScreenPresence();assert.equal(p.update(eye(),0,face).ready,false);for(let at=100;at<=1500;at+=100)p.update(eye(),at,face);
 const sample={at_ms:1600,validated:false,validity:'unknown',pose_ok:false,presence:p.update(eye(),1600,face)};
 assert.equal(sample.presence.state,'on_screen');assert.equal(new FocusController().update(sample,{mode:'screen'}).state,'attending');
 assert.equal(new FocusController().update(sample,{mode:'region'}).state,'unknown','precise mode keeps its original calibration gate');
});
test('actual coarse classifier drives 8s notice, 20s nag, and two-second recovery without pixel coordinates',()=>{
 const p=ready(),focus=new FocusController();let result;
 for(let at=1600;at<=23000;at+=100){result=focus.update({at_ms:at,presence:p.update(eye(40),at,face)},{mode:'screen'});if(at===5000)assert.equal(result.notice,false);if(at===10000)assert.equal(result.notice,true);if(result.nag)assert.ok(at-focus.awayAt>=20000);}
 assert.equal(result.state,'away');assert.ok(focus.nagged);
 for(let at=23100;at<=25800;at+=100)result=focus.update({at_ms:at,presence:p.update(eye(),at,face)},{mode:'screen'});
 assert.equal(result.state,'attending');assert.equal(result.notice,false);
});
test('missing eyes, camera gaps and moved seating stay unknown and cannot accumulate a scolding',()=>{
 const p=ready(),focus=new FocusController();
 assert.equal(p.update(null,1600,face).state,'unknown');assert.equal(p.update(eye(),2500,face).reason,'stale');
 assert.equal(p.update(eye(),2600,[.8,.5,.25]).reason,'position_changed');
 for(let at=2700;at<40000;at+=100){const r=focus.update({at_ms:at,presence:p.update(null,at,face)},{mode:'screen'});assert.equal(r.nag,false);assert.equal(r.notice,false);}
});
test('looking away never trains itself into the reference and sensitivity is adjustable',()=>{
 const p=ready(),baseline=[...p.reference];for(let at=1600;at<=9000;at+=100)p.update(eye(40),at,face);assert.deepEqual(p.reference,baseline);assert.equal(p.state,'away');
 const relaxed=ready();relaxed.sensitivity='relaxed';for(let at=1600;at<=2000;at+=100)relaxed.update(eye(25),at,face);assert.equal(relaxed.state,'on_screen');
 const sensitive=ready();sensitive.sensitivity='sensitive';for(let at=1600;at<=2000;at+=100)sensitive.update(eye(25),at,face);assert.equal(sensitive.state,'away');
});
test('unstable startup and repeated timestamps cannot establish a reference',()=>{
 const p=new ScreenPresence();let result;for(let at=0;at<=1500;at+=100)result=p.update(eye(at%200?15:-15),at,face);assert.equal(result.ready,false);assert.equal(p.reference,null);
 p.reset();for(let i=0;i<30;i++)result=p.update(eye(),0,face);assert.equal(result.ready,false);assert.equal(p.reference,null);
});
