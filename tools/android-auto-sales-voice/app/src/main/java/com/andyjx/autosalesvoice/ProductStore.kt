package com.andyjx.autosalesvoice

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class Product(val name: String, val scripts: List<String>)

object ProductStore {
    fun load(context: Context): MutableList<Product> {
        val raw = context.getSharedPreferences("sales_voice", Context.MODE_PRIVATE)
            .getString("products_json", null)
        if (raw.isNullOrBlank()) return mutableListOf(sample())
        return try {
            val out = mutableListOf<Product>()
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val scriptsJson = obj.getJSONArray("scripts")
                val scripts = mutableListOf<String>()
                for (j in 0 until scriptsJson.length()) scripts += scriptsJson.getString(j)
                out += Product(obj.getString("name"), scripts)
            }
            if (out.isEmpty()) mutableListOf(sample()) else out
        } catch (_: Exception) {
            mutableListOf(sample())
        }
    }

    fun save(context: Context, products: List<Product>) {
        val arr = JSONArray()
        products.forEach { p ->
            val obj = JSONObject().put("name", p.name)
            val scripts = JSONArray()
            p.scripts.forEach { scripts.put(it) }
            obj.put("scripts", scripts)
            arr.put(obj)
        }
        context.getSharedPreferences("sales_voice", Context.MODE_PRIVATE)
            .edit().putString("products_json", arr.toString()).apply()
    }

    fun sample() = Product(
        "溜溜凳示例",
        listOf(
            "现在镜头里这款是带轮靠背溜溜凳，整体低矮小巧，坐着移动比较方便。",
            "大家现在看到的是经典黑款，可以重点看看靠背、坐垫和轮子的细节。",
            "底部带四只万向轮，梳妆台、工作台、厨房或者门店里都能灵活移动。",
            "这款还有墨绿色、暖橙色和复古棕，可以按照使用环境选择。",
            "购买前建议先确认使用位置的高度和空间，再对照商品详情里的尺寸。"
        )
    )
}
