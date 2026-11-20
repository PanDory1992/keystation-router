import run, mega_protocol as mp, statistics as st, sys
from test_sim_firmware import press, events
V1='/home/claude/skaner/build/skaner/skaner.ino.elf'
T0=400_000
def bench(elf):
    notes=[48,52,55,60,64,67,71,76,79,83]
    scen=[]
    for i,n in enumerate(notes): scen+=press(T0+i*100,n,6000,hold_us=20000,rel_us=3000)
    for i,n in enumerate(notes): scen+=press(T0+29000+i*100,n+1,5200+300*i,hold_us=50000)
    scen.sort(key=lambda s: float(s.split()[0]))
    _,m3=run.sim(scen,1_000_000,elf=elf)
    on3={e.note:e.us for e in events(m3,'on')}
    err3=[on3.get(n+1,0)-(5200+300*i) for i,n in enumerate(notes)]
    scen=[]
    for n in range(21,109): scen+=press(T0+(n%5)*50,n,8000,hold_us=200000)
    scen.sort(key=lambda s: float(s.split()[0]))
    _,m2=run.sim(scen,1_600_000,elf=elf)
    e2=[e.us-8000 for e in events(m2,'on')]
    last=max(t for t,m in m2 if isinstance(m,mp.Event) and m.kind=='on')
    return max(map(abs,err3)), len(e2), max(map(abs,e2)), round((last-T0-8000)/1000,1)
for name,elf in [('v1.2',V1),('v2.0',run.ELF)]:
    a,n,b,c=bench(elf)
    print(f'{name}: akord w trakcie wysylki max blad {a} us | 88 naraz: {n} nut, max blad {b} us, ostatnia nuta po {c} ms')
