import {ScreenGazeModel} from './screen-gaze.mjs';
const KEY='study-calibrations-v1';
// Version includes the neural feature/normalization pipeline, not just the weights.
export function calibrationContext(tracker,display){
 return {pipeline:1,engine:tracker.engineInfo?.model,camera_id:tracker.cameraId,video_size:tracker.videoSize,display_id:String(display.display_id),x:display.x,y:display.y,width:display.width,height:display.height,scale:display.scale_factor??1,rotation:display.rotation??0};
}
const fingerprint=context=>JSON.stringify(context);
export class CalibrationStore{
 constructor(storage){this.storage=storage;}
 entries(){
  try{const text=this.storage.getItem(KEY);if(!text||text.length>64000)return [];const entries=JSON.parse(text);return Array.isArray(entries)?entries.slice(0,8):[];}catch{return [];}
 }
 load(context,display){
  if(!context.engine||!context.camera_id||!context.video_size)return null;
  const saved=this.entries().find(v=>v&&fingerprint(v.context)===fingerprint(context));
  if(!saved)return null;
  try{ScreenGazeModel.restore(saved.model,display);if(!Number.isFinite(saved.saved_at))return null;return saved;}catch{return null;}
 }
 save(context,model){
  if(!context.engine||!context.camera_id||!context.video_size)throw new Error('카메라 정보를 확인하지 못해 보정을 저장하지 못했어요.');
  const entry={context,model:model.serialize(),saved_at:Date.now()};
  this.storage.setItem(KEY,JSON.stringify([entry,...this.entries().filter(v=>v&&fingerprint(v.context)!==fingerprint(context))].slice(0,8)));
  return entry;
 }
 clear(){this.storage.removeItem(KEY);}
}
