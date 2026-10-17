package com.hypertechwidget.cosmo

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.Drawable
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.BaseAdapter
import android.widget.EditText
import android.widget.GridView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/** COSMO's app drawer: every installed app, searchable. Tap to open, long-press for app info. */
class AppsActivity : Activity() {

    private class App(val label: String, val component: ComponentName, val icon: Drawable)

    private var all: List<App> = emptyList()
    private var shown: List<App> = emptyList()
    private lateinit var adapter: BaseAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = Ui.dp(this, 16)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Ui.BG)
            setPadding(pad, pad, pad, 0)
        }
        root.addView(Ui.text(this, "APPS", 18f, Ui.CYAN, bold = true).apply { letterSpacing = 0.25f })
        val search = EditText(this).apply {
            hint = "Search apps"
            setHintTextColor(Ui.MUTED)
            setTextColor(Ui.FG)
            setSingleLine()
            setBackgroundColor(Color.parseColor("#14202A"))
            setPadding(pad, pad / 2, pad, pad / 2)
        }
        root.addView(search, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = pad / 2; bottomMargin = pad / 2 })

        val grid = GridView(this).apply {
            numColumns = 4
            verticalSpacing = pad
            stretchMode = GridView.STRETCH_COLUMN_WIDTH
        }
        adapter = object : BaseAdapter() {
            override fun getCount() = shown.size
            override fun getItem(position: Int) = shown[position]
            override fun getItemId(position: Int) = position.toLong()
            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                val cell = (convertView as? LinearLayout) ?: LinearLayout(this@AppsActivity).apply {
                    orientation = LinearLayout.VERTICAL
                    gravity = Gravity.CENTER_HORIZONTAL
                    addView(ImageView(context), LinearLayout.LayoutParams(Ui.dp(context, 52), Ui.dp(context, 52)))
                    addView(Ui.text(context, "", 12f, Ui.FG).apply {
                        gravity = Gravity.CENTER; maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END
                    }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
                }
                val app = shown[position]
                (cell.getChildAt(0) as ImageView).setImageDrawable(app.icon)
                (cell.getChildAt(1) as TextView).text = app.label
                return cell
            }
        }
        grid.adapter = adapter
        grid.setOnItemClickListener { _, _, pos, _ ->
            val app = shown[pos]
            startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                .setComponent(app.component).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            finish()
        }
        grid.setOnItemLongClickListener { _, _, pos, _ ->
            startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + shown[pos].component.packageName)))
            true
        }
        root.addView(grid, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        setContentView(root)

        search.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) = filter(s?.toString().orEmpty())
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        // Icons are slow to load on some phones, so read the app list off the main thread.
        Thread {
            val pm = packageManager
            val apps = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
                .filter { it.activityInfo.packageName != packageName }
                .map { App(it.loadLabel(pm).toString(), ComponentName(it.activityInfo.packageName, it.activityInfo.name), it.loadIcon(pm)) }
                .sortedBy { it.label.lowercase() }
            runOnUiThread { all = apps; filter(search.text.toString()) }
        }.start()
    }

    private fun filter(q: String) {
        shown = if (q.isBlank()) all else all.filter { it.label.contains(q.trim(), ignoreCase = true) }
        adapter.notifyDataSetChanged()
    }
}
