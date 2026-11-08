const $=id=>document.getElementById(id),bridge=window.studyBridge;
export function setupConnection(error){
 bridge.window('connection-settings').then(value=>{if(!value)return;$('connection-model').value=value.model;$('connection-key-state').textContent=value.key_configured?'저장된 API 키가 있어요. 빈칸으로 두면 유지해요.':'OpenRouter API 키를 입력하면 실제 음성 질문을 쓸 수 있어요.';}).catch(e=>error(e.message));
 $('connection-form').onsubmit=async event=>{
  event.preventDefault();const button=$('connection-save');button.disabled=true;error();
  try{await bridge.window('connection-save',{api_key:$('connection-key').value.trim(),model:$('connection-model').value.trim()});$('connection-key').value='';$('connection-key-state').textContent='저장했어요. 앱을 다시 시작하고 있어요…';}
  catch(e){error(e.message);button.disabled=false;}
 };
}
