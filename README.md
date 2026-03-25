# Object Detection Live pentru Raspberry Pi 5 (Python)

Proiect Python pentru recunoaștere de obiecte în timp real din camera Raspberry Pi 5,
cu interfață web în FastAPI (fără ferestre OpenCV locale).

## Ce face

- preia cadre live din cameră (prioritar prin `Picamera2`)
- face detecție obiecte în fiecare cadru
- desenează bounding box + etichetă + scor de încredere
- servește streamul într-o pagină web (`/`)

## Cerințe

- Raspberry Pi 5 (Raspberry Pi OS Bookworm recomandat)
- cameră compatibilă Raspberry Pi
- Python 3.10+

## Instalare

### 1) Pachete de sistem (recomandat pe Raspberry Pi)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-picamera2 libcamera-apps
```

### 2) Mediu virtual și dependențe Python

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Descarcă modelul

```bash
python scripts/download_model.py
```

Dacă ai eroare SSL/certificate în mediul tău:

```bash
python scripts/download_model.py --insecure
```

## Rulare

```bash
python src/main.py --backend picamera2 --host 0.0.0.0 --port 8000 --width 1280 --height 720 --confidence 0.5
```

După pornire, deschide în browser:

```text
http://<IP_RASPBERRY_PI>:8000
```

Endpoint-uri:

- `GET /` - interfața web
- `GET /video_feed` - stream MJPEG live
- `GET /status` - status backend cameră și configurare

Oprire server: `Ctrl+C`

## Clase detectate

Modelul detectează cele 20 clase Pascal VOC (ex: `person`, `car`, `dog`, `cat`, `bus`, `bottle` etc.).

## Structură

```text
.
├── models/
├── scripts/
│   └── download_model.py
├── src/
│   ├── camera.py
│   ├── detector.py
│   └── main.py
├── requirements.txt
└── README.md
```

## Troubleshooting

- Dacă nu găsește camera:
  - verifică panglica camerei și activarea libcamera
  - testează: `libcamera-hello`
  - verifică importul `Picamera2` în venv:
    - `.venv/bin/python -c "from picamera2 import Picamera2; print('ok')"`
  - dacă importul eșuează, recreează venv cu system packages:
    - `rm -rf .venv && python3 -m venv --system-site-packages .venv`
- Dacă rulezi lent:
  - scade rezoluția (`--width 640 --height 480`)
  - crește pragul de încredere (`--confidence 0.6`)
  - scade calitatea streamului JPEG (`--jpeg-quality 70`)
