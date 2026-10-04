#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "app"

(app / "build.gradle.kts").write_text(r'''plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.miniichat"
    compileSdk = 36

    defaultConfig {
        applicationId = "studio.reverfyx.ai"
        minSdk = 26
        targetSdk = 36
        versionCode = 9
        versionName = "0.0.7"
        vectorDrawables { useSupportLibrary = true }
    }

    signingConfigs {
        create("reverfyx") {
            storeFile = file("release.keystore")
            storePassword = "reverfyxdev"
            keyAlias = "reverfyx"
            keyPassword = "reverfyxdev"
        }
    }

    buildTypes {
        debug { isMinifyEnabled = false }
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("reverfyx")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    sourceSets["main"].java.srcDirs("src/main/kotlin")

    packaging {
        resources {
            excludes += setOf(
                "/META-INF/{AL2.0,LGPL2.1}",
                "/META-INF/DEPENDENCIES",
                "/META-INF/LICENSE",
                "/META-INF/LICENSE.txt",
                "/META-INF/NOTICE",
                "/META-INF/NOTICE.txt"
            )
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.09.02")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.6")
    implementation("androidx.navigation:navigation-compose:2.8.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("io.ktor:ktor-client-core:2.3.12")
    implementation("io.ktor:ktor-client-okhttp:2.3.12")
    implementation("io.ktor:ktor-client-content-negotiation:2.3.12")
    implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.12")
    implementation("io.ktor:ktor-client-logging:2.3.12")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
''', encoding="utf-8")

(root / "settings.gradle.kts").write_text(r'''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "ReVerfyxAI"
include(":app")
''', encoding="utf-8")

manifest = app / "src/main/AndroidManifest.xml"
text = manifest.read_text(encoding="utf-8")
text = text.replace('android:label="@string/app_name"', 'android:label="@string/app_name"\n        android:usesCleartextTraffic="true"')
text = text.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@drawable/ic_reverfyx"')
text = text.replace('android:roundIcon="@mipmap/ic_launcher_round"', 'android:roundIcon="@drawable/ic_reverfyx"')
manifest.write_text(text, encoding="utf-8")

