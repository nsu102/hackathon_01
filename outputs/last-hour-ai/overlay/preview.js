let revision = 0;
async function refresh() {
  const request = ++revision;
  const state = await window.lastHour.window('preview-state');
  if (!state) { document.getElementById('screen').hidden = true; document.getElementById('empty').hidden = false; return; }
  try {
    const image = await window.lastHour.request('GET', `/tasks/${state.taskId}/screens/${state.screenId}.png`);
    if (request !== revision) return;
    document.getElementById('screen').src = image; document.getElementById('screen').hidden = false; document.getElementById('empty').hidden = true;
  } catch { document.getElementById('empty').textContent = '화면을 불러오지 못했어요.'; }
}
window.lastHour.onPreview(refresh); refresh();
