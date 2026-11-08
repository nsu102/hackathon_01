const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('gazePointer',{onPoint:callback=>ipcRenderer.on('gaze:point',(_,value)=>callback(value))});
