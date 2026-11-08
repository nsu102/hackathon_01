// The website shows an unedited native app capture. No sensor or AI requests.
const viewer = document.getElementById('app-viewer');
let previousFocus;
for (const button of document.querySelectorAll('[data-open-app]')) {
  button.addEventListener('click', () => {
    previousFocus = button;
    if (document.querySelector('.nav').classList.contains('is-open')) document.querySelector('.nav__toggle').click();
    viewer.showModal();
    document.body.classList.add('viewer-open');
    document.getElementById('close-viewer').focus();
  });
}
document.getElementById('close-viewer').addEventListener('click', () => viewer.close());
viewer.addEventListener('click', event => {
  if (event.target !== viewer) return;
  const bounds = viewer.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) viewer.close();
});
viewer.addEventListener('close', () => {
  document.body.classList.remove('viewer-open');
  previousFocus?.focus({preventScroll:true});
});
const toggle = document.querySelector('.nav__toggle');
new MutationObserver(() => {
  const open = toggle.getAttribute('aria-expanded') === 'true';
  toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  document.querySelector('main').inert = open;
  document.querySelector('footer').inert = open;
}).observe(toggle, {attributes:true,attributeFilter:['aria-expanded']});
