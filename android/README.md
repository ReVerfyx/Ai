# ReVerfyx AI Android client — 0.0.2

The Android app talks only to the application gateway:

- Gateway/client server: `31.77.14.194:8090`
- AI server: not embedded in the APK; the gateway knows it.

Implemented in 0.0.2:

- registration/login;
- persistent chat history from the gateway database;
- ChatGPT-inspired side drawer with chat search;
- new chat, rename and delete chat;
- text chat;
- long-press to copy messages;
- text/code file attachment and analysis;
- image generation inside a chat;
- generated-image history;
- Android speech-to-text input;
- fixed gateway routing, so the AI backend IP/API key are not stored in the app.

Current core limitations:

- image understanding is not wired to the model yet;
- video understanding is not wired to the model yet;
- voice is speech-to-text from the Android recognizer; the AI core itself has no audio model yet.

## Build

Use Android Studio Quail 4+ or Gradle 9.6 / JDK 17:

```bash
cd android
gradle assembleDebug
```

APK:

```text
app/build/outputs/apk/debug/app-debug.apk
```
