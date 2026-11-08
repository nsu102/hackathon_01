// Watchdog always discards; a genuine release is the only send path.
class Hold {
 constructor(emit,now=()=>performance.now()){this.emit=emit;this.now=now;this.state='idle';this.id=0;}
 start(){if(this.state!=='idle')return null;this.id++;this.state='preparing';this.started=this.now();return this.id;}
 ready(id){if(this.id!==id||this.state!=='preparing')return false;this.state='recording';return true;}
 release(){if(this.state==='recording'){this.state='released';this.emit('release',this.id);}else if(this.state==='preparing')this.cancel('너무 짧게 눌렀어요. 화면 준비 후 말해주세요.');}
 cancel(reason){if(this.state==='idle')return;this.state='idle';this.id++;this.emit('cancel',reason);}
 done(){this.state='idle';}
}
module.exports={Hold};
