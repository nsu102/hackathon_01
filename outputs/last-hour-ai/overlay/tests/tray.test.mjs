import test from 'node:test';import assert from 'node:assert/strict';import createStudyTray from '../tray.cjs';
test('macOS template icon and menu remain available for settings, monitoring and explicit quit',()=>{
 let template,menu,builds=0,destroyed=false;const actions=[],shown=[];let quit=false;
 class Tray{setToolTip(){}setContextMenu(value){menu=value;}destroy(){destroyed=true;}}
 const tray=createStudyTray({Tray,Menu:{buildFromTemplate:value=>{builds++;return value;}},nativeImage:{createFromPath:()=>({isEmpty:()=>false,setTemplateImage:v=>template=v})},iconPath:'StudySignalTemplate.png',show:section=>shown.push(section),action:(...args)=>actions.push(args),quit:()=>quit=true});
 assert.equal(template,true);const find=name=>menu.find(item=>item.label===name);
 find('설정…').click();assert.deepEqual(shown,['settings']);find('집중 감지 켜기').click();assert.deepEqual(actions[0],['monitor']);
 tray.update({camera:true,running:true,focus:'화면 응시 중'});assert.ok(find('집중 감지 끄기'));assert.equal(find('잠깐 쉬기').enabled,true);
 const count=builds;tray.update({camera:true,running:true,focus:'화면 응시 중'});assert.equal(builds,count);
 find('잔소리 음소거').click({checked:true});assert.deepEqual(actions.at(-1),['nag-mute',true]);find('Study Signal 종료').click();assert.equal(quit,true);tray.destroy();assert.equal(destroyed,true);
});
