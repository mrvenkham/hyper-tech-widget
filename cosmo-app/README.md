# COSMO for Android

A native app that gives COSMO its own icon, a home-screen widget, an app drawer,
an optional **home-screen (launcher) mode** and an **assistant** entry.
COSMO's brain still runs in Termux (`cosmo-local/`), so install that first.

## Install

1. Run the COSMO installer in Termux (`cosmo-local/README.md`). It also lets this
   app start COSMO by itself (`allow-external-apps = true`).
2. On the phone, download the APK:
   **https://github.com/mrvenkham/hyper-tech-widget/releases/download/cosmo-app-latest/cosmo.apk**
3. Open it and allow "Install unknown apps" for your browser when Android asks.
4. Open **COSMO**. The first time, allow it to **run commands in Termux**; it then
   starts COSMO for you whenever the server isn't running.

Every push to `cosmo-app/` builds a new APK (GitHub Actions → *COSMO Android app*).
It installs over the old one and keeps your settings.

## What's in it

| Feature | How |
|---|---|
| Full-screen JARVIS, no browser bar | Just open COSMO |
| Starts COSMO in Termux automatically | Happens on open, or tap **Start COSMO** |
| Voice in and out | **MIC** button; `/voice` for spoken replies |
| App drawer | **⌗ APPS** button or `/apps`. Long-press an app for its info page. |
| COSMO as your home screen | `/home on`, then pick COSMO in the list. `/home off` to undo. |
| COSMO as your assistant | `/assistant`, then pick COSMO. Long-press home or power, depending on the phone, and COSMO opens with the keyboard up. |
| Home-screen widget | Long-press the home screen → Widgets → COSMO |

## Limits

- It's sideloaded, not from the Play Store. Android warns about unknown apps;
  that's expected for apps you build yourself.
- The signing key in this folder is public. It's fine for your own phone, but
  never use it for a store release; make a private key for that.
- Some phones, like Samsung with Bixby, limit which apps can be the power-button
  assistant. The home-button long-press usually still works.
- Voice input uses the phone's speech service, which on most phones is Google's
  and needs internet.
