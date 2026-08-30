import subprocess, os, glob, shutil, time, json

ZSTD = '/Users/yunpeng/anaconda3/bin/zstd'
BACKUP_ROOT = f'/tmp/session-blankline-backup-{int(time.time())}'
os.makedirs(BACKUP_ROOT, exist_ok=True)

def decompress(path):
    r = subprocess.run([ZSTD, '-d', '-c', '-f', path], capture_output=True)
    if r.returncode != 0: raise RuntimeError(r.stderr[:200])
    return r.stdout

def compress_single(data: bytes):
    r = subprocess.run([ZSTD, '-q', '-c'], input=data, capture_output=True)
    if r.returncode != 0: raise RuntimeError(r.stderr[:200])
    return r.stdout

targets = []
roots = ['/Users/yunpeng/.dsh-agent-dh/sessions', '/Users/yunpeng/.dsh/sessions']
# only the 28 previously rewritten (agent-dh session-* + old-store) -> detect by 2-frame + presence of blank lines
for root in roots:
    if not os.path.isdir(root): continue
    for p in sorted(glob.glob(root + '/**/session.jsonl.zstd', recursive=True)):
        raw = decompress(p)
        lines = raw.split(b'\n')
        blanks = [i+1 for i, l in enumerate(lines) if not l.strip()]
        if blanks:
            targets.append((p, blanks))

print('files with blank lines:', len(targets))
fixed = []
for p, blanks in targets:
    raw = decompress(p)
    lines = raw.split(b'\n')
    kept = [l for l in lines if l.strip()]
    new_raw = b'\n'.join(kept)
    if not new_raw.endswith(b'\n'): new_raw += b'\n'
    nl = new_raw.find(b'\n')
    header = new_raw[:nl+1]
    events = new_raw[nl+1:]
    hf = compress_single(header)
    ef = compress_single(events)
    bak = os.path.join(BACKUP_ROOT, os.path.basename(os.path.dirname(p)) + '.zstd')
    shutil.copy2(p, bak)
    with open(p + '.tmp', 'wb') as f: f.write(hf + ef)
    os.replace(p + '.tmp', p)
    fixed.append((p, len(blanks), len(kept)))

print('fixed:', len(fixed))
for p, nb, nk in fixed[:30]:
    print(f'  blanks={nb} lines={nk} {p}')
print('backup:', BACKUP_ROOT)
