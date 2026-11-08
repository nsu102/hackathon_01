const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
function paths({packaged,resourcesPath,appData,sourceRoot}){
 return packaged?{root:path.join(appData,'Study Signal'),service:path.join(resourcesPath,'service','study-service'),models:path.join(resourcesPath,'models','unigaze'),defaults:path.join(resourcesPath,'defaults.env')}:{root:sourceRoot,service:null,models:null,defaults:path.join(sourceRoot,'.env.example')};
}
function writeEnv(file,values){
 let text=fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';
 for(const [key,value] of Object.entries(values)){
  const line=key+'='+JSON.stringify(value),expression=new RegExp('^(?:export\\s+)?'+key+'\\s*=.*$','m');
  text=expression.test(text)?text.replace(expression,()=>line):text.replace(/\n?$/,'\n')+line+'\n';
 }
 fs.mkdirSync(path.dirname(file),{recursive:true});const temporary=file+'.tmp-'+crypto.randomBytes(5).toString('hex');
 fs.writeFileSync(temporary,text,{mode:0o600});fs.renameSync(temporary,file);fs.chmodSync(file,0o600);
}
function initialize(runtime){
 fs.mkdirSync(runtime.root,{recursive:true});const file=path.join(runtime.root,'.env');
 if(!fs.existsSync(file)){
  const defaults=fs.readFileSync(runtime.defaults,'utf8');fs.writeFileSync(file,defaults,{mode:0o600});
  writeEnv(file,{LAST_HOUR_TOKEN:crypto.randomBytes(32).toString('base64url')});
 }
 fs.chmodSync(file,0o600);
}
function connectionValues(data){
 if(!data||typeof data.model!=='string'||! /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/.test(data.model))throw new Error('설명 모델 ID를 확인해주세요.');
 const values={AI_PROVIDER:'openrouter',STUDY_MODEL_PROVIDER:'openrouter',OPENROUTER_MODEL:data.model,STUDY_MODEL_ID:data.model};
 if(data.api_key!==undefined&&data.api_key!==''){
  if(typeof data.api_key!=='string'||data.api_key.length<12||data.api_key.length>1024||/\s|["'\\]/.test(data.api_key))throw new Error('OpenRouter API 키 형식을 확인해주세요.');
  values.OPENROUTER_API_KEY=data.api_key;
 }
 return values;
}
module.exports={paths,initialize,writeEnv,connectionValues};
