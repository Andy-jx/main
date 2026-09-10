package com.andyjx.autosalesvoice

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.*

class MainActivity : Activity() {
    companion object {
        private const val REQUEST_AUDIO_PACK = 202
    }

    private val products by lazy { ProductStore.load(this) }
    private var currentIndex = 0
    private var refreshing = false
    private var currentAudioUris = mutableListOf<String>()
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
    private lateinit var audioStatusText: TextView
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
            text = "自然音色包优先｜系统TTS仅作回退｜切到直播App后后台继续讲"
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
        row.addView(button("新建") {
            currentIndex = -1
            currentAudioUris.clear()
            nameEdit.setText("")
            scriptsEdit.setText("")
            updateAudioStatus()
            status("正在新建商品")
        }, weight())
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

        root.addView(label("自然音色包"))
        audioStatusText = TextView(this).apply {
            textSize = 14f
            setPadding(0, 0, 0, dp(6))
        }
        root.addView(audioStatusText)
        val audioRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        audioRow.addView(button("导入 MP3/WAV 音色包") { chooseAudioPack() }, weight())
        audioRow.addView(button("清除音色包") {
            currentAudioUris.clear()
            updateAudioStatus()
            status("已清除当前商品音色包")
        }, weight())
        root.addView(audioRow)
        root.addView(TextView(this).apply {
            text = "文件按名称排序后与话术逐行对应，建议命名：01.mp3、02.mp3、03.mp3……。音频数量与话术数量一致时，可全程使用自然音色。"
            textSize = 12f
        })

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
        interjectEdit = EditText(this).apply { hint = "输入一句话，立即插播（临时文字仍使用系统TTS）"; minLines = 2 }
        root.addView(interjectEdit)
        root.addView(button("立即插播，播完自动恢复") { interject() })

        statusText = TextView(this).apply { text = "状态：待机"; setPadding(0, dp(14), 0, dp(8)) }
        root.addView(statusText)
        root.addView(TextView(this).apply {
            text = "正式直播建议使用自然音色包。先在本软件点开始，再切到视频号直播；首次必须用另一台设备进直播间确认直播端能收进手机播放的声音。"
            textSize = 12f
        })
        return scroll
    }

    private fun chooseAudioPack() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "audio/*"
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        startActivityForResult(intent, REQUEST_AUDIO_PACK)
    }

    @Deprecated("Deprecated in Android API, retained for broad device compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_AUDIO_PACK || resultCode != RESULT_OK || data == null) return

        val selected = mutableListOf<Uri>()
        data.clipData?.let { clip ->
            for (i in 0 until clip.itemCount) selected += clip.getItemAt(i).uri
        }
        data.data?.let { if (selected.none { existing -> existing == it }) selected += it }
        if (selected.isEmpty()) return

        selected.forEach { uri ->
            try {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: Exception) {
            }
        }

        currentAudioUris = selected
            .sortedBy { displayName(it).lowercase() }
            .map { it.toString() }
            .toMutableList()
        updateAudioStatus()
        status("已导入 ${currentAudioUris.size} 个自然音频")
    }

    private fun displayName(uri: Uri): String {
        return try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) ?: uri.lastPathSegment.orEmpty()
                else uri.lastPathSegment.orEmpty()
            } ?: uri.lastPathSegment.orEmpty()
        } catch (_: Exception) {
            uri.lastPathSegment.orEmpty()
        }
    }

    private fun updateAudioStatus() {
        if (!::audioStatusText.isInitialized) return
        val scriptCount = if (::scriptsEdit.isInitialized) parseScripts().size else 0
        audioStatusText.text = when {
            currentAudioUris.isEmpty() -> "未导入：当前会使用系统TTS，正式直播不建议。"
            scriptCount == 0 -> "已导入 ${currentAudioUris.size} 个音频，填写话术后再核对数量。"
            currentAudioUris.size == scriptCount -> "已导入 ${currentAudioUris.size}/${scriptCount}：自然音色完整匹配。"
            else -> "已导入 ${currentAudioUris.size}/${scriptCount}：数量不一致，缺少的段落会回退系统TTS。"
        }
    }

    private fun startLoop() {
        val scripts = parseScripts()
        if (scripts.isEmpty()) return toast("先填写话术")
        if (nameEdit.text.toString().trim().isNotEmpty()) saveProduct(true)
        val i = Intent(this, SalesVoiceService::class.java).apply {
            action = SalesVoiceService.ACTION_START
            putStringArrayListExtra(SalesVoiceService.EXTRA_SCRIPTS, ArrayList(scripts))
            putStringArrayListExtra(SalesVoiceService.EXTRA_AUDIO_URIS, ArrayList(currentAudioUris))
            putExtra(SalesVoiceService.EXTRA_RANDOM, randomCheck.isChecked)
            putExtra(SalesVoiceService.EXTRA_DELAY_MS, delaySeek.progress * 1000L)
            putExtra(SalesVoiceService.EXTRA_RATE, 0.5f + rateSeek.progress / 100f)
            putExtra(SalesVoiceService.EXTRA_VOLUME, volumeSeek.progress / 100f)
        }
        startForegroundService(i)
        status(if (currentAudioUris.isNotEmpty()) "自然音色后台循环已启动，可切到视频号" else "系统TTS后台循环已启动")
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
        status("正在临时插播")
    }

    private fun action(value: String) = startForegroundService(Intent(this, SalesVoiceService::class.java).apply { action = value })

    private fun saveProduct(silent: Boolean) {
        val name = nameEdit.text.toString().trim()
        val scripts = parseScripts()
        if (name.isEmpty() || scripts.isEmpty()) { if (!silent) toast("商品名和话术不能为空"); return }
        val p = Product(name, scripts, currentAudioUris.toList())
        if (currentIndex in products.indices) products[currentIndex] = p else { products += p; currentIndex = products.lastIndex }
        ProductStore.save(this, products)
        refreshProducts(currentIndex)
        if (!silent) status("商品和音色包已保存")
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
        currentAudioUris = products[index].audioUris.toMutableList()
        updateAudioStatus()
    }

    private fun parseScripts() = scriptsEdit.text.toString().lines().map { it.trim() }.filter { it.isNotEmpty() }
    private fun updateLabels() {
        if (::delayText.isInitialized) delayText.text = "每段结束间隔：${delaySeek.progress} 秒"
        if (::rateText.isInitialized) rateText.text = "语速：${50 + rateSeek.progress}%（仅系统TTS回退）"
        if (::volumeText.isInitialized) volumeText.text = "音量：${volumeSeek.progress}%"
        updateAudioStatus()
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
