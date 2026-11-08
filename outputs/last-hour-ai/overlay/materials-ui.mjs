const $=id=>document.getElementById(id),bridge=window.studyBridge;
export function setupMaterials({error,onChange,busy}){
 let files=[];
 try{const value=JSON.parse(localStorage.getItem('study-materials')||'[]');if(Array.isArray(value))files=value.filter(v=>v&&typeof v.name==='string'&&typeof v.text==='string'&&v.text.length<=24000).slice(0,5);}catch{}
 function text(){return [$('material').value.trim(),...files.map(f=>`[첨부 자료: ${f.name}]\n${f.text}`)].filter(Boolean).join('\n\n').slice(0,30000);}
 function render(){
  const nodes=()=>files.map((file,index)=>{const row=document.createElement('li'),name=document.createElement('span'),remove=document.createElement('button');name.textContent=file.name+(file.truncated?' · 일부 발췌':'');remove.textContent='삭제';remove.setAttribute('aria-label',file.name+' 삭제');remove.onclick=async()=>{if(busy()){error('질문이 끝난 뒤 자료를 바꿔주세요.');return;}files.splice(index,1);save();await onChange(text(),files.length);};row.append(name,remove);return row;});$('material-list').replaceChildren(...nodes());$('materials-manage-list').replaceChildren(...nodes());
  const note=files.length?`자료 ${files.length}개 · 질문할 때 화면과 함께 참고해요. 텍스트는 총 30,000자까지 사용해요.`:'PDF·TXT·MD·DOCX, 파일당 20 MB · 원본 대신 읽은 텍스트를 참고해요.';$('material-note').textContent=note;$('materials-manage-note').textContent=note;
 }
 function save(){localStorage.setItem('study-materials',JSON.stringify(files));render();}
 async function add(){
  if(busy()){error('질문이 끝난 뒤 자료를 추가해주세요.');return;}
  try{const selected=await bridge.window('materials-import');if(!selected?.length)return;
   const next=[...files];for(const file of selected){const index=next.findIndex(v=>v.name===file.name);if(index>=0)next[index]=file;else next.push(file);}
   if(next.length>5)throw new Error('자료는 최대 5개예요. 기존 자료를 지운 뒤 추가해주세요.');
   files=next;save();await onChange(text(),files.length);
  }catch(e){error(e.message);}
 }
 $('material-add').onclick=add;$('materials-manage-add').onclick=add;$('material').addEventListener('change',()=>{if(!busy())onChange(text(),files.length).catch(e=>error(e.message));});render();
 return {add,text,count:()=>files.length};
}
