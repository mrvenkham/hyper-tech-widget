# COSMO: living on your phone

COSMO is a coach that runs on your Android phone, with your laptop as an optional
faster brain. It reads the news, checks the weather, sales and commits, plans
your day, remembers you, sends notifications and controls a few safe phone
features.

```
JARVIS page (Chrome) ──► COSMO server (Termux, 127.0.0.1:8080)
                              ├─ AI: laptop Ollama (RTX 5070) → falls back to phone Ollama
                              ├─ News: BBC, Al Jazeera, FMT, Malay Mail, The Verge, TechCrunch, Hacker News
                              ├─ Weather: Open-Meteo · Sales: Gumroad · Commits: GitHub
                              ├─ Phone: notifications, torch, volume, brightness, voice (Termux:API)
                              └─ Your data: ~/cosmo/data/*.json (brain, memories, chat)
```

## 1. Install on the phone

1. From **F-Droid**, install **Termux**, **Termux:API**, **Termux:Boot** and
   **Termux:Widget**. Open each one once. They must all come from F-Droid.
2. In Termux:
   ```bash
   curl -fsSLo install.sh https://raw.githubusercontent.com/mrvenkham/hyper-tech-widget/claude/hydeck-dashboard-frontend-pvipz2/cosmo-local/install.sh
   bash install.sh
   ```
   Running it again later is safe; it keeps your data and settings.
3. Type `cosmo`. JARVIS opens in Chrome.
4. When Android asks, allow Termux:API to show notifications.

## 2. Laptop brain (optional, much faster)

On the Windows laptop:
1. Install Ollama from https://ollama.com/download
2. Download `laptop/setup-laptop.ps1` from this folder, right-click PowerShell →
   **Run as administrator**, then:
   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass; .\setup-laptop.ps1
   ```
3. It prints a line like `cosmo laptop 192.168.1.23 qwen2.5:7b`. Type that in Termux.

The laptop and phone must be on the same **private** Wi-Fi. The firewall rule
only opens on private networks, so Ollama is never exposed on public or school Wi-Fi.
When the laptop is off, COSMO uses the phone model automatically.
The header shows which one is thinking.

## 3. Connect Gumroad (optional)

Gumroad → Settings → Advanced → Applications → create an application → generate an
access token. Then in Termux: `cosmo gumroad YOUR_TOKEN`.
The token is stored only in `~/cosmo/config.json` on your phone.

## Commands

| In Termux | Does |
|---|---|
| `cosmo` | Start and open JARVIS |
| `cosmo stop` | Stop everything (saves battery) |
| `cosmo talk` | Hands-free voice conversation. Say "stop" to end. |
| `cosmo laptop <ip> [model]` / `cosmo laptop off` | Use or stop using the laptop brain |
| `cosmo gumroad <token>` / `cosmo gumroad off` | Connect Gumroad sales |
| `cosmo city Jitra 6.268 100.421` | Change the weather city |
| `cosmo status` · `cosmo logs` · `cosmo update` | Check, debug, update |

| In JARVIS | Does |
|---|---|
| Type normally | Talk to COSMO |
| "What's the news?" | Summary of real headlines, each tagged with its source |
| "Plan my day" | A plan from your tasks, sales, commits and weather |
| "Turn on the torch" | Phone actions from the safe list |
| Tap a country on the **World Grid** globe | Its latest headlines, then **What's happening?** for COSMO's summary |
| `/world Japan` · `/brief` · `/news` · `/do battery` · `/status` · `/model` · `/focus 25` · `/voice` · `/forget` | Shortcuts |

Home screen: long-press → Widgets → **Termux:Widget** → pick **COSMO** or **COSMO Talk**.

## Notifications

| When | What |
|---|---|
| 06:45 | Morning briefing: news, weather, today's top 3 |
| 16:30 | Check-in on your oldest open task |
| 21:30 | Evening recap |
| 22:30–06:30 | Quiet hours: nothing is sent |

Change the times in `~/cosmo/config.json` under `"schedule"`, then `cosmo stop` and `cosmo`.

## How "authentic news" works

- COSMO only gets headlines from the named outlets in `config.json`, and is told
  to use nothing else and to name the source of each item.
- The **Live News** panel shows the original headlines with links. Tap one to read
  it on the outlet's own site.
- An AI summary can still get details wrong, especially a small phone model.
  For anything important, read the original article.

## World Grid globe

- The globe is drawn on the phone from Natural Earth country borders
  (`countries.json`, public domain), with no 3D library.
- Drag sideways to spin it. A mouse can also tilt it. Tap a country, or type
  its name and tap **Go**.
- Headlines come from Google News search for that country over the last 2 days,
  and each one names its outlet. Tap a headline to open the original.
- **What's happening?** has COSMO summarise only those headlines, citing each outlet.

## What COSMO can't do

- It isn't conscious and doesn't think between messages. It feels alive because
  of memory, greetings and check-ins.
- It can't tap or type inside other apps, and there's no "Hey COSMO" wake word.
  Both need a native Android app.
- It won't send texts, make calls or delete files. That's deliberate.
- Voice input uses Google's speech service, so it needs internet. Everything
  else works offline except news, weather and sales.

## Troubleshooting

| Problem | Fix |
|---|---|
| JARVIS says **Offline** | In Termux: `cosmo` |
| Brain says **No engine** | `ollama pull llama3.2:3b`, or check the laptop is on |
| Laptop not used | Same Wi-Fi? Wi-Fi set to Private on Windows? Then `cosmo status` |
| No news | Check the internet. `cosmo logs` lists the feeds that failed. Edit `feeds` in `config.json` to swap sources. |
| No notifications | Open Termux:API once and allow notifications. Turn off battery optimization for Termux. |
| Slow replies | Use the laptop brain, or a smaller phone model: `ollama pull qwen2.5:1.5b`, then `/model qwen2.5:1.5b` |
