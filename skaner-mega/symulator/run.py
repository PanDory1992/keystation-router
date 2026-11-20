import sys, subprocess
sys.path.insert(0, '..')
import mega_protocol as mp
ELF = '../build/skaner/skaner.ino.elf'
def sim(scen, us=1500000, elf=ELF, env=None):
    open('scen.txt','w').write(''.join(f'{l}\n' for l in scen))
    import os
    e = dict(os.environ); e.update(env or {})
    subprocess.run(['./matrix_sim', elf, 'scen.txt', 'out.txt', str(us)], check=True, capture_output=True, env=e)
    d = mp.Decoder(); msgs = []
    for line in open('out.txt'):
        t, b = line.split(); r = d.feed(bytes([int(b)]))
        for m in r: msgs.append((float(t), m))
    return d, msgs
if __name__ == '__main__':
    d, msgs = sim(open(sys.argv[1]).read().splitlines(), int(sys.argv[2]) if len(sys.argv) > 2 else 1500000)
    for t, m in msgs: print(f'{t/1000:9.2f} ms', m if not isinstance(m, mp.SelfTest) else ('TEST', m.counts, m.stuck))
    print('frames', d.frames, 'crc', d.crc_errors, 'lost', d.lost, 'garbage', d.garbage)
