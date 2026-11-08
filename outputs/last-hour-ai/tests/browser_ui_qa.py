"""Owned headless UI with synthetic microphone and mocked native capture/menu IPC."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import threading,json
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+str(root/'tests/fixtures/voice-question.wav'),'--autoplay-policy=no-user-gesture-required'])
 page=browser.new_page(viewport=dict(width=440,height=820),device_scale_factor=1)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script('''
 const fixturePNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8GQAAAAASUVORK5CYII=';
 window.actions=[];window.recordId=0;window.pendingTarget='screen';
 const reply=async()=>{const message={id:'answer-'+window.recordId,role:'assistant',content:'빨간 카드 4장이 기준이에요.',source:'openrouter',mode:'context'};window.testSession.messages.push({id:'user-'+window.recordId,role:'user',content:'이 공식에서 왜 4로 나눠?'},message);await window.voiceEvent({type:'answer',data:{message}});};
 window.studyBridge={ready:async()=>({ok:true,health:{study_model:{configured:true}}}),onDisplayChanged:()=>{},onLost:()=>{},onVoice:cb=>{window.voiceEvent=cb;},onAppAction:cb=>{window.appAction=cb;},
 window:async(action,data)=>{window.actions.push({action,data});
 if(action==='collapse'){window.collapsed=!window.collapsed;return window.collapsed;}
 if(action==='displays')return [{id:1,label:'모의 모니터',x:-1440,y:0,width:1440,height:900,scale:2}];
 if(action==='gaze-display')return {x:-1440,y:0,width:1440,height:900,display_id:1};
 if(action==='overlay-bounds')return null;
 if(action==='calibration-open')return {x:-1440,y:0,width:440,height:820,display_id:1};
 if(action==='materials-import')return [{name:'notes.pdf',text:'고유 확인 코드 37. 조건에 해당하는 카드만 분모에 포함합니다.',pages:1,truncated:false}];if(action==='voice-configure')return {enabled:data.enabled};if(action==='connection-settings')return {key_configured:true,model:'anthropic/claude-sonnet-5.5'};
 if(action==='voice-button-start'){window.pendingTarget=data.target;window.recordId++;window.voiceEvent({type:'start',data:{id:window.recordId,control:'button',attachment:{display_id:1,width:2880,height:1800}}});return {started:true};}
 if(action==='voice-button-release')window.voiceEvent({type:'release',data:window.recordId});
 if(action==='voice-submit'){if(window.pendingTarget==='manual')window.voiceEvent({type:'select',data:{png:fixturePNG,display:{display_id:1}}});else await reply();}
 if(action==='voice-select')await reply();return null;},
 request:async(method,route,body)=>{const heart={reading:false,bpm:null,message:'미연결',age_seconds:null,connected:false,source:null};
 if(route==='/study/heart')return heart;
 if(route==='/study/sessions')window.testSession={id:'12345678123456781234567812345678',goal:body.goal,status:'running',elapsed_seconds:0,ai_enabled:body.ai_enabled,minutes:20,messages:[],heart,summary:null,busy:false,personalization:{dismissals:0,helpful:0}};
 if(route.includes('/materials'))window.materialContext=body.material;
 if(route.includes('/pause'))window.testSession.status=body.paused?'paused':'running';
 if(route.includes('/end')){window.testSession.status='ended';window.testSession.summary={studied_seconds:2,help_requests:window.recordId,helpful_feedback:0,note:'테스트'};}
 if(route.includes('focus-events'))return {recorded:true};return window.testSession;}};
 ''')
 page.goto(f'http://127.0.0.1:{server.server_port}/overlay/index.html')
 page.evaluate('''async()=>{const {GazeTracker}=await import('/overlay/gaze.mjs');GazeTracker.prototype.start=async function(){this.running=true;this.update({status:'tracking',label:'모의 카메라'});window.injectGaze=sample=>this.sample(sample);};}''')
 page.locator('#sample').click();page.locator('#start').click();page.locator('#learning').wait_for(state='visible')
 assert page.locator('#hint,#explain,#quiz,#message,#chat-form').count()==0
 assert page.locator('#calibration').is_hidden()
 assert page.locator('#voice-talk').inner_text()=='말하기 시작'
 page.locator('#settings-toggle').click();page.locator('#read-answer').uncheck();page.locator('#nag-mute').check();page.locator('#settings-toggle').click()
 page.evaluate('''()=>{const at=performance.now()+22000;for(let t=at-21000;t<=at;t+=100)window.injectGaze({at_ms:t,validated:false,validity:'unknown',pose_ok:false,presence:{ready:true,state:'away',reason:'direction_away'}});}''')
 assert page.locator('#focus-notice').is_visible();assert '화면 이탈' in page.locator('#focus-state').inner_text()
 page.locator('#focus-correction').click();assert page.locator('#focus-notice').is_hidden()
 page.evaluate("window.appAction({action:'settings'})");page.locator('#settings').wait_for(state='visible')
 page.locator('#precise-settings>summary').click();page.locator('#study-region').click();page.locator('#region-editor').wait_for(state='visible')
 page.mouse.move(30,250);page.mouse.down();page.mouse.move(380,620);page.mouse.up();page.locator('#region-save').click();page.locator('#region-editor').wait_for(state='hidden')
 assert '학습 영역 설정됨' in page.locator('#region-status').inner_text()
 page.locator('#settings-toggle').click();page.locator('#voice-consent').check();page.evaluate("window.appAction({action:'bubble-add-material'})");page.wait_for_function("() => document.getElementById('material-list').textContent.includes('notes.pdf')");assert '37' in page.evaluate('window.materialContext');page.locator('#voice-talk').click()
 page.wait_for_function("() => document.getElementById('voice-status').textContent.startsWith('녹음 중')")
 assert page.locator('#voice-talk').inner_text()=='말 끝내고 보내기'
 assert page.locator('#voice-attachment').is_visible()
 assert page.evaluate("window.actions.filter(a=>a.action==='voice-submit').length")==0
 page.wait_for_timeout(1200);page.locator('#voice-talk').click()
 page.wait_for_function("() => document.getElementById('chat').textContent.includes('빨간 카드 4장')")
 audio=page.evaluate("window.actions.find(a=>a.action==='voice-submit').data")
 assert audio['id']==1 and audio['speech_detected'] and audio['audio'].startswith('GkXf')
 assert not page.evaluate("window.actions.some(a=>a.action==='voice-configure')"),'button path must not require global hooks'
 page.locator('#voice-talk').click();page.wait_for_function("() => document.getElementById('voice-status').textContent.startsWith('녹음 중')")
 page.locator('#voice-cancel').click();page.wait_for_timeout(150)
 assert page.evaluate("window.actions.filter(a=>a.action==='voice-submit').length")==1
 page.locator('#settings-toggle').click();page.locator('#voice-target').select_option('manual');page.locator('#settings-toggle').click()
 page.locator('#voice-talk').click();page.wait_for_function("() => document.getElementById('voice-status').textContent.startsWith('녹음 중')")
 page.wait_for_timeout(1200);page.locator('#voice-talk').click();page.locator('#region-editor').wait_for(state='visible')
 page.mouse.move(30,250);page.mouse.down();page.mouse.move(380,620);page.mouse.up();page.locator('#region-save').click();page.locator('#region-editor').wait_for(state='hidden')
 page.wait_for_function("() => document.querySelectorAll('#chat .assistant').length===2")
 page.locator('#settings-toggle').click();page.locator('#voice-target').select_option('screen');page.locator('#settings-toggle').click()
 page.locator('#voice-talk').click();page.wait_for_function("() => document.getElementById('voice-status').textContent.startsWith('녹음 중')")
 page.locator('#collapse').click();page.set_viewport_size(dict(width=320,height=64))
 assert page.locator('#voice-indicator').is_visible();assert page.evaluate('document.documentElement.scrollWidth')<=320
 page.evaluate("window.voiceEvent({type:'cancel',data:'시험 취소'})");page.locator('#collapse').click();page.set_viewport_size(dict(width=440,height=820))
 page.evaluate("window.appAction({action:'pause'})");page.wait_for_function("() => document.getElementById('pause').textContent==='다시 공부하기'")
 page.locator('#end').click();page.locator('#summary').wait_for(state='visible');page.locator('#new-session').click();assert page.locator('#setup').is_visible()
 page.evaluate("window.appAction({action:'settings'})");page.locator('#settings').wait_for(state='visible')
 page.locator('#connection-key').fill('fixture-api-key-for-ui-only');page.locator('#connection-model').fill('anthropic/claude-sonnet-5.5');page.locator('#connection-save').click()
 page.wait_for_function("() => document.getElementById('connection-key').value===''")
 assert page.evaluate("window.actions.some(a=>a.action==='connection-save'&&a.data.api_key==='fixture-api-key-for-ui-only')")
 assert not page.evaluate("JSON.stringify(localStorage).includes('fixture-api-key-for-ui-only')")
 assert not errors,errors
 out=root/'docs/qa';out.mkdir(exist_ok=True)
 passed=['session lifecycle','voice-only controls and removed text presets','coarse away state visible without pixel calibration','false-alarm grace','menu action opens settings','negative-origin manual region','button starts actual WebM/Opus recording','explicit send receives answer','button needs no keyboard hook','cancel discards recording','manual voice crop and answer','collapsed recording indicator','menu pause and end cleanup','connection settings clears API key after save','file attachment enters session context','screenshot attachment shown while recording','answer and focus bubble IPC']
 (out/'browser-qa.json').write_text(json.dumps(dict(passed=passed,page_errors=errors,environment='headless system Chrome; synthetic microphone; mock native capture/menu/camera. No human accuracy claims.'),ensure_ascii=False,indent=2))
 page.screenshot(path=str(out/'overlay-v0.6-mocked.png'))
 print(f'Browser UI: {len(passed)} workflows passed; 0 page errors (mock native bridge)')
 browser.close()
server.shutdown();server.server_close()
