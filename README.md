# Jarvis

Локальный офлайн-ассистент для Linux. Он постоянно слушает микрофон, распознаёт русские команды, отвечает голосом через `Piper` и открывает только заранее разрешённые приложения.

## Возможности

- непрерывное прослушивание микрофона через `ffmpeg` + PipeWire/PulseAudio
- выделение фраз по VAD через `webrtcvad`
- офлайн-распознавание речи через `vosk`
- нейросетевой TTS через `Piper`
- запуск или фокус уже открытых программ через `wmctrl`
- fallback-голос через `spd-say`
- управление daemon-процессом через Unix socket
- системный трей через `yad`

## Быстрый старт

1. Установите Python-зависимости:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

2. Скачайте русскую модель Vosk и распакуйте её в `data/models/vosk-ru`.

3. Скачайте голос `Piper`:

```bash
.venv/bin/python -m piper.download_voices --data-dir data/voices/piper ru_RU-irina-medium
```

4. При необходимости отредактируйте `config/settings.toml` и `config/apps.toml`.

5. Проверьте окружение:

```bash
.venv/bin/python -m jarvis doctor
```

6. Запустите ассистента:

```bash
.venv/bin/python -m jarvis run
```

## Команды

```bash
.venv/bin/python -m jarvis run
.venv/bin/python -m jarvis doctor
.venv/bin/python -m jarvis list-devices
.venv/bin/python -m jarvis ctl status
.venv/bin/python -m jarvis ctl pause
.venv/bin/python -m jarvis ctl resume
.venv/bin/python -m jarvis ctl reload
.venv/bin/python -m jarvis ctl stop
.venv/bin/python -m jarvis tray
```

## Конфигурация

- [config/settings.toml](config/settings.toml)
- [config/apps.toml](config/apps.toml)