drawable = app / "src/main/res/drawable"
drawable.mkdir(parents=True, exist_ok=True)
(drawable / "ic_reverfyx.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#111111"
        android:pathData="M18,6 L90,6 C96.6,6 102,11.4 102,18 L102,90 C102,96.6 96.6,102 90,102 L18,102 C11.4,102 6,96.6 6,90 L6,18 C6,11.4 11.4,6 18,6 Z"/>
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M34,27 L57,27 C70,27 78,34 78,45 C78,53 74,59 66,62 L80,81 L66,81 L54,64 L47,64 L47,81 L34,81 Z M47,38 L47,54 L56,54 C62,54 66,51 66,46 C66,41 62,38 56,38 Z"/>
</vector>
''', encoding="utf-8")

strings = app / "src/main/res/values/strings.xml"
strings.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">ReVerfyx AI</string>
    <string name="new_chat">Новый чат</string>
    <string name="send">Отправить</string>
    <string name="settings">Настройки</string>
    <string name="hint_input">Спросить что угодно…</string>
    <string name="empty_title">Чем я могу помочь?</string>
    <string name="empty_subtitle">ReVerfyx AI подключён к вашему серверу.</string>
    <string name="copy">Копировать</string>
    <string name="delete">Удалить</string>
    <string name="rename">Переименовать</string>
    <string name="cancel">Отмена</string>
    <string name="ok">OK</string>
    <string name="save">Сохранить</string>
    <string name="add">Добавить</string>
    <string name="chats">Чаты</string>
    <string name="providers">Сервер</string>
    <string name="provider">Сервер</string>
    <string name="assistants">Ассистенты</string>
    <string name="assistant">Ассистент</string>
    <string name="active">Активен</string>
    <string name="add_provider">Добавить сервер</string>
    <string name="edit_provider">Изменить сервер</string>
    <string name="add_assistant">Добавить ассистента</string>
    <string name="edit_assistant">Изменить ассистента</string>
    <string name="assistant_name">Имя</string>
    <string name="assistant_avatar">Emoji</string>
    <string name="assistant_system_prompt">Системный промпт</string>
    <string name="prompt_vars_hint">Переменные: {model} {provider} {assistant} {date} {time} {datetime} {weekday} {locale}</string>
    <string name="override_temperature">Своя температура</string>
    <string name="provider_name">Название</string>
    <string name="setting_base_url">Адрес API</string>
    <string name="setting_api_key">API ключ</string>
    <string name="setting_model">Модель</string>
    <string name="setting_system">Системный промпт</string>
    <string name="setting_temperature">Температура</string>
    <string name="setting_stream">Потоковый ответ</string>
    <string name="setting_about">О приложении</string>
    <string name="setting_appearance">Оформление</string>
    <string name="setting_dynamic_color">Динамические цвета Material You</string>
    <string name="setting_dynamic_color_hint">Использовать цвета системы Android 12+</string>
    <string name="setting_theme_mode">Тема</string>
    <string name="setting_theme_system">Как в системе</string>
    <string name="setting_theme_light">Светлая</string>
    <string name="setting_theme_dark">Тёмная</string>
    <string name="setting_language">Язык</string>
    <string name="setting_language_system">Системный</string>
    <string name="setting_language_en">English</string>
    <string name="setting_language_zh">中文</string>
    <string name="custom_headers">HTTP заголовки</string>
    <string name="custom_headers_hint">Отправляются с каждым запросом</string>
    <string name="extra_body">Дополнительные параметры</string>
    <string name="extra_body_hint">Добавляются в JSON запроса</string>
    <string name="key">Ключ</string>
    <string name="value">Значение</string>
    <string name="add_row">Добавить</string>
    <string name="about_text">ReVerfyx AI. Android-клиент основан на MiniiChat (MIT).</string>
    <string name="error_no_provider">Сервер не настроен.</string>
    <string name="stop">Остановить</string>
    <string name="regenerate">Повторить</string>
    <string name="thinking">Думает…</string>
    <string name="example_prompt_1">Объясни простыми словами, что такое нейросеть.</string>
    <string name="example_prompt_2">Помоги написать код.</string>
    <string name="example_prompt_3">Придумай пять идей для проекта.</string>
    <string name="example_prompt_4">Переведи текст на английский.</string>
    <string name="search_chats">Поиск чатов</string>
    <string name="search_models">Поиск моделей</string>
    <string name="fetch_models">Получить модели</string>
    <string name="fetching">Загрузка…</string>
    <string name="add_model_manually">Добавить модель вручную</string>
    <string name="select_model">Выбрать модель</string>
    <string name="no_models">Моделей пока нет.</string>
    <string name="no_providers">Сервер не настроен</string>
    <string name="no_providers_hint">Добавьте сервер для начала</string>
    <string name="pick_preset_or_manual">Выберите сервер или заполните вручную</string>
    <string name="choose_preset">Выбрать…</string>
    <string name="expand_models">Показать ещё: %1$d</string>
    <string name="collapse_models">Свернуть</string>
    <string name="attach_image">Прикрепить фото</string>
    <string name="attach_file">Прикрепить файл</string>
    <string name="attachment_image">Фото</string>
    <string name="attachment_file">Файл</string>
    <string name="attachment_unsupported">Этот сервер пока не поддерживает мультимодальный ввод.</string>
    <string name="attachment_too_large">Файл слишком большой, максимум %1$d МБ</string>
    <string name="date_today">Сегодня</string>
    <string name="date_yesterday">Вчера</string>
    <string name="date_previous_7">Последние 7 дней</string>
    <string name="date_previous_30">Последние 30 дней</string>
    <string name="date_older">Ранее</string>
    <string name="section_behavior">Поведение</string>
    <string name="section_about">О приложении</string>
    <string name="error_dialog_title">Произошла ошибка</string>
    <string name="error_open_providers">Открыть сервер</string>
    <string name="edit">Изменить</string>
    <string name="regenerate_from_here">Повторить отсюда</string>
    <string name="advanced_options">Дополнительно</string>
</resources>
''', encoding="utf-8")

provider_store = app / "src/main/kotlin/com/miniichat/data/ProviderStore.kt"
text = provider_store.read_text(encoding="utf-8")
old = '''            val raw = prefs[key] ?: return@map emptyList()
            runCatching { json.decodeFromString(ListSerializer(ProviderConfig.serializer()), raw) }
                .getOrDefault(emptyList())'''
