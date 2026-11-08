// Coarse screen-facing evidence, independent of pixel-coordinate calibration.
// These initial angular thresholds need human/device validation; no mind-wandering claim.
const median=values=>[...values].sort((a,b)=>a-b)[Math.floor(values.length/2)];
const middle=rows=>rows[0].map((_,i)=>median(rows.map(r=>r[i])));
const radians=degrees=>degrees*Math.PI/180;
export class ScreenPresence{
 constructor(){this.reset();this.sensitivity='balanced';}
 reset(){this.reference=null;this.referencePose=null;this.rows=[];this.poses=[];this.recent=[];this.started=null;this.last=null;this.state='unknown';}
 unknown(reason='missing_eyes'){return {ready:Boolean(this.reference),state:'unknown',reason};}
 update(features,at,pose=null){
  if(!Number.isFinite(at))return this.unknown('stale');
  const gap=this.last!==null&&(at-this.last>650||at<=this.last);this.last=at;
  if(!Array.isArray(features)||features.length!==5||!features.every(Number.isFinite)){
   this.recent=[];if(!this.reference){this.rows=[];this.poses=[];this.started=null;}
   return this.unknown('missing_eyes');
  }
  const angles=[Math.atan(features[0]),Math.atan(features[1]),features[3],features[4]];
  if(gap){this.recent=[];if(!this.reference){this.rows=[];this.poses=[];this.started=null;}return this.unknown('stale');}
  if(!this.reference){
   this.started??=at;this.rows.push(angles);if(pose)this.poses.push(pose);
   if(this.rows.length<12||at-this.started<1500)return {ready:false,state:'unknown',reason:'reference',progress:Math.min(1,(at-this.started)/1500)};
   const center=middle(this.rows);
   // A single neural outlier must not trap a user in an endless startup loop.
   if(center.some((_,i)=>median(this.rows.map(r=>Math.abs(r[i]-center[i])))>radians(i<2?8:5))){this.rows=[];this.poses=[];this.started=null;return {ready:false,state:'unknown',reason:'unstable_reference'};}
   this.reference=center;this.referencePose=this.poses.length?middle(this.poses):null;this.rows=[];this.poses=[];
  }
  if(this.referencePose&&(!pose||Math.abs(pose[0]-this.referencePose[0])>.16||Math.abs(pose[1]-this.referencePose[1])>.16||pose[2]/this.referencePose[2]<.65||pose[2]/this.referencePose[2]>1.5))return this.unknown('position_changed');
  this.recent.push(angles);this.recent=this.recent.slice(-3);
  const current=middle(this.recent),delta=current.map((v,i)=>Math.abs(v-this.reference[i]));
  const limits=({relaxed:[30,25,38,30],balanced:[22,18,30,25],sensitive:[16,14,24,20]})[this.sensitivity]||[22,18,30,25];
  const ratio=Math.max(...delta.map((v,i)=>v/radians(limits[i])));
  // Hysteresis prevents a boundary flicker from restarting the eight-second timer.
  this.state=ratio>(this.state==='away'?.8:1)?'away':'on_screen';
  return {ready:true,state:this.state,reason:this.state==='away'?'direction_away':'screen_facing'};
 }
}
