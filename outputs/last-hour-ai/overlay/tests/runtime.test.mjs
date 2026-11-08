import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import os from 'node:os';import path from 'node:path';
import runtime from '../runtime.cjs';
test('installed app separates immutable bundled assets from writable personal configuration',()=>{
 const p=runtime.paths({packaged:true,resourcesPath:'/Applications/Study Signal.app/Contents/Resources',appData:'/user/Library/Application Support',sourceRoot:'/source'});
 assert.equal(p.root,'/user/Library/Application Support/Study Signal');assert.ok(p.service.startsWith('/Applications/'));assert.ok(!p.models.startsWith(p.root));
 const dev=runtime.paths({packaged:false,sourceRoot:'/source'});assert.equal(dev.root,'/source');assert.equal(dev.service,null);
});
test('first launch creates a private token; existing credentials and unrelated settings survive updates',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'study-settings-'));
 try{
  const defaults=path.join(dir,'defaults.env');fs.writeFileSync(defaults,'OPENROUTER_API_KEY=\nLAST_HOUR_TOKEN=\nSTUDY_HEART_URL=https://heart.example/latest\n');
  const root=path.join(dir,'personal');runtime.initialize({root,defaults});const file=path.join(root,'.env');const initial=fs.readFileSync(file,'utf8');
  assert.match(initial,/LAST_HOUR_TOKEN="[A-Za-z0-9_-]{24,}"/);assert.equal(fs.statSync(file).mode&0o777,0o600);
  runtime.writeEnv(file,{OPENROUTER_API_KEY:'fixture-private-key'});runtime.initialize({root,defaults});runtime.writeEnv(file,runtime.connectionValues({model:'anthropic/test',api_key:''}));
  const saved=fs.readFileSync(file,'utf8');assert.ok(saved.includes('fixture-private-key'));assert.ok(saved.includes('STUDY_HEART_URL=https://heart.example/latest'));assert.match(saved,/STUDY_MODEL_ID="anthropic\/test"/);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('connection fields reject multiline credentials and invalid model identifiers before writing',()=>{
 for(const data of [{model:'bad\nmodel'},{model:'test',api_key:'secret\nINJECT=1'},{model:'test',api_key:'short'},{model:'test',api_key:'secret-with-"quote'}])assert.throws(()=>runtime.connectionValues(data));
 assert.equal(runtime.connectionValues({model:'anthropic/claude-sonnet-5.5',api_key:'fixture-valid-key'}).OPENROUTER_API_KEY,'fixture-valid-key');
});
