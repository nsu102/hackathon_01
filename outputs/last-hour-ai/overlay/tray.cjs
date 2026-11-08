module.exports=function createStudyTray({Tray,Menu,nativeImage,iconPath,show,action,quit}){
 const image=nativeImage.createFromPath(iconPath);if(image.isEmpty())throw new Error('메뉴 막대 아이콘을 읽지 못했어요.');image.setTemplateImage(true);
 const tray=new Tray(image);let state={running:false,paused:false,camera:false,focus_enabled:true,muted:false,focus:'대기 중'},previous='';
 function update(next={}){
  state={...state,...next};const signature=JSON.stringify(state);if(signature===previous)return;previous=signature;
  tray.setToolTip('Study Signal · '+state.focus);
  tray.setContextMenu(Menu.buildFromTemplate([
   {label:'Study Signal',enabled:false},{label:state.focus,enabled:false},{type:'separator'},
   {label:'도우미 열기',click:()=>show()},
   {label:'설정…',accelerator:'CommandOrControl+,',click:()=>show('settings')},
   {type:'separator'},
   {label:state.camera?'집중 감지 끄기':'집중 감지 켜기',click:()=>action('monitor')},
   {label:'이탈 알림',type:'checkbox',checked:state.focus_enabled,click:item=>action('focus-enabled',item.checked)},
   {label:'잔소리 음소거',type:'checkbox',checked:state.muted,click:item=>action('nag-mute',item.checked)},
   {label:state.paused?'학습 다시 시작':'잠깐 쉬기',enabled:state.running,click:()=>action('pause')},
   {type:'separator'},
   {label:'Study Signal 종료',click:quit}
  ]));
 }
 update();return {update,inspect:()=>({bounds:tray.getBounds(),template:image.isTemplateImage(),scales:image.getScaleFactors()}),destroy:()=>tray.destroy()};
};
