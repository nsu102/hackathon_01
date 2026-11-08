// Raw samples stay in memory. Validated coefficients may be saved on this device.
const mean=x=>x.reduce((a,b)=>a+b,0)/x.length;
export const median=x=>[...x].sort((a,b)=>a-b)[Math.floor(x.length/2)];
export const center=rows=>rows[0].map((_,i)=>median(rows.map(r=>r[i])));
function solve(matrix,vector){
 const a=matrix.map((row,i)=>[...row,vector[i]]),n=vector.length;
 for(let c=0;c<n;c++){
  let p=c;for(let r=c+1;r<n;r++)if(Math.abs(a[r][c])>Math.abs(a[p][c]))p=r;
  if(Math.abs(a[p][c])<1e-10)throw new Error('보정 신호가 충분하지 않아요.');
  [a[c],a[p]]=[a[p],a[c]];const d=a[c][c];for(let k=c;k<=n;k++)a[c][k]/=d;
  for(let r=0;r<n;r++)if(r!==c){const v=a[r][c];for(let k=c;k<=n;k++)a[r][k]-=v*a[c][k];}
 }return a.map(row=>row[n]);
}
export class ScreenGazeModel{
 serialize(){
  if(!this.validated)throw new Error('검증을 통과한 보정만 저장할 수 있어요.');
  return {means:[...this.means],scales:[...this.scales],weights:this.weights.map(r=>[...r])};
 }
 static restore(data,display){
  const vector=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(x=>Number.isFinite(x)&&Math.abs(x)<1e8);
  if(!data||!vector(data.means,5)||!vector(data.scales,5)||data.scales.some(x=>x<=0)||!Array.isArray(data.weights)||data.weights.length!==2||!data.weights.every(r=>vector(r,6)))throw new Error('저장된 보정을 읽을 수 없어요.');
  const model=new ScreenGazeModel();model.means=[...data.means];model.scales=[...data.scales];model.weights=data.weights.map(r=>[...r]);model.display={...display};model.validated=false;model.errorPx=null;return model;
 }
 fit(rows,display){
  if(rows.length<9||!rows.every(r=>r.features.length===5&&r.features.every(Number.isFinite)))throw new Error('9개 지점의 보정이 필요해요.');
  this.means=rows[0].features.map((_,i)=>mean(rows.map(r=>r.features[i])));
  const spreads=this.means.map((v,i)=>Math.sqrt(mean(rows.map(r=>(r.features[i]-v)**2))));
  // The absolute iris movement varies substantially by camera and anatomy.
  // Standardize the observed eye signal; held-out screen error is the quality
  // gate. Keep head terms conservative so tiny head noise cannot dominate.
  this.scales=spreads.map((v,i)=>Math.max(i<3?1e-5:.02,v));
  if(spreads.every(v=>v<1e-7))throw new Error('카메라에서 서로 다른 시선 신호를 구분하지 못했어요. 카메라 영상과 눈 감지를 확인해주세요.');
  this.display={...display};this.validated=false;this.errorPx=null;
  const design=rows.map(r=>this.design(r.features)),n=design[0].length;
  const gram=Array.from({length:n},(_,i)=>Array.from({length:n},(_,j)=>design.reduce((v,r)=>v+r[i]*r[j],0)+(i===j?(i===0?1e-6:.12):0)));
  this.weights=['x','y'].map(axis=>solve(gram,Array.from({length:n},(_,i)=>rows.reduce((v,r,k)=>v+design[k][i]*r.target[axis],0))));return this;
 }
 design(value){return [1,...value.map((v,i)=>(v-this.means[i])/this.scales[i])];}
 raw(value){
  if(!this.weights||!value||value.length!==5||!value.every(Number.isFinite))return null;
  const d=this.design(value);if(d.slice(1).some(v=>Math.abs(v)>7))return null;
  return {x:this.weights[0].reduce((v,w,i)=>v+w*d[i],0),y:this.weights[1].reduce((v,w,i)=>v+w*d[i],0)};
 }
 validate(rows, validRatio=1){
  if(rows.length<5)throw new Error('별도의 5개 지점에서 오차를 확인해주세요.');
  const errors=rows.map(r=>{const p=this.raw(r.features);return p?Math.hypot((p.x-r.target.x)*this.display.width,(p.y-r.target.y)*this.display.height):Infinity;});
  this.errorPx=median(errors);this.maxErrorPx=Math.max(...errors);const scale=Math.min(this.display.width/1440,this.display.height/900);
  this.validated=Number.isFinite(this.errorPx)&&this.errorPx<=120*scale&&this.maxErrorPx<=220*scale&&validRatio>=.8;
  return {accepted:this.validated,median_error_px:Math.round(this.errorPx),max_error_px:Math.round(this.maxErrorPx),valid_ratio:validRatio};
 }
 predict(value){
  if(!this.validated)return null;const p=this.raw(value);if(!p)return null;
  return {x:this.display.x+p.x*this.display.width,y:this.display.y+p.y*this.display.height,nx:p.x,ny:p.y,error_px:this.errorPx};
 }
}
export const calibrationTargets=[{x:.5,y:.5},{x:.12,y:.12},{x:.5,y:.12},{x:.88,y:.12},{x:.88,y:.5},{x:.88,y:.88},{x:.5,y:.88},{x:.12,y:.88},{x:.12,y:.5}];
export const validationTargets=[{x:.25,y:.25},{x:.75,y:.25},{x:.5,y:.5},{x:.25,y:.75},{x:.75,y:.75}];
