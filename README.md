<p align="center">
  <img src="docs/assets/aura-banner.svg" alt="AURA — Your hands become the interface" width="100%">
</p>

<h1 align="center">AURA</h1>

<p align="center">
  <strong>Hands-free desktop control with hand gestures and voice</strong><br>
  <sub>A little more magic in your everyday workflow ✨</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-f4a7c7?style=for-the-badge&logo=python&logoColor=5a3045" alt="Python 3.10 or later">
  <img src="https://img.shields.io/badge/Platform-Windows-f8c4dc?style=for-the-badge" alt="Windows">
  <img src="https://img.shields.io/badge/License-MIT-fce1ec?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  <a href="https://project-aura-322.netlify.app/">🌷 Live demo</a>
  &nbsp; · &nbsp;
  <a href="#getting-started">Getting started</a>
  &nbsp; · &nbsp;
  <a href="#privacy">Privacy</a>
</p>

---

## 🌸 Overview

AURA is a Windows desktop application that uses a webcam to track hand gestures and offline speech recognition to control common desktop actions. Move the pointer, scroll, click with a pinch, pause or resume control, and launch supported apps by voice.

The [browser demo](https://project-aura-322.netlify.app/) requests camera access when you click “Try the demo.” It tracks hands (not faces) locally in your browser and applies gestures only to the sample preview. It does not listen for voice or control your laptop; use the Windows app below for desktop control.

## ✨ Controls

| Gesture or command | Action |
| --- | --- |
| Index finger | Move the pointer |
| Index finger or peace sign | Scroll |
| Pinch | Click |
| “Scroll up” / “Scroll down” | Scroll by voice |
| Hold a fist | Pause controls |
| Hold an open palm | Resume controls |
| “Open [app]” | Launch a matching installed app |
| “Pause AURA” / “Resume AURA” | Pause or resume controls |

Live control starts paused. Resume with an open palm or voice command before using desktop actions.

Keep your hand clearly visible in the camera. A face in view alone does not trigger gestures. The website preview never controls the system mouse.

## 💻 Getting started

Requirements: Windows and Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python aura_controls.py --live
```

Allow camera and microphone access when prompted. Press `P` to pause or resume, and `Q` or `Esc` to quit. Run `python aura_controls.py` without `--live` for a dry run.

### Optional OpenAI voice enhancement

The Windows app's default voice mode uses offline Vosk. OpenAI is an optional voice transcription and command-interpretation service; it does not improve hand tracking. Start the app from a terminal with `--openai` and enter your key at the hidden prompt:

```powershell
python aura_controls.py --live --openai
```

The app must be running on your laptop, and it starts paused. Say “Resume AURA” or hold an open palm to resume. Then say commands such as “scroll down” or “open Chrome.” In this mode, detected voice clips are sent to OpenAI for transcription; API usage may incur charges. Keep the key local; never commit it or put it in the public website.

## 🔒 Privacy

Hand tracking runs locally. Voice recognition is local by default; desktop `--openai` mode uploads detected voice clips for cloud transcription and command interpretation. The browser demo requests camera access only after you click “Try the demo.” Video stays in your browser and is not uploaded; the hand-tracking library and model are loaded from jsDelivr. The browser demo cannot control your system mouse, listen for voice, or launch desktop apps.

## 📁 Project files

- `aura_controls.py` — desktop controls and safety behavior
- `main.py` — hand tracking and gesture recognition
- `voice_control.py` — offline voice commands and app launching
- `docs/` — static browser demo

## License

The AURA source code is licensed under the MIT License. See [LICENSE](LICENSE). The bundled Vosk model is licensed under Apache-2.0; see [third-party notices](THIRD_PARTY_NOTICES.md).
