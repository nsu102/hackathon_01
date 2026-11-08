import test from 'node:test';import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';import {PassThrough} from 'node:stream';
import {NeuralWorker} from '../neural-worker.cjs';
function fixture(){const child=new EventEmitter();child.stdin=new PassThrough();child.stdout=new PassThrough();child.stderr=new PassThrough();child.kill=()=>{child.killed=true;};let args;
 const worker=new NeuralWorker('/fixture',{exists:()=>true,spawnImpl:(...a)=>{args=a;return child;}});return {worker,child,getArgs:()=>args};}
test('local neural process readiness and one bounded frame are carried over owned stdio',async()=>{const {worker,child,getArgs}=fixture();const p=worker.start();child.stdout.write(JSON.stringify({ready:true,model:'unigaze_l16_joint',device:'mps'})+'\n');assert.equal((await p).device,'mps');assert.ok(getArgs()[1].includes('--worker'));
 const pending=worker.predict({image:'test',points:Array(6).fill([1,2]),bbox:[0,0,10,10]});await Promise.resolve();child.stdout.write(JSON.stringify({ok:true,features:[1,2,3,4,5]})+'\n');assert.deepEqual((await pending).features,[1,2,3,4,5]);worker.stop();assert.equal(child.killed,true);});
test('cancelling while a model starts rejects its waiter and releases the process',async()=>{const {worker,child}=fixture();const p=worker.start();worker.stop();await assert.rejects(p,/취소/);assert.equal(child.killed,true);assert.equal(worker.ready,null);});
test('unsupported model selection and over-sized camera input cannot be forwarded',async()=>{const {worker,child}=fixture();assert.throws(()=>worker.setModel('remote-gpu'));const p=worker.start();child.stdout.write('{"ready":true}\n');await p;
 await assert.rejects(()=>worker.predict({image:'x'.repeat(2000001),points:Array(6).fill([1,2]),bbox:[0,0,10,10]}));worker.stop();});
test('installed worker uses bundled service and immutable model path instead of a development venv',async()=>{
 const child=new EventEmitter();child.stdin=new PassThrough();child.stdout=new PassThrough();child.stderr=new PassThrough();child.kill=()=>{};let called;
 const worker=new NeuralWorker('/personal',{exists:()=>true,executable:'/bundle/service',weightsDir:'/bundle/models',spawnImpl:(...args)=>{called=args;return child;}});
 const ready=worker.start();child.stdout.write('{"ready":true}\n');await ready;
 assert.equal(called[0],'/bundle/service');assert.deepEqual(called[1],['neural','--model','unigaze_l16_joint']);assert.equal(called[2].env.STUDY_GAZE_WEIGHTS,'/bundle/models');assert.equal(called[2].cwd,'/personal');worker.stop();
});
