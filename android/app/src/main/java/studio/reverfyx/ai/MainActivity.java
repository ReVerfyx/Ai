package studio.reverfyx.ai;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.speech.RecognizerIntent;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String GATEWAY = "http://31.77.14.194:8090";
    private static final String PREFS = "reai";
    private static final int PICK_FILE = 7001;
    private static final int SPEECH = 7002;

    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private String token = "";
    private String username = "";
    private String currentChatId = null;
    private String pendingFileId = null;
    private String pendingFileName = null;

    private FrameLayout shell;
    private View scrim;
    private LinearLayout drawer;
    private LinearLayout drawerChats;
    private EditText drawerSearch;

    private ScrollView messagesScroll;
    private LinearLayout messages;
    private EditText composer;
    private TextView attachLabel;
    private ProgressBar typing;
    private TextView headerTitle;
    private JSONArray cachedChats = new JSONArray();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        token = prefs.getString("token", "");
        username = prefs.getString("username", "");
        if (token.isEmpty()) showAuth();
        else showApp();
    }

    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable bg(int color, float radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp((int) radius));
        return d;
    }

    private TextView text(String value, float size, int color) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private Button pill(String value) {
        Button b = new Button(this);
        b.setText(value);
        b.setTextAllCaps(false);
        b.setTextSize(14);
        b.setBackground(bg(Color.rgb(238,238,238), 18));
        return b;
    }

    private void showAuth() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(26), dp(30), dp(26), dp(30));
        root.setBackgroundColor(Color.rgb(250,250,250));

        TextView logo = text("AI", 34, Color.BLACK);
        logo.setGravity(Gravity.CENTER);
        logo.setTypeface(Typeface.DEFAULT_BOLD);
        logo.setBackground(bg(Color.WHITE, 40));
        root.addView(logo, new LinearLayout.LayoutParams(dp(78), dp(78)));

        TextView title = text("ReVerfyx AI", 30, Color.BLACK);
        title.setGravity(Gravity.CENTER);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.topMargin = dp(18);
        root.addView(title, tp);

        TextView subtitle = text("Войди или создай аккаунт", 15, Color.DKGRAY);
        subtitle.setGravity(Gravity.CENTER);
        root.addView(subtitle, new LinearLayout.LayoutParams(-1, -2));

        EditText user = new EditText(this);
        user.setHint("Username");
        user.setSingleLine(true);
        LinearLayout.LayoutParams ep = new LinearLayout.LayoutParams(-1, dp(58));
        ep.topMargin = dp(30);
        root.addView(user, ep);

        EditText pass = new EditText(this);
        pass.setHint("Пароль");
        pass.setSingleLine(true);
        pass.setInputType(0x00000081);
        root.addView(pass, new LinearLayout.LayoutParams(-1, dp(58)));

        Button login = pill("Войти");
        login.setTextColor(Color.WHITE);
        login.setBackground(bg(Color.BLACK, 28));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, dp(56));
        bp.topMargin = dp(18);
        root.addView(login, bp);

        Button register = pill("Создать аккаунт");
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, dp(54));
        rp.topMargin = dp(8);
        root.addView(register, rp);

        ProgressBar progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(-2, -2));

        login.setOnClickListener(v -> auth(false, user.getText().toString(), pass.getText().toString(), progress));
        register.setOnClickListener(v -> auth(true, user.getText().toString(), pass.getText().toString(), progress));

        setContentView(root);
    }

    private void auth(boolean register, String user, String pass, ProgressBar progress) {
        user = user.trim();
        if (user.isEmpty() || pass.length() < 8) {
            Toast.makeText(this, "Username и пароль минимум 8 символов", Toast.LENGTH_SHORT).show();
            return;
        }
        progress.setVisibility(View.VISIBLE);
        final String path = register ? "/v1/auth/register" : "/v1/auth/login";
        final String u = user;
        final String p = pass;
        io.execute(() -> {
            try {
                JSONObject body = new JSONObject().put("username", u).put("password", p);
                JSONObject res = request("POST", path, body, false);
                token = res.getString("token");
                username = res.getJSONObject("user").getString("username");
                prefs.edit().putString("token", token).putString("username", username).apply();
                ui.post(this::showApp);
            } catch (Exception e) {
                ui.post(() -> {
                    progress.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void showApp() {
        shell = new FrameLayout(this);
        shell.setBackgroundColor(Color.WHITE);

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.VERTICAL);
        main.setBackgroundColor(Color.WHITE);
        shell.addView(main, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(8), dp(8), dp(8), dp(8));

        Button menu = pill("☰");
        menu.setTextSize(24);
        menu.setBackgroundColor(Color.TRANSPARENT);
        top.addView(menu, new LinearLayout.LayoutParams(dp(52), dp(52)));

        headerTitle = text("ReAI 0.0.2 ▾", 18, Color.BLACK);
        headerTitle.setTypeface(Typeface.DEFAULT_BOLD);
        headerTitle.setPadding(dp(8), 0, dp(8), 0);
        top.addView(headerTitle, new LinearLayout.LayoutParams(0, dp(52), 1f));

        Button newChat = pill("✎");
        newChat.setTextSize(22);
        newChat.setBackgroundColor(Color.TRANSPARENT);
        top.addView(newChat, new LinearLayout.LayoutParams(dp(52), dp(52)));

        main.addView(top, new LinearLayout.LayoutParams(-1, dp(66)));

        messagesScroll = new ScrollView(this);
        messagesScroll.setFillViewport(true);
        messages = new LinearLayout(this);
        messages.setOrientation(LinearLayout.VERTICAL);
        messages.setPadding(dp(16), dp(10), dp(16), dp(20));
        messagesScroll.addView(messages, new ScrollView.LayoutParams(-1, -2));
        main.addView(messagesScroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        typing = new ProgressBar(this);
        typing.setIndeterminate(true);
        typing.setVisibility(View.GONE);
        main.addView(typing, new LinearLayout.LayoutParams(-1, dp(3)));

        attachLabel = text("", 12, Color.DKGRAY);
        attachLabel.setPadding(dp(16), 0, dp(16), 0);
        attachLabel.setVisibility(View.GONE);
        main.addView(attachLabel, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout composerWrap = new LinearLayout(this);
        composerWrap.setGravity(Gravity.BOTTOM | Gravity.CENTER_VERTICAL);
        composerWrap.setPadding(dp(8), dp(6), dp(8), dp(10));
        composerWrap.setBackgroundColor(Color.WHITE);

        LinearLayout composerBox = new LinearLayout(this);
        composerBox.setGravity(Gravity.CENTER_VERTICAL);
        composerBox.setPadding(dp(4), dp(2), dp(4), dp(2));
        composerBox.setBackground(bg(Color.rgb(242,242,242), 26));

        Button plus = pill("+");
        plus.setTextSize(27);
        plus.setBackgroundColor(Color.TRANSPARENT);
        composerBox.addView(plus, new LinearLayout.LayoutParams(dp(52), dp(52)));

        composer = new EditText(this);
        composer.setHint("Спросить что угодно");
        composer.setTextSize(16);
        composer.setBackgroundColor(Color.TRANSPARENT);
        composer.setMaxLines(6);
        composer.setPadding(dp(4), dp(10), dp(4), dp(10));
        composerBox.addView(composer, new LinearLayout.LayoutParams(0, -2, 1f));

        Button mic = pill("●");
        mic.setTextSize(14);
        mic.setBackgroundColor(Color.TRANSPARENT);
        composerBox.addView(mic, new LinearLayout.LayoutParams(dp(48), dp(52)));

        Button send = pill("↑");
        send.setTextSize(22);
        send.setTextColor(Color.WHITE);
        send.setBackground(bg(Color.BLACK, 24));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(dp(46), dp(46));
        sp.setMargins(0,0,dp(3),0);
        composerBox.addView(send, sp);

        composerWrap.addView(composerBox, new LinearLayout.LayoutParams(-1, -2));
        main.addView(composerWrap, new LinearLayout.LayoutParams(-1, -2));

        buildDrawer();

        menu.setOnClickListener(v -> showDrawer());
        newChat.setOnClickListener(v -> createChat());
        send.setOnClickListener(v -> sendMessage());
        mic.setOnClickListener(v -> startSpeech());
        plus.setOnClickListener(v -> showPlusMenu(plus));
        headerTitle.setOnClickListener(v -> showModelInfo());

        showEmpty();
        setContentView(shell);
        loadChats();
    }

    private void buildDrawer() {
        scrim = new View(this);
        scrim.setBackgroundColor(0x66000000);
        scrim.setVisibility(View.GONE);
        scrim.setOnClickListener(v -> hideDrawer());
        shell.addView(scrim, new FrameLayout.LayoutParams(-1, -1));

        drawer = new LinearLayout(this);
        drawer.setOrientation(LinearLayout.VERTICAL);
        drawer.setPadding(dp(12), dp(10), dp(12), dp(10));
        drawer.setBackgroundColor(Color.rgb(247,247,247));
        drawer.setVisibility(View.GONE);

        TextView brand = text("ReVerfyx AI", 20, Color.BLACK);
        brand.setTypeface(Typeface.DEFAULT_BOLD);
        brand.setPadding(dp(8), dp(8), dp(8), dp(8));
        drawer.addView(brand, new LinearLayout.LayoutParams(-1, dp(52)));

        drawerSearch = new EditText(this);
        drawerSearch.setHint("Поиск");
        drawerSearch.setSingleLine(true);
        drawerSearch.setBackground(bg(Color.WHITE, 18));
        drawerSearch.setPadding(dp(14),0,dp(14),0);
        LinearLayout.LayoutParams sr = new LinearLayout.LayoutParams(-1, dp(48));
        sr.bottomMargin = dp(8);
        drawer.addView(drawerSearch, sr);

        Button nc = pill("✎   Новый чат");
        nc.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        nc.setPadding(dp(14),0,0,0);
        nc.setBackgroundColor(Color.TRANSPARENT);
        drawer.addView(nc, new LinearLayout.LayoutParams(-1, dp(50)));

        TextView chatsTitle = text("Чаты", 12, Color.GRAY);
        chatsTitle.setPadding(dp(12), dp(10),0,dp(4));
        drawer.addView(chatsTitle, new LinearLayout.LayoutParams(-1, -2));

        ScrollView listScroll = new ScrollView(this);
        drawerChats = new LinearLayout(this);
        drawerChats.setOrientation(LinearLayout.VERTICAL);
        listScroll.addView(drawerChats, new ScrollView.LayoutParams(-1,-2));
        drawer.addView(listScroll, new LinearLayout.LayoutParams(-1,0,1f));

        LinearLayout profile = new LinearLayout(this);
        profile.setGravity(Gravity.CENTER_VERTICAL);
        profile.setPadding(dp(8), dp(8), dp(8), dp(8));
        TextView avatar = text(username.isEmpty() ? "U" : username.substring(0,1).toUpperCase(Locale.ROOT), 16, Color.BLACK);
        avatar.setGravity(Gravity.CENTER);
        avatar.setTypeface(Typeface.DEFAULT_BOLD);
        avatar.setBackground(bg(Color.WHITE, 20));
        profile.addView(avatar, new LinearLayout.LayoutParams(dp(38),dp(38)));
        TextView name = text(username, 15, Color.BLACK);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setPadding(dp(10),0,0,0);
        profile.addView(name, new LinearLayout.LayoutParams(0,dp(48),1f));
        drawer.addView(profile, new LinearLayout.LayoutParams(-1,dp(60)));

        FrameLayout.LayoutParams dlp = new FrameLayout.LayoutParams(dp(320), -1);
        dlp.gravity = Gravity.START;
        shell.addView(drawer, dlp);

        nc.setOnClickListener(v -> {
            hideDrawer();
            createChat();
        });
        profile.setOnClickListener(v -> showAccountDialog());
        drawerSearch.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int st, int c, int a) {}
            public void onTextChanged(CharSequence s, int st, int before, int count) {
                renderDrawerChats(s.toString());
            }
            public void afterTextChanged(Editable e) {}
        });
    }

    private void showDrawer() {
        loadChats();
        scrim.setVisibility(View.VISIBLE);
        drawer.setVisibility(View.VISIBLE);
    }

    private void hideDrawer() {
        drawer.setVisibility(View.GONE);
        scrim.setVisibility(View.GONE);
    }

    private void showModelInfo() {
        new AlertDialog.Builder(this)
                .setTitle("ReAI 0.0.2")
                .setMessage("Собственное ядро ReVerfyx AI.\n\nЧат • история • файлы кода • генерация изображений.\nVision/video будут подключены к ядру следующими модулями.")
                .setPositiveButton("OK", null)
                .show();
    }

    private void showAccountDialog() {
        new AlertDialog.Builder(this)
                .setTitle(username)
                .setItems(new String[]{"Новый чат", "Выйти"}, (d, which) -> {
                    if (which == 0) createChat();
                    else logout();
                })
                .show();
    }

    private void logout() {
        io.execute(() -> {
            try { request("POST", "/v1/auth/logout", new JSONObject(), true); } catch (Exception ignored) {}
            token = "";
            username = "";
            prefs.edit().clear().apply();
            ui.post(this::showAuth);
        });
    }

    private void showEmpty() {
        messages.removeAllViews();
        LinearLayout center = new LinearLayout(this);
        center.setOrientation(LinearLayout.VERTICAL);
        center.setGravity(Gravity.CENTER);
        TextView logo = text("AI", 30, Color.BLACK);
        logo.setGravity(Gravity.CENTER);
        logo.setTypeface(Typeface.DEFAULT_BOLD);
        logo.setBackground(bg(Color.rgb(245,245,245), 35));
        center.addView(logo, new LinearLayout.LayoutParams(dp(70),dp(70)));
        TextView t = text("Чем я могу помочь?", 27, Color.BLACK);
        t.setGravity(Gravity.CENTER);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2);
        lp.topMargin = dp(18);
        center.addView(t, lp);
        TextView s = text("Начни новый чат или открой историю слева.", 14, Color.GRAY);
        s.setGravity(Gravity.CENTER);
        center.addView(s, new LinearLayout.LayoutParams(-1,-2));
        messages.addView(center, new LinearLayout.LayoutParams(-1, dp(360)));
    }

    private void loadChats() {
        io.execute(() -> {
            try {
                JSONObject res = request("GET", "/v1/chats", null, true);
                JSONArray arr = res.getJSONArray("data");
                cachedChats = arr;
                ui.post(() -> renderDrawerChats(drawerSearch == null ? "" : drawerSearch.getText().toString()));
            } catch (Exception e) {
                if (isAuthError(e)) ui.post(this::forceLogin);
            }
        });
    }

    private void renderDrawerChats(String filter) {
        if (drawerChats == null) return;
        drawerChats.removeAllViews();
        String q = filter == null ? "" : filter.toLowerCase(Locale.ROOT).trim();
        for (int i=0;i<cachedChats.length();i++) {
            JSONObject chat = cachedChats.optJSONObject(i);
            if (chat == null) continue;
            String title = chat.optString("title","Новый чат");
            if (!q.isEmpty() && !title.toLowerCase(Locale.ROOT).contains(q)) continue;
            String id = chat.optString("id");
            TextView row = text(title, 15, Color.BLACK);
            row.setSingleLine(true);
            row.setPadding(dp(12),0,dp(8),0);
            row.setBackgroundColor(Color.TRANSPARENT);
            row.setOnClickListener(v -> {
                hideDrawer();
                openChat(id, title);
            });
            row.setOnLongClickListener(v -> {
                chatMenu(id, title);
                return true;
            });
            drawerChats.addView(row, new LinearLayout.LayoutParams(-1,dp(48)));
        }
    }

    private void chatMenu(String id, String title) {
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setItems(new String[]{"Переименовать", "Удалить"}, (d, which) -> {
                    if (which == 0) renameChat(id, title);
                    else deleteChat(id);
                }).show();
    }

    private void renameChat(String id, String old) {
        EditText e = new EditText(this);
        e.setText(old);
        new AlertDialog.Builder(this)
                .setTitle("Название чата")
                .setView(e)
                .setPositiveButton("Сохранить", (d,w) -> io.execute(() -> {
                    try {
                        request("PATCH", "/v1/chats/" + id, new JSONObject().put("title", e.getText().toString()), true);
                        loadChats();
                    } catch (Exception ex) { ui.post(() -> toast(errorText(ex))); }
                }))
                .setNegativeButton("Отмена", null).show();
    }

    private void deleteChat(String id) {
        io.execute(() -> {
            try {
                request("DELETE", "/v1/chats/" + id, null, true);
                if (id.equals(currentChatId)) {
                    currentChatId = null;
                    ui.post(this::showEmpty);
                }
                loadChats();
            } catch (Exception e) { ui.post(() -> toast(errorText(e))); }
        });
    }

    private void createChat() {
        typing.setVisibility(View.VISIBLE);
        io.execute(() -> {
            try {
                JSONObject res = request("POST", "/v1/chats", new JSONObject().put("title","Новый чат"), true);
                currentChatId = res.getString("id");
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    headerTitle.setText("ReAI 0.0.2 ▾");
                    messages.removeAllViews();
                    pendingFileId = null;
                    pendingFileName = null;
                    updateAttachment();
                    composer.requestFocus();
                });
                loadChats();
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void openChat(String id, String title) {
        currentChatId = id;
        headerTitle.setText("ReAI 0.0.2 ▾");
        typing.setVisibility(View.VISIBLE);
        io.execute(() -> {
            try {
                JSONObject res = request("GET", "/v1/chats/" + id + "/messages", null, true);
                JSONArray arr = res.getJSONArray("data");
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    renderMessages(arr);
                });
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void renderMessages(JSONArray arr) {
        messages.removeAllViews();
        if (arr.length() == 0) {
            showEmpty();
            return;
        }
        for (int i=0;i<arr.length();i++) {
            JSONObject m = arr.optJSONObject(i);
            if (m == null) continue;
            addMessageView(m.optString("role"), m.optString("content"), false);
        }
        scrollBottom();
    }

    private void addMessageView(String role, String content, boolean animate) {
        if ("assistant".equals(role) && content.startsWith("[image:") && content.endsWith("]")) {
            String path = content.substring(7, content.length()-1);
            addImageMessage(path);
            return;
        }

        boolean userMsg = "user".equals(role);
        LinearLayout row = new LinearLayout(this);
        row.setGravity(userMsg ? Gravity.END : Gravity.START);
        row.setPadding(0, dp(7),0,dp(7));

        TextView bubble = text(content, 16, Color.BLACK);
        bubble.setTextIsSelectable(true);
        bubble.setPadding(dp(14),dp(11),dp(14),dp(11));
        if (userMsg) {
            bubble.setBackground(bg(Color.rgb(238,238,238), 20));
        } else {
            bubble.setBackgroundColor(Color.TRANSPARENT);
        }
        bubble.setOnLongClickListener(v -> {
            ClipboardManager cm = (ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("ReAI message", content));
            toast("Скопировано");
            return true;
        });

        int max = (int)(getResources().getDisplayMetrics().widthPixels * (userMsg ? .82f : .96f));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-2,-2);
        bp.width = max;
        row.addView(bubble, bp);
        messages.addView(row, new LinearLayout.LayoutParams(-1,-2));
        if (animate) scrollBottom();
    }

    private void addImageMessage(String path) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0,dp(8),0,dp(8));
        TextView label = text("Изображение", 14, Color.DKGRAY);
        box.addView(label, new LinearLayout.LayoutParams(-1,-2));
        ImageView iv = new ImageView(this);
        iv.setAdjustViewBounds(true);
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        iv.setBackground(bg(Color.rgb(245,245,245), 18));
        box.addView(iv, new LinearLayout.LayoutParams(-1,dp(320)));
        messages.addView(box, new LinearLayout.LayoutParams(-1,-2));
        io.execute(() -> {
            try {
                Bitmap bm = downloadBitmap(path);
                ui.post(() -> iv.setImageBitmap(bm));
            } catch (Exception e) {
                ui.post(() -> label.setText("Ошибка изображения: " + errorText(e)));
            }
        });
    }

    private void sendMessage() {
        String content = composer.getText().toString().trim();
        if (content.isEmpty() && pendingFileId == null) return;
        if (currentChatId == null) {
            createAndSend(content);
            return;
        }
        doSend(content);
    }

    private void createAndSend(String content) {
        typing.setVisibility(View.VISIBLE);
        io.execute(() -> {
            try {
                JSONObject res = request("POST","/v1/chats",new JSONObject().put("title","Новый чат"),true);
                currentChatId = res.getString("id");
                ui.post(() -> doSend(content));
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void doSend(String content) {
        final String fid = pendingFileId;
        final String fname = pendingFileName;
        pendingFileId = null;
        pendingFileName = null;
        updateAttachment();
        composer.setText("");

        String visible = content;
        if (fname != null) visible += (visible.isEmpty() ? "" : "\n") + "📎 " + fname;
        addMessageView("user", visible, true);
        typing.setVisibility(View.VISIBLE);

        io.execute(() -> {
            try {
                JSONObject body = new JSONObject().put("content", content).put("max_tokens", 512);
                if (fid != null) body.put("file_ids", new JSONArray().put(fid));
                JSONObject res = request("POST","/v1/chats/" + currentChatId + "/messages",body,true);
                String answer = res.getString("content");
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView("assistant", answer, true);
                });
                loadChats();
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView("assistant", "Ошибка: " + errorText(e), true);
                });
            }
        });
    }

    private void showPlusMenu(View anchor) {
        PopupMenu p = new PopupMenu(this, anchor);
        p.getMenu().add("Прикрепить файл");
        p.getMenu().add("Создать изображение");
        p.getMenu().add("Новый чат");
        p.setOnMenuItemClickListener(item -> {
            String t = item.getTitle().toString();
            if (t.startsWith("Прикрепить")) pickFile();
            else if (t.startsWith("Создать")) imageDialog();
            else createChat();
            return true;
        });
        p.show();
    }

    private void imageDialog() {
        EditText prompt = new EditText(this);
        prompt.setHint("Опиши изображение");
        prompt.setMinLines(3);
        new AlertDialog.Builder(this)
                .setTitle("Создать изображение")
                .setView(prompt)
                .setPositiveButton("Создать", (d,w) -> generateImage(prompt.getText().toString().trim()))
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void generateImage(String prompt) {
        if (prompt.isEmpty()) return;
        if (currentChatId == null) {
            typing.setVisibility(View.VISIBLE);
            io.execute(() -> {
                try {
                    JSONObject res = request("POST","/v1/chats",new JSONObject().put("title","Новый чат"),true);
                    currentChatId = res.getString("id");
                    ui.post(() -> generateImage(prompt));
                } catch (Exception e) {
                    ui.post(() -> { typing.setVisibility(View.GONE); toast(errorText(e)); });
                }
            });
            return;
        }

        addMessageView("user","Создай изображение: " + prompt,true);
        typing.setVisibility(View.VISIBLE);
        io.execute(() -> {
            try {
                JSONObject body = new JSONObject().put("prompt",prompt).put("steps",32).put("chat_id",currentChatId);
                JSONObject res = request("POST","/v1/images/generations",body,true);
                String path = res.getJSONArray("data").getJSONObject(0).getString("url");
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addImageMessage(path);
                    scrollBottom();
                });
                loadChats();
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView("assistant","Ошибка генерации: " + errorText(e),true);
                });
            }
        });
    }

    private void pickFile() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.setType("*/*");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(i, PICK_FILE);
    }

    private void startSpeech() {
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
            i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Говорите");
            startActivityForResult(i, SPEECH);
        } catch (Exception e) {
            toast("Голосовой ввод недоступен");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if (resultCode != RESULT_OK || data == null) return;

        if (requestCode == SPEECH) {
            java.util.ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) composer.setText(results.get(0));
            return;
        }

        if (requestCode == PICK_FILE) {
            Uri uri = data.getData();
            if (uri != null) uploadFile(uri);
        }
    }

    private void uploadFile(Uri uri) {
        typing.setVisibility(View.VISIBLE);
        io.execute(() -> {
            try {
                String name = fileName(uri);
                String mime = getContentResolver().getType(uri);
                if (mime == null) mime = "application/octet-stream";
                byte[] raw;
                try (InputStream in = getContentResolver().openInputStream(uri)) {
                    if (in == null) throw new RuntimeException("Не удалось открыть файл");
                    raw = readBytes(in, 12 * 1024 * 1024 + 1);
                }
                if (raw.length > 12 * 1024 * 1024) throw new RuntimeException("Файл больше 12 МБ");
                JSONObject body = new JSONObject()
                        .put("name",name)
                        .put("mime",mime)
                        .put("data_base64", Base64.encodeToString(raw, Base64.NO_WRAP));
                if (currentChatId != null) body.put("chat_id", currentChatId);
                JSONObject res = request("POST","/v1/files",body,true);
                pendingFileId = res.getString("id");
                pendingFileName = res.getString("name");
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    updateAttachment();
                });
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void updateAttachment() {
        if (pendingFileId == null) {
            attachLabel.setVisibility(View.GONE);
            attachLabel.setText("");
        } else {
            attachLabel.setVisibility(View.VISIBLE);
            attachLabel.setText("📎 " + pendingFileName + "  • будет отправлен со следующим сообщением");
            attachLabel.setOnClickListener(v -> {
                pendingFileId = null;
                pendingFileName = null;
                updateAttachment();
            });
        }
    }

    private String fileName(Uri uri) {
        String name = "file.bin";
        android.database.Cursor c = getContentResolver().query(uri,null,null,null,null);
        if (c != null) {
            try {
                int idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (idx >= 0 && c.moveToFirst()) name = c.getString(idx);
            } finally { c.close(); }
        }
        return name;
    }

    private JSONObject request(String method, String path, JSONObject body, boolean auth) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(GATEWAY + path).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setRequestMethod(method);
        c.setRequestProperty("Accept","application/json");
        if (auth && !token.isEmpty()) c.setRequestProperty("Authorization","Bearer " + token);
        if (body != null) {
            byte[] raw = body.toString().getBytes(StandardCharsets.UTF_8);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type","application/json; charset=utf-8");
            c.setFixedLengthStreamingMode(raw.length);
            try (OutputStream out = c.getOutputStream()) { out.write(raw); }
        }
        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        String response = readString(stream);
        c.disconnect();
        if (code < 200 || code >= 300) throw new RuntimeException("HTTP " + code + ": " + response);
        return response.isEmpty() ? new JSONObject() : new JSONObject(response);
    }

    private Bitmap downloadBitmap(String path) throws Exception {
        HttpURLConnection c = (HttpURLConnection)new URL(GATEWAY + path).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setRequestProperty("Authorization","Bearer " + token);
        int code = c.getResponseCode();
        if (code != 200) {
            String msg = readString(c.getErrorStream());
            c.disconnect();
            throw new RuntimeException("HTTP " + code + ": " + msg);
        }
        Bitmap b;
        try (InputStream in = c.getInputStream()) { b = BitmapFactory.decodeStream(in); }
        c.disconnect();
        if (b == null) throw new RuntimeException("Некорректное изображение");
        return b;
    }

    private static String readString(InputStream in) throws Exception {
        if (in == null) return "";
        return new String(readBytes(in, 4 * 1024 * 1024), StandardCharsets.UTF_8);
    }

    private static byte[] readBytes(InputStream in, int max) throws Exception {
        try (InputStream src = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = src.read(buf)) >= 0) {
                out.write(buf,0,n);
                if (out.size() > max) break;
            }
            return out.toByteArray();
        }
    }

    private void scrollBottom() {
        messagesScroll.post(() -> messagesScroll.fullScroll(View.FOCUS_DOWN));
    }

    private void toast(String s) {
        Toast.makeText(this,s,Toast.LENGTH_LONG).show();
    }

    private static String errorText(Exception e) {
        String s = e.getMessage();
        return s == null || s.isEmpty() ? e.getClass().getSimpleName() : s;
    }

    private static boolean isAuthError(Exception e) {
        String s = e.getMessage();
        return s != null && s.contains("HTTP 401");
    }

    private void forceLogin() {
        token = "";
        username = "";
        prefs.edit().clear().apply();
        showAuth();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }
}
