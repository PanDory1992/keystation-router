import numpy as np
exec(open('ramps.py').read().split('allres = []')[0])   # reuse loading and ramp detection
def smooth(y, w=13):
    return np.array([np.median(y[max(0, i - w // 2):i + w // 2 + 1]) for i in range(len(y))])
A = []; floor = []; tot = 0
for name, a, z in ramps:
    r, o, n = R[a:z], O[a:z], N[a:z]; tot += len(o)
    tr = smooth(o.astype(float)); A += list(zip(tr, o - tr))
    floor += list(o[r == 1])
A = np.array(A); floor = np.array(floor)
print(f'nut w rampach {tot}; z tego "1" z klawiatury {len(floor)} ({100*len(floor)/tot:.0f}%) -> na wyjsciu: {dict(zip(*np.unique(floor, return_counts=True)))}')
edges = [1, 20, 30, 45, 60, 75, 90, 105, 128]; sig = []
print('WYJSCIE z routera (to, co slyszysz):  zakres / nut / rozrzut sigma / poziomy')
tot_l = 0
for a, z in zip(edges[:-1], edges[1:]):
    j = (A[:, 0] >= a) & (A[:, 0] < z)
    if j.sum() < 6: print(f'  {a:3d}-{z-1:3d}  n={j.sum():3d}   (za malo)'); continue
    s = max(1.0, 1.4826 * np.median(np.abs(A[j, 1]))); l = (z - a) / (2 * s); tot_l += l
    print(f'  {a:3d}-{z-1:3d}  n={j.sum():3d}   sigma {s:5.1f}   poziomy {l:4.1f}')
print(f'razem okolo {tot_l + 1:.1f} poziomow na wyjsciu')
