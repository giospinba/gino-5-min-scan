import os
from glob import glob

# Cartella dove vengono salvate le scansioni HTML
dir_scan = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../docs'))
scan_files = sorted(
    [f for f in glob(os.path.join(dir_scan, 'scan_*.html'))],
    key=os.path.getmtime,
    reverse=True
)

# Mantieni solo i 3 più recenti
to_delete = scan_files[3:]
for f in to_delete:
    os.remove(f)
    print(f"Rimosso: {f}")
