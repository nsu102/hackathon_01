from pathlib import Path
from playwright.sync_api import sync_playwright
import struct,zlib
root=Path(__file__).resolve().parents[1]/'overlay/assets'
svg=(root/'StudySignalTemplate.svg').read_text()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 for scale in (1,2):
  page=browser.new_page(viewport=dict(width=16,height=16),device_scale_factor=scale)
  page.set_content('<style>html,body{margin:0;width:16px;height:16px;background:transparent}svg{display:block}</style>'+svg)
  raw=page.screenshot(omit_background=True)
  dpi=round(72*scale/0.0254);data=struct.pack('>IIB',dpi,dpi,1);kind=b'pHYs'
  chunk=struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
  raw=raw[:33]+chunk+raw[33:]
  name='StudySignalTemplate'+('@2x' if scale==2 else '')+'.png'
  (root/name).write_bytes(raw);page.close()
 browser.close()
print('Rendered template icons: 16px/72dpi and 32px/144dpi')
