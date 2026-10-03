/*
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * This file is a ReVerfyx adaptation of the Android UI architecture used by
 * Google AI Edge Gallery: ComponentActivity + Compose, ModalNavigationDrawer,
 * Scaffold, scrollable chat content, IME-aware input and Material 3 sheets.
 */
package studio.reverfyx.ai

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.AddPhotoAlternate
import androidx.compose.material.icons.rounded.AttachFile
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.ChatBubbleOutline
import androidx.compose.material.icons.rounded.Code
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.Extension
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Logout
import androidx.compose.material.icons.rounded.Menu
import androidx.compose.material.icons.rounded.Mic
import androidx.compose.material.icons.rounded.Psychology
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class ComposeMainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(null)
        enableEdgeToEdge()
        setContent {
            ReVerfyxTheme {
                ReVerfyxRoot()
            }
        }
    }
}

private val ReAiLight = lightColorScheme(
    primary = Color(0xFF111111),
    onPrimary = Color.White,
    background = Color.White,
    onBackground = Color(0xFF111111),
    surface = Color.White,
    onSurface = Color(0xFF111111),
    surfaceVariant = Color(0xFFF2F2F2),
    onSurfaceVariant = Color(0xFF666666),
    outlineVariant = Color(0xFFE5E5E5)
)

@Composable
private fun ReVerfyxTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ReAiLight, content = content)
}

@Composable
private fun ReVerfyxRoot() {
    val context = LocalContext.current
    val api = remember { GatewayApi(context.applicationContext) }
    var loggedIn by remember { mutableStateOf(api.token.isNotBlank()) }

    if (!loggedIn) {
        AuthScreen(api = api, onAuthenticated = { loggedIn = true })
    } else {
        ChatShell(
            api = api,
            onLogout = {
                api.clearSession()
                loggedIn = false
            }
        )
    }
}

