#!/usr/bin/env python3
from pathlib import Path
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
        versionCode = 8
        versionName = "0.0.6"
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
manifest.write_text(text, encoding="utf-8")

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
new = '''            val raw = prefs[key]
            if (raw == null) {
                return@map listOf(
                    ProviderConfig(
                        id = "reverfyx",
                        name = "ReVerfyx AI",
                        baseUrl = "http://31.77.14.194:8090/v1",
                        apiKey = "reai-mobile-v1",
                        models = listOf("reverfyx-ai")
                    )
                )
            }
            runCatching { json.decodeFromString(ListSerializer(ProviderConfig.serializer()), raw) }
                .getOrDefault(emptyList())'''
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
    '        Preset("ReVerfyx AI", "http://31.77.14.194:8090/v1", "reverfyx-ai",\n'
    '            "ReVerfyx server"),\n'
)
provider.write_text(text, encoding="utf-8")

print("ReVerfyx MiniiChat patch applied to", root)
