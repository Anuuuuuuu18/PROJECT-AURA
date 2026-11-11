<p align="center">
  <img src="docs/assets/aura-banner.svg" alt="AURA — Your hands become the interface" width="100%">
</p>

<p align="center">
  <a href="https://project-aura-322.netlify.app/"><img src="https://img.shields.io/badge/Live%20demo-Try%20AURA-d94f91?style=for-the-badge" alt="Try the live AURA demo"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-e982b1?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/Computer%20vision-MediaPipe-c7659c?style=for-the-badge" alt="MediaPipe computer vision">
  <img src="https://img.shields.io/badge/Voice-Offline-d94f91?style=for-the-badge" alt="Offline voice recognition">
  <img src="https://img.shields.io/badge/License-MIT-e982b1?style=for-the-badge" alt="MIT license">
</p>

<h1 align="center">AURA</h1>

<p align="center"><strong>Your hands become the interface.</strong><br>Move your cursor, scroll with one finger, click with a pinch, and open apps by voice.</p>

<p align="center">
  <a href="https://project-aura-322.netlify.app/">✨ Open the interactive demo</a>
  &nbsp; · &nbsp;
  <a href="#run-aura-on-windows">Run the desktop controller</a>
  &nbsp; · &nbsp;
  <a href="#privacy-by-design">Privacy</a>
</p>

---

## Meet AURA

AURA is a free Windows desktop experiment that combines webcam hand tracking with offline voice commands. It is built to feel approachable: one finger moves the pointer and scrolls vertically, a pinch clicks, and a short spoken command can open a Windows app.

The **live demo** is a browser-safe interactive preview of the controls. Real webcam and desktop control run locally in the Python app; a hosted website cannot move the visitor's system cursor.

## Try the demo

**[Open the pink AURA demo →](https://project-aura-322.netlify.app/)**

Drag in the mock browser window to move the glowing pointer and scroll its sample page. Try the pinch button or type **“open Chrome”** in the voice simulator. The page needs no camera, microphone, account, or installation.

## What you can do

| Input | Action |
| --- | --- |
| ☝️ Index finger | Move the cursor; move up or down to scroll the page under it |
| ✌️ Two fingers | Scroll vertically |
| 🤏 Pinch | Click once |
| ✊ Fist for one second | Pause all desktop controls |
| ✋ Open palm for 1.5 seconds | Resume controls |
| 🗣️ “Open Chrome” | Launch an installed app with a matching Start Menu shortcut |
| 🗣️ “Pause AURA” / “Resume AURA” | Pause or resume hands-free |

Live control starts **paused**. Say **“resume AURA”** or hold an open palm to activate it. AURA never runs spoken text as a shell command; voice launch only opens an installed Windows app.

## Run AURA on Windows

Use Python 3.10 or newer. Open this repository in VS Code, then run these commands in its terminal:

<pre><code>python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python aura_controls.py --live</code></pre>

Allow camera and microphone access for desktop apps when Windows asks. Keep your hand in the camera frame; move your index finger up or down slowly to scroll. Press <code>P</code> to pause/resume or <code>Q</code> / <code>Esc</code> to exit. For a no-control preview, omit <code>--live</code>.

The included Vosk English (India) model is about 57 MB. Voice recognition runs locally. To disable voice listening, add <code>--no-voice</code>.

## Publish the demo

The static demo is in <code>docs/</code>. Netlify is configured to publish that directory using <code>netlify.toml</code> and the free site has been deployed to <code>https://project-aura-322.netlify.app/</code>. The project is currently behind Netlify sign-in protection; set its visibility to <strong>Public</strong> in <strong>Project configuration → General → Visitor access</strong> to let visitors in. Connect this repository to Netlify for automatic future deploys, or run <code>netlify deploy --prod --dir docs</code> after signing in.

## Privacy by design

- Camera frames are processed locally by MediaPipe and are not recorded or uploaded.
- Voice is recognized locally by Vosk; audio is not sent to a cloud service.
- PyAutoGUI acts on the local desktop only when <code>--live</code> is enabled and controls are resumed.
- The hosted demo is a simulation and does not request camera or microphone access.

## Project layout

<pre><code>main.py                         Hand and finger recognition
aura_controls.py                Cursor, one-finger scroll, pinch, and safety controls
voice_control.py                Offline voice listener and safe app launching
vosk-model-small-en-in-0.4/     Bundled offline English (India) model
docs/index.html                 Pink interactive static demo
docs/assets/aura-banner.svg     Project banner
requirements.txt                Python dependencies</code></pre>

## Technology

Python · OpenCV · MediaPipe · NumPy · PyAutoGUI · Vosk · sounddevice

The bundled Vosk model is licensed under Apache-2.0. See [third-party notices](THIRD_PARTY_NOTICES.md). AURA's source code is MIT licensed; see [LICENSE](LICENSE).

<p align="center"><sub>Made with a little pink, a webcam, and a curious idea. 🎀</sub></p>
