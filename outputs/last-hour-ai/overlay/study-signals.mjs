// Eye-corner referenced iris features for personal screen calibration. No camera data is saved.
export const median = values => { const x = [...values].sort((a,b) => a-b); return x[Math.floor(x.length/2)]; };
const dist = (a,b) => Math.hypot(a.x-b.x,a.y-b.y);
const mean = x => x.reduce((a,b) => a+b,0)/x.length;
export function features(p) {
  if (!Array.isArray(p) || p.length < 478) return null;
  if ([33,133,159,145,362,263,386,374,468,473,1].some(i => !p[i] || !Number.isFinite(p[i].x) || !Number.isFinite(p[i].y))) return null;
  const lw=dist(p[33],p[133]), rw=dist(p[362],p[263]), span=dist(p[33],p[263]);
  if (Math.min(lw,rw)<0.02 || span<0.12 || p[1].x<0.08 || p[1].x>0.92 || dist(p[159],p[145])/lw<0.09 || dist(p[386],p[374])/rw<0.09) return null;
  // Lid centres move with vertical gaze. Referencing the iris to them removes
  // useful vertical signal; use the stable canthus line for both eye axes.
  function eye(a,b,iris) {
    const dx=b.x-a.x,dy=b.y-a.y,length2=dx*dx+dy*dy;
    const ix=iris.x-a.x,iy=iris.y-a.y;
    return [(dx*ix+dy*iy)/length2,(-dy*ix+dx*iy)/length2];
  }
  const l=eye(p[33],p[133],p[468]),r=eye(p[362],p[263],p[473]);
  return [l[0],r[0],(l[1]+r[1])/2,(p[1].x-(p[33].x+p[263].x)/2)/span,(p[1].y-(p[33].y+p[263].y)/2)/span];
}
export class DirectionEstimator {
  constructor(){this.reset();}
  reset(){this.baseline=null;this.calibration=[];this.pending='unknown';this.count=0;}
  calibrate(value){
    if(!value)return this.calibration.length;
    this.calibration.push(value);
    if(this.calibration.length>=25){
      const columns=value.map((_,i)=>this.calibration.map(v=>v[i])),centers=columns.map(median);
      const spread=Math.max(...columns.map((c,i)=>Math.sqrt(mean(c.map(v=>(v-centers[i])**2)))));
      if(spread>0.10){this.calibration=[];return 0;}
      this.baseline=centers;
    }
    return this.calibration.length;
  }
  classify(value){
    if(!value||!this.baseline){this.count=0;return 'unknown';}
    const d=value.map((v,i)=>Math.abs(v-this.baseline[i]));
    const state=d[0]>0.17||d[1]>0.17||d[2]>0.09||d[3]>0.18||d[4]>0.18?'away':'on';
    if(this.pending===state)this.count++;else{this.pending=state;this.count=1;}
    return this.count>=3?state:'unknown';
  }
}
export class ObservationWindow {
  constructor(){this.reset();}
  reset(){this.started=null;this.states=[];}
  add(state,at){if(this.started===null)this.started=at;this.states.push(['on','away'].includes(state)?state:'unknown');}
  summary(at,calibrated,source='webcam'){
    if(this.started===null||!this.states.length)return null;
    const n=this.states.length;
    return {source,samples:n,window_seconds:Math.min(60,Math.max(1,(at-this.started)/1000)),on_ratio:this.states.filter(v=>v==='on').length/n,away_ratio:this.states.filter(v=>v==='away').length/n,unknown_ratio:this.states.filter(v=>v==='unknown').length/n,calibrated:Boolean(calibrated)};
  }
}
