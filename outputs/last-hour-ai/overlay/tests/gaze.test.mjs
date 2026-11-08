import test from 'node:test';
import assert from 'node:assert/strict';
import {ScreenGazeModel,calibrationTargets,validationTargets} from '../screen-gaze.mjs';
import {features,ObservationWindow} from '../study-signals.mjs';
const display={x:-1440,y:24,width:1440,height:900};
// Synthetic eyes with a known coordinate mapping; this is not human accuracy evidence.
const eye=(x,y)=>[.4+x*.2,.6-x*.18,(y-.5)*.12,.03+(x-.5)*.01,.1+(y-.5)*.01];
const rows=targets=>targets.map(target=>({target,features:eye(target.x,target.y)}));
test('calibration alone cannot produce a screen coordinate',()=>{const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);assert.equal(m.predict(eye(.4,.6)),null);});
test('held-out points validate mapping including a negative display origin',()=>{const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);const result=m.validate(rows(validationTargets));assert.equal(result.accepted,true);const p=m.predict(eye(.25,.75));assert.ok(Math.abs(p.x-(-1080))<15);assert.ok(Math.abs(p.y-699)<15);});
test('constant eyes and deliberately incorrect held-out labels are rejected',()=>{assert.throws(()=>new ScreenGazeModel().fit(calibrationTargets.map(target=>({target,features:eye(.5,.5)})),display));const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);const bad=rows(validationTargets).map(r=>({...r,target:{x:1-r.target.x,y:1-r.target.y}}));assert.equal(m.validate(bad).accepted,false);assert.equal(m.predict(eye(.5,.5)),null);});
test('missing eyes, non-finite and out-of-domain inputs have no coordinate',()=>{const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);m.validate(rows(validationTargets));assert.equal(m.predict(null),null);assert.equal(m.predict([NaN,0,0,0,0]),null);assert.equal(m.predict(eye(5,5)),null);assert.equal(features([]),null);});
test('aggregates describe missing measurements without inventing an away gaze',()=>{const w=new ObservationWindow();w.add('on',0);w.add('unknown',5000);const s=w.summary(10000,true);assert.equal(s.on_ratio,.5);assert.equal(s.unknown_ratio,.5);assert.equal(s.away_ratio,0);assert.equal(s.window_seconds,10);});
import {decodeAngle,projectGaze} from '../pretrained-gaze.mjs';
test('pretrained logits decode yaw/pitch angles without user samples',()=>{const logits=new Float32Array(90).fill(-100);logits[45]=100;assert.equal(decodeAngle(logits),0);assert.equal(decodeAngle([0]),null);});
test('uncalibrated projection is explicitly unvalidated and never clamps off-screen gaze',()=>{const d={x:0,y:0,width:1440,height:900},eye={x:.5,y:.5,separation:.075,videoAspect:4/3};const p=projectGaze(0,-.10,eye,d);assert.ok(p&&p.x===720&&p.y>0);assert.equal(p.error_px,null);assert.equal(p.validated,false);assert.equal(projectGaze(0,0,{...eye,separation:0},d),null);assert.equal(projectGaze(1.2,0,eye,d),null);});
test('valid offscreen prediction is preserved and validation quality is mandatory',()=>{const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);assert.equal(m.validate(rows(validationTargets),.79).accepted,false);assert.equal(m.predict(eye(.5,.5)),null);assert.equal(m.validate(rows(validationTargets),.8).accepted,true);const p=m.predict(eye(1.15,.5));assert.ok(p.nx>1);assert.ok(p.x>display.x+display.width);});
test('validation uses resolution-scaled median and max thresholds',()=>{for(const factor of [1,2,.5]){const d={...display,width:1440*factor,height:900*factor},m=new ScreenGazeModel().fit(rows(calibrationTargets),d);const bad=rows(validationTargets).map(r=>({...r,target:{x:r.target.x+.1,y:r.target.y}}));assert.equal(m.validate(bad).accepted,false);}});
import {GazeTracker} from '../gaze.mjs';
test('collector waits for stabilization and exactly 12 valid samples on 9+5 separate targets',()=>{const updates=[],tracker=new GazeTracker({},v=>updates.push(v),()=>{},()=>{});tracker.running=true;tracker.beginCalibration(display);let at=tracker.calibration.started;
 for(let target=0;target<14;target++){
  const c=tracker.calibration,t=(c.stage==='train'?calibrationTargets:validationTargets)[c.index];
  tracker.collect(eye(t.x,t.y),c.started+500);assert.equal(c.samples.length,0);
  for(let i=0;i<12;i++){at=c.started+1000+i*120;tracker.collect(eye(t.x,t.y),at);}
 }
 assert.equal(tracker.mapping.validated,true);assert.equal(tracker.calibration,null);assert.ok(tracker.calibrationId);assert.equal(updates.at(-1).valid_ratio,1);
 tracker.cancelCalibration();assert.equal(tracker.mapping,null);
});
test('work-area calibration targets map to full-monitor DIP despite menu and dock insets',()=>{
 const d={x:-1440,y:-100,width:1440,height:900,display_id:2,viewport:{x:-1440,y:-76,width:1440,height:840}},tracker=new GazeTracker({},()=>{},()=>{},()=>{});
 tracker.running=true;tracker.beginCalibration(d);
 for(let target=0;target<14;target++){
  const c=tracker.calibration,t=(c.stage==='train'?calibrationTargets:validationTargets)[c.index];
  for(let i=0;i<12;i++)tracker.collect(eye(t.x,t.y),c.started+1000+i*120);
 }
 assert.equal(tracker.mapping.validated,true);assert.equal(tracker.mapping.display.height,900);
 const p=tracker.mapping.predict(eye(.25,.75));assert.ok(Math.abs(p.x+1080)<15);assert.ok(Math.abs(p.y-554)<15);
});
