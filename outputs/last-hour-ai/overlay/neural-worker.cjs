const {spawn}=require('node:child_process');
const {createInterface}=require('node:readline');
const path=require('node:path'),fs=require('node:fs');
class NeuralWorker {
 constructor(root,{spawnImpl=spawn,exists=fs.existsSync,executable=null,weightsDir=null}={}){this.root=root;this.spawn=spawnImpl;this.exists=exists;this.executable=executable;this.weightsDir=weightsDir;this.model=process.env.STUDY_GAZE_MODEL||'unigaze_l16_joint';this.child=null;this.ready=null;this.info=null;this.pending=null;this.startup=null;this.generation=0;}
 setModel(model){if(!['unigaze_l16_joint','unigaze_b16_joint'].includes(model))throw new Error('지원하지 않는 시선 모델 설정이에요.');if(model!==this.model)this.stop();this.model=model;}
 start(){
  if(this.ready)return this.ready;
  const python=this.executable||path.join(this.root,'.gaze-venv','bin','python');
  if(!this.exists(python))return Promise.reject(new Error('신경망 시선 설치.command를 먼저 실행해주세요.'));
  const generation=++this.generation;
  const model=this.model;
  if(!['unigaze_l16_joint','unigaze_b16_joint'].includes(model))return Promise.reject(new Error('지원하지 않는 시선 모델 설정이에요.'));
  this.ready=new Promise((resolve,reject)=>{
   const args=this.executable?['neural','--model',model]:[path.join(this.root,'last_hour/neural_gaze.py'),'--worker','--model',model];
   const child=this.spawn(python,args,{cwd:this.root,stdio:['pipe','pipe','pipe'],env:{...process.env,HF_HUB_OFFLINE:'1',PYTHONUNBUFFERED:'1',...(this.weightsDir?{STUDY_GAZE_WEIGHTS:this.weightsDir}:{})}});this.child=child;
   const startup=setTimeout(()=>fail('시선 신경망 준비 시간이 초과됐어요.'),90000);this.startup={timer:startup,reject};
   const fail=message=>{if(generation!==this.generation)return;clearTimeout(startup);reject(new Error(message));this.stop();};
   child.stderr.on('data',()=>{}); // No camera content or stack traces forwarded.
   const lines=createInterface({input:child.stdout});
   lines.on('line',line=>{
    if(generation!==this.generation||line.length>16000)return;
    let value;try{value=JSON.parse(line);}catch{return;}
    if('ready' in value){clearTimeout(startup);this.startup=null;if(value.ready){this.info=value;resolve(value);}else fail(value.error);return;}
    if(this.pending){const current=this.pending;this.pending=null;clearTimeout(current.timer);current.resolve(value);}
   });
   child.once('error',()=>fail('로컬 시선 신경망 프로세스를 시작하지 못했어요.'));
   child.once('exit',()=>{lines.close();if(generation===this.generation)fail('로컬 시선 신경망 연결이 종료됐어요.');});
  });
  return this.ready;
 }
 async predict(value){
  await this.start();
  if(!this.child)throw new Error('시선 신경망 연결이 종료됐어요.');
  if(this.pending)throw new Error('이전 시선 프레임을 처리하고 있어요.');
  if(!value||typeof value.image!=='string'||value.image.length>2000000||!Array.isArray(value.points)||value.points.length!==6||!Array.isArray(value.bbox)||value.bbox.length!==4)throw new Error('시선 입력 형식을 확인해주세요.');
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.stop();reject(new Error('시선 신경망 응답이 지연됐어요.'));},5000);
   this.pending={resolve,reject,timer};
   this.child.stdin.write(JSON.stringify(value)+'\n',error=>{if(error)this.stop();});
  });
 }
 stop(){
  ++this.generation;
  if(this.startup){clearTimeout(this.startup.timer);this.startup.reject(new Error('시선 신경망 준비를 취소했어요.'));this.startup=null;}
  if(this.pending){clearTimeout(this.pending.timer);this.pending.reject(new Error('시선 측정을 종료했어요.'));this.pending=null;}
  const child=this.child;this.child=null;this.ready=null;this.info=null;child?.kill('SIGTERM');
 }
}
module.exports={NeuralWorker};
