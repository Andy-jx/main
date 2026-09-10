package com.andyjx.voiceclonesales

import android.app.*
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import kotlin.random.Random

class CloneVoiceService : Service() {
    companion object {
        const val ACTION_START = "start"
        const val ACTION_PAUSE = "pause"
        const val ACTION_RESUME = "resume"
        const val ACTION_STOP = "stop"
        const val ACTION_INTERJECT_FILE = "interject_file"
        const val EXTRA_FILES = "files"
        const val EXTRA_RANDOM = "random"
        const val EXTRA_DELAY_MS = "delay_ms"
        const val EXTRA_INTERJECT_PATH = "interject_path"
        private const val CHANNEL_ID = "clone_sales_voice"
        private const val NOTIFICATION_ID = 2001
    }

    private val handler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var files = listOf<String>()
    private var randomMode = true
    private var delayMs = 2500L
    private var running = false
    private var nextIndex = 0
    private var lastRandom = -1
    private var resumeAfterInterject = false

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ID, "声音复刻讲品", NotificationManager.IMPORTANCE_LOW))
        startForeground(NOTIFICATION_ID, notification("待机"))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                files = intent.getStringArrayListExtra(EXTRA_FILES)?.filter { it.isNotBlank() } ?: emptyList()
                randomMode = intent.getBooleanExtra(EXTRA_RANDOM, true)
                delayMs = intent.getLongExtra(EXTRA_DELAY_MS, 2500L)
                nextIndex = 0
                lastRandom = -1
                running = files.isNotEmpty()
                handler.removeCallbacksAndMessages(null)
                stopPlayer()
                if (running) playNext()
                update("复刻音色循环讲品中")
            }
            ACTION_PAUSE -> {
                running = false
                handler.removeCallbacksAndMessages(null)
                stopPlayer()
                update("已暂停")
            }
            ACTION_RESUME -> {
                if (files.isNotEmpty()) {
                    running = true
                    playNext()
                    update("复刻音色循环讲品中")
                }
            }
            ACTION_INTERJECT_FILE -> {
                val path = intent.getStringExtra(EXTRA_INTERJECT_PATH).orEmpty()
                if (path.isNotBlank()) {
                    resumeAfterInterject = running
                    running = false
                    handler.removeCallbacksAndMessages(null)
                    stopPlayer()
                    playFile(path, true)
                    update("正在复刻音色插话")
                }
            }
            ACTION_STOP -> {
                running = false
                handler.removeCallbacksAndMessages(null)
                stopPlayer()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_STICKY
    }

    private fun playNext() {
        if (!running || files.isEmpty()) return
        val index = if (randomMode) {
            if (files.size == 1) 0 else {
                var v: Int
                do v = Random.nextInt(files.size) while (v == lastRandom)
                lastRandom = v
                v
            }
        } else {
            val v = nextIndex % files.size
            nextIndex = (nextIndex + 1) % files.size
            v
        }
        playFile(files[index], false)
    }

    private fun playFile(path: String, isInterject: Boolean) {
        stopPlayer()
        try {
            val mp = MediaPlayer()
            player = mp
            mp.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            mp.setDataSource(path)
            mp.setOnPreparedListener { if (player === it) it.start() }
            mp.setOnCompletionListener {
                if (player === it) stopPlayer()
                if (isInterject) {
                    if (resumeAfterInterject) {
                        resumeAfterInterject = false
                        running = true
                        handler.postDelayed({ if (running) playNext() }, 600L)
                        update("复刻音色循环讲品中")
                    }
                } else if (running) {
                    handler.postDelayed({ if (running) playNext() }, delayMs)
                }
            }
            mp.setOnErrorListener { _, _, _ ->
                stopPlayer()
                if (isInterject && resumeAfterInterject) {
                    resumeAfterInterject = false
                    running = true
                }
                if (running) handler.postDelayed({ playNext() }, 600L)
                true
            }
            mp.prepareAsync()
        } catch (_: Exception) {
            stopPlayer()
            if (running) handler.postDelayed({ playNext() }, 600L)
        }
    }

    private fun stopPlayer() {
        val old = player
        player = null
        if (old != null) {
            try { old.stop() } catch (_: Exception) {}
            try { old.release() } catch (_: Exception) {}
        }
    }

    private fun notification(text: String) = Notification.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_btn_speak_now)
        .setContentTitle("自动讲品·声音复刻")
        .setContentText(text)
        .setOngoing(true)
        .build()

    private fun update(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        stopPlayer()
        super.onDestroy()
    }
}
