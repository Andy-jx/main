package com.andyjx.autosalesvoice

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class PlaylistProfile(
    val name: String,
    val audioUris: List<String>
)

object ProductStore {
    private const val PREFS = "real_audio_sales"
    private const val KEY = "profiles_json"

    fun load(context: Context): MutableList<PlaylistProfile> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
        if (raw.isNullOrBlank()) return mutableListOf(sample())
        return try {
            val out = mutableListOf<PlaylistProfile>()
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val audio = mutableListOf<String>()
                val audioJson = obj.optJSONArray("audioUris") ?: JSONArray()
                for (j in 0 until audioJson.length()) {
                    val uri = audioJson.optString(j)
                    if (uri.isNotBlank()) audio += uri
                }
                out += PlaylistProfile(obj.optString("name", "直播方案 ${i + 1}"), audio)
            }
            if (out.isEmpty()) mutableListOf(sample()) else out
        } catch (_: Exception) {
            mutableListOf(sample())
        }
    }

    fun save(context: Context, profiles: List<PlaylistProfile>) {
        val arr = JSONArray()
        profiles.forEach { p ->
            val audio = JSONArray()
            p.audioUris.forEach { audio.put(it) }
            arr.put(JSONObject().put("name", p.name).put("audioUris", audio))
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, arr.toString()).apply()
    }

    fun sample() = PlaylistProfile("溜溜凳直播", emptyList())
}
