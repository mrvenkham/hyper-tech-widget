package com.hypertechwidget.cosmo

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.util.Locale

/**
 * COSMO's home: shows the JARVIS page from the COSMO server running in Termux
 * (http://127.0.0.1:8080) full screen, and gives the page native powers through
 * `window.CosmoNative`: app drawer, Android speech in and out, home-screen mode
 * and the assistant setting. If the server isn't running, it asks Termux to start it.
 */
class MainActivity : Activity() {

    companion object {
        private const val REQ_MIC = 1
        private const val REQ_TERMUX = 2
    }

    private lateinit var web: WebView
    private lateinit var offline: LinearLayout
    private lateinit var status: TextView
    private val main = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var recognizer: SpeechRecognizer? = null
    private var pageShown = false
    private var connecting = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = FrameLayout(this).apply { setBackgroundColor(Ui.BG) }
        web = WebView(this)
        setupWeb()
        offline = buildOfflineScreen()
        root.addView(web, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        root.addView(offline, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        setContentView(root)
        tts = TextToSpeech(this) { ok -> if (ok == TextToSpeech.SUCCESS) tts?.language = Locale.UK }
        connect()
        handleAssist(intent)
    }

    // ───────────── connecting to the COSMO server ─────────────

    /** Checks the server; if it's down, asks Termux to start it and waits up to ~45 s. */
    private fun connect() {
        if (connecting) return
        connecting = true
        Thread {
            if (Server.alive()) {
                main.post { connecting = false; showPage() }
                return@Thread
            }
            main.post { showOffline("Waking COSMO up…") }
            val problem = Termux.start(this)
            if (problem == Termux.NEEDS_PERMISSION) {
                main.post {
                    connecting = false
                    showOffline("COSMO needs permission to start itself in Termux.")
                    requestPermissions(arrayOf(Termux.PERMISSION), REQ_TERMUX)
                }
                return@Thread
            }
            if (problem != null) {
                main.post { connecting = false; showOffline(problem) }
                return@Thread
            }
            for (i in 0 until 30) {
                Thread.sleep(1500)
                if (Server.alive()) {
                    main.post { connecting = false; showPage() }
                    return@Thread
                }
            }
            main.post {
                connecting = false
                showOffline("COSMO didn't start. Open Termux and type: cosmo")
            }
        }.start()
    }

    private fun showPage() {
        offline.visibility = View.GONE
        web.visibility = View.VISIBLE
        if (!pageShown) {
            pageShown = true
            web.loadUrl(Server.HOME)
        }
        CosmoWidget.refresh(this)
    }

    private fun showOffline(message: String) {
        status.text = message
        offline.visibility = View.VISIBLE
        web.visibility = View.INVISIBLE
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWeb() {
        web.setBackgroundColor(Ui.BG)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            setSupportMultipleWindows(false)
        }
        web.addJavascriptInterface(Bridge(), "CosmoNative")
        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                if (url.host == "127.0.0.1" || url.host == "localhost") return false
                // News links and anything else on the internet open in the browser.
                try { startActivity(Intent(Intent.ACTION_VIEW, url)) } catch (_: Exception) {}
                return true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) {
                    pageShown = false
                    showOffline("Lost the COSMO server. Reconnecting…")
                    main.postDelayed({ connect() }, 1500)
                }
            }
        }
    }

    private fun buildOfflineScreen(): LinearLayout {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Ui.BG)
            setPadding(Ui.dp(this@MainActivity, 28), 0, Ui.dp(this@MainActivity, 28), 0)
        }
        val icon = ImageView(this).apply { setImageResource(R.mipmap.ic_launcher) }
        box.addView(icon, LinearLayout.LayoutParams(Ui.dp(this, 96), Ui.dp(this, 96)))
        box.addView(Ui.text(this, "COSMO", 28f, Ui.CYAN, bold = true).apply { letterSpacing = 0.25f; gravity = Gravity.CENTER })
        status = Ui.text(this, "Connecting…", 16f, Ui.FG).apply { gravity = Gravity.CENTER }
        box.addView(status, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = Ui.dp(this@MainActivity, 12) })
        fun button(label: String, onClick: () -> Unit) = Button(this).apply {
            text = label
            setTextColor(Ui.CYAN)
            setBackgroundColor(Color.parseColor("#14202A"))
            setOnClickListener { onClick() }
        }
        val lp = { LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = Ui.dp(this@MainActivity, 12) } }
        box.addView(button("Start COSMO") { connect() }, lp())
        box.addView(button("Open Termux") { if (!Termux.open(this)) showOffline("Termux isn't installed. Get it from F-Droid.") }, lp())
        return box
    }

    // ───────────── native powers for the page ─────────────

    private fun js(code: String) = main.post { web.evaluateJavascript(code, null) }

    inner class Bridge {
        @JavascriptInterface fun isApp() = true

        @JavascriptInterface fun openApps() = main.post {
            startActivity(Intent(this@MainActivity, AppsActivity::class.java))
        }

        @JavascriptInterface fun speak(text: String) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "cosmo")
        }

        @JavascriptInterface fun stopSpeaking() { tts?.stop() }

        @JavascriptInterface fun listen() = main.post { startListening() }

        /** Turns home-screen mode on or off, then opens Android's "Default home app" list. */
        @JavascriptInterface fun setLauncher(on: Boolean) = main.post {
            packageManager.setComponentEnabledSetting(
                ComponentName(this@MainActivity, "$packageName.LauncherAlias"),
                if (on) PackageManager.COMPONENT_ENABLED_STATE_ENABLED else PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                PackageManager.DONT_KILL_APP
            )
            openSettings(Settings.ACTION_HOME_SETTINGS)
        }

        @JavascriptInterface fun openAssistantSettings() = main.post {
            openSettings(Settings.ACTION_VOICE_INPUT_SETTINGS)
        }

        @JavascriptInterface fun startServer() = main.post { connect() }
    }

    private fun openSettings(action: String) {
        try { startActivity(Intent(action)) } catch (_: Exception) {
            try { startActivity(Intent("android.settings.MANAGE_DEFAULT_APPS_SETTINGS")) } catch (_: Exception) {
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
        }
    }

    private fun startListening() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQ_MIC)
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            js("window.cosmoMicError && cosmoMicError('This phone has no speech recognizer. Install Google app or type instead.')")
            return
        }
        val rec = recognizer ?: SpeechRecognizer.createSpeechRecognizer(this).also { recognizer = it }
        rec.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) { js("window.cosmoListening && cosmoListening(true)") }
            override fun onResults(results: Bundle?) {
                val heard = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                js("window.cosmoListening && cosmoListening(false)")
                if (heard.isNotBlank()) js("window.cosmoHeard && cosmoHeard(${JSONObject.quote(heard)})")
            }
            override fun onError(error: Int) {
                js("window.cosmoListening && cosmoListening(false)")
                val msg = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Didn't catch that. Tap MIC and try again."
                    SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Voice input needs internet. Type instead."
                    else -> "Mic error ($error). Type instead."
                }
                js("window.cosmoMicError && cosmoMicError(${JSONObject.quote(msg)})")
            }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        rec.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        })
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        when (requestCode) {
            REQ_MIC -> if (granted) startListening() else js("window.cosmoMicError && cosmoMicError('Microphone permission was declined.')")
            REQ_TERMUX -> if (granted) connect() else showOffline("Without that permission, start COSMO yourself: open Termux and type cosmo.")
        }
    }

    // ───────────── lifecycle ─────────────

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleAssist(intent)
    }

    /** Opened from the assistant button: jump to COSMO's input with the keyboard up. */
    private fun handleAssist(intent: Intent?) {
        val a = intent?.action ?: return
        if (a == Intent.ACTION_ASSIST || a == Intent.ACTION_SEARCH_LONG_PRESS) {
            main.postDelayed({ js("(()=>{const i=document.querySelector('#tin'); if(i){i.scrollIntoView({block:'center'}); i.focus();}})()") }, 600)
        }
    }

    override fun onResume() {
        super.onResume()
        if (!pageShown) connect()
    }

    private fun isHomeMode() = packageManager.getComponentEnabledSetting(
        ComponentName(this, "$packageName.LauncherAlias")) == PackageManager.COMPONENT_ENABLED_STATE_ENABLED

    @Deprecated("Still the simplest back handling without AndroidX")
    override fun onBackPressed() {
        when {
            web.canGoBack() -> web.goBack()
            isHomeMode() -> Unit // the home screen doesn't close on Back
            else -> @Suppress("DEPRECATION") super.onBackPressed()
        }
    }

    override fun onDestroy() {
        recognizer?.destroy()
        tts?.shutdown()
        web.destroy()
        super.onDestroy()
    }
}
