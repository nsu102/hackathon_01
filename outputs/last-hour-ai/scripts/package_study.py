from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import shutil
project=Path(__file__).resolve().parents[1]
target=project.parent/'study-signal.zip'
with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=7) as archive:
 for file in sorted(project.rglob('*')):
  relative=file.relative_to(project)
  if not file.is_file() or any(p in {'node_modules','data','__pycache__','.venv','.gaze-venv','.git','.taste-skill','.build'} for p in relative.parts):continue
  if file.suffix in {'.zip','.dmg','.pyc','.private'} or file.name=='.DS_Store' or (file.name.startswith('.env') and file.name!='.env.example'):continue
  archive.write(file,Path('study-signal')/relative)
with ZipFile(target) as archive:
 names=archive.namelist()
 assert not any(n.endswith('/.env') or '.private' in n or '/node_modules/' in n or '/data/' in n for n in names)
 assert 'study-signal/.env.example' in names
shutil.copy2(target,project/'product/study-signal.zip')
print('Source package:',len(names),'files;',target.stat().st_size,'bytes; excluded private configuration and study data')
