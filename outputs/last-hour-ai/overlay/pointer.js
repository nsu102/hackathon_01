const dot=document.getElementById('gaze');let expiry;
window.gazePointer.onPoint(value=>{clearTimeout(expiry);dot.hidden=!value;if(!value)return;dot.style.left=value.x+'px';dot.style.top=value.y+'px';dot.style.width=dot.style.height=value.radius*2+'px';expiry=setTimeout(()=>dot.hidden=true,700);});
