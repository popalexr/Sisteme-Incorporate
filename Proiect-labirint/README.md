# Joc de reflexe / labirint pentru Raspberry Pi Sense HAT

Aplicatie Python pentru Sense HAT in care controlezi un punct albastru pe matricea LED 8x8.
Folosesti:

- joystick-ul pentru miscari rapide in directia dorita
- accelerometrul pentru drift: daca inclini placa, punctul este impins in acea directie

Scopul este sa ajungi la punctul verde fara sa fii lovit de obstacolele portocalii.
Peretii rosii blocheaza miscarea si formeaza labirintul.

## Cerinte

- Raspberry Pi cu Raspberry Pi OS
- Sense HAT conectat si functional
- Python 3.10+

## Instalare

```bash
cd Proiect-labirint
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Pe unele imagini de Raspberry Pi OS, biblioteca `sense-hat` si dependintele ei pot fi instalate si din sistem:

```bash
sudo apt update
sudo apt install -y python3-sense-hat
```

## Rulare

```bash
cd Proiect-labirint
python3 src/main.py
```

Sau:

```bash
./script.sh
```

## Controale

- joystick `up/down/left/right`: muta punctul albastru
- inclinare Sense HAT: adauga drift pe axa dominanta
- joystick `middle`: inchide jocul

## Optiuni utile

```bash
python3 src/main.py --rotation 90
python3 src/main.py --invert-x --invert-y
python3 src/main.py --tilt-threshold 0.70 --tilt-interval 0.25
```

Explicatii:

- `--rotation`: roteste matricea LED daca orientarea fizica este diferita
- `--invert-x` / `--invert-y`: inverseaza directia accelerometrului daca miscarea pare rasturnata
- `--tilt-threshold`: cat de mult trebuie inclinata placa pentru a produce drift
- `--tilt-interval`: cat de des se aplica drift-ul

## Testare fara hardware

Poti porni aplicatia si fara Sense HAT doar pentru un smoke test local:

```bash
python3 src/main.py --mock --max-frames 10
```

In modul `--mock` nu ai control real din joystick, dar poti verifica importurile si structura aplicatiei.
