const $ = id => document.getElementById(id);
const terminal = new Set(['completed', 'handoff', 'cancelled', 'failed', 'deadline_stopped']);
const labels = { created: '작업을 준비하고 있어요', planning: '목표와 자료를 확인하고 있어요', running: '가상 과제함에서 작업하고 있어요',
  verifying: '저장 내용과 제출 접수증을 확인하고 있어요', waiting_input: '답변을 기다리고 있어요', completed: '가상 과제 제출을 확인했어요',
  handoff: '여기서 확인이 필요해요', cancelled: '작업을 중지했어요', failed: '작업을 완료하지 못했어요', deadline_stopped: '검토 시간을 남기고 멈췄어요' };
let mode = 'rehearsal', current = null, connected = false, busy = false, generation = 0;
let pendingApproval = null, health, clockAnchor = null, totalSeconds = 3600;

function error(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
function appendMessage(role, text) {
  if (!text) return;
  const node = document.createElement('div'); node.className = `chat-message ${role}`;
  const author = document.createElement('span'); author.className = 'message-author'; author.textContent = role === 'user' ? '나' : 'Last Hour';
  node.append(author, document.createTextNode(text)); $('messages').append(node);
  $('conversation').scrollTop = $('conversation').scrollHeight;
}
function remaining() {
  if (!clockAnchor) return Number($('minutes').value) * 60;
  return Math.max(0, clockAnchor.seconds - (clockAnchor.frozen ? 0 : (performance.now() - clockAnchor.at) / 1000));
}
function renderClock() {
  const seconds = Math.ceil(remaining()), minutes = Math.floor(seconds / 60), rest = seconds % 60;
  const text = `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
  $('clock').replaceChildren(document.createTextNode(String(minutes).padStart(2, '0')));
  const colon = document.createElement('span'); colon.textContent = ':';
  $('clock').append(colon, document.createTextNode(String(rest).padStart(2, '0')));
  $('compact-time').textContent = text;
  $('time-used').style.width = current ? `${Math.min(100, Math.max(0, (1 - seconds / totalSeconds) * 100))}%` : '0%';
  $('time-reserve').style.width = `${Math.min(100, 300 / totalSeconds * 100)}%`;
}
function renderSnapshot(value) {
  current = value;
  clockAnchor = { seconds: value.seconds_remaining, at: performance.now(), frozen: terminal.has(value.status) };
  $('clock-label').textContent = terminal.has(value.status) ? '작업 종료 시 남은 시간' : '마감까지 남은 시간';
  $('activity-text').textContent = labels[value.status] || value.status;
  $('activity-dot').classList.toggle('active', !terminal.has(value.status));
  $('stop').disabled = terminal.has(value.status);
  $('minutes').disabled = true; $('draft').disabled = true;
  $('mode-live').disabled = true; $('mode-rehearsal').disabled = true;
  $('message').placeholder = terminal.has(value.status) ? '새 작업을 눌러 다시 시작하세요' : '추가로 알려주거나 수정할 내용을 입력하세요';
  $('send').disabled = !connected || terminal.has(value.status) || busy;
  $('message').disabled = terminal.has(value.status);
  if (value.pending_approval) showApproval(value.pending_approval);
  else { pendingApproval = null; $('approval').hidden = true; }
  if (value.verification) {
    for (const check of value.verification.checks) {
      if (!$('messages').querySelector(`[data-check="${CSS.escape(check.id)}"]`)) {
        const line = document.createElement('p'); line.className = 'chat-message assistant'; line.dataset.check = check.id;
        line.textContent = check.evidence; $('messages').append(line);
      }
    }
  }
  renderClock();
}
function showApproval(approval) {
  pendingApproval = approval;
  $('approval-summary').textContent = approval.summary;
  $('approval-draft').textContent = $('draft').value;
  $('approval').hidden = false;
  $('approve').textContent = approval.effect === 'api_safety' ? '확인하고 계속' : '확인하고 제출';
  $('approve').disabled = false; $('decline').disabled = false;
  $('activity-text').textContent = '제출 확인을 기다리고 있어요';
}
function renderPlan(plan) {
  $('plan').hidden = false; $('plan-steps').replaceChildren();
  for (const step of plan.steps) { const row = document.createElement('li'); row.textContent = step.title; $('plan-steps').append(row); }
}
async function screenEvent(data) {
  $('preview').disabled = false;
  await window.lastHour.window('screen', { taskId: current.id, screenId: data.screen_id });
}
async function follow(taskId, runGeneration) {
  let cursor = 0;
  while (runGeneration === generation) {
    try {
      const batch = await window.lastHour.request('GET', `/tasks/${taskId}/events?after=${cursor}&wait=20`);
      if (runGeneration !== generation) return;
      for (const event of batch.events) {
        cursor = event.seq;
        const data = event.data;
        if (event.type === 'chat.assistant') appendMessage('assistant', data.message);
        if (event.type === 'plan.ready') renderPlan(data.plan);
        if (event.type === 'task.replanning') $('activity-text').textContent = '새 메시지를 반영하고 있어요';
        if (event.type === 'computer.action') $('activity-text').textContent = data.summary;
        if (event.type === 'computer.screen') await screenEvent(data);
        if (event.type === 'approval.required') showApproval(data);
        if (event.type === 'approval.closed') { pendingApproval = null; $('approval').hidden = true; }
        if (event.type === 'task.status' && terminal.has(data.status) && data.message) appendMessage('assistant', data.message);
      }
      const snapshot = await window.lastHour.request('GET', `/tasks/${taskId}`);
      if (runGeneration !== generation) return;
      renderSnapshot(snapshot);
      if (terminal.has(snapshot.status)) return;
    } catch (exception) {
      if (runGeneration !== generation) return;
      error(exception.message); await new Promise(resolve => setTimeout(resolve, 1500));
    }
  }
}
async function send(event) {
  event?.preventDefault();
  if (!connected || busy) return;
  const text = $('message').value.trim(); if (!text) return;
  error(''); busy = true; $('send').disabled = true;
  try {
    if (!current) {
      if (!$('draft').value.trim()) throw new Error('테스트할 초안을 입력해주세요.');
      if (mode === 'live' && !health.model.key_configured) throw new Error('.env에 OpenRouter 키를 입력하고 앱을 다시 실행해주세요.');
      totalSeconds = Number($('minutes').value) * 60;
      const task = await window.lastHour.request('POST', '/tasks', {
        mode, goal: text, context: $('draft').value, deadline: new Date(Date.now() + totalSeconds * 1000).toISOString(), reserve_seconds: 300,
      });
      $('setup').hidden = true; appendMessage('user', text); $('message').value = '';
      renderSnapshot(task); generation++; follow(task.id, generation);
    } else {
      await window.lastHour.request('POST', `/tasks/${current.id}/messages`, { message: text });
      appendMessage('user', text); $('message').value = '';
    }
  } catch (exception) { error(exception.message); }
  finally { busy = false; $('send').disabled = !connected || Boolean(current && terminal.has(current.status)); }
}
async function approve(approved) {
  if (!pendingApproval || !current) return;
  const id = pendingApproval.id; $('approve').disabled = true; $('decline').disabled = true;
  try { renderSnapshot(await window.lastHour.request('POST', `/tasks/${current.id}/approvals`, { approval_id: id, approved })); }
  catch (exception) { error(exception.message); }
}
function setMode(value) {
  if (current) return;
  mode = value;
  for (const item of ['rehearsal', 'live']) { $(`mode-${item}`).classList.toggle('selected', mode === item); $(`mode-${item}`).setAttribute('aria-pressed', String(mode === item)); }
  $('mode-description').textContent = mode === 'live' ? '선택한 AI 모델이 화면을 보고 판단해요. 모델 사용 요금이 발생해요.' : '고정된 순서로 입력·저장·승인 흐름을 확인해요. 모델 호출 비용은 없어요.';
}
$('chat-form').addEventListener('submit', send);
$('message').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); } });
$('sample-goal').onclick = () => { $('message').value = '가상 과제함에 이 초안을 원문 그대로 입력하고 저장해줘. 확인을 받은 뒤 제출하고 접수증을 확인해줘.'; $('message').focus(); };
$('mode-rehearsal').onclick = () => setMode('rehearsal'); $('mode-live').onclick = () => setMode('live');
$('minutes').onchange = () => { totalSeconds = Number($('minutes').value) * 60; renderClock(); };
$('approve').onclick = () => approve(true); $('decline').onclick = () => approve(false);
$('preview').onclick = () => window.lastHour.window('preview');
$('close').onclick = () => window.lastHour.window('close');
$('collapse').onclick = async () => { const collapsed = await window.lastHour.window('collapse'); document.body.classList.toggle('collapsed', collapsed); $('collapse').setAttribute('aria-label', collapsed ? '오버레이 펼치기' : '오버레이 접기'); };
$('plan-toggle').onclick = () => { const collapsed = !$('plan-steps').hidden; $('plan-steps').hidden = collapsed; $('plan-toggle').textContent = collapsed ? '펼치기' : '접기'; $('plan-toggle').setAttribute('aria-expanded', String(!collapsed)); };
$('stop').onclick = async () => { if (!current) return; try { renderSnapshot(await window.lastHour.request('POST', `/tasks/${current.id}/cancel`, {})); } catch (exception) { error(exception.message); } };
$('reset').onclick = async () => {
  try { if (current && !terminal.has(current.status)) await window.lastHour.request('POST', `/tasks/${current.id}/cancel`, {}); }
  catch (exception) { error(exception.message); return; }
  generation++; current = null; clockAnchor = null; pendingApproval = null; busy = false;
  $('messages').replaceChildren(); $('plan').hidden = true; $('approval').hidden = true; $('setup').hidden = false;
  $('draft').disabled = false; $('minutes').disabled = false; $('mode-live').disabled = false; $('mode-rehearsal').disabled = false;
  $('message').disabled = false; $('message').value = ''; $('message').placeholder = '어떤 일을 끝낼까요?';
  $('clock-label').textContent = '시작 후 작업 시간'; $('activity-text').textContent = '새 작업을 시작할 수 있어요';
  $('activity-dot').classList.remove('active'); $('stop').disabled = true; $('preview').disabled = true; $('send').disabled = !connected;
  error(''); renderClock();
};
window.lastHour.onLost(() => { connected = false; $('send').disabled = true; $('connection').textContent = '로컬 서버 연결 끊김'; error('앱을 다시 실행해주세요.'); });
(async () => {
  try {
    const result = await window.lastHour.ready();
    if (!result?.ok) throw new Error(result?.message || 'AI 서버를 시작하지 못했어요.');
    health = result.health; connected = true; $('connection').textContent = health.model.key_configured ? '로컬 연결됨 · API 키 준비됨' : '로컬 연결됨 · 리허설 사용 가능';
    $('activity-text').textContent = '테스트할 내용을 입력해주세요'; $('send').disabled = false;
  } catch (exception) { error(exception.message); $('connection').textContent = '연결 실패'; }
})();
setInterval(renderClock, 1000); renderClock();
