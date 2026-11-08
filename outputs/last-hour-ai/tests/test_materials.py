import tempfile,unittest,zipfile
from pathlib import Path
from last_hour.materials import extract,MAX_BYTES

class MaterialTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_text_and_korean_encoding_and_bounds(self):
  path=self.root/'노트.txt';path.write_bytes('확인 코드 37'.encode('cp949'));self.assertIn('37',extract(path)['text'])
  path.write_text('a'*25000);self.assertTrue(extract(path)['truncated']);self.assertEqual(len(extract(path)['text']),24000)
 def test_docx_is_read_locally_without_copying_original(self):
  path=self.root/'참고.docx'
  with zipfile.ZipFile(path,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>고유 확인 코드 37</w:t></w:r></w:p></w:body></w:document>')
  result=extract(path);self.assertIn('37',result['text']);self.assertEqual(result['name'],'참고.docx')
 def test_pdf_text_and_scanned_pdf_guidance(self):
  try:from pypdf import PdfWriter
  except ImportError:self.skipTest('Install pypdf for PDF extraction test')
  from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
  writer=PdfWriter();page=writer.add_blank_page(width=612,height=792)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 40 700 Td (Reference code is 37.) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
  path=self.root/'notes.pdf';writer.write(path);self.assertIn('37',extract(path)['text']);self.assertEqual(extract(path)['pages'],1)
  blank=PdfWriter();blank.add_blank_page(width=612,height=792);blank.write(path)
  with self.assertRaisesRegex(ValueError,'스캔 PDF'):extract(path)
 def test_unknown_empty_and_large_files_rejected(self):
  for name in ['script.exe','empty.txt']:
   path=self.root/name;path.write_text('')
   with self.assertRaises(ValueError):extract(path)
  path=self.root/'large.pdf'
  with path.open('wb') as f:f.truncate(MAX_BYTES+1)
  with self.assertRaises(ValueError):extract(path)