@Composable
private fun AuthScreen(api: GatewayApi, onAuthenticated: () -> Unit) {
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .imePadding(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Surface(
                modifier = Modifier.size(54.dp),
                shape = RoundedCornerShape(18.dp),
                color = Color(0xFF111111)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text("R", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(20.dp))
            Text("ReVerfyx AI", fontSize = 30.sp, fontWeight = FontWeight.SemiBold)
            androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))
            Text("Войдите, чтобы продолжить", color = Color(0xFF6B6B6B))
            androidx.compose.foundation.layout.Spacer(Modifier.height(30.dp))

            OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Username") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Down) }),
                shape = RoundedCornerShape(18.dp)
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Пароль") },
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                shape = RoundedCornerShape(18.dp)
            )

            if (error.isNotBlank()) {
                androidx.compose.foundation.layout.Spacer(Modifier.height(12.dp))
                Text(error, color = Color(0xFFB42318), fontSize = 13.sp)
            }

            androidx.compose.foundation.layout.Spacer(Modifier.height(18.dp))
            Button(
                onClick = {
                    if (username.trim().length < 3 || password.length < 8 || busy) return@Button
                    busy = true
                    error = ""
                    scope.launch {
                        try {
                            api.auth(username.trim(), password, false)
                            onAuthenticated()
                        } catch (e: Throwable) {
                            error = e.message ?: "Ошибка входа"
                        } finally {
                            busy = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = RoundedCornerShape(28.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF111111))
            ) {
                if (busy) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        color = Color.White,
                        strokeWidth = 2.dp
                    )
                } else Text("Продолжить")
            }

            TextButton(
                onClick = {
                    if (username.trim().length < 3 || password.length < 8 || busy) return@TextButton
                    busy = true
                    error = ""
                    scope.launch {
                        try {
                            api.auth(username.trim(), password, true)
                            onAuthenticated()
                        } catch (e: Throwable) {
                            error = e.message ?: "Ошибка регистрации"
                        } finally {
                            busy = false
                        }
                    }
                }
            ) { Text("Создать аккаунт", color = Color(0xFF111111)) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatShell(api: GatewayApi, onLogout: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val snackbar = remember { SnackbarHostState() }
    val listState = rememberLazyListState()

    var tab by remember { mutableStateOf("Чат") }
    var currentChat by remember { mutableStateOf<ChatSummary?>(null) }
    var chats by remember { mutableStateOf<List<ChatSummary>>(emptyList()) }
    var messages by remember { mutableStateOf<List<UiMessage>>(emptyList()) }
    var input by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var showTools by remember { mutableStateOf(false) }
    var showEffort by remember { mutableStateOf(false) }
    var effortValue by remember { mutableFloatStateOf(0f) }

    fun effortLabel(): String = when {
        effortValue >= 0.75f -> "Высокий"
        effortValue >= 0.25f -> "Средний"
        else -> "Instant"
    }

    fun refreshChats() {
        scope.launch {
            try {
                chats = api.chats()
            } catch (e: Throwable) {
                if (e.message?.contains("HTTP 401") == true) onLogout()
            }
        }
    }

    fun openChat(chat: ChatSummary) {
        currentChat = chat
        scope.launch {
            try {
                messages = api.messages(chat.id)
                drawerState.close()
            } catch (e: Throwable) {
                snackbar.showSnackbar(e.message ?: "Не удалось открыть чат")
            }
        }
    }

    fun newChat() {
        currentChat = null
        messages = emptyList()
        input = ""
        scope.launch { drawerState.close() }
    }

    fun send() {
        val text = input.trim()
        if (text.isBlank() || busy) return
        input = ""
        messages = messages + UiMessage("user", text)
        busy = true
        scope.launch {
            try {
                var chat = currentChat
                if (chat == null) {
                    chat = api.createChat()
                    currentChat = chat
                }
                val reply = api.sendMessage(chat.id, text, effortLabel())
                messages = messages + reply
                chats = api.chats()
            } catch (e: Throwable) {
                val msg = e.message ?: "Ошибка"
                messages = messages + UiMessage("assistant", "Ошибка: $msg")
                if (msg.contains("HTTP 401")) onLogout()
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(Unit) { refreshChats() }
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.lastIndex)
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(
                modifier = Modifier.width(330.dp).fillMaxHeight(),
                drawerContainerColor = Color(0xFFF7F7F7)
            ) {
                DrawerContent(
                    username = api.username,
                    chats = chats,
                    onNewChat = { newChat() },
                    onChat = { openChat(it) },
                    onLogout = onLogout
                )
            }
        }
    ) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.White,
            contentWindowInsets = WindowInsets.safeDrawing,
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopBar(
                    tab = tab,
                    onTab = { tab = it },
                    onMenu = { scope.launch { drawerState.open() } },
                    onNew = { newChat() }
                )
            },
            bottomBar = {
                if (tab == "Чат") {
                    Composer(
                        value = input,
                        onValue = { input = it },
                        busy = busy,
                        effort = effortLabel(),
                        onTools = { showTools = true },
                        onEffort = { showEffort = true },
                        onSend = { send() }
                    )
                }
            }
        ) { padding ->
            if (tab == "Чат") {
                ChatBody(
                    messages = messages,
                    listState = listState,
                    busy = busy,
                    modifier = Modifier.padding(padding)
                )
            } else {
                WorkScreen(modifier = Modifier.padding(padding))
            }
        }
    }

    if (showTools) {
        ModalBottomSheet(
            onDismissRequest = { showTools = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Color.White
        ) {
            ToolRow(Icons.Rounded.CameraAlt, "Камера") {
                Toast.makeText(context, "Камера будет подключена к multimodal API", Toast.LENGTH_SHORT).show()
                showTools = false
            }
            ToolRow(Icons.Rounded.AddPhotoAlternate, "Фото") {
                Toast.makeText(context, "Фото будет подключено к multimodal API", Toast.LENGTH_SHORT).show()
                showTools = false
            }
            ToolRow(Icons.Rounded.AttachFile, "Файлы") {
                Toast.makeText(context, "Файлы доступны через gateway", Toast.LENGTH_SHORT).show()
                showTools = false
            }
            ToolRow(Icons.Rounded.Extension, "Плагины") {
                Toast.makeText(context, "Плагины", Toast.LENGTH_SHORT).show()
                showTools = false
            }
            ToolRow(Icons.Rounded.Psychology, "Размышлять глубже", tint = Color(0xFF2F6FEC)) {
                effortValue = 1f
                showTools = false
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))
        }
    }

    if (showEffort) {
        ModalBottomSheet(
            onDismissRequest = { showEffort = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Color.White
        ) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 28.dp, vertical = 10.dp)) {
                Text(
                    "Уровень усилий: \${effortLabel()}",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.SemiBold
                )
                androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))
                Slider(
                    value = effortValue,
                    onValueChange = { effortValue = it },
                    steps = 1
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Instant", color = Color(0xFF777777))
                    Text("Средний", color = Color(0xFF777777))
                    Text("Высокий", color = Color(0xFF2F6FEC))
                }
                androidx.compose.foundation.layout.Spacer(Modifier.height(26.dp))
            }
        }
    }
}

