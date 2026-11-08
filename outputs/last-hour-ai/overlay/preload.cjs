const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('studyBridge', {
  ready: () => ipcRenderer.invoke('backend:ready'),
  request: (method, route, body) => ipcRenderer.invoke('backend:request', method, route, body),
  window: (action, data) => ipcRenderer.invoke('window:action', action, data),
  onDisplayChanged: callback => ipcRenderer.on('display:changed', () => callback()),
  onVoice: callback => { const listener=(_,event)=>callback(event);ipcRenderer.on('voice:event',listener);return ()=>ipcRenderer.removeListener('voice:event',listener); },
  onLost: callback => ipcRenderer.on('backend:lost', () => callback()),
  onAppAction: callback => {const listener=(_,event)=>callback(event);ipcRenderer.on('app:action',listener);return ()=>ipcRenderer.removeListener('app:action',listener);},
});
