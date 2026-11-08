// Pixels/anchors only cross owned local IPC/stdio. No network or persistence.
const FACE_CONTOUR=[127,234,93,132,58,172,136,150,176,152,400,379,365,397,288,361,323,454,356,70,63,105,66,107,336,296,334,293,300];
// Dlib 0-based 36,39,42,45,31,35 -> MediaPipe eye corners/nose wings.
export const NEURAL_ANCHORS=[33,133,362,263,75,305];
export class NeuralGaze {
 constructor(video){this.video=video;this.canvas=document.createElement('canvas');this.context=this.canvas.getContext('2d',{alpha:false});this.info=null;}
 async start(){this.info=await window.studyBridge.window('neural-start');return this.info;}
 freeze(){
  const scale=Math.min(1,960/this.video.videoWidth);
  const width=Math.round(this.video.videoWidth*scale),height=Math.round(this.video.videoHeight*scale);
  if(width<64||height<64)return this.video;
  if(this.canvas.width!==width||this.canvas.height!==height){this.canvas.width=width;this.canvas.height=height;}
  this.context.drawImage(this.video,0,0,width,height);return this.canvas;
 }
 async estimate(landmarks){
  if(!landmarks||this.canvas.width<64)return null;
  const w=this.canvas.width,h=this.canvas.height;
  const points=NEURAL_ANCHORS.map(i=>[landmarks[i].x*w,landmarks[i].y*h]);
  const contour=FACE_CONTOUR.map(i=>landmarks[i]);
  const bbox=[Math.max(0,Math.min(...contour.map(p=>p.x))*w),Math.max(0,Math.min(...contour.map(p=>p.y))*h),Math.min(w,Math.max(...contour.map(p=>p.x))*w),Math.min(h,Math.max(...contour.map(p=>p.y))*h)];
  const image=this.canvas.toDataURL('image/jpeg',.97).split(',')[1];
  const result=await window.studyBridge.window('neural-predict',{image,points,bbox});
  return result.ok&&result.features?.length===5&&result.features.every(Number.isFinite)?result:null;
 }
 close(){this.canvas.width=this.canvas.height=0;window.studyBridge.window('neural-stop').catch(()=>{});}
}
