#!/data/data/com.termux/files/usr/bin/python
"""
`cosmo talk`: a hands-free voice conversation with COSMO.

Listens with Android's speech recognizer (termux-speech-to-text, which may use
Google's online service), sends the words to the COSMO server, and speaks the
reply with termux-tts-speak. Say "stop", "bye" or "goodbye" to end.
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.request

SERVER = "http://127.0.0.1:8080"
END = re.compile(r"^\s*(stop|bye|goodbye|that's all|thats all|exit)\W*$", re.I)


def speak(text):
    subprocess.run(["termux-tts-speak", "-r", "1.05", text])


def listen():
    r = subprocess.run(["termux-speech-to-text"], capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def ask(message):
    req = urllib.request.Request(SERVER + "/api/ask", data=json.dumps({"message": message}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def spoken(text):
    # Drop the TASK:/MEMORY:/ACTION: lines and the [status] line; they read badly aloud.
    text = re.sub(r"^\s*(?:[-*\d.)\s]*)(TASK|MEMORY|ACTION)\s*:.*$", "", text, flags=re.I | re.M)
    return re.sub(r"\[[^\]]*\]\s*$", "", text).strip()


def main():
    if not shutil.which("termux-speech-to-text"):
        print("Voice needs Termux:API (from F-Droid) and: pkg install termux-api")
        return 1
    try:
        urllib.request.urlopen(SERVER + "/api/greet", timeout=3)
    except Exception:
        print("COSMO isn't running. Type: cosmo --no-open   then try again.")
        return 1
    speak("COSMO here. Go ahead, boss.")
    while True:
        print("\n🎙  Listening… (say 'stop' to end)")
        heard = listen()
        if not heard:
            speak("Didn't catch that. Ending voice mode.")
            break
        print("you  ›", heard)
        if END.match(heard):
            speak("Steady. Talk later, boss.")
            break
        try:
            r = ask(heard)
        except Exception as ex:
            print("error:", ex)
            speak("I lost my brain for a second. Check the engine is running.")
            break
        print("COSMO ›", r["text"])
        for e in r.get("events", []):
            print(f"  [{e['kind']}] {e['text']}" + (f" → {e['result']}" if e.get("result") else ""))
        speak(spoken(r["text"]) or "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
