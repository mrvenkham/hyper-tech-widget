# COSMO Local

JARVIS OS with COSMO running **on your Android phone**. The AI model, your
notes and your tasks all stay on the device. It works in airplane mode.

| Part | What runs it |
|---|---|
| The AI (COSMO's brain) | [Ollama](https://ollama.com) inside Termux, at `127.0.0.1:11434` |
| The screen (JARVIS OS) | `index.html`, served by Python at `127.0.0.1:8080` |
| Your notes and tasks | Chrome's storage for `127.0.0.1:8080`, on the phone |

## Install (about 30–60 minutes, mostly downloading)

1. **Install Termux from F-Droid** (https://f-droid.org/packages/com.termux/).
   Don't use the Play Store version; it's outdated and its packages break.
2. Open Termux and paste these two lines:

   ```bash
   curl -fsSLo install.sh https://raw.githubusercontent.com/mrvenkham/hyper-tech-widget/claude/hydeck-dashboard-frontend-pvipz2/cosmo-local/install.sh
   bash install.sh
   ```

   The installer picks a model by RAM: under 5 GB → `gemma3:1b`,
   5–6 GB → `llama3.2:3b`, 7 GB+ → `gemma3:4b`. To choose yourself:
   `bash install.sh qwen2.5:1.5b`.
3. When it says **Done**, type `cosmo`. Chrome opens JARVIS OS.

## Daily use

| Do this | How |
|---|---|
| Start COSMO | Open Termux, type `cosmo` |
| Stop COSMO (saves battery) | In Termux, type `cosmo stop` |
| Home-screen icon | In Chrome on the JARVIS page: ⋮ → Add to Home screen. Termux still has to be running. |
| Switch model | `ollama pull <name>` in Termux, then `/model <name>` in JARVIS |

## Know the limits

- **Small models are less smart.** A 1–4B model on a phone is fine for
  planning and coaching, but weaker at code and facts than the cloud COSMO.
- **Battery and heat.** Running a model works the phone hard. Stop it when
  you're done.
- **Voice input (MIC) is not local.** Chrome's speech recognition sends audio
  to Google, so it needs internet. Typing and voice output (`/voice`) stay on
  the phone.
- **Android may kill Termux** in the background. `cosmo` takes a wake lock to
  prevent that. If it still happens, exclude Termux from battery optimization
  in Android settings.
- **It's not a system assistant.** There's no wake word, and it can't read
  notifications or control other apps. That needs a native Android app.

## Troubleshooting

| Problem | Fix |
|---|---|
| `pkg install ollama` fails | The installer retries through the TUR repo. If both fail, run `pkg update` and try again later. |
| JARVIS says **Engine Offline** | Termux isn't running COSMO. Type `cosmo`. |
| JARVIS says **No model** | `ollama pull llama3.2:3b` |
| Replies are very slow | Use a smaller model: `ollama pull gemma3:1b`, then `/model gemma3:1b` |
| Notes vanished | They live in Chrome's storage for `127.0.0.1:8080`. Clearing Chrome's site data deletes them. |
