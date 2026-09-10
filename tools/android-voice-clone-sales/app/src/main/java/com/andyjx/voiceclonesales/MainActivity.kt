package com.andyjx.voiceclonesales

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.*
import org.json.JSONObject
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class MainActivity : Activity() {
    private var referenceUri: Uri? = null
    private lateinit var serverEdit: EditText
    private lateinit var voiceNameEdit: EditText
    private lateinit var promptTextEdit: EditText
    private lateinit var scriptsEdit: EditText
    private lateinit var consentCheck: CheckBox
    private lateinit var randomCheck: CheckBox
    private lateinit var delaySeek: SeekBar
    private lateinit var delayText: TextView
    private lateinit var interjectEdit: EditText
    private lateinit var statusText: TextView
    private lateinit var refStatus: TextView

    companion object { private const val PICK_AUDIO = 41 }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 42)
        setContentView(buildUi())
    }

    private fun buildUi(): View {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(30))
        }
        scroll.addView(root)

        root.addView(TextView(this).apply { text = "自动讲品 · 声音复刻版"; textSize = 24f })
        root.addView(TextView(this).apply {
            text = "参考声音注册 → 批量生成并缓存 → 直播时本地循环播放"
            setPadding(0, dp(4), 0, dp(12))
        })

        root.addView(label("电脑语音服务地址"))
        serverEdit = EditText(this).apply { setText("http://192.168.1.2:8787"); setSingleLine(true) }
        root.addView(serverEdit)
        root.addView(button("测试电脑语音服务") { testServer() })

        root.addView(label("音色名称"))
        voiceNameEdit = EditText(this).apply { hint = "例如：主播01"; setText("主播01"); setSingleLine(true) }
        root.addView(voiceNameEdit)

        root.addView(label("参考声音"))
        root.addView(button("选择参考音频（建议清晰、单人、无背景音乐）") { chooseAudio() })
        refStatus = TextView(this).apply { text = "尚未选择参考声音"; textSize = 12f }
        root.addView(refStatus)

        root.addView(label("参考音频里实际说的文字"))
        promptTextEdit = EditText(this).apply {
            hint = "必须尽量准确写出参考音频中说的内容"
            minLines = 3
            gravity = Gravity.TOP
        }
        root.addView(promptTextEdit)
        consentCheck = CheckBox(this).apply { text = "我确认对该声音拥有使用/复刻授权" }
        root.addView(consentCheck)
        root.addView(button("注册/更新这个音色") { registerVoice() })

        root.addView(label("讲品话术（每行一段）"))
        scriptsEdit = EditText(this).apply {
            minLines = 9
            gravity = Gravity.TOP
            setText("现在镜头里这款商品大家可以先看一下整体做工和细节。\n这款主要卖点我给大家分开讲，先看实物，再看使用场景。\n刚进来的朋友可以先停留一下，镜头里展示的就是当前这款实物。")
        }
        root.addView(scriptsEdit, LinearLayout.LayoutParams(-1, dp(240)))
        root.addView(button("一键生成并缓存全部话术") { generateAll() })

        randomCheck = CheckBox(this).apply { text = "随机播放（关闭后按顺序循环）"; isChecked = true }
        root.addView(randomCheck)
        delayText = label("")
        delaySeek = SeekBar(this).apply {
            max = 20; progress = 2
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) { updateDelay() }
                override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
            })
        }
        root.addView(delayText); root.addView(delaySeek); updateDelay()

        val controls = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        controls.addView(button("开始") { startLoop() }, weight())
        controls.addView(button("暂停") { serviceAction(CloneVoiceService.ACTION_PAUSE); status("已暂停") }, weight())
        controls.addView(button("继续") { serviceAction(CloneVoiceService.ACTION_RESUME); status("已继续") }, weight())
        root.addView(controls)
        root.addView(button("停止本场讲品") { serviceAction(CloneVoiceService.ACTION_STOP); status("已停止") })

        root.addView(label("临时插话（使用同一复刻音色实时生成）"))
        interjectEdit = EditText(this).apply { minLines = 2; hint = "例如：刚才问尺寸的朋友，我现在给你看一下。" }
        root.addView(interjectEdit)
        root.addView(button("生成并立即插播") { interject() })

        statusText = TextView(this).apply { text = "状态：待机"; setPadding(0, dp(14), 0, dp(6)) }
        root.addView(statusText)
        root.addView(TextView(this).apply {
            text = "说明：这版与普通自动讲品版包名不同，可同时安装。正式直播前先批量生成缓存，直播时不依赖持续联网。仅复刻你本人或已获得明确授权的声音。"
            textSize = 12f
        })
        return scroll
    }

    private fun chooseAudio() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "audio/*"
        }, PICK_AUDIO)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == PICK_AUDIO && resultCode == RESULT_OK) {
            val uri = data?.data ?: return
            referenceUri = uri
            try { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: Exception) {}
            refStatus.text = "已选择：${uri.lastPathSegment ?: "参考音频"}"
        }
    }

    private fun testServer() = background("正在连接电脑语音服务…") {
        val conn = open("/health", "GET")
        val code = conn.responseCode
        val body = readText(if (code in 200..299) conn.inputStream else conn.errorStream)
        if (code !in 200..299) error("服务返回 $code：$body")
        ui { status("服务正常：$body") }
    }

    private fun registerVoice() {
        val uri = referenceUri ?: return toast("先选择参考声音")
        val name = voiceNameEdit.text.toString().trim()
        val prompt = promptTextEdit.text.toString().trim()
        if (name.isEmpty()) return toast("填写音色名称")
        if (prompt.isEmpty()) return toast("填写参考音频里的实际文字")
        if (!consentCheck.isChecked) return toast("需要确认你拥有该声音的使用授权")

        background("正在上传并注册音色…") {
            val boundary = "----VoiceClone${System.currentTimeMillis()}"
            val conn = open("/api/voices/register", "POST").apply {
                setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                doOutput = true
            }
            DataOutputStream(conn.outputStream).use { out ->
                writeField(out, boundary, "voice_name", name)
                writeField(out, boundary, "prompt_text", prompt)
                writeField(out, boundary, "consent", "true")
                out.writeBytes("--$boundary\r\n")
                out.writeBytes("Content-Disposition: form-data; name=\"audio\"; filename=\"reference_audio\"\r\n")
                out.writeBytes("Content-Type: audio/*\r\n\r\n")
                contentResolver.openInputStream(uri)!!.use { input -> input.copyTo(out) }
                out.writeBytes("\r\n--$boundary--\r\n")
            }
            val code = conn.responseCode
            val body = readText(if (code in 200..299) conn.inputStream else conn.errorStream)
            if (code !in 200..299) error("注册失败 $code：$body")
            ui { status("音色“$name”注册成功") }
        }
    }

    private fun generateAll() {
        val scripts = scripts()
        val voice = voiceNameEdit.text.toString().trim()
        if (voice.isEmpty() || scripts.isEmpty()) return toast("先填写音色名称和话术")
        background("准备生成 ${scripts.size} 段话术…") {
            scripts.forEachIndexed { index, text ->
                val file = cacheFile(voice, text)
                if (!file.exists() || file.length() < 512) synthesizeToFile(voice, text, file)
                ui { status("已缓存 ${index + 1}/${scripts.size} 段") }
            }
            ui { status("全部话术已缓存，可以开始直播") }
        }
    }

    private fun startLoop() {
        val scripts = scripts()
        val voice = voiceNameEdit.text.toString().trim()
        val files = scripts.map { cacheFile(voice, it) }
        if (files.isEmpty()) return toast("先填写话术")
        val missing = files.count { !it.exists() || it.length() < 512 }
        if (missing > 0) return toast("还有 $missing 段未生成，先点“一键生成并缓存”")
        val i = Intent(this, CloneVoiceService::class.java).apply {
            action = CloneVoiceService.ACTION_START
            putStringArrayListExtra(CloneVoiceService.EXTRA_FILES, ArrayList(files.map { it.absolutePath }))
            putExtra(CloneVoiceService.EXTRA_RANDOM, randomCheck.isChecked)
            putExtra(CloneVoiceService.EXTRA_DELAY_MS, delaySeek.progress * 1000L)
        }
        startForegroundService(i)
        status("复刻音色后台循环已启动，可切到视频号")
    }

    private fun interject() {
        val text = interjectEdit.text.toString().trim()
        val voice = voiceNameEdit.text.toString().trim()
        if (text.isEmpty() || voice.isEmpty()) return toast("填写音色名称和插话内容")
        background("正在生成临时插话…") {
            val dir = File(cacheDir, "interject").apply { mkdirs() }
            val file = File(dir, "${System.currentTimeMillis()}.wav")
            synthesizeToFile(voice, text, file)
            val i = Intent(this, CloneVoiceService::class.java).apply {
                action = CloneVoiceService.ACTION_INTERJECT_FILE
                putExtra(CloneVoiceService.EXTRA_INTERJECT_PATH, file.absolutePath)
            }
            startForegroundService(i)
            ui { interjectEdit.setText(""); status("正在用复刻音色插播") }
        }
    }

    private fun synthesizeToFile(voice: String, text: String, file: File) {
        file.parentFile?.mkdirs()
        val conn = open("/api/tts", "POST").apply {
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            doOutput = true
        }
        val body = JSONObject().put("voice_name", voice).put("text", text).toString().toByteArray(Charsets.UTF_8)
        conn.outputStream.use { it.write(body) }
        val code = conn.responseCode
        if (code !in 200..299) error("生成失败 $code：${readText(conn.errorStream)}")
        FileOutputStream(file).use { out -> conn.inputStream.use { it.copyTo(out) } }
        if (file.length() < 512) error("生成的音频文件异常")
    }

    private fun open(path: String, method: String): HttpURLConnection {
        val base = serverEdit.text.toString().trim().trimEnd('/')
        if (!base.startsWith("http://") && !base.startsWith("https://")) error("服务地址必须以 http:// 或 https:// 开头")
        return (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 10000
            readTimeout = 180000
            useCaches = false
        }
    }

    private fun cacheFile(voice: String, text: String): File {
        val dir = File(filesDir, "voice_cache/${safeName(voice)}").apply { mkdirs() }
        return File(dir, sha256(text) + ".wav")
    }

    private fun sha256(text: String): String = MessageDigest.getInstance("SHA-256")
        .digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    private fun safeName(v: String) = v.replace(Regex("[^0-9A-Za-z\\u4e00-\\u9fa5_-]"), "_")
    private fun scripts() = scriptsEdit.text.toString().lines().map { it.trim() }.filter { it.isNotEmpty() }

    private fun writeField(out: DataOutputStream, boundary: String, name: String, value: String) {
        out.writeBytes("--$boundary\r\n")
        out.writeBytes("Content-Disposition: form-data; name=\"$name\"\r\n\r\n")
        out.write(value.toByteArray(Charsets.UTF_8))
        out.writeBytes("\r\n")
    }

    private fun readText(stream: InputStream?): String = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""

    private fun background(start: String, work: () -> Unit) {
        status(start)
        Thread {
            try { work() }
            catch (e: Exception) { ui { status("失败：${e.message ?: e.javaClass.simpleName}") } }
        }.start()
    }

    private fun serviceAction(actionValue: String) = startForegroundService(Intent(this, CloneVoiceService::class.java).apply { action = actionValue })
    private fun updateDelay() { if (::delayText.isInitialized) delayText.text = "段落间隔：${delaySeek.progress} 秒" }
    private fun ui(block: () -> Unit) = runOnUiThread(block)
    private fun status(v: String) { if (::statusText.isInitialized) statusText.text = "状态：$v" }
    private fun toast(v: String) = Toast.makeText(this, v, Toast.LENGTH_SHORT).show()
    private fun label(v: String) = TextView(this).apply { text = v; setPadding(0, dp(10), 0, dp(3)) }
    private fun button(v: String, click: () -> Unit) = Button(this).apply { text = v; setOnClickListener { click() } }
    private fun weight() = LinearLayout.LayoutParams(0, -2, 1f)
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