@Composable
private fun TopBar(
    tab: String,
    onTab: (String) -> Unit,
    onMenu: () -> Unit,
    onNew: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth().background(Color.White)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(modifier = Modifier.size(48.dp), color = Color(0xFFF4F4F4), shape = CircleShape) {
            IconButton(onClick = onMenu) {
                Icon(Icons.Rounded.Menu, contentDescription = "Меню")
            }
        }
        androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
        Surface(color = Color(0xFFEDEDED), shape = RoundedCornerShape(30.dp)) {
            Row(Modifier.padding(4.dp)) {
                Segment("Чат", tab == "Чат", onTab)
                Segment("Работа", tab == "Работа", onTab)
            }
        }
        androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
        Surface(modifier = Modifier.size(48.dp), color = Color(0xFFF4F4F4), shape = CircleShape) {
            IconButton(onClick = onNew) {
                Icon(Icons.Rounded.Edit, contentDescription = "Новый чат")
            }
        }
    }
}

@Composable
private fun Segment(label: String, active: Boolean, onTab: (String) -> Unit) {
    Surface(
        modifier = Modifier.clip(RoundedCornerShape(24.dp)).clickable { onTab(label) },
        color = if (active) Color.White else Color.Transparent,
        shape = RoundedCornerShape(24.dp),
        shadowElevation = if (active) 1.dp else 0.dp
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 28.dp, vertical = 10.dp),
            fontSize = 16.sp,
            color = Color(0xFF222222)
        )
    }
}

@Composable
private fun ChatBody(
    messages: List<UiMessage>,
    listState: androidx.compose.foundation.lazy.LazyListState,
    busy: Boolean,
    modifier: Modifier = Modifier
) {
    Box(modifier.fillMaxSize()) {
        if (messages.isEmpty()) {
            Column(
                modifier = Modifier.align(Alignment.Center).padding(bottom = 80.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Surface(
                    modifier = Modifier.size(58.dp),
                    shape = RoundedCornerShape(20.dp),
                    color = Color(0xFF111111)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("R", color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                    }
                }
                androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))
                Text("Чем я могу помочь?", fontSize = 30.sp, fontWeight = FontWeight.SemiBold)
                androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 22.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Suggestion("Объясни тему", Modifier.weight(1f))
                    Suggestion("Помоги с кодом", Modifier.weight(1f))
                    Suggestion("Создай идею", Modifier.weight(1f))
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                state = listState,
                contentPadding = androidx.compose.foundation.layout.PaddingValues(
                    start = 16.dp, end = 16.dp, top = 12.dp, bottom = 18.dp
                ),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                itemsIndexed(messages) { _, message -> MessageItem(message) }
                if (busy) {
                    item {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(vertical = 8.dp)
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            androidx.compose.foundation.layout.Spacer(Modifier.width(10.dp))
                            Text("ReVerfyx думает…", color = Color(0xFF666666))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Suggestion(text: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(24.dp),
        color = Color.White,
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE4E4E4))
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            fontSize = 13.sp
        )
    }
}

@Composable
private fun MessageItem(message: UiMessage) {
    val isUser = message.role == "user"
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        if (isUser) {
            Surface(color = Color(0xFFF0F0F0), shape = RoundedCornerShape(22.dp)) {
                Text(
                    message.content,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 11.dp),
                    fontSize = 16.sp,
                    lineHeight = 23.sp
                )
            }
        } else {
            Text(
                message.content,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                fontSize = 16.sp,
                lineHeight = 24.sp
            )
        }
    }
}