new = '''            // ReVerfyx endpoint is application-internal. Never expose or
            // preserve an old user-editable gateway address from earlier builds.
            return@map listOf(
                ProviderConfig(
                    id = "reverfyx",
                    name = "ReVerfyx AI",
                    baseUrl = "http://2.26.85.86:8080/v1",
                    apiKey = "reai-mobile-v1",
                    models = listOf("reverfyx-ai")
                )
            )'''
if old not in text:
    raise SystemExit("ProviderStore patch anchor not found")
provider_store.write_text(text.replace(old, new), encoding="utf-8")

settings = app / "src/main/kotlin/com/miniichat/data/SettingsRepository.kt"
text = settings.read_text(encoding="utf-8")
for a, b in [
    ('val activeProviderId: String = "",', 'val activeProviderId: String = "reverfyx",'),
    ('val activeModel: String = "",', 'val activeModel: String = "reverfyx-ai",'),
    ('val systemPrompt: String = "You are a helpful assistant.",',
     'val systemPrompt: String = "Ты ReVerfyx AI. Отвечай полезно и по существу.",'),
    ('val stream: Boolean = true,', 'val stream: Boolean = false,'),
    ('activeProviderId = p[Keys.PROVIDER] ?: "",',
     'activeProviderId = p[Keys.PROVIDER] ?: "reverfyx",'),
    ('activeModel = p[Keys.MODEL] ?: "",',
     'activeModel = p[Keys.MODEL] ?: "reverfyx-ai",'),
    ('systemPrompt = p[Keys.SYSTEM] ?: "You are a helpful assistant.",',
     'systemPrompt = p[Keys.SYSTEM] ?: "Ты ReVerfyx AI. Отвечай полезно и по существу.",'),
    ('stream = p[Keys.STREAM] ?: true,', 'stream = p[Keys.STREAM] ?: false,'),
]:
    text = text.replace(a, b)
settings.write_text(text, encoding="utf-8")

provider = app / "src/main/kotlin/com/miniichat/data/Provider.kt"
text = provider.read_text(encoding="utf-8")
text = text.replace(
    '    val all: List<Preset> = listOf(\n',
    '    val all: List<Preset> = listOf(\n'
    '        Preset("ReVerfyx AI", "http://2.26.85.86:8080/v1", "reverfyx-ai",\n'
    '            "ReVerfyx server"),\n'
)
provider.write_text(text, encoding="utf-8")


# Hide internal provider/server configuration from the user interface.
settings_ui = app / "src/main/kotlin/com/miniichat/ui/SettingsScreen.kt"
text = settings_ui.read_text(encoding="utf-8")
text = re.sub(
    r'\n\s*// Providers entry\n.*?\n\s*// Assistants entry',
    '\n\n            // Assistants entry',
    text,
    flags=re.S,
)
settings_ui.write_text(text, encoding="utf-8")

# Hide model/provider internals from the chat header and assistant label.
chat_ui = app / "src/main/kotlin/com/miniichat/ui/ChatScreen.kt"
text = chat_ui.read_text(encoding="utf-8")
text = text.replace(
    'else settings.activeModel.ifBlank { activeProvider?.name ?: "Assistant" },',
    'else "ReVerfyx AI",'
)
text = re.sub(
    r'\n\s*// Row 2: small model chip aligned right\n.*?\n\s*HorizontalDivider',
    '\n        HorizontalDivider',
    text,
    flags=re.S,
)
chat_ui.write_text(text, encoding="utf-8")

# Provider/model editor still exists upstream for code compatibility, but there
# is no navigation path to it in the ReVerfyx UI.
app_root = app / "src/main/kotlin/com/miniichat/ui/AppRoot.kt"
text = app_root.read_text(encoding="utf-8")
text = re.sub(
    r'onPickModel = \{\n\s*if \(providers\.isEmpty\(\)\) \{\n.*?\n\s*\} else showModelPicker = true\n\s*\}',
    'onPickModel = { }',
    text,
    flags=re.S,
)
text = re.sub(
    r'val needsProviderFix = msg\.contains\("provider".*?\|\| msg\.contains\("403"\)',
    'val needsProviderFix = false',
    text,
    flags=re.S,
)
app_root.write_text(text, encoding="utf-8")

print("ReVerfyx MiniiChat patch applied to", root)
