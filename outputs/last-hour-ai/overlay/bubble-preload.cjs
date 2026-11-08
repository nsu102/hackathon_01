const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('bubbleBridge',{onState:callback=>{ipcRenderer.on('bubble:state',(_,state)=>callback(state));},action:(action,value)=>ipcRenderer.invoke('bubble:action',action,value),resize:height=>ipcRenderer.send('bubble:resize',height)});
