package com.hypertechwidget.cosmo

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.os.Build
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** The COSMO server that runs in Termux (server.py). */
object Server {
    const val HOME = "http://127.0.0.1:8080/"

    fun get(path: String, timeoutMs: Int = 2500): String? = try {
        val c = URL(HOME + path).openConnection() as HttpURLConnection
        c.connectTimeout = 1200
        c.readTimeout = timeoutMs
        try {
            if (c.responseCode == 200) c.inputStream.bufferedReader().readText() else null
        } finally { c.disconnect() }
    } catch (_: Exception) { null }

    fun alive() = get("api/greet") != null

    fun greeting(): String? = get("api/greet")?.let { JSONObject(it).optString("text") }

    /** "Laptop", "Phone" or null, from /api/status. */
    fun engine(): String? = get("api/status", 6000)?.let {
        JSONObject(it).optJSONObject("engine")?.optString("name")
    }
}

/**
 * Asks Termux to run `cosmo --no-open` in the background (Termux's RUN_COMMAND).
 * Needs: Termux from F-Droid, "allow-external-apps = true" in ~/.termux/termux.properties
 * (the COSMO installer sets it), and the RUN_COMMAND permission granted to this app.
 */
object Termux {
    const val PACKAGE = "com.termux"
    const val PERMISSION = "com.termux.permission.RUN_COMMAND"
    const val NEEDS_PERMISSION = "needs-permission"

    fun installed(ctx: Context) = try {
        ctx.packageManager.getPackageInfo(PACKAGE, 0); true
    } catch (_: PackageManager.NameNotFoundException) { false }

    /** Returns null when the request was sent, or a message saying what's wrong. */
    fun start(ctx: Context): String? {
        if (!installed(ctx)) return "Termux isn't installed. Get it from F-Droid, then run the COSMO installer."
        if (ctx.checkSelfPermission(PERMISSION) != PackageManager.PERMISSION_GRANTED) return NEEDS_PERMISSION
        val i = Intent().apply {
            setClassName(PACKAGE, "com.termux.app.RunCommandService")
            action = "com.termux.RUN_COMMAND"
            putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/cosmo")
            putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arrayOf("--no-open"))
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
        }
        return try {
            if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i) else ctx.startService(i)
            null
        } catch (e: Exception) {
            "Termux didn't accept the request (${e.javaClass.simpleName}). Run the COSMO installer again, then retry."
        }
    }

    fun open(ctx: Context): Boolean {
        val launch = ctx.packageManager.getLaunchIntentForPackage(PACKAGE) ?: return false
        ctx.startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        return true
    }
}

/** Shared colours and tiny view helpers (no AndroidX, no layout files needed). */
object Ui {
    val BG = Color.parseColor("#090A0F")
    val FG = Color.parseColor("#E4F6FB")
    val MUTED = Color.parseColor("#7F93A3")
    val CYAN = Color.parseColor("#00F0FF")

    fun dp(ctx: Context, v: Int) = (v * ctx.resources.displayMetrics.density).toInt()

    fun text(ctx: Context, s: String, sizeSp: Float, color: Int, bold: Boolean = false) = TextView(ctx).apply {
        text = s
        textSize = sizeSp
        setTextColor(color)
        if (bold) typeface = Typeface.DEFAULT_BOLD
    }
}
