const path=require('node:path');
const ACTIONS=new Set(['talk','cancel','settings','history','materials','add-material','grace','false-alarm','dismiss','start','consent']);
function bounded(value,max){return typeof value==='string'?value.slice(0,max):'';}
module.exports=function createBubbles({BrowserWindow,display,action}){
 let win=null,loaded=false,suspended=false,state={kind:'welcome',text:'궁금한 부분이 생기면 말로 물어봐요.',question:'',phase:'idle',consent:false,configured:false,attachment:false,materials:0},height=210;
 function position(){if(!win||win.isDestroyed())return;const area=display().workArea,width=Math.min(370,area.width-32);win.setBounds({x:area.x+area.width-width-20,y:area.y+area.height-height-20,width,height});}
 function ensure(){
  if(win&&!win.isDestroyed())return;
  win=new BrowserWindow({width:370,height,frame:false,transparent:true,backgroundColor:'#00000000',alwaysOnTop:true,show:false,focusable:false,acceptFirstMouse:true,skipTaskbar:true,resizable:false,hasShadow:false,webPreferences:{preload:path.join(__dirname,'bubble-preload.cjs'),sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
  win.setAlwaysOnTop(true,'floating');win.setVisibleOnAllWorkspaces(true,{visibleOnFullScreen:true});win.webContents.setWindowOpenHandler(()=>({action:'deny'}));win.webContents.on('will-navigate',event=>event.preventDefault());
  win.webContents.once('did-finish-load',()=>{loaded=true;win.webContents.send('bubble:state',state);position();if(!suspended)win.showInactive();});
  win.on('closed',()=>{win=null;loaded=false;});win.loadURL('study://app/bubble.html');
 }
 function update(value={}){
  const {show,...next}=value;
  if(next.kind&&!['welcome','answer','nag','voice','error','info'].includes(next.kind))throw new Error('잘못된 버블 상태예요.');
  if(next.phase&&!['idle','preparing','recording','processing','selecting'].includes(next.phase))throw new Error('잘못된 녹음 상태예요.');
  state={...state,...next,text:next.text===undefined?state.text:bounded(next.text,2400),question:next.question===undefined?state.question:bounded(next.question,400),consent:next.consent===undefined?state.consent:next.consent===true,configured:next.configured===undefined?state.configured:next.configured===true,attachment:next.attachment===undefined?state.attachment:next.attachment===true,materials:Number.isInteger(next.materials)?Math.max(0,Math.min(5,next.materials)):state.materials};
  ensure();if(loaded)win.webContents.send('bubble:state',state);if(show&&!suspended){position();win.showInactive();}
 }
 function valid(event){return event.sender===win?.webContents&&event.senderFrame.url==='study://app/bubble.html';}
 return {update,valid,position,suppress:value=>{suspended=value===true;},hide:()=>win?.hide(),resize:h=>{if(Number.isFinite(h)){height=Math.min(Math.max(150,Math.ceil(h)),Math.min(510,display().workArea.height-40));position();}},clearNag:()=>{if(state.kind==='nag')update({kind:'info',text:'화면으로 돌아오면 조용히 있을게요.',show:false});},handle:(name,value)=>{if(!ACTIONS.has(name))throw new Error('허용되지 않은 버블 동작이에요.');if(name==='dismiss'){win?.hide();return;}action(name,name==='consent'?value===true:undefined);},windows:()=>win&&!win.isDestroyed()?[win]:[],destroy:()=>win?.destroy()};
};
