package com.andyjx.autosalesvoice

import android.app.*
import android.content.Intent
import android.media.AudioAttributes
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import kotlin.random.Random

class SalesVoiceService : Service(), TextToSpeech.OnInitListener {
    companion object {
        const val ACTION_START = "start"
        const val ACTION_PAUSE = "pause"
        const val ACTION_RESUME = "resume"
        const val ACTION_STOP = "stop"
        const val ACTION_INTERJECT = "interject"
        const val EXTRA_SCRIPTS = "scripts"
        const val EXTRA_RANDOM = "random"
        const val EXTRA_DELAY_MS = "delay_ms"
        const val EXTRA_RATE = "rate"
        const val EXTRA_VOLUME = "volume"
        const val EXTRA_INTERJECTION = "interjection"
        private const val CHANNEL_ID = "sales_voice"
        private const val NOTIFICATION_ID = 1001
    }

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var tts: TextToSpeech
    private var ready = false
    private var running = false
    private var paused = false
    private var resumeAfterInterjection = false
    private var scripts = listOf<String>()
    private var randomMode = true
    private var delayMs = 3000L
    private var rate = 1.0f
    private var volume = 1.0f
    private var nextIndex = 0
    private var lastRandomIndex = -1

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("自动讲品待机中"))
        tts = TextToSpeech(this, this)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                scripts = intent.getStringArrayListExtra(EXTRA_SCRIPTS)?.filter { it.isNotBlank() } ?: emptyList()
                randomMode = intent.getBooleanExtra(EXTRA_RANDOM, true)
                delayMs = intent.getLongExtra(EXTRA_DELAY_MS, 3000L)
                rate = intent.getFloatExtra(EXTRA_RATE, 1.0f)
                volume = intent.getFloatExtra(EXTRA_VOLUME, 1.0f)
                running = scripts.isNotEmpty()
                paused = false
                handler.removeCallbacksAndMessages(null)
                if (ready && running) speakNext()
                updateNotification("后台循环讲品中")
            }
            ACTION_PAUSE -> {
                running = false
                paused = true
                handler.removeCallbacksAndMessages(null)
                if (ready) tts.stop()
                updateNotification("已暂停")
            }
            ACTION_RESUME -> {
                if (scripts.isNotEmpty()) {
                    running = true
                    paused = false
                    if (ready) speakNext()
                    updateNotification("后台循环讲品中")
                }
            }
            ACTION_INTERJECT -> {
                val text = intent.getStringExtra(EXTRA_INTERJECTION)?.trim().orEmpty()
                if (text.isNotEmpty() && ready) {
                    resumeAfterInterjection = running
                    running = false
                    handler.removeCallbacksAndMessages(null)
                    tts.stop()
                    speak(text, "manual")
                    updateNotification("正在临时插话")
                }
            }
            ACTION_STOP -> {
                running = false
                paused = false
                handler.removeCallbacksAndMessages(null)
                if (ready) tts.stop()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_STICKY
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        ready = true
        tts.language = Locale.SIMPLIFIED_CHINESE
        tts.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
        )
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onError(utteranceId: String?) = onDone(utteranceId)
            override fun onDone(utteranceId: String?) {
                handler.post {
                    when {
                        utteranceId == "manual" && resumeAfterInterjection -> {
                            resumeAfterInterjection = false
                            running = true
                            handler.postDelayed({ if (running) speakNext() }, 700L)
                            updateNotification("后台循环讲品中")
                        }
                        utteranceId?.startsWith("loop_") == true && running ->
                            handler.postDelayed({ if (running) speakNext() }, delayMs)
                    }
                }
            }
        })
        if (running) speakNext()
    }

    private fun speakNext() {
        if (!ready || !running || scripts.isEmpty()) return
        val index = if (randomMode) randomIndex() else {
            val i = nextIndex % scripts.size
            nextIndex = (nextIndex + 1) % scripts.size
            i
        }
        speak(scripts[index], "loop_${System.currentTimeMillis()}")
    }

    private fun randomIndex(): Int {
        if (scripts.size <= 1) return 0
        var candidate: Int
        do candidate = Random.nextInt(scripts.size) while (candidate == lastRandomIndex)
        lastRandomIndex = candidate
        return candidate
    }

    private fun speak(text: String, id: String) {
        tts.setSpeechRate(rate.coerceIn(0.5f, 2.0f))
        val params = Bundle().apply {
            putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, volume.coerceIn(0f, 1f))
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, id)
    }

    private fun createNotificationChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "自动讲品后台服务", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun buildNotification(text: String): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("自动讲品")
            .setContentText(text)
            .setOngoing(true)
            .build()

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(text))
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        super.onDestroy()
    }
}