@Composable
private fun Composer(
    value: String,
    onValue: (String) -> Unit,
    busy: Boolean,
    effort: String,
    onTools: () -> Unit,
    onEffort: () -> Unit,
    onSend: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth().background(Color.White)
            .navigationBarsPadding().imePadding()
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        AnimatedVisibility(visible = effort != "Instant", enter = fadeIn(), exit = fadeOut()) {
            Surface(
                modifier = Modifier.padding(start = 4.dp, bottom = 6.dp).clickable { onEffort() },
                color = Color(0xFFF4F4F4),
                shape = RoundedCornerShape(16.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Rounded.Psychology,
                        contentDescription = null,
                        modifier = Modifier.size(17.dp),
                        tint = Color(0xFF2F6FEC)
                    )
                    androidx.compose.foundation.layout.Spacer(Modifier.width(6.dp))
                    Text(effort, fontSize = 12.sp, color = Color(0xFF2F6FEC))
                }
            }
        }

        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = Color(0xFFF4F4F4),
            shape = RoundedCornerShape(30.dp)
        ) {
            Column(Modifier.padding(horizontal = 8.dp, vertical = 6.dp)) {
                BasicTextField(
                    value = value,
                    onValueChange = onValue,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp),
                    textStyle = TextStyle(color = Color(0xFF111111), fontSize = 17.sp),
                    maxLines = 6,
                    decorationBox = { inner ->
                        if (value.isEmpty()) {
                            Text("Спросить что угодно", color = Color(0xFF8A8A8A), fontSize = 17.sp)
                        }
                        inner()
                    }
                )

                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onTools) {
                        Icon(Icons.Rounded.Add, contentDescription = "Инструменты")
                    }
                    TextButton(onClick = onEffort) {
                        Text(
                            if (effort == "Instant") "Инструменты" else effort,
                            color = Color(0xFF666666),
                            fontSize = 13.sp
                        )
                    }
                    androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                    IconButton(onClick = {}) {
                        Icon(Icons.Rounded.Mic, contentDescription = "Микрофон")
                    }
                    FilledIconButton(
                        onClick = onSend,
                        enabled = value.isNotBlank() && !busy,
                        modifier = Modifier.size(42.dp),
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                            containerColor = if (value.isNotBlank() && !busy)
                                Color(0xFF2F6FEC) else Color(0xFFAAAAAA)
                        )
                    ) {
                        Icon(
                            Icons.AutoMirrored.Rounded.Send,
                            contentDescription = "Отправить",
                            tint = Color.White
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DrawerContent(
    username: String,
    chats: List<ChatSummary>,
    onNewChat: () -> Unit,
    onChat: (ChatSummary) -> Unit,
    onLogout: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp)
            .windowInsetsPadding(WindowInsets.safeDrawing)
    ) {
        androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))
        Text(
            "ReVerfyx AI",
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            fontSize = 22.sp,
            fontWeight = FontWeight.SemiBold
        )
        DrawerAction(Icons.Rounded.Search, "Поиск") {}
        DrawerAction(Icons.Rounded.Image, "Картинки") {}
        DrawerAction(Icons.Rounded.Description, "Библиотека") {}
        DrawerAction(Icons.Rounded.FolderOpen, "Проекты") {}
        DrawerAction(Icons.Rounded.Code, "Codex") {}
        DrawerAction(Icons.Rounded.History, "Запланированные") {}
        DrawerAction(Icons.Rounded.Extension, "Плагины") {}

        Divider(Modifier.padding(vertical = 10.dp), color = Color(0xFFE3E3E3))
        Text(
            "Чаты",
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            color = Color(0xFF777777),
            fontSize = 13.sp
        )

        LazyColumn(modifier = Modifier.weight(1f)) {
            item { DrawerAction(Icons.Rounded.Edit, "Новый чат", onNewChat) }
            itemsIndexed(chats) { _, chat ->
                Row(
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                        .clickable { onChat(chat) }
                        .padding(horizontal = 12.dp, vertical = 11.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Rounded.ChatBubbleOutline,
                        contentDescription = null,
                        modifier = Modifier.size(19.dp)
                    )
                    androidx.compose.foundation.layout.Spacer(Modifier.width(10.dp))
                    Text(
                        chat.title,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        fontSize = 14.sp
                    )
                }
            }
        }

        Divider(color = Color(0xFFE3E3E3))
        Row(
            modifier = Modifier.fillMaxWidth().clickable { onLogout() }.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(modifier = Modifier.size(38.dp), color = Color(0xFF202020), shape = CircleShape) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        (username.firstOrNull()?.uppercase() ?: "R"),
                        color = Color.White,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.width(12.dp))
            Text(username.ifBlank { "Профиль" }, modifier = Modifier.weight(1f))
            Icon(Icons.Rounded.Logout, contentDescription = "Выйти")
        }
        androidx.compose.foundation.layout.Spacer(Modifier.height(6.dp))
    }
}

