package com.andyjx.autosalesvoice

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.*

class MainActivity : Activity() {
    private val products by lazy { ProductStore.load(this) }
    private var currentIndex = 0
    private var refreshing = false
    private lateinit var spinner: Spinner
    private lateinit var nameEdit: EditText
    private lateinit var scriptsEdit: EditText
    private lateinit var randomCheck: CheckBox
    private lateinit var delaySeek: SeekBar
    private lateinit var rateSeek: SeekBar
    private lateinit var volumeSeek: SeekBar
    private lateinit var delayText: TextView
    private lateinit var rateText: TextView
    private lateinit var volumeText: TextView
    private lateinit var interjectEdit: EditText
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 10)
        setContentView(buildUi())
        refreshProducts(0)
    }

    private fun buildUi(): View {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(30))
        }
        scroll.addView(root)
        root.addView(TextView(this).apply { text = "自动讲品 · 安卓版"; textSize = 24f })
        root.addView(TextView(this).apply {
            text = "纯本地TTS｜多商品话术｜切到直播App后后台继续讲"
            setPadding(0, dp(4), 0, dp(12))
        })

        root.addView(label("当前商品"))
        spinner = Spinner(this)
        root.addView(spinner)
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (!refreshing && position in products.indices) loadProduct(position)
            }
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }

        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        row.addView(button("新建") { currentIndex = -1; nameEdit.setText(""); scriptsEdit.setText(""); status("正在新建商品") }, weight())
        row.addView(button("保存") { saveProduct(false) }, weight())
        row.addView(button("删除") { deleteProduct() }, weight())
        root.addView(row)

        root.addView(label("商品名称"))
        nameEdit = EditText(this).apply { hint = "例如：带轮靠背溜溜凳"; setSingleLine(true) }
        root.addView(nameEdit)
        root.addView(label("讲品话术（每行一段，建议20～60段）"))
        scriptsEdit = EditText(this).apply {
            hint = "一行一段话术"
            minLines = 9
            gravity = Gravity.TOP
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        }
        root.addView(scriptsEdit, LinearLayout.LayoutParams(-1, dp(240)))

        randomCheck = CheckBox(this).apply { text = "随机顺序（关闭后按顺序循环）"; isChecked = true }
        root.addView(randomCheck)
        delayText = label("")
        delaySeek = SeekBar(this).apply { max = 30; progress = 3; setOnSeekBarChangeListener(seekListener()) }
        rateText = label("")
        rateSeek = SeekBar(this).apply { max = 150; progress = 50; setOnSeekBarChangeListener(seekListener()) }
        volumeText = label("")
        volumeSeek = SeekBar(this).apply { max = 100; progress = 100; setOnSeekBarChangeListener(seekListener()) }
        root.addView(delayText); root.addView(delaySeek)
        root.addView(rateText); root.addView(rateSeek)
        root.addView(volumeText); root.addView(volumeSeek)
        updateLabels()

        val controls = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        controls.addView(button("开始") { startLoop() }, weight())
        controls.addView(button("暂停") { action(SalesVoiceService.ACTION_PAUSE); status("已暂停") }, weight())
        controls.addView(button("继续") { action(SalesVoiceService.ACTION_RESUME); status("已继续") }, weight())
        root.addView(controls)
        root.addView(button("停止本场讲品") { action(SalesVoiceService.ACTION_STOP); status("已停止") })

        root.addView(label("临时插话"))
        interjectEdit = EditText(this).apply { hint = "输入一句话，立即插播"; minLines = 2 }
        root.addView(interjectEdit)
        root.addView(button("立即插播，播完自动恢复") { interject() })

        statusText = TextView(this).apply { text = "状态：待机"; setPadding(0, dp(14), 0, dp(8)) }
        root.addView(statusText)
        root.addView(TextView(this).apply {
            text = "先在本软件点开始，再切到视频号直播。声音来自手机系统TTS。首次必须实际进直播间测试，确认直播端能收进手机播出的声音。"
            textSize = 12f
        })
        return scroll
    }

    private fun startLoop() {
        val scripts = parseScripts()
        if (scripts.isEmpty()) return toast("先填写话术")
        if (nameEdit.text.toString().trim().isNotEmpty()) saveProduct(true)
        val i = Intent(this, SalesVoiceService::class.java).apply {
            action = SalesVoiceService.ACTION_START
            putStringArrayListExtra(SalesVoiceService.EXTRA_SCRIPTS, ArrayList(scripts))
            putExtra(SalesVoiceService.EXTRA_RANDOM, randomCheck.isChecked)
            putExtra(SalesVoiceService.EXTRA_DELAY_MS, delaySeek.progress * 1000L)
            putExtra(SalesVoiceService.EXTRA_RATE, 0.5f + rateSeek.progress / 100f)
            putExtra(SalesVoiceService.EXTRA_VOLUME, volumeSeek.progress / 100f)
        }
        startForegroundService(i)
        status("后台循环已启动，可切到视频号")
    }

    private fun interject() {
        val text = interjectEdit.text.toString().trim()
        if (text.isEmpty()) return toast("先输入插话内容")
        val i = Intent(this, SalesVoiceService::class.java).apply {
            action = SalesVoiceService.ACTION_INTERJECT
            putExtra(SalesVoiceService.EXTRA_INTERJECTION, text)
        }
        startForegroundService(i)
        interjectEdit.setText("")
        status("正在插播")
    }

    private fun action(value: String) = startForegroundService(Intent(this, SalesVoiceService::class.java).apply { action = value })

    private fun saveProduct(silent: Boolean) {
        val name = nameEdit.text.toString().trim()
        val scripts = parseScripts()
        if (name.isEmpty() || scripts.isEmpty()) { if (!silent) toast("商品名和话术不能为空"); return }
        val p = Product(name, scripts)
        if (currentIndex in products.indices) products[currentIndex] = p else { products += p; currentIndex = products.lastIndex }
        ProductStore.save(this, products)
        refreshProducts(currentIndex)
        if (!silent) status("商品已保存")
    }

    private fun deleteProduct() {
        if (currentIndex !in products.indices) return
        products.removeAt(currentIndex)
        if (products.isEmpty()) products += ProductStore.sample()
        ProductStore.save(this, products)
        refreshProducts(0)
        status("商品已删除")
    }

    private fun refreshProducts(index: Int) {
        refreshing = true
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, products.map { it.name })
        val safe = index.coerceIn(0, products.lastIndex)
        spinner.setSelection(safe, false)
        loadProduct(safe)
        refreshing = false
    }

    private fun loadProduct(index: Int) {
        currentIndex = index
        nameEdit.setText(products[index].name)
        scriptsEdit.setText(products[index].scripts.joinToString("\n"))
    }

    private fun parseScripts() = scriptsEdit.text.toString().lines().map { it.trim() }.filter { it.isNotEmpty() }
    private fun updateLabels() {
        if (::delayText.isInitialized) delayText.text = "每段结束间隔：${delaySeek.progress} 秒"
        if (::rateText.isInitialized) rateText.text = "语速：${50 + rateSeek.progress}%"
        if (::volumeText.isInitialized) volumeText.text = "音量：${volumeSeek.progress}%"
    }
    private fun seekListener() = object : SeekBar.OnSeekBarChangeListener {
        override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) = updateLabels()
        override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
        override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
    }
    private fun button(textValue: String, click: () -> Unit) = Button(this).apply { text = textValue; setOnClickListener { click() } }
    private fun label(textValue: String) = TextView(this).apply { text = textValue; setPadding(0, dp(10), 0, dp(3)) }
    private fun weight() = LinearLayout.LayoutParams(0, -2, 1f)
    private fun status(v: String) { if (::statusText.isInitialized) statusText.text = "状态：$v" }
    private fun toast(v: String) { Toast.makeText(this, v, Toast.LENGTH_SHORT).show() }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
