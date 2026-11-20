Symulator skanera Mega (20.11.2026, MEGA 2.0)

Prawdziwy program skaner (plik .elf z kompilacji) dziala na wirtualnym ATmega2560 (simavr), a klawiatura jest
modelowana tak jak w Keystation: dioda i styk miedzy linia grupy a linia klawisza, Y2 na A8.
Tak sprawdzamy kazda zmiane programu, zanim trafi na Mege: 88 klawiszy, akordy, odbicia styków, odwrocone styki,
polecenia z komputera, znak zycia, a od klawisza do routera (MegaReader) i do mega.py diagnoza.

Uruchamiane w chmurze Claude (Linux): gcc + libsimavr-dev, potem
  python3 -m unittest test_sim_firmware test_sim_end_to_end
compare.py porownuje stary skaner v1.2 z v2.0 pod obciazeniem.
Wynik 20.11: akord w trakcie wysylki v1.2 blad do 2,2 ms, v2.0 do 0,15 ms; 88 klawiszy naraz v1.2 do 36 ms, v2.0 1,3 ms.
