import test from 'node:test';import assert from 'node:assert/strict';import {EventEmitter} from 'node:events';import createBubbles from '../bubbles.cjs';
test('separate bubble stays bottom-right on a negative-origin display, uses inactive display and validates sender/actions',async()=>{
 let made;const actions=[];
 class Window extends EventEmitter{
  constructor(options){super();this.options=options;this.visible=false;this.destroyed=false;this.webContents=new EventEmitter();this.webContents.send=(_,state)=>{this.state=state;};this.webContents.setWindowOpenHandler=()=>{};made=this;}
  setAlwaysOnTop(){}setVisibleOnAllWorkspaces(){}loadURL(url){this.url=url;queueMicrotask(()=>this.webContents.emit('did-finish-load'));}isDestroyed(){return this.destroyed;}isVisible(){return this.visible;}setBounds(value){this.bounds=value;}showInactive(){this.visible=true;}hide(){this.visible=false;}destroy(){this.destroyed=true;}
 }
 const bubbles=createBubbles({BrowserWindow:Window,display:()=>({workArea:{x:-1440,y:24,width:1440,height:840}}),action:(...a)=>actions.push(a)});
 bubbles.update({kind:'answer',text:'<script>unsafe()</script>',question:'설명해줘',phase:'idle',configured:true,consent:true,show:true});await Promise.resolve();
 assert.equal(made.options.focusable,false);assert.equal(made.options.acceptFirstMouse,true);assert.equal(made.bounds.x,-390);assert.equal(made.bounds.y,634);assert.equal(made.state.text,'<script>unsafe()</script>');
 assert.ok(bubbles.valid({sender:made.webContents,senderFrame:{url:'study://app/bubble.html'}}));assert.equal(bubbles.valid({sender:made.webContents,senderFrame:{url:'https://other.example'}}),false);
 bubbles.handle('talk');assert.deepEqual(actions[0],['talk',undefined]);bubbles.handle('consent',true);assert.deepEqual(actions.at(-1),['consent',true]);assert.throws(()=>bubbles.handle('arbitrary-command'));
 bubbles.resize(1000);assert.equal(made.bounds.height,510);assert.ok(made.bounds.y>=24);bubbles.handle('dismiss');assert.equal(made.visible,false);
 bubbles.update({phase:'processing',show:false});assert.equal(made.visible,false);bubbles.destroy();
});
