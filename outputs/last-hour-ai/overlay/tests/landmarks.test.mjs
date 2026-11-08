import test from 'node:test';
import assert from 'node:assert/strict';
import {features} from '../study-signals.mjs';
import {ScreenGazeModel,calibrationTargets,validationTargets} from '../screen-gaze.mjs';
// Synthetic landmark geometry, including eyelids that follow the iris vertically.
// Tests the actual extractor -> regression path; not human webcam accuracy.
function landmarks(x=.5,y=.5,{blink=false,roll=0}={}){
 const p=Array.from({length:478},()=>({x:.5,y:.5}));
 const hx=(x-.5)*.002,vy=(y-.5)*.001;
 for(const [index,px,py] of [[33,.3,.4],[133,.4,.4],[362,.6,.4],[263,.7,.4],
  [468,.35+hx,.4+vy],[473,.65+hx,.4+vy],[159,.35,.4+vy-(blink?.001:.015)],[145,.35,.4+vy+(blink?.001:.015)],
  [386,.65,.4+vy-(blink?.001:.015)],[374,.65,.4+vy+(blink?.001:.015)],[1,.5,.52]])p[index]={x:px,y:py};
 if(roll)for(const a of p){const dx=a.x-.5,dy=a.y-.4;a.x=.5+Math.cos(roll)*dx-Math.sin(roll)*dy;a.y=.4+Math.sin(roll)*dx+Math.cos(roll)*dy;}
 return p;
}
const rows=targets=>targets.map(target=>({target,features:features(landmarks(target.x,target.y))}));
const display={x:0,y:0,width:1440,height:900};
test('vertical iris signal survives eyelids following the same vertical motion',()=>{
 const up=features(landmarks(.5,.12)),down=features(landmarks(.5,.88));
 assert.ok(down[2]-up[2]>.007);assert.equal(features(landmarks(.5,.5,{blink:true})),null);
});
test('small consistent signals below the former absolute thresholds can validate',()=>{
 const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);
 assert.equal(m.validate(rows(validationTargets)).accepted,true);
 const p=m.predict(features(landmarks(.25,.75)));assert.ok(Math.abs(p.x-360)<15);assert.ok(Math.abs(p.y-675)<15);
});
test('eye axes remain consistent during an in-plane head tilt',()=>{
 const base=features(landmarks(.25,.75)),tilted=features(landmarks(.25,.75,{roll:.15}));
 for(let i=0;i<3;i++)assert.ok(Math.abs(base[i]-tilted[i])<1e-10);
});
test('permissive fitting never turns a poor independent validation into a pass',()=>{
 const m=new ScreenGazeModel().fit(rows(calibrationTargets),display);
 const bad=rows(validationTargets).map(r=>({...r,target:{x:1-r.target.x,y:1-r.target.y}}));
 assert.equal(m.validate(bad).accepted,false);assert.equal(m.predict(features(landmarks())),null);
});
test('small gaze motion with independent landmark jitter still validates through real extraction',()=>{
 let seed=731;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/2**32-.5;};
 const build=targets=>targets.map(target=>{
  const samples=Array.from({length:12},()=>{
   const p=landmarks(target.x,target.y);
   for(const i of [33,133,362,263,468,473,159,145,386,374]){p[i].x+=random()*.00005;p[i].y+=random()*.00005;}
   return features(p);
  });
  return {target,features:samples[0].map((_,i)=>samples.map(r=>r[i]).sort((a,b)=>a-b)[6])};
 });
 const m=new ScreenGazeModel().fit(build(calibrationTargets),display),result=m.validate(build(validationTargets));
 assert.equal(result.accepted,true);assert.ok(result.max_error_px<50);
});
import {GazeTracker} from '../gaze.mjs';
test('a repeated or stalled video frame cannot be counted as a fresh calibration sample',async()=>{
 const video={readyState:4,currentTime:1},tracker=new GazeTracker(video,()=>{},()=>{},()=>{});let detections=0;
 tracker.running=true;tracker.setDisplay(display);tracker.model={detectForVideo:()=>{detections++;return {faceLandmarks:[landmarks()]};}};
 tracker.beginCalibration(display);tracker.calibration.started=performance.now()-1100;
 await tracker.tick();clearTimeout(tracker.timer);await tracker.tick();clearTimeout(tracker.timer);
 assert.equal(detections,1);assert.equal(tracker.calibration.samples.length,1);
 video.currentTime+=1/30;await tracker.tick();clearTimeout(tracker.timer);
 assert.equal(detections,2);assert.equal(tracker.calibration.samples.length,2);tracker.running=false;
});
