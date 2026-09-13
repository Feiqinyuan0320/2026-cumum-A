"""Recompute every run used by the final handoff; preserves supplied files."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parent
runs=[
 ('be1600_64',1600,1/64,'be','original'),
 ('be1600_128',1600,1/128,'be','original'),
 ('bdf800_32',800,1/32,'bdf2','integrated'),
 ('bdf1600_32',1600,1/32,'bdf2','integrated'),
 ('bdf1600_64',1600,1/64,'bdf2','integrated'),
 ('bdf3200_64',3200,1/64,'bdf2','integrated'),
 ('bdf3200_128',3200,1/128,'bdf2','integrated'),
 ('bdf6400_128',6400,1/128,'bdf2','integrated')]
for label,n,dt,scheme,boundary in runs:
 subprocess.run([sys.executable,str(ROOT/'verify_q1.py'),'--n',str(n),'--dt',str(dt),
                 '--scheme',scheme,'--boundary',boundary,'--label',label],check=True)
subprocess.run([sys.executable,str(ROOT/'compare_q1.py')],check=True)
subprocess.run([sys.executable,str(ROOT/'build_delivery.py')],check=True)
