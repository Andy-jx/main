package com.andyjx.autosalesvoice

import android.app.*
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import kotlin.math.max
import kotlin.random.Random

class SalesVoiceService : Service() {
    companion object {
        const val ACTION_START = "start"
        const val ACTION_PAUSE = "pause"
        const val ACTION_RESUME = "resume"
        const val ACTION_NEXT = "next"
        const val ACTION_STOP = "stop"

        const val EXTRA_AUDIO_URIS = "audio_uris"
        const val EXTRA_SHUFFLE = "shuffle"
        const val EXTRA_GAP_MIN_MS = "gap_min_ms"
        const val EXTRA_GAP_MAX_MS = "gap_max_ms"
        const val EXTRA_VOLUME = "volume"

        private const val CHANNEL_ID = "real_audio_sales"
        private const val NOTIFICATION_ID = 1201
    }

    private val handler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var audioUris = listOf<String>()
    private var shuffleMode = true
    private var gapMinMs = 1000L
    private var gapMaxMs = 4000L
    private var volume = 1.0f
    private var running = false
    private var paused = false
    private var sequentialIndex = 0
    private var shuffleQueue = mutableListOf<Int>()
    private var lastPlayedIndex = -1

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification("真人音频播放待机中"))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startSession(intent)
            ACTION_PAUSE -> pausePlayback()
            ACTION_RESUME -> resumePlayback()
            ACTION_NEXT -> skipToNext()
            ACTION_STOP -> stopSession()
        }
        return START_NOT_STICKY
    }

    private fun startSession(intent: Intent) {
        audioUris = intent.getStringArrayListExtra(EXTRA_AUDIO_URIS)
            ?.filter { it.isNotBlank() }
            ?.distinct()
            ?: emptyList()
        shuffleMode = intent.getBooleanExtra(EXTRA_SHUFFLE, true)
        gapMinMs = max(0L, intent.getLongExtra(EXTRA_GAP_MIN_MS, 1000L))
        gapMaxMs = max(gapMinMs, intent.getLongExtra(EXTRA_GAP_MAX_MS, 4000L))
        volume = intent.getFloatExtra(EXTRA_VOLUME, 1.0f).coerceIn(0f, 1f)

        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        sequentialIndex = 0
        shuffleQueue.clear()
        lastPlayedIndex = -1
        paused = false
        running = audioUris.isNotEmpty()

        if (running) {
            playNext()
            updateNotification(if (shuffleMode) "整轮乱序循环中" else "顺序循环中")
        } else {
            updateNotification("没有可播放的音频")
        }
    }

    private fun pausePlayback() {
        handler.removeCallbacksAndMessages(null)
        val p = player
        if (p != null) {
            try {
                if (p.isPlaying) p.pause()
            } catch (_: Exception) {
            }
        }
        paused = true
        running = false
        updateNotification("已暂停")
    }

    private fun resumePlayback() {
        if (audioUris.isEmpty()) return
        running = true
        paused = false
        val p = player
        if (p != null) {
            try {
                p.start()
                updateNotification(if (shuffleMode) "整轮乱序循环中" else "顺序循环中")
                return
            } catch (_: Exception) {
                releasePlayer()
            }
        }
        playNext()
        updateNotification(if (shuffleMode) "整轮乱序循环中" else "顺序循环中")
    }

    private fun skipToNext() {
        if (audioUris.isEmpty()) return
        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        running = true
        paused = false
        playNext()
        updateNotification(if (shuffleMode) "整轮乱序循环中" else "顺序循环中")
    }

    private fun stopSession() {
        running = false
        paused = false
        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun playNext() {
        if (!running || paused || audioUris.isEmpty()) return
        val index = nextIndex()
        if (index !in audioUris.indices) return
        lastPlayedIndex = index
        playUri(index, audioUris[index])
    }

    private fun nextIndex(): Int {
        if (!shuffleMode) {
            val index = sequentialIndex % audioUris.size
            sequentialIndex = (sequentialIndex + 1) % audioUris.size
            return index
        }

        if (shuffleQueue.isEmpty()) refillShuffleQueue()
        return shuffleQueue.removeAt(0)
    }

    private fun refillShuffleQueue() {
        shuffleQueue = audioUris.indices.shuffled().toMutableList()
        if (shuffleQueue.size > 1 && shuffleQueue.firstOrNull() == lastPlayedIndex) {
            val first = shuffleQueue[0]
            shuffleQueue[0] = shuffleQueue[1]
            shuffleQueue[1] = first
        }
    }

    private fun playUri(index: Int, uriText: String) {
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
            mp.setVolume(volume, volume)
            mp.setOnPreparedListener { prepared ->
                if (running && !paused && player === prepared) {
                    prepared.start()
                    updateNotification("正在播放第 ${index + 1}/${audioUris.size} 条")
                } else {
                    releasePlayer()
                }
            }
            mp.setOnCompletionListener { completed ->
                if (player === completed) releasePlayer()
                if (running && !paused) scheduleNext()
            }
            mp.setOnErrorListener { failed, _, _ ->
                if (player === failed) releasePlayer()
                if (running && !paused) {
                    handler.postDelayed({ if (running && !paused) playNext() }, 500L)
                }
                true
            }
            mp.prepareAsync()
        } catch (_: Exception) {
            releasePlayer()
            if (running && !paused) {
                handler.postDelayed({ if (running && !paused) playNext() }, 500L)
            }
        }
    }

    private fun scheduleNext() {
        val delay = if (gapMaxMs <= gapMinMs) {
            gapMinMs
        } else {
            Random.nextLong(gapMinMs, gapMaxMs + 1)
        }
        updateNotification("随机停顿 ${"%.1f".format(delay / 1000.0)} 秒")
        handler.postDelayed({ if (running && !paused) playNext() }, delay)
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "真人音频讲品", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun buildNotification(text: String): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("自动讲品·真人音频")
            .setContentText(text)
            .setOngoing(true)
            .build()

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun releasePlayer() {
        val old = player
        player = null
        if (old != null) {
            try { old.setOnPreparedListener(null) } catch (_: Exception) {}
            try { old.setOnCompletionListener(null) } catch (_: Exception) {}
            try { old.setOnErrorListener(null) } catch (_: Exception) {}
            try { old.stop() } catch (_: Exception) {}
            try { old.release() } catch (_: Exception) {}
        }
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        releasePlayer()
        super.onDestroy()
    }
}
