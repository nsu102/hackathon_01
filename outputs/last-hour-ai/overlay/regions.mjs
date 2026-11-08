const $=id=>document.getElementById(id),bridge=window.studyBridge;
let selecting=false;
export async function selectRegion(label,{display_id,preview=null,initial=null}={}){
 if(selecting||!$('calibration').hidden)throw new Error('진행 중인 보정·선택을 먼저 마쳐주세요.');
 selecting=true;let display;
 try{display=await bridge.window('calibration-open',{display_id});}catch(e){selecting=false;throw e;}
 const panel=$('region-editor'),image=$('region-image'),box=$('region-box');
 $('region-title').textContent=label+' · 문단이나 문제 전체를 드래그하세요';
 image.hidden=!preview;if(preview)image.src=preview;panel.hidden=false;document.body.classList.add('selecting');box.hidden=true;
 return new Promise((resolve,reject)=>{
  let start=null,rect=null;
  $('region-save').disabled=true;
  if(preview&&initial){
   const x=Math.max(0,Math.min(innerWidth,(initial.x-display.x)*innerWidth/display.width)),y=Math.max(0,Math.min(innerHeight,(initial.y-display.y)*innerHeight/display.height));
   rect={x,y,width:Math.min(innerWidth-x,initial.width*innerWidth/display.width),height:Math.min(innerHeight-y,initial.height*innerHeight/display.height)};
   box.hidden=false;Object.assign(box.style,{left:x+'px',top:y+'px',width:rect.width+'px',height:rect.height+'px'});$('region-save').disabled=rect.width<80||rect.height<60;
  }
  const finish=async value=>{panel.onpointerdown=null;panel.onpointermove=null;panel.onpointerup=null;document.removeEventListener('keydown',escape);panel.hidden=true;image.removeAttribute('src');document.body.classList.remove('selecting');selecting=false;await bridge.window('calibration-close');value?resolve(value):reject(new Error('영역 선택을 취소했어요.'));};
  const escape=e=>{if(e.key==='Escape')finish(null);};document.addEventListener('keydown',escape);
  $('region-cancel').onclick=()=>finish(null);$('region-save').onclick=()=>{if(rect&&rect.width>=80&&rect.height>=60)finish(preview?{x:display.x+rect.x*display.width/innerWidth,y:display.y+rect.y*display.height/innerHeight,width:rect.width*display.width/innerWidth,height:rect.height*display.height/innerHeight,display_id:display.display_id}:{...rect,x:rect.x+(display.viewport||display).x,y:rect.y+(display.viewport||display).y,display_id:display.display_id});};
  panel.onpointerdown=e=>{if(e.target.closest('button')||e.target.closest('.region-tools'))return;start={x:e.clientX,y:e.clientY};panel.setPointerCapture(e.pointerId);};
  panel.onpointermove=e=>{if(!start)return;rect={x:Math.min(start.x,e.clientX),y:Math.min(start.y,e.clientY),width:Math.abs(e.clientX-start.x),height:Math.abs(e.clientY-start.y)};box.hidden=false;Object.assign(box.style,{left:rect.x+'px',top:rect.y+'px',width:rect.width+'px',height:rect.height+'px'});$('region-save').disabled=rect.width<80||rect.height<60;};
  panel.onpointerup=()=>{start=null;};
 });
}