@Composable
private fun DrawerAction(icon: ImageVector, label: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
        androidx.compose.foundation.layout.Spacer(Modifier.width(12.dp))
        Text(label, fontSize = 15.sp)
    }
}

@Composable
private fun ToolRow(
    icon: ImageVector,
    title: String,
    tint: Color = Color(0xFF111111),
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)
            .padding(horizontal = 24.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(modifier = Modifier.size(44.dp), shape = CircleShape, color = Color(0xFFF1F1F1)) {
            Box(contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = null, tint = tint)
            }
        }
        androidx.compose.foundation.layout.Spacer(Modifier.width(16.dp))
        Text(title, fontSize = 18.sp, color = tint)
    }
}

@Composable
private fun WorkScreen(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Работа", fontSize = 30.sp, fontWeight = FontWeight.SemiBold)
        Text(
            "Проекты, файлы и длинные задачи будут жить здесь.",
            color = Color(0xFF6B6B6B),
            fontSize = 16.sp
        )
        WorkCard(Icons.Rounded.FolderOpen, "Проекты", "Храни контекст и файлы по задачам")
        WorkCard(Icons.Rounded.Code, "Код", "Разбор репозиториев и программ")
        WorkCard(Icons.Rounded.AutoAwesome, "Исследование", "Длинные исследовательские задачи")
        WorkCard(Icons.Rounded.Settings, "Инструменты", "API, плагины и подключённые сервисы")
    }
}

@Composable
private fun WorkCard(icon: ImageVector, title: String, subtitle: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color(0xFFF7F7F7),
        shape = RoundedCornerShape(20.dp)
    ) {
        Row(modifier = Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(
                modifier = Modifier.size(46.dp),
                color = Color.White,
                shape = RoundedCornerShape(14.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(icon, contentDescription = null)
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.width(14.dp))
            Column {
                Text(title, fontSize = 17.sp, fontWeight = FontWeight.Medium)
                androidx.compose.foundation.layout.Spacer(Modifier.height(3.dp))
                Text(subtitle, color = Color(0xFF6F6F6F), fontSize = 14.sp)
            }
        }
    }
}
