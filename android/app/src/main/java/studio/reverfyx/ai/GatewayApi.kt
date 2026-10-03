/*
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 *
 * This ReVerfyx adaptation uses the networking/state separation pattern from
 * Google AI Edge Gallery's Android client, with all gateway-specific code
 * rewritten for ReVerfyx AI.
 */
package studio.reverfyx.ai

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

data class ChatSummary(val id: String, val title: String)
data class UiMessage(val role: String, val content: String)

class GatewayApi(context: Context) {
    companion object {
        private const val BASE = "http://31.77.14.194:8090"
    }

    private val prefs = context.getSharedPreferences("reai", Context.MODE_PRIVATE)

    var token: String
        get() = prefs.getString("token", "") ?: ""
        set(value) { prefs.edit().putString("token", value).apply() }

    var username: String
        get() = prefs.getString("username", "") ?: ""
        set(value) { prefs.edit().putString("username", value).apply() }

    fun clearSession() {
        prefs.edit().remove("token").remove("username").apply()
    }

    suspend fun auth(user: String, password: String, register: Boolean): String =
        withContext(Dispatchers.IO) {
            val path = if (register) "/v1/auth/register" else "/v1/auth/login"
            val res = request(
                "POST",
                path,
                JSONObject().put("username", user).put("password", password),
                useAuth = false
            )
            val t = res.getString("token")
            val u = res.getJSONObject("user").getString("username")
            token = t
            username = u
            u
        }

    suspend fun health(): JSONObject = withContext(Dispatchers.IO) {
        request("GET", "/health", null, useAuth = false)
    }

    suspend fun chats(): List<ChatSummary> = withContext(Dispatchers.IO) {
        val arr = request("GET", "/v1/chats", null, true).optJSONArray("data") ?: JSONArray()
        buildList {
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                add(ChatSummary(o.getString("id"), o.optString("title", "Новый чат")))
            }
        }
    }

    suspend fun createChat(): ChatSummary = withContext(Dispatchers.IO) {
        val o = request("POST", "/v1/chats", JSONObject().put("title", "Новый чат"), true)
        ChatSummary(o.getString("id"), o.optString("title", "Новый чат"))
    }

    suspend fun messages(chatId: String): List<UiMessage> = withContext(Dispatchers.IO) {
        val arr = request("GET", "/v1/chats/$chatId/messages", null, true)
            .optJSONArray("data") ?: JSONArray()
        buildList {
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                add(UiMessage(o.optString("role", "assistant"), o.optString("content", "")))
            }
        }
    }

    suspend fun sendMessage(chatId: String, text: String, effort: String): UiMessage =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("content", text)
                .put("max_tokens", when (effort) {
                    "Высокий" -> 1400
                    "Средний" -> 850
                    else -> 500
                })
                .put("temperature", if (effort == "Высокий") 0.75 else 0.85)
                .put("top_k", if (effort == "Высокий") 60 else 40)
            val o = request("POST", "/v1/chats/$chatId/messages", body, true)
            UiMessage(o.optString("role", "assistant"), o.optString("content", ""))
        }

    suspend fun generateImage(prompt: String, chatId: String?): String =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("prompt", prompt)
                .put("steps", 48)
            if (!chatId.isNullOrBlank()) body.put("chat_id", chatId)
            val o = request("POST", "/v1/images/generations", body, true)
            o.getJSONArray("data").getJSONObject(0).getString("url")
        }

    suspend fun deleteChat(chatId: String) = withContext(Dispatchers.IO) {
        request("DELETE", "/v1/chats/$chatId", null, true)
    }

    private fun request(
        method: String,
        path: String,
        body: JSONObject?,
        useAuth: Boolean
    ): JSONObject {
        val conn = URL(BASE + path).openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 15_000
            conn.readTimeout = 600_000
            conn.requestMethod = method
            conn.setRequestProperty("Accept", "application/json")

            if (useAuth && token.isNotBlank()) {
                conn.setRequestProperty("Authorization", "Bearer $token")
            }

            if (body != null) {
                val raw = body.toString().toByteArray(StandardCharsets.UTF_8)
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.setFixedLengthStreamingMode(raw.size)
                conn.outputStream.use { it.write(raw) }
            }

            val code = conn.responseCode
            val stream: InputStream? =
                if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()

            if (code !in 200..299) {
                val message = try {
                    val obj = JSONObject(text)
                    val detail = obj.optString("detail")
                    if (detail.isNotBlank()) detail else obj.optString("error", text)
                } catch (_: Throwable) {
                    text.ifBlank { "HTTP $code" }
                }
                if (code == 401) clearSession()
                throw RuntimeException("HTTP $code: $message")
            }

            return if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }
}
