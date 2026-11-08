# torchvision 0.29 loads _C_stable.so through torch.ops rather than Python import.
# Include both stable native operators and their private image-codec libraries.
from PyInstaller.utils.hooks import collect_dynamic_libs
binaries = collect_dynamic_libs('torchvision', search_patterns=['*.so', '*.dylib'])
module_collection_mode = 'pyz+py'
