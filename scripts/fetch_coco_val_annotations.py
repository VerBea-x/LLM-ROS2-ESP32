#!/usr/bin/env python3
"""Read only one member of the official COCO ZIP via validated HTTP ranges."""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

URL='https://s3.amazonaws.com/images.cocodataset.org/annotations/annotations_trainval2017.zip'
class RemoteZip(io.RawIOBase):
    def __init__(self):self.position=0;self.size=252907541
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        self.position=offset+(0 if whence==0 else self.position if whence==1 else self.size)
        return self.position
    def read(self,n=-1):
        n=min(n if n>=0 else self.size-self.position,self.size-self.position)
        if n<=0:return b''
        start=self.position;end=start+n-1
        request=urllib.request.Request(URL+f'?course_range={start}-{end}',headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(request,timeout=90) as response:
            expected=f'bytes {start}-{end}/{self.size}'
            if response.status!=206 or response.headers.get('Content-Range')!=expected:
                raise RuntimeError('Server did not return the requested byte range')
            data=response.read()
        if len(data)!=n:raise RuntimeError('Truncated range')
        self.position+=n;return data

root=Path(__file__).resolve().parents[1];out=root/'data/annotations'
out.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(RemoteZip()) as z:
    info=z.getinfo('annotations/instances_val2017.json')
    print('compressed bytes',info.compress_size,'uncompressed',info.file_size,flush=True)
    raw=z.read(info)
    (out/'instances_val2017.json').write_bytes(raw)
    (out/'annotation_source.json').write_text(json.dumps({'official_archive':URL,'archive_member':info.filename,
       'member_crc32':hex(info.CRC),'compressed_bytes':info.compress_size,'uncompressed_bytes':len(raw)},indent=2)+'\n')
print('Saved official COCO validation annotations',flush=True)
