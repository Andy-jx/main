package com.andyjx.autosalesvoice

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import android.widget.*

class MainActivity : Activity() {
    companion object {
        private const val REQUEST_AUDIO_PACK = 302
    }

    private val profiles by lazy { ProductStore.load(this) }
    private var currentIndex = 0
    private var refreshing = false
    private var currentAudioUris = mutableListOf<String>()

    private lateinit var spinner: Spinner
    private lateinit var nameEdit: EditText
    private lateinit var audioStatusText: TextView
    private lateinit var audioListText: TextView
    private lateinit var sequentialRadio: RadioButton
    private lateinit var shuffleRadio: RadioButton
    private lateinit var gapMinSeek: SeekBar
    private lateinit var gapMaxSeek: SeekBar
    private lateinit var gapMinText: TextView
    private lateinit var gapMaxText: TextView
    private lateinit var volumeSeek: SeekBar
    private lateinit var volumeText: TextView
    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 10)
        }
        setContentView(buildUi())
        refreshProfiles(0)
    }

    private fun buildUi(): View {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(30))
        }
        scroll.addView(root)

        root.addView(TextView(this).apply {
            text = "自动讲品 · 真人音频版"
            textSize = 24f
        })
        root.addView(TextView(this).apply {
            text = "只播放你导入的复刻音频｜不调用系统TTS｜适合顺序/乱序循环"
            setPadding(0, dp(4), 0, dp(12))
        })

        root.addView(label("直播方案"))
        spinner = Spinner(this)
        root.addView(spinner)
        spinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (!refreshing && position in profiles.indices) loadProfile(position)
            }
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }

        val profileRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        profileRow.addView(button("新建") {
            currentIndex = -1
            currentAudioUris.clear()
            nameEdit.setText("")
            updateAudioStatus()
            status("正在新建直播方案")
        }, weight())
        profileRow.addView(button("保存") { saveProfile(false) }, weight())
        profileRow.addView(button("删除") { deleteProfile() }, weight())
        root.addView(profileRow)

        root.addView(label("方案名称"))
        nameEdit = EditText(this).apply {
            hint = "例如：溜溜凳直播"
            setSingleLine(true)
        }
        root.addView(nameEdit)

        root.addView(label("复刻音频"))
        audioStatusText = TextView(this).apply { textSize = 14f }
        root.addView(audioStatusText)
        audioListText = TextView(this).apply {
            textSize = 12f
            setPadding(0, dp(4), 0, dp(8))
        }
        root.addView(audioListText)

        val audioRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        audioRow.addView(button("一次导入多条 MP3/WAV") { chooseAudioPack() }, weight())
        audioRow.addView(button("清空") {
            currentAudioUris.clear()
            updateAudioStatus()
            status("已清空当前音频")
        }, weight())
        root.addView(audioRow)
        root.addView(TextView(this).apply {
            text = "建议把电脑生成的音频命名为 01、02、03……再一次全选导入。顺序循环按文件名播放；整轮乱序会每轮全部播完后再重新洗牌。"
            textSize = 12f
        })

        root.addView(label("播放方式"))
        val modeGroup = RadioGroup(this).apply { orientation = RadioGroup.HORIZONTAL }
        sequentialRadio = RadioButton(this).apply { text = "顺序循环" }
        shuffleRadio = RadioButton(this).apply { text = "整轮乱序"; isChecked = true }
        modeGroup.addView(sequentialRadio, weight())
        modeGroup.addView(shuffleRadio, weight())
        root.addView(modeGroup)

        gapMinText = label("")
        gapMinSeek = SeekBar(this).apply {
            max = 10
            progress = 1
            setOnSeekBarChangeListener(seekListener())
        }
        gapMaxText = label("")
        gapMaxSeek = SeekBar(this).apply {
            max = 15
            progress = 4
            setOnSeekBarChangeListener(seekListener())
        }
        volumeText = label("")
        volumeSeek = SeekBar(this).apply {
            max = 100
            progress = 100
            setOnSeekBarChangeListener(seekListener())
        }
        root.addView(gapMinText); root.addView(gapMinSeek)
        root.addView(gapMaxText); root.addView(gapMaxSeek)
        root.addView(volumeText); root.addView(volumeSeek)
        updateLabels()

        val controls1 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        controls1.addView(button("开始") { startLoop() }, weight())
        controls1.addView(button("暂停") { action(SalesVoiceService.ACTION_PAUSE); status("已暂停") }, weight())
        controls1.addView(button("继续") { action(SalesVoiceService.ACTION_RESUME); status("已继续") }, weight())
        root.addView(controls1)

        val controls2 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        controls2.addView(button("下一条") { action(SalesVoiceService.ACTION_NEXT); status("已切到下一条") }, weight())
        controls2.addView(button("停止本场") { action(SalesVoiceService.ACTION_STOP); status("已停止") }, weight())
        root.addView(controls2)

        statusText = TextView(this).apply {
            text = "状态：待机"
            setPadding(0, dp(14), 0, dp(8))
        }
        root.addView(statusText)
        root.addView(TextView(this).apply {
            text = "直播建议：每条音频约 15～45 秒，准备 10～30 条不同表达。默认 1～4 秒随机停顿会比固定间隔更自然。首次使用仍需用另一台设备进入直播间确认视频号能收到手机播放的声音。"
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
        data.data?.let { uri -> if (selected.none { it == uri }) selected += uri }
        if (selected.isEmpty()) return

        selected.forEach { uri ->
            try {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: Exception) {
            }
        }

        currentAudioUris = selected
            .distinctBy { it.toString() }
            .sortedBy { displayName(it).lowercase() }
            .map { it.toString() }
            .toMutableList()
        updateAudioStatus()
        status("已导入 ${currentAudioUris.size} 条真人音频")
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
        if (!::audioStatusText.isInitialized || !::audioListText.isInitialized) return
        audioStatusText.text = if (currentAudioUris.isEmpty()) {
            "未导入音频：不能开始播放。"
        } else {
            "已导入 ${currentAudioUris.size} 条复刻音频，只会播放这些文件。"
        }

        if (currentAudioUris.isEmpty()) {
            audioListText.text = ""
            return
        }
        val names = currentAudioUris.map { displayName(Uri.parse(it)) }
        val visible = names.take(12).mapIndexed { i, name -> "%02d. %s".format(i + 1, name) }
        audioListText.text = buildString {
            append(visible.joinToString("\n"))
            if (names.size > visible.size) append("\n……还有 ${names.size - visible.size} 条")
        }
    }

    private fun startLoop() {
        if (currentAudioUris.isEmpty()) return toast("先导入你复刻生成的 MP3/WAV")
        saveProfile(true)
        val minSec = gapMinSeek.progress
        val maxSec = gapMaxSeek.progress.coerceAtLeast(minSec)
        val intent = Intent(this, SalesVoiceService::class.java).apply {
            action = SalesVoiceService.ACTION_START
            putStringArrayListExtra(SalesVoiceService.EXTRA_AUDIO_URIS, ArrayList(currentAudioUris))
            putExtra(SalesVoiceService.EXTRA_SHUFFLE, shuffleRadio.isChecked)
            putExtra(SalesVoiceService.EXTRA_GAP_MIN_MS, minSec * 1000L)
            putExtra(SalesVoiceService.EXTRA_GAP_MAX_MS, maxSec * 1000L)
            putExtra(SalesVoiceService.EXTRA_VOLUME, volumeSeek.progress / 100f)
        }
        startForegroundService(intent)
        status(if (shuffleRadio.isChecked) "整轮乱序循环已启动，可切到直播" else "顺序循环已启动，可切到直播")
    }

    private fun action(value: String) {
        startForegroundService(Intent(this, SalesVoiceService::class.java).apply { action = value })
    }

    private fun saveProfile(silent: Boolean) {
        val name = nameEdit.text.toString().trim().ifEmpty { "直播方案" }
        val profile = PlaylistProfile(name, currentAudioUris.toList())
        if (currentIndex in profiles.indices) {
            profiles[currentIndex] = profile
        } else {
            profiles += profile
            currentIndex = profiles.lastIndex
        }
        ProductStore.save(this, profiles)
        refreshProfiles(currentIndex)
        if (!silent) status("直播方案已保存")
    }

    private fun deleteProfile() {
        if (currentIndex !in profiles.indices) return
        profiles.removeAt(currentIndex)
        if (profiles.isEmpty()) profiles += ProductStore.sample()
        ProductStore.save(this, profiles)
        refreshProfiles(0)
        status("直播方案已删除")
    }

    private fun refreshProfiles(index: Int) {
        refreshing = true
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, profiles.map { it.name })
        val safe = index.coerceIn(0, profiles.lastIndex)
        spinner.setSelection(safe, false)
        loadProfile(safe)
        refreshing = false
    }

    private fun loadProfile(index: Int) {
        currentIndex = index
        nameEdit.setText(profiles[index].name)
        currentAudioUris = profiles[index].audioUris.toMutableList()
        updateAudioStatus()
    }

    private fun updateLabels() {
        if (::gapMinText.isInitialized) gapMinText.text = "随机停顿最短：${gapMinSeek.progress} 秒"
        if (::gapMaxText.isInitialized) gapMaxText.text = "随机停顿最长：${gapMaxSeek.progress} 秒"
        if (::volumeText.isInitialized) volumeText.text = "播放音量：${volumeSeek.progress}%"
    }

    private fun seekListener() = object : SeekBar.OnSeekBarChangeListener {
        override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) = updateLabels()
        override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
        override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
    }

    private fun button(textValue: String, click: () -> Unit) = Button(this).apply {
        text = textValue
        setOnClickListener { click() }
    }
    private fun label(textValue: String) = TextView(this).apply {
        text = textValue
        setPadding(0, dp(10), 0, dp(3))
    }
    private fun weight() = LinearLayout.LayoutParams(0, -2, 1f)
    private fun status(value: String) {
        if (::statusText.isInitialized) statusText.text = "状态：$value"
    }
    private fun toast(value: String) = Toast.makeText(this, value, Toast.LENGTH_SHORT).show()
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
