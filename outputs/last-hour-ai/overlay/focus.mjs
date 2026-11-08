// Local, monotonic controller. Gaps never count as continuous evidence.
export const inside=(p,r)=>Boolean(p&&r&&p.x>=r.x&&p.y>=r.y&&p.x<=r.x+r.width&&p.y<=r.y+r.height);
export class FocusController {
 constructor(event=()=>{}){this.event=event;this.state='unknown';this.enabled=true;this.last=null;this.awayAt=null;this.returnAt=null;this.lastNag=-Infinity;this.nagged=false;this.notice=false;this.graceUntil=0;}
 reset(){this.last=null;this.awayAt=null;this.returnAt=null;this.nagged=false;this.notice=false;}
 transition(state,reason,at,duration=0){if(this.state!==state){const from=this.state;this.state=state;this.event({from,to:state,reason,duration_ms:Math.round(duration),at_ms:Math.round(at),correction:null});}}
 grace(at,ms=60000){this.graceUntil=at+ms;this.reset();}
 update(sample,{running=true,helping=false,study=null,notes=null,overlay=null,mode='region'}={}){
  const at=sample.at_ms;
  const gap=this.last!==null&&(at-this.last>650||at<this.last);this.last=at;
  let suppressed=!running||!this.enabled||at<this.graceUntil;
  const invalid=gap||(mode==='screen'?(!sample.presence?.ready||!['on_screen','away'].includes(sample.presence.state)):(!sample.validated||sample.validity==='unknown'||!study||!sample.pose_ok));
  if(helping||suppressed||invalid){this.awayAt=null;this.returnAt=null;this.notice=false;this.nagged=false;this.transition(helping?'helping':suppressed?'paused':'unknown',helping?'help':suppressed?'user_pause':'quality',at);return {state:this.state,notice:false,nag:false};}
  const on=mode==='screen'?sample.presence.state==='on_screen':inside(sample,study)||inside(sample,notes)||(Array.isArray(overlay)?overlay:[overlay]).some(r=>inside(sample,r));
  if(on){
   this.returnAt??=at;
   if(this.awayAt===null||at-this.returnAt>=2000){this.awayAt=null;this.notice=false;this.nagged=false;this.transition('attending','in_allowed_region',at);}
  }else{
   this.returnAt=null;this.awayAt??=at;const elapsed=at-this.awayAt;
   this.transition(elapsed>=8000?'away':'away_pending',mode==='screen'||sample.validity==='offscreen'?'offscreen':'outside_study',at,elapsed);
   this.notice=elapsed>=8000;
   if(elapsed>=20000&&!this.nagged&&at-this.lastNag>=90000){this.nagged=true;this.lastNag=at;return {state:this.state,notice:true,nag:true};}
  }
  return {state:this.state,notice:this.notice,nag:false};
 }
}
export class GazeBuffer {
 constructor(){this.samples=[];}
 add(s){this.samples.push({...s});this.samples=this.samples.filter(p=>p.at_ms>=s.at_ms-1500);}
 freeze(at){
  if(!this.samples.length||!this.samples.at(-1).validated||this.samples.at(-1).validity!=='valid'||!this.samples.at(-1).pose_ok)return null;
  const rows=this.samples.filter(s=>s.at_ms>=at-1000&&s.at_ms<=at&&s.validity==='valid'&&s.validated&&s.pose_ok);
  if(rows.length<4||at-rows.at(-1).at_ms>350||rows.at(-1).at_ms-rows[0].at_ms<450)return null;
  if(rows.some(s=>s.calibration_id!==rows[0].calibration_id||s.display_id!==rows[0].display_id))return null;
  const med=a=>[...a].sort((x,y)=>x-y)[Math.floor(a.length/2)],x=med(rows.map(s=>s.x)),y=med(rows.map(s=>s.y));
  const error=rows.at(-1).validation_error_px;
  if(rows.some(s=>Math.hypot(s.x-x,s.y-y)>Math.max(100,error*1.5)))return null;
  return {x,y,error_px:error,display_id:rows[0].display_id,calibration_id:rows[0].calibration_id};
 }
 clear(){this.samples=[];}
}
export function dipToPixels(rect,display,image){
 if(!rect||!['x','y','width','height'].every(k=>Number.isFinite(rect[k]))||rect.width<=0||rect.height<=0)throw new Error('선택 영역 좌표를 확인해주세요.');
 const x=Math.max(display.x,rect.x),y=Math.max(display.y,rect.y),right=Math.min(display.x+display.width,rect.x+rect.width),bottom=Math.min(display.y+display.height,rect.y+rect.height);
 if(right<=x||bottom<=y)throw new Error('선택 영역이 화면 밖에 있어요.');
 const sx=image.width/display.width,sy=image.height/display.height;
 const left=Math.floor((x-display.x)*sx),top=Math.floor((y-display.y)*sy);
 return {x:left,y:top,width:Math.min(image.width-left,Math.ceil((right-display.x)*sx)-left),height:Math.min(image.height-top,Math.ceil((bottom-display.y)*sy)-top)};
}
