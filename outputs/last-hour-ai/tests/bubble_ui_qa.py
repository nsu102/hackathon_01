from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
import threading,json
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 page=browser.new_page(viewport={'width':370,'height':510},device_scale_factor=2)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("window.sent=[];window.bubbleBridge={onState:cb=>window.setBubble=cb,action:async(action,value)=>window.sent.push({action,value}),resize:height=>window.measuredHeight=height}")
 page.goto(f'http://127.0.0.1:{server.server_port}/overlay/bubble.html')
 state=dict(kind='welcome',text='화면을 보고 말로 질문해줘.',question='',phase='idle',configured=True,consent=False,attachment=False,materials=0)
 page.evaluate('s=>window.setBubble(s)',state);assert page.locator('#talk').is_disabled()
 page.locator('#consent').check();assert page.evaluate("window.sent.at(-1).action")=='consent'
 state.update(consent=True);page.evaluate('s=>window.setBubble(s)',state);page.locator('#talk').click();assert page.evaluate("window.sent.at(-1).action")=='talk'
 state.update(kind='voice',phase='recording',text='녹음 중 · 다 말하면 보내기를 눌러줘.',attachment=True,materials=2);page.evaluate('s=>window.setBubble(s)',state)
 assert '말 끝내고 보내기' in page.locator('#talk').inner_text();assert '자료 2개' in page.locator('#attachment').inner_text();page.locator('#talk').click()
 state.update(kind='answer',phase='idle',question='왜 분모가 4야?',text='빨간 카드라는 조건이 주어졌으니, 빨간 카드 4장이 새로운 전체예요. 그중 별 표시는 2장이라서 2/4이에요.');page.evaluate('s=>window.setBubble(s)',state)
 assert page.locator('#history').is_visible();assert page.locator('#question').inner_text()=='왜 분모가 4야?'
 assert page.evaluate('document.documentElement.scrollWidth')==370
 page.screenshot(path=str(root/'docs/qa/bubble-answer.png'),omit_background=True)
 state.update(kind='nag',text='화면으로 돌아와서 한 줄만 더 읽자.',attachment=False);page.evaluate('s=>window.setBubble(s)',state);page.locator('[data-action=grace]').click();assert page.evaluate("window.sent.at(-1).action")=='grace'
 state.update(kind='answer',text='<img src=x onerror=alert(1)>');page.evaluate('s=>window.setBubble(s)',state);assert page.locator('img').count()==1;assert '<img' in page.locator('#body').inner_text()
 assert not errors,errors
 (root/'docs/qa/bubble-ui.json').write_text(json.dumps(dict(passed=['consent gating','voice action','recording and attached screenshot','material count','answer and question','focus grace action','untrusted text stays text','370px no horizontal overflow'],page_errors=errors),ensure_ascii=False,indent=2))
 browser.close()
server.shutdown();server.server_close();print('Bubble UI: 8 scenarios passed; no JavaScript errors')
