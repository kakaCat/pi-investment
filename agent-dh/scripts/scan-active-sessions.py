import subprocess, json

ZSTD = '/Users/yunpeng/anaconda3/bin/zstd'
base = '/Users/yunpeng/.dsh-agent-dh/sessions/--Users-yunpeng-pi-investment-agent-dh--'

def decompress(path):
    r = subprocess.run([ZSTD, '-d', '-c', '-f', path], capture_output=True)
    return r.stdout if r.returncode == 0 else None

for sid in ['session-d8c936df-7d52-452e-b3ea-8d5eaf87d3df', 'session-a1484624-d538-4e42-8a83-dd15c522bce5']:
    p = f'{base}/{sid}/session.jsonl.zstd'
    raw = decompress(p)
    lines = raw.split(b'\n')
    bad = []
    n_user = 0
    for i, line in enumerate(lines, 1):
        if not line.strip(): continue
        try:
            ev = json.loads(line)
        except Exception as e:
            bad.append((i, 'JSON_PARSE', '', str(e)[:60])); continue
        typ = ev.get('type', '')
        seq = ev.get('seq')
        data = ev.get('data') or {}
        if typ == 'user/message':
            n_user += 1
            if not data.get('id'):
                bad.append((i, 'user/message missing data.id', seq, line.decode('utf-8','replace')[:200]))
        elif typ in ('assistant/message', 'tool/result'):
            if not (data.get('message') or {}).get('id'):
                bad.append((i, f'{typ} missing data.message.id', seq, line.decode('utf-8','replace')[:200]))
    print(f'=== {sid} ===')
    print('  lines:', len(lines), ' user/message events:', n_user)
    print('  bad events:', len(bad))
    for ln, why, seq, head in bad:
        print(f'    line {ln} seq={seq} {why}')
        print(f'      {head}')
