// MobileGaze MobileOne S0: face RGB -> yaw/pitch. Screen position is a geometric
// estimate using assumed hardware dimensions, not a trained pixel-coordinate output.
// See assets/mobilegaze-source.json and MobileGaze-LICENSE.txt.
export function decodeAngle(logits){
 if(!logits||logits.length!==90||!Array.from(logits).every(Number.isFinite))return null;
 const max=Math.max(...logits),exps=Array.from(logits,v=>Math.exp(v-max)),sum=exps.reduce((a,b)=>a+b,0);
 return (exps.reduce((a,b,i)=>a+b*i,0)/sum*4-180)*Math.PI/180;
}
export function projectGaze(yaw,pitch,eyes,display,options={}){
 if(![yaw,pitch,eyes?.x,eyes?.y,eyes?.separation,display?.width,display?.height].every(Number.isFinite)||eyes.separation<.035||Math.abs(yaw)>.95||Math.abs(pitch)>.95)return null;
 const inches=options.diagonal||14,fov=(options.fov||70)*Math.PI/180,aspect=display.width/display.height;
 const heightM=inches*.0254/Math.sqrt(1+aspect*aspect),widthM=heightM*aspect;
 const focal=1/(2*Math.tan(fov/2)),distance=.063*focal/eyes.separation;
 if(distance<.2||distance>1.6)return null;
 // Camera at the top-center of the display. Camera X is opposite screen X.
 const originX=(eyes.x-.5)*distance/focal;
 const originY=(eyes.y-.5)*(eyes.videoAspect?1/eyes.videoAspect:3/4)*distance/focal;
 const nx=.5-(originX-distance*Math.tan(yaw))/widthM;
 const ny=(originY-distance*Math.tan(pitch)/Math.cos(yaw))/heightM;
 if(nx<0||nx>1||ny<0||ny>1)return null;
 return {x:display.x+nx*display.width,y:display.y+ny*display.height,nx,ny,error_px:null,validated:false,method:'pretrained_geometry'};
}
export class PretrainedGaze{
 async load(){
  this.ort=await import('./node_modules/onnxruntime-web/dist/ort.wasm.min.mjs');
  this.ort.env.wasm.numThreads=1;this.ort.env.wasm.proxy=false;
  this.ort.env.wasm.wasmPaths=new URL('./node_modules/onnxruntime-web/dist/',location.href).href;
  this.session=await this.ort.InferenceSession.create(new URL('./assets/mobileone_s0_gaze.onnx',location.href).href,{executionProviders:['wasm'],graphOptimizationLevel:'all'});
  const shape=this.session.inputMetadata[0].shape;this.size=Number(shape[3])||448;
  this.canvas=document.createElement('canvas');this.canvas.width=this.canvas.height=this.size;this.ctx=this.canvas.getContext('2d',{willReadFrequently:true});return this;
 }
 async estimate(video,landmarks,display,options){
  if(!this.session||!landmarks?.length)return null;
  const w=video.videoWidth,h=video.videoHeight;
  let xs=landmarks.map(p=>p.x),ys=landmarks.map(p=>p.y);
  const minX=Math.max(0,Math.min(...xs)),minY=Math.max(0,Math.min(...ys)),maxX=Math.min(1,Math.max(...xs)),maxY=Math.min(1,Math.max(...ys));
  if((maxX-minX)*w<90||(maxY-minY)*h<90)return null;
  this.ctx.drawImage(video,minX*w,minY*h,(maxX-minX)*w,(maxY-minY)*h,0,0,this.size,this.size);
  const rgba=this.ctx.getImageData(0,0,this.size,this.size).data,n=this.size*this.size,input=new Float32Array(n*3),mean=[.485,.456,.406],std=[.229,.224,.225];
  for(let c=0;c<3;c++)for(let i=0;i<n;i++)input[c*n+i]=(rgba[i*4+c]/255-mean[c])/std[c];
  const tensor=new this.ort.Tensor('float32',input,[1,3,this.size,this.size]);let outputs;
  try{
   outputs=await this.session.run({[this.session.inputNames[0]]:tensor});
   const yaw=decodeAngle(outputs[this.session.outputNames[0]].data),pitch=decodeAngle(outputs[this.session.outputNames[1]].data);
   if(yaw===null||pitch===null)return null;
   const l=landmarks[468],r=landmarks[473];
   return projectGaze(yaw,pitch,{x:(l.x+r.x)/2,y:(l.y+r.y)/2,separation:Math.hypot(l.x-r.x,(l.y-r.y)*h/w),videoAspect:w/h},display,options);
  }finally{tensor.dispose();if(outputs)for(const value of Object.values(outputs))value.dispose();}
 }
 close(){const s=this.session;this.session=null;s?.release().catch(()=>{});}
}
