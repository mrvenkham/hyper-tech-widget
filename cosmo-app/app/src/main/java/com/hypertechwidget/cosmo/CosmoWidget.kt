package com.hypertechwidget.cosmo

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Home-screen widget: COSMO's latest line to you (same as the JARVIS greeting). Tap to open. */
class CosmoWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        val pending = goAsync()
        Thread {
            try {
                val greet = Server.greeting()
                val engine = if (greet != null) Server.engine() else null
                val text = greet ?: "COSMO is offline. Tap to start."
                val state = when {
                    greet == null -> "OFFLINE"
                    engine != null -> engine.uppercase(Locale.ROOT) + " · " + SimpleDateFormat("HH:mm", Locale.ROOT).format(Date())
                    else -> "NO ENGINE"
                }
                val open = PendingIntent.getActivity(
                    context, 0, Intent(context, MainActivity::class.java),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                )
                for (id in ids) {
                    val v = RemoteViews(context.packageName, R.layout.widget_cosmo)
                    v.setTextViewText(R.id.widget_text, text)
                    v.setTextViewText(R.id.widget_state, state)
                    v.setOnClickPendingIntent(R.id.widget_root, open)
                    manager.updateAppWidget(id, v)
                }
            } finally {
                pending.finish()
            }
        }.start()
    }

    companion object {
        /** Ask every COSMO widget on the home screen to refresh now. */
        fun refresh(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, CosmoWidget::class.java))
            if (ids.isEmpty()) return
            context.sendBroadcast(Intent(context, CosmoWidget::class.java)
                .setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids))
        }
    }
}
