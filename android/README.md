# ReVerfyx AI Android client — 0.0.3

The Android app talks only to the application gateway:

- Gateway/client server: `31.77.14.194:8090`
- AI server: not embedded in the APK; the gateway knows it.

Implemented in 0.0.3:

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


## APK delivery

Every Android/client update should produce a fresh debug APK artifact via GitHub Actions.
The UI reference is the current ChatGPT-style mobile layout: side drawer/history,
bottom composer, attachment menu, voice button, and effort-mode control.


## Host helper

AI server:
```bash
bash host.sh ai
```

Gateway server:
```bash
bash host.sh gateway AI_KEY
```

Continuous training:
```bash
bash host.sh train
```


## Modern UI refresh

The launcher now uses `ModernMainActivity`, which replaces the earlier legacy
drawer/composer shell. The refreshed client uses the current simplified mobile
layout direction: compact header, horizontally grouped tools in the sidebar,
minimal chat history, modern bottom composer, bottom sheets, and model modes.


## Learning backend sync

This APK build is synced with the staged learning backend:
Wikipedia bootstrap -> coverage-based read-only research browser -> independent workers.


## 0.0.3 backend profile

- sparse ~50.7M parameter text core;
- API remains available while training uses independent checkpoints;
- multiple API keys;
- 64x64 from-scratch image generator endpoint;
- observer dashboard and candidate self-improvement loop.


Final 0.0.3 sync: sparse 50M engine, multi-key API, public-web research,
observer dashboard, and guarded self-improvement modes are now part of the backend.

Final sparse-loader verification synced after successful 0.0.3 CI.
