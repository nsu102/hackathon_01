"""Extract user-chosen study documents locally. Original files are never copied."""
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES=20_000_000
MAX_TEXT=24000

def extract(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError('자료 파일은 20 MB 이내로 선택해주세요.')
    kind=path.suffix.lower();pages=None;truncated=False
    if kind in {'.txt','.md'}:
        raw=path.read_bytes()
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:text=raw.decode('cp949')
            except UnicodeDecodeError:raise ValueError('UTF-8 또는 한글 텍스트 파일로 저장해주세요.') from None
    elif kind=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('비밀번호가 없는 PDF를 선택해주세요.')
        pages=len(reader.pages);parts=[];length=0
        for page in reader.pages[:min(40,pages)]:
            part=page.extract_text() or '';parts.append(part);length+=len(part)
            if length>=MAX_TEXT:truncated=True;break
        text='\n\n'.join(parts);truncated=truncated or pages>40
    elif kind=='.docx':
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('word/document.xml')
            if info.file_size>4_000_000:raise ValueError('문서 내용이 너무 커요. 필요한 부분만 별도 파일로 저장해주세요.')
            tree=ET.fromstring(archive.read(info))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text='\n'.join(''.join(p.itertext()) for p in tree.findall('.//w:p',ns))
    else:raise ValueError('PDF, TXT, MD, DOCX 자료를 선택해주세요.')
    text=text.replace('\x00','').strip()
    if not text:raise ValueError('읽을 텍스트가 없어요. 스캔 PDF는 화면에 열고 스크린샷으로 질문해주세요.')
    return {'name':path.name[:200],'text':text[:MAX_TEXT],'pages':pages,'truncated':truncated or len(text)>MAX_TEXT}

def main():
    try:print(json.dumps({'ok':True,**extract(sys.argv[1])},ensure_ascii=False))
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) else '파일을 읽지 못했어요. 문서 형식이나 암호 여부를 확인해주세요.'
        print(json.dumps({'ok':False,'error':message},ensure_ascii=False));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
