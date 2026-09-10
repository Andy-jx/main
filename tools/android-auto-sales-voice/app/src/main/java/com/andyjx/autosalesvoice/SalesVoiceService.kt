package com.andyjx.autosalesvoice

import android.app.*
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
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
        const val EXTRA_AUDIO_URIS = "audio_uris"
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
    private var player: MediaPlayer? = null
    private var ttsReady = false
    private var running = false
    private var paused = false
    private var resumeAfterInterjection = false
    private var scripts = listOf<String>()
    private var audioUris = listOf<String>()
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
                audioUris = intent.getStringArrayListExtra(EXTRA_AUDIO_URIS)?.toList() ?: emptyList()
                randomMode = intent.getBooleanExtra(EXTRA_RANDOM, true)
                delayMs = intent.getLongExtra(EXTRA_DELAY_MS, 3000L)
                rate = intent.getFloatExtra(EXTRA_RATE, 1.0f)
                volume = intent.getFloatExtra(EXTRA_VOLUME, 1.0f)
                running = scripts.isNotEmpty()
                paused = false
                nextIndex = 0
                lastRandomIndex = -1
                handler.removeCallbacksAndMessages(null)
                stopCurrentPlayback()
                if (running) speakNext()
                updateNotification(if (audioUris.isNotEmpty()) "自然音色后台循环讲品中" else "系统TTS后台循环讲品中")
            }
            ACTION_PAUSE -> {
                running = false
                paused = true
                handler.removeCallbacksAndMessages(null)
                stopCurrentPlayback()
                updateNotification("已暂停")
            }
            ACTION_RESUME -> {
                if (scripts.isNotEmpty()) {
                    running = true
                    paused = false
                    speakNext()
                    updateNotification(if (audioUris.isNotEmpty()) "自然音色后台循环讲品中" else "系统TTS后台循环讲品中")
                }
            }
            ACTION_INTERJECT -> {
                val text = intent.getStringExtra(EXTRA_INTERJECTION)?.trim().orEmpty()
                if (text.isNotEmpty()) {
                    resumeAfterInterjection = running
                    running = false
                    handler.removeCallbacksAndMessages(null)
                    stopCurrentPlayback()
                    if (ttsReady) {
                        speakTts(text, "manual")
                        updateNotification("正在临时插话")
                    } else {
                        if (resumeAfterInterjection) {
                            running = true
                            handler.postDelayed({ if (running) speakNext() }, 700L)
                        }
                        updateNotification("系统TTS未就绪，临时插话已跳过")
                    }
                }
            }
            ACTION_STOP -> {
                running = false
                paused = false
                handler.removeCallbacksAndMessages(null)
                stopCurrentPlayback()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_STICKY
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        ttsReady = true
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
                            updateNotification(if (audioUris.isNotEmpty()) "自然音色后台循环讲品中" else "系统TTS后台循环讲品中")
                        }
                        utteranceId?.startsWith("loop_") == true && running -> scheduleNext()
                    }
                }
            }
        })
    }

    private fun speakNext() {
        if (!running || scripts.isEmpty()) return
        val index = if (randomMode) randomIndex() else {
            val i = nextIndex % scripts.size
            nextIndex = (nextIndex + 1) % scripts.size
            i
        }

        val uriText = audioUris.getOrNull(index).orEmpty()
        if (uriText.isNotBlank()) {
            playNaturalAudio(index, uriText)
        } else if (ttsReady) {
            speakTts(scripts[index], "loop_${System.currentTimeMillis()}")
        } else {
            handler.postDelayed({ if (running) speakFallbackWhenReady(index) }, 500L)
        }
    }

    private fun speakFallbackWhenReady(index: Int) {
        if (!running || index !in scripts.indices) return
        if (ttsReady) speakTts(scripts[index], "loop_${System.currentTimeMillis()}")
        else handler.postDelayed({ if (running) speakFallbackWhenReady(index) }, 500L)
    }

    private fun playNaturalAudio(index: Int, uriText: String) {
        releasePlayer()
        val mp = MediaPlayer()
        player = mp
        try {
            mp.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            mp.setDataSource(this, Uri.parse(uriText))
            mp.setVolume(volume.coerceIn(0f, 1f), volume.coerceIn(0f, 1f))
            mp.setOnPreparedListener { prepared ->
                if (running && player === prepared) prepared.start() else releasePlayer()
            }
            mp.setOnCompletionListener { completed ->
                if (player === completed) releasePlayer()
                if (running) scheduleNext()
            }
            mp.setOnErrorListener { failed, _, _ ->
                if (player === failed) releasePlayer()
                if (running) {
                    if (ttsReady && index in scripts.indices) {
                        speakTts(scripts[index], "loop_${System.currentTimeMillis()}")
                    } else {
                        scheduleNext()
                    }
                }
                true
            }
            mp.prepareAsync()
        } catch (_: Exception) {
            releasePlayer()
            if (ttsReady && index in scripts.indices) speakTts(scripts[index], "loop_${System.currentTimeMillis()}")
            else if (running) scheduleNext()
        }
    }

    private fun scheduleNext() {
        handler.postDelayed({ if (running) speakNext() }, delayMs)
    }

    private fun randomIndex(): Int {
        if (scripts.size <= 1) return 0
        var candidate: Int
        do candidate = Random.nextInt(scripts.size) while (candidate == lastRandomIndex)
        lastRandomIndex = candidate
        return candidate
    }

    private fun speakTts(text: String, id: String) {
        if (!ttsReady) return
        tts.setSpeechRate(rate.coerceIn(0.5f, 2.0f))
        val params = Bundle().apply {
            putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, volume.coerceIn(0f, 1f))
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, id)
    }

    private fun stopCurrentPlayback() {
        releasePlayer()
        if (ttsReady) tts.stop()
    }

    private fun releasePlayer() {
        val old = player
        player = null
        if (old != null) {
            try { old.setOnCompletionListener(null) } catch (_: Exception) {}
            try { old.setOnErrorListener(null) } catch (_: Exception) {}
            try { old.stop() } catch (_: Exception) {}
            try { old.release() } catch (_: Exception) {}
        }
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
        releasePlayer()
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        super.onDestroy()
    }
}
