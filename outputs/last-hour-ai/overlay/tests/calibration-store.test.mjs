import test from 'node:test';import assert from 'node:assert/strict';
import {CalibrationStore,calibrationContext} from '../calibration-store.mjs';
import {ScreenGazeModel,calibrationTargets,validationTargets} from '../screen-gaze.mjs';
import {GazeTracker} from '../gaze.mjs';
const display={x:-1440,y:24,width:1440,height:900,display_id:2,scale_factor:2,rotation:0};
const eye=(x,y)=>[.4+x*.2,.6-x*.18,(y-.5)*.12,.03+(x-.5)*.01,.1+(y-.5)*.01];
const rows=targets=>targets.map(target=>({target,features:eye(target.x,target.y)}));
function fixture(){
 const data=new Map(),storage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const tracker={engineInfo:{model:'unigaze_l16_joint'},cameraId:'camera-1',videoSize:'1280x720'};
 const model=new ScreenGazeModel().fit(rows(calibrationTargets),display);model.validate(rows(validationTargets));
 return {storage,data,context:calibrationContext(tracker,display),model};
}
test('validated coefficients survive a store restart; raw samples/face data are never saved',()=>{
 const f=fixture();new CalibrationStore(f.storage).save(f.context,f.model);
 const profile=new CalibrationStore(f.storage).load(f.context,display);assert.ok(profile);
 assert.deepEqual(Object.keys(profile).sort(),['context','model','saved_at']);
 assert.deepEqual(Object.keys(profile.model).sort(),['means','scales','weights']);
 const restored=ScreenGazeModel.restore(profile.model,display);
 assert.deepEqual(restored.raw(eye(.25,.75)),f.model.raw(eye(.25,.75)));
 assert.equal(restored.predict(eye(.25,.75)),null,'loading must not activate focus before revalidation');
});
test('saved calibration reuses coefficients and requires only five fresh held-out targets',()=>{
 const f=fixture(),profile=new CalibrationStore(f.storage).save(f.context,f.model),updates=[];
 const tracker=new GazeTracker({},v=>updates.push(v),()=>{},()=>{});tracker.running=true;
 tracker.beginSavedValidation(display,profile);assert.equal(tracker.mapping,null);assert.equal(tracker.calibration.stage,'validation');
 for(const target of validationTargets){const c=tracker.calibration;for(let i=0;i<12;i++)tracker.collect(eye(target.x,target.y),c.started+1000+i*120);}
 assert.ok(tracker.mapping.validated);assert.equal(updates.at(-1).reused,true);assert.equal(tracker.calibration,null);
});
test('changed camera, model, monitor, scale or resolution never restores another setup',()=>{
 const f=fixture(),store=new CalibrationStore(f.storage);store.save(f.context,f.model);
 for(const changed of [{camera_id:'other'},{engine:'unigaze_b16_joint'},{video_size:'640x480'},{display_id:'3'},{width:1920},{scale:1},{rotation:90},{pipeline:2}])assert.equal(store.load({...f.context,...changed},display),null);
 assert.ok(store.load({...f.context}, {...display,viewport:{x:0,y:30,width:100,height:100}}),'Dock/work-area changes do not invalidate full-display mapping');
});
test('failed revalidation never enables a saved model; unvalidated or corrupt profiles are rejected',()=>{
 const f=fixture(),store=new CalibrationStore(f.storage);f.model.validated=false;assert.throws(()=>store.save(f.context,f.model));
 f.model.validated=true;const profile=store.save(f.context,f.model),tracker=new GazeTracker({},()=>{},()=>{},()=>{});tracker.running=true;tracker.beginSavedValidation(display,profile);
 for(const target of validationTargets){const c=tracker.calibration;for(let i=0;i<12;i++)tracker.collect(eye(1-target.x,1-target.y),c.started+1000+i*120);}
 assert.equal(tracker.mapping,null);
 f.storage.setItem('study-calibrations-v1',JSON.stringify([{...profile,model:{...profile.model,scales:[0,0,0,0,0]}}]));assert.equal(store.load(f.context,display),null);
 f.storage.setItem('study-calibrations-v1','bad JSON');assert.equal(store.load(f.context,display),null);
});
test('saving is bounded to eight setups and explicit deletion persists',()=>{
 const f=fixture(),store=new CalibrationStore(f.storage);for(let i=0;i<12;i++)store.save({...f.context,camera_id:'camera-'+i},f.model);
 assert.equal(store.entries().length,8);store.clear();assert.equal(new CalibrationStore(f.storage).entries().length,0);
});
