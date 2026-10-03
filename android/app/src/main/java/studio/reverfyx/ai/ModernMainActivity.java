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
import android.view.Window;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
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
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ModernMainActivity extends Activity {
    private static final String GATEWAY = "http://31.77.14.194:8090";
    private static final String PREFS = "reai";
    private static final int PICK_FILE = 7001;
    private static final int PICK_PHOTO = 7003;
    private static final int SPEECH = 7002;

    private static final int BLACK = 0xff111111;
    private static final int MUTED = 0xff707070;
    private static final int BG = 0xffffffff;
    private static final int SOFT = 0xfff4f4f4;
    private static final int SOFT_2 = 0xfff8f8f8;
    private static final int LINE = 0xffe7e7e7;
    private static final int BLUE = 0xff2f6fec;

    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private String token = "";
    private String username = "";
    private String currentChatId;
    private String currentChatTitle = "Новый чат";
    private String pendingFileId;
    private String pendingFileName;
    private String currentMode = "Instant";

    private FrameLayout shell;
    private View scrim;
    private LinearLayout drawer;
    private int drawerWidth;
    private LinearLayout drawerChats;
    private EditText drawerSearch;
    private boolean drawerOpen;

    private ScrollView messagesScroll;
    private LinearLayout messages;
    private EditText composer;
    private TextView attachLabel;
    private ProgressBar typing;
    private TextView headerTitle;
    private TextView modePill;
    private FrameLayout sendButton;
    private JSONArray cachedChats = new JSONArray();

    private View sheetScrim;
    private LinearLayout activeSheet;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        setupSystemBars();

        prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        token = prefs.getString("token", "");
        username = prefs.getString("username", "");
        currentMode = prefs.getString("mode", "Instant");

        if (token.isEmpty()) showAuth();
        else showApp();
    }

    @Override
    public void onBackPressed() {
        if (activeSheet != null) {
            dismissSheet();
            return;
        }
        if (drawerOpen) {
            hideDrawer();
            return;
        }
        super.onBackPressed();
    }

    private void setupSystemBars() {
        Window w = getWindow();
        w.setStatusBarColor(Color.WHITE);
        w.setNavigationBarColor(Color.WHITE);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = w.getInsetsController();
            if (c != null) {
                c.setSystemBarsAppearance(
                        WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS |
                                WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                        WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS |
                                WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
                );
            }
        } else {
            w.getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR |
                            View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            );
        }
    }

    private int dp(int n) {
        return Math.round(n * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable round(int color, int radiusDp) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radiusDp));
        return d;
    }

    private GradientDrawable stroke(int fill, int radiusDp, int strokeColor) {
        GradientDrawable d = round(fill, radiusDp);
        d.setStroke(dp(1), strokeColor);
        return d;
    }

    private TextView tv(String value, float size, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        v.setGravity(Gravity.CENTER_VERTICAL);
        if (bold) v.setTypeface(Typeface.DEFAULT_BOLD);
        return v;
    }

    private FrameLayout iconButton(int kind, int boxDp, int iconDp) {
        FrameLayout box = new FrameLayout(this);
        box.setClickable(true);
        box.setFocusable(true);
        box.setBackground(round(Color.TRANSPARENT, boxDp / 2));
        LineIconView icon = new LineIconView(this, kind);
        box.addView(icon, new FrameLayout.LayoutParams(dp(iconDp), dp(iconDp), Gravity.CENTER));
        box.setTag(icon);
        return box;
    }

    private LineIconView iconOf(FrameLayout box) {
        return (LineIconView) box.getTag();
    }

    private LinearLayout actionRow(int iconKind, String title, String subtitle) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(5), dp(14), dp(5));
        row.setClickable(true);

        LineIconView icon = new LineIconView(this, iconKind);
        row.addView(icon, new LinearLayout.LayoutParams(dp(28), dp(28)));

        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(14), 0, 0, 0);

        TextView t = tv(title, 16, BLACK, false);
        labels.addView(t, new LinearLayout.LayoutParams(-1, dp(subtitle == null ? 44 : 26)));

        if (subtitle != null) {
            TextView s = tv(subtitle, 12, MUTED, false);
            labels.addView(s, new LinearLayout.LayoutParams(-1, dp(20)));
        }

        row.addView(labels, new LinearLayout.LayoutParams(0, dp(subtitle == null ? 44 : 48), 1f));
        return row;
    }

    private void showAuth() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(24), dp(72), dp(24), dp(24));
        root.setBackgroundColor(Color.WHITE);

        TextView mark = tv("R", 24, Color.WHITE, true);
        mark.setGravity(Gravity.CENTER);
        mark.setBackground(round(BLACK, 22));
        root.addView(mark, new LinearLayout.LayoutParams(dp(44), dp(44)));

        TextView title = tv("ReVerfyx AI", 28, BLACK, true);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(-1, dp(58));
        titleLp.topMargin = dp(12);
        root.addView(title, titleLp);

        TextView subtitle = tv("Войдите, чтобы продолжить", 15, MUTED, false);
        subtitle.setGravity(Gravity.CENTER);
        root.addView(subtitle, new LinearLayout.LayoutParams(-1, dp(36)));

        EditText user = authField("Username");
        LinearLayout.LayoutParams userLp = new LinearLayout.LayoutParams(-1, dp(56));
        userLp.topMargin = dp(28);
        root.addView(user, userLp);

        EditText pass = authField("Пароль");
        pass.setInputType(0x00000081);
        LinearLayout.LayoutParams passLp = new LinearLayout.LayoutParams(-1, dp(56));
        passLp.topMargin = dp(10);
        root.addView(pass, passLp);

        TextView login = tv("Продолжить", 16, Color.WHITE, true);
        login.setGravity(Gravity.CENTER);
        login.setBackground(round(BLACK, 28));
        LinearLayout.LayoutParams loginLp = new LinearLayout.LayoutParams(-1, dp(56));
        loginLp.topMargin = dp(18);
        root.addView(login, loginLp);

        TextView register = tv("Создать аккаунт", 15, BLACK, false);
        register.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams regLp = new LinearLayout.LayoutParams(-1, dp(50));
        regLp.topMargin = dp(4);
        root.addView(register, regLp);

        ProgressBar progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(-2, -2));

        login.setOnClickListener(v ->
                auth(false, user.getText().toString(), pass.getText().toString(), progress));
        register.setOnClickListener(v ->
                auth(true, user.getText().toString(), pass.getText().toString(), progress));

        setContentView(root);
    }

    private EditText authField(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(16);
        e.setSingleLine(true);
        e.setPadding(dp(16), 0, dp(16), 0);
        e.setBackground(stroke(Color.WHITE, 14, 0xffdddddd));
        return e;
    }

    private void auth(boolean register, String user, String pass, ProgressBar progress) {
        user = user.trim();
        if (user.length() < 3 || pass.length() < 8) {
            toast("Username от 3 символов, пароль от 8");
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
                prefs.edit()
                        .putString("token", token)
                        .putString("username", username)
                        .apply();
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
        shell.setBackgroundColor(BG);

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setBackgroundColor(BG);
        shell.addView(page, new FrameLayout.LayoutParams(-1, -1));

        page.addView(buildHeader(), new LinearLayout.LayoutParams(-1, dp(58)));

        messagesScroll = new ScrollView(this);
        messagesScroll.setFillViewport(true);
        messagesScroll.setClipToPadding(false);

        messages = new LinearLayout(this);
        messages.setOrientation(LinearLayout.VERTICAL);
        messages.setPadding(dp(16), dp(6), dp(16), dp(12));
        messagesScroll.addView(messages, new ScrollView.LayoutParams(-1, -2));

        page.addView(messagesScroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        typing = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        typing.setIndeterminate(true);
        typing.setVisibility(View.GONE);
        page.addView(typing, new LinearLayout.LayoutParams(-1, dp(2)));

        attachLabel = tv("", 12, MUTED, false);
        attachLabel.setPadding(dp(16), dp(2), dp(16), dp(2));
        attachLabel.setVisibility(View.GONE);
        page.addView(attachLabel, new LinearLayout.LayoutParams(-1, -2));

        page.addView(buildComposer(), new LinearLayout.LayoutParams(-1, -2));

        buildDrawer();
        showEmpty();
        setContentView(shell);
        loadChats();
    }

    private View buildHeader() {
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(6), dp(3), dp(6), dp(3));

        FrameLayout menu = iconButton(LineIconView.MENU, 48, 26);
        bar.addView(menu, new LinearLayout.LayoutParams(dp(48), dp(48)));

        headerTitle = tv("ReVerfyx AI", 17, BLACK, true);
        headerTitle.setGravity(Gravity.CENTER);
        bar.addView(headerTitle, new LinearLayout.LayoutParams(0, dp(48), 1f));

        FrameLayout compose = iconButton(LineIconView.EDIT, 48, 25);
        FrameLayout more = iconButton(LineIconView.MORE, 48, 24);
        bar.addView(compose, new LinearLayout.LayoutParams(dp(48), dp(48)));
        bar.addView(more, new LinearLayout.LayoutParams(dp(48), dp(48)));

        menu.setOnClickListener(v -> showDrawer());
        compose.setOnClickListener(v -> createChat());
        more.setOnClickListener(v -> showChatMenu());
        headerTitle.setOnClickListener(v -> showModePicker());

        return bar;
    }

    private View buildComposer() {
        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        outer.setPadding(dp(10), dp(2), dp(10), dp(10));

        modePill = tv(modeLabel(), 12, MUTED, false);
        modePill.setGravity(Gravity.CENTER);
        modePill.setPadding(dp(11), 0, dp(11), 0);
        modePill.setBackground(stroke(SOFT_2, 14, LINE));
        modePill.setOnClickListener(v -> showModePicker());

        LinearLayout modeRow = new LinearLayout(this);
        modeRow.setGravity(Gravity.START);
        modeRow.addView(modePill, new LinearLayout.LayoutParams(-2, dp(28)));
        outer.addView(modeRow, new LinearLayout.LayoutParams(-1, dp(30)));

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(10), dp(8), dp(8), dp(7));
        box.setBackground(stroke(0xfff7f7f7, 26, 0xffe9e9e9));

        composer = new EditText(this);
        composer.setHint("Спросить что угодно");
        composer.setHintTextColor(0xff777777);
        composer.setTextColor(BLACK);
        composer.setTextSize(17);
        composer.setBackgroundColor(Color.TRANSPARENT);
        composer.setPadding(dp(4), 0, dp(4), 0);
        composer.setMinLines(1);
        composer.setMaxLines(7);
        box.addView(composer, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout controls = new LinearLayout(this);
        controls.setGravity(Gravity.CENTER_VERTICAL);
        controls.setPadding(0, dp(4), 0, 0);

        FrameLayout plus = iconButton(LineIconView.PLUS, 42, 25);
        controls.addView(plus, new LinearLayout.LayoutParams(dp(42), dp(42)));

        TextView tools = tv("Инструменты", 12, MUTED, false);
        tools.setGravity(Gravity.CENTER);
        tools.setPadding(dp(10), 0, dp(10), 0);
        tools.setBackground(stroke(Color.TRANSPARENT, 15, LINE));
        LinearLayout.LayoutParams toolsLp = new LinearLayout.LayoutParams(-2, dp(31));
        toolsLp.leftMargin = dp(4);
        controls.addView(tools, toolsLp);

        View spacer = new View(this);
        controls.addView(spacer, new LinearLayout.LayoutParams(0, dp(1), 1f));

        FrameLayout mic = iconButton(LineIconView.MIC, 42, 25);
        controls.addView(mic, new LinearLayout.LayoutParams(dp(42), dp(42)));

        sendButton = iconButton(LineIconView.SEND, 42, 22);
        sendButton.setBackground(round(BLACK, 22));
        iconOf(sendButton).setIconColor(Color.WHITE);
        sendButton.setAlpha(.42f);
        LinearLayout.LayoutParams sendLp = new LinearLayout.LayoutParams(dp(42), dp(42));
        sendLp.leftMargin = dp(3);
        controls.addView(sendButton, sendLp);

        box.addView(controls, new LinearLayout.LayoutParams(-1, dp(46)));
        outer.addView(box, new LinearLayout.LayoutParams(-1, -2));

        plus.setOnClickListener(v -> showAttachSheet());
        tools.setOnClickListener(v -> showToolsSheet());
        mic.setOnClickListener(v -> startSpeech());
        sendButton.setOnClickListener(v -> sendMessage());

        composer.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int st, int c, int a) {}
            public void onTextChanged(CharSequence s, int st, int before, int count) {
                updateSendState();
            }
            public void afterTextChanged(Editable e) {}
        });

        return outer;
    }

    private String modeLabel() {
        if ("Thinking".equals(currentMode)) return "◌ Thinking";
        if ("Pro".equals(currentMode)) return "◉ Pro";
        return "Instant";
    }

    private void updateSendState() {
        if (sendButton == null || composer == null) return;
        boolean enabled = composer.getText().toString().trim().length() > 0 || pendingFileId != null;
        sendButton.setAlpha(enabled ? 1f : .42f);
    }

    private void buildDrawer() {
        scrim = new View(this);
        scrim.setBackgroundColor(0x52000000);
        scrim.setVisibility(View.GONE);
        scrim.setAlpha(0f);
        scrim.setOnClickListener(v -> hideDrawer());
        shell.addView(scrim, new FrameLayout.LayoutParams(-1, -1));

        drawerWidth = Math.min(
                dp(340),
                (int) (getResources().getDisplayMetrics().widthPixels * .88f)
        );

        drawer = new LinearLayout(this);
        drawer.setOrientation(LinearLayout.VERTICAL);
        drawer.setPadding(dp(12), dp(10), dp(12), dp(10));
        drawer.setBackgroundColor(0xfffafafa);

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);

        TextView brand = tv("ReVerfyx AI", 20, BLACK, true);
        top.addView(brand, new LinearLayout.LayoutParams(0, dp(48), 1f));

        FrameLayout searchBtn = iconButton(LineIconView.SEARCH, 44, 24);
        top.addView(searchBtn, new LinearLayout.LayoutParams(dp(44), dp(44)));
        drawer.addView(top, new LinearLayout.LayoutParams(-1, dp(50)));

        drawerSearch = new EditText(this);
        drawerSearch.setHint("Поиск чатов");
        drawerSearch.setSingleLine(true);
        drawerSearch.setTextSize(15);
        drawerSearch.setPadding(dp(14), 0, dp(14), 0);
        drawerSearch.setBackground(round(SOFT, 18));
        drawerSearch.setVisibility(View.GONE);

        LinearLayout.LayoutParams searchLp = new LinearLayout.LayoutParams(-1, dp(44));
        searchLp.bottomMargin = dp(8);
        drawer.addView(drawerSearch, searchLp);

        HorizontalScrollView quickScroll = new HorizontalScrollView(this);
        quickScroll.setHorizontalScrollBarEnabled(false);

        LinearLayout quick = new LinearLayout(this);
        quick.setOrientation(LinearLayout.HORIZONTAL);
        quick.setPadding(0, dp(2), 0, dp(8));

        TextView images = quickChip("Изображения");
        TextView codex = quickChip("Код");
        TextView apps = quickChip("Инструменты");

        quick.addView(images, quickLp());
        quick.addView(codex, quickLp());
        quick.addView(apps, quickLp());

        quickScroll.addView(quick, new HorizontalScrollView.LayoutParams(-2, dp(48)));
        drawer.addView(quickScroll, new LinearLayout.LayoutParams(-1, dp(50)));

        LinearLayout newChat = actionRow(LineIconView.EDIT, "Новый чат", null);
        newChat.setBackground(round(0xfff0f0f0, 13));
        drawer.addView(newChat, new LinearLayout.LayoutParams(-1, dp(52)));

        TextView chatsLabel = tv("Чаты", 13, MUTED, true);
        chatsLabel.setPadding(dp(10), dp(14), 0, dp(4));
        drawer.addView(chatsLabel, new LinearLayout.LayoutParams(-1, dp(44)));

        ScrollView chatScroll = new ScrollView(this);
        drawerChats = new LinearLayout(this);
        drawerChats.setOrientation(LinearLayout.VERTICAL);
        chatScroll.addView(drawerChats, new ScrollView.LayoutParams(-1, -2));
        drawer.addView(chatScroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout profile = new LinearLayout(this);
        profile.setGravity(Gravity.CENTER_VERTICAL);
        profile.setPadding(dp(8), dp(5), dp(6), dp(5));
        profile.setBackground(round(0xfff1f1f1, 14));

        TextView avatar = tv(
                username.isEmpty() ? "R" : username.substring(0, 1).toUpperCase(Locale.ROOT),
                15, Color.WHITE, true
        );
        avatar.setGravity(Gravity.CENTER);
        avatar.setBackground(round(BLACK, 18));
        profile.addView(avatar, new LinearLayout.LayoutParams(dp(36), dp(36)));

        TextView name = tv(username, 14, BLACK, true);
        name.setPadding(dp(10), 0, 0, 0);
        profile.addView(name, new LinearLayout.LayoutParams(0, dp(44), 1f));

        LineIconView profileMore = new LineIconView(this, LineIconView.MORE);
        profile.addView(profileMore, new LinearLayout.LayoutParams(dp(28), dp(28)));
        drawer.addView(profile, new LinearLayout.LayoutParams(-1, dp(56)));

        FrameLayout.LayoutParams drawerLp = new FrameLayout.LayoutParams(drawerWidth, -1, Gravity.START);
        drawer.setTranslationX(-drawerWidth);
        drawer.setVisibility(View.GONE);
        shell.addView(drawer, drawerLp);

        searchBtn.setOnClickListener(v -> {
            boolean show = drawerSearch.getVisibility() != View.VISIBLE;
            drawerSearch.setVisibility(show ? View.VISIBLE : View.GONE);
            if (show) drawerSearch.requestFocus();
        });

        newChat.setOnClickListener(v -> {
            hideDrawer();
            createChat();
        });

        images.setOnClickListener(v -> {
            hideDrawer();
            imageDialog();
        });

        codex.setOnClickListener(v -> {
            hideDrawer();
            pickFile();
        });

        apps.setOnClickListener(v -> {
            hideDrawer();
            showToolsSheet();
        });

        profile.setOnClickListener(v -> showAccountSheet());

        drawerSearch.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int st, int c, int a) {}
            public void onTextChanged(CharSequence s, int st, int before, int count) {
                renderDrawerChats(s.toString());
            }
            public void afterTextChanged(Editable e) {}
        });
    }

    private TextView quickChip(String title) {
        TextView t = tv(title, 14, BLACK, false);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(14), 0, dp(14), 0);
        t.setBackground(stroke(Color.WHITE, 18, LINE));
        return t;
    }

    private LinearLayout.LayoutParams quickLp() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-2, dp(38));
        p.rightMargin = dp(8);
        return p;
    }

    private void showDrawer() {
        loadChats();
        drawerOpen = true;
        drawer.setVisibility(View.VISIBLE);
        scrim.setVisibility(View.VISIBLE);

        drawer.animate()
                .translationX(0)
                .setDuration(220)
                .setInterpolator(new DecelerateInterpolator())
                .start();

        scrim.animate().alpha(1f).setDuration(170).start();
    }

    private void hideDrawer() {
        if (!drawerOpen) return;
        drawerOpen = false;

        drawer.animate()
                .translationX(-drawerWidth)
                .setDuration(190)
                .withEndAction(() -> drawer.setVisibility(View.GONE))
                .start();

        scrim.animate()
                .alpha(0f)
                .setDuration(150)
                .withEndAction(() -> scrim.setVisibility(View.GONE))
                .start();
    }

    private void showEmpty() {
        messages.removeAllViews();

        LinearLayout center = new LinearLayout(this);
        center.setOrientation(LinearLayout.VERTICAL);
        center.setGravity(Gravity.CENTER);

        TextView mark = tv("R", 21, Color.WHITE, true);
        mark.setGravity(Gravity.CENTER);
        mark.setBackground(round(BLACK, 24));
        center.addView(mark, new LinearLayout.LayoutParams(dp(48), dp(48)));

        TextView title = tv("Чем я могу помочь?", 26, BLACK, true);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(-1, dp(62));
        titleLp.topMargin = dp(8);
        center.addView(title, titleLp);

        HorizontalScrollView suggestionsScroll = new HorizontalScrollView(this);
        suggestionsScroll.setHorizontalScrollBarEnabled(false);

        LinearLayout suggestions = new LinearLayout(this);
        suggestions.setGravity(Gravity.CENTER);
        suggestions.setPadding(dp(2), 0, dp(2), 0);

        TextView s1 = suggestion("Объясни тему");
        TextView s2 = suggestion("Помоги с кодом");
        TextView s3 = suggestion("Создай изображение");

        suggestions.addView(s1, suggestionLp());
        suggestions.addView(s2, suggestionLp());
        suggestions.addView(s3, suggestionLp());

        suggestionsScroll.addView(suggestions, new HorizontalScrollView.LayoutParams(-2, dp(44)));
        center.addView(suggestionsScroll, new LinearLayout.LayoutParams(-1, dp(48)));

        messages.addView(center, new LinearLayout.LayoutParams(-1, dp(360)));

        s1.setOnClickListener(v -> {
            composer.setText("Объясни мне простыми словами: ");
            composer.requestFocus();
            composer.setSelection(composer.length());
        });

        s2.setOnClickListener(v -> {
            composer.setText("Помоги разобраться с этим кодом: ");
            composer.requestFocus();
            composer.setSelection(composer.length());
        });

        s3.setOnClickListener(v -> imageDialog());
    }

    private TextView suggestion(String title) {
        TextView t = tv(title, 13, BLACK, false);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(13), 0, dp(13), 0);
        t.setBackground(stroke(Color.WHITE, 18, LINE));
        return t;
    }

    private LinearLayout.LayoutParams suggestionLp() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-2, dp(38));
        p.rightMargin = dp(8);
        return p;
    }

    private void showModePicker() {
        LinearLayout sheet = baseSheet("Режим");

        String[] names = {"Instant", "Thinking", "Pro"};
        String[] descriptions = {
                "Быстрые ответы",
                "Больше времени на рассуждение",
                "Максимальный режим"
        };

        for (int i = 0; i < names.length; i++) {
            String name = names[i];
            int icon = "Instant".equals(name)
                    ? LineIconView.CLOCK
                    : ("Thinking".equals(name) ? LineIconView.EFFORT : LineIconView.CODE);

            LinearLayout row = actionRow(icon, name, descriptions[i]);

            if (name.equals(currentMode)) {
                LineIconView check = new LineIconView(this, LineIconView.CHECK);
                check.setIconColor(BLUE);
                row.addView(check, new LinearLayout.LayoutParams(dp(24), dp(24)));
            }

            row.setOnClickListener(v -> {
                currentMode = name;
                prefs.edit().putString("mode", currentMode).apply();
                modePill.setText(modeLabel());
                dismissSheet();
            });

            sheet.addView(row, new LinearLayout.LayoutParams(-1, dp(64)));
        }

        showSheet(sheet);
    }

    private void showAttachSheet() {
        LinearLayout sheet = baseSheet("Добавить");

        LinearLayout photo = actionRow(LineIconView.PHOTO, "Фото", "Выбрать из галереи");
        LinearLayout file = actionRow(LineIconView.FILE, "Файлы", "Документы и исходный код");
        LinearLayout image = actionRow(LineIconView.IMAGE, "Создать изображение", null);

        sheet.addView(photo, new LinearLayout.LayoutParams(-1, dp(64)));
        sheet.addView(file, new LinearLayout.LayoutParams(-1, dp(64)));
        sheet.addView(image, new LinearLayout.LayoutParams(-1, dp(56)));

        photo.setOnClickListener(v -> {
            dismissSheet();
            pickPhoto();
        });

        file.setOnClickListener(v -> {
            dismissSheet();
            pickFile();
        });

        image.setOnClickListener(v -> {
            dismissSheet();
            imageDialog();
        });

        showSheet(sheet);
    }

    private void showToolsSheet() {
        LinearLayout sheet = baseSheet("Инструменты");

        LinearLayout thinking = actionRow(
                LineIconView.EFFORT,
                "Размышлять глубже",
                "Переключить на Thinking"
        );
        LinearLayout images = actionRow(
                LineIconView.IMAGE,
                "Изображения",
                "Сгенерировать по описанию"
        );
        LinearLayout code = actionRow(
                LineIconView.CODE,
                "Код",
                "Загрузить исходники"
        );

        sheet.addView(thinking, new LinearLayout.LayoutParams(-1, dp(64)));
        sheet.addView(images, new LinearLayout.LayoutParams(-1, dp(64)));
        sheet.addView(code, new LinearLayout.LayoutParams(-1, dp(64)));

        thinking.setOnClickListener(v -> {
            currentMode = "Thinking";
            prefs.edit().putString("mode", currentMode).apply();
            modePill.setText(modeLabel());
            dismissSheet();
        });

        images.setOnClickListener(v -> {
            dismissSheet();
            imageDialog();
        });

        code.setOnClickListener(v -> {
            dismissSheet();
            pickFile();
        });

        showSheet(sheet);
    }

    private void showChatMenu() {
        LinearLayout sheet = baseSheet(currentChatTitle);

        LinearLayout share = actionRow(LineIconView.SHARE, "Поделиться", null);
        LinearLayout pin = actionRow(LineIconView.PIN, "Закрепить", null);
        LinearLayout search = actionRow(LineIconView.SEARCH, "Найти в чате", null);
        LinearLayout archive = actionRow(LineIconView.ARCHIVE, "Архивировать", null);
        LinearLayout trash = actionRow(LineIconView.TRASH, "Удалить", null);

        ((LineIconView) trash.getChildAt(0)).setIconColor(0xffd76d6d);
        ((TextView) ((LinearLayout) trash.getChildAt(1)).getChildAt(0))
                .setTextColor(0xffd76d6d);

        sheet.addView(share, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(pin, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(search, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(archive, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(trash, new LinearLayout.LayoutParams(-1, dp(56)));

        share.setOnClickListener(v -> {
            dismissSheet();
            shareCurrentChat();
        });

        pin.setOnClickListener(v -> {
            dismissSheet();
            toast("Чат закреплён локально");
        });

        search.setOnClickListener(v -> {
            dismissSheet();
            showDrawer();
            drawerSearch.setVisibility(View.VISIBLE);
            drawerSearch.requestFocus();
        });

        archive.setOnClickListener(v -> {
            dismissSheet();
            toast("Архивирование будет подключено к серверу позже");
        });

        trash.setOnClickListener(v -> {
            dismissSheet();
            if (currentChatId != null) deleteChat(currentChatId);
        });

        showSheet(sheet);
    }

    private void showAccountSheet() {
        LinearLayout sheet = baseSheet(username);

        LinearLayout settings = actionRow(LineIconView.PLUGIN, "Настройки", null);
        LinearLayout newChat = actionRow(LineIconView.EDIT, "Новый чат", null);
        LinearLayout logout = actionRow(LineIconView.TRASH, "Выйти", null);

        sheet.addView(settings, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(newChat, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(logout, new LinearLayout.LayoutParams(-1, dp(56)));

        settings.setOnClickListener(v -> {
            dismissSheet();
            toast("Настройки ReVerfyx AI");
        });

        newChat.setOnClickListener(v -> {
            dismissSheet();
            createChat();
        });

        logout.setOnClickListener(v -> {
            dismissSheet();
            logout();
        });

        showSheet(sheet);
    }

    private LinearLayout baseSheet(String title) {
        LinearLayout sheet = new LinearLayout(this);
        sheet.setOrientation(LinearLayout.VERTICAL);
        sheet.setPadding(dp(12), dp(8), dp(12), dp(18));

        View handle = new View(this);
        handle.setBackground(round(0xffd7d7d7, 3));
        LinearLayout handleRow = new LinearLayout(this);
        handleRow.setGravity(Gravity.CENTER);
        handleRow.addView(handle, new LinearLayout.LayoutParams(dp(42), dp(4)));
        sheet.addView(handleRow, new LinearLayout.LayoutParams(-1, dp(18)));

        TextView heading = tv(title == null ? "" : title, 17, BLACK, true);
        heading.setPadding(dp(10), dp(2), dp(10), dp(6));
        sheet.addView(heading, new LinearLayout.LayoutParams(-1, dp(46)));
        return sheet;
    }

    private void showSheet(LinearLayout sheet) {
        dismissSheet();

        sheetScrim = new View(this);
        sheetScrim.setBackgroundColor(0x4d000000);
        sheetScrim.setAlpha(0f);
        shell.addView(sheetScrim, new FrameLayout.LayoutParams(-1, -1));

        activeSheet = sheet;
        activeSheet.setBackground(round(Color.WHITE, 28));

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM);
        lp.setMargins(dp(8), dp(8), dp(8), dp(8));
        shell.addView(activeSheet, lp);

        activeSheet.setTranslationY(dp(440));
        activeSheet.animate()
                .translationY(0)
                .setDuration(230)
                .setInterpolator(new DecelerateInterpolator())
                .start();

        sheetScrim.animate().alpha(1f).setDuration(170).start();
        sheetScrim.setOnClickListener(v -> dismissSheet());
    }

    private void dismissSheet() {
        if (activeSheet == null) return;

        LinearLayout oldSheet = activeSheet;
        View oldScrim = sheetScrim;
        activeSheet = null;
        sheetScrim = null;

        oldSheet.animate()
                .translationY(dp(440))
                .setDuration(180)
                .withEndAction(() -> {
                    if (oldSheet.getParent() != null) shell.removeView(oldSheet);
                })
                .start();

        if (oldScrim != null) {
            oldScrim.animate()
                    .alpha(0f)
                    .setDuration(150)
                    .withEndAction(() -> {
                        if (oldScrim.getParent() != null) shell.removeView(oldScrim);
                    })
                    .start();
        }
    }

    private void loadChats() {
        io.execute(() -> {
            try {
                JSONObject res = request("GET", "/v1/chats", null, true);
                cachedChats = res.getJSONArray("data");
                ui.post(() -> renderDrawerChats(
                        drawerSearch == null ? "" : drawerSearch.getText().toString()
                ));
            } catch (Exception e) {
                if (isAuthError(e)) ui.post(this::forceLogin);
            }
        });
    }

    private void renderDrawerChats(String filter) {
        if (drawerChats == null) return;

        drawerChats.removeAllViews();
        String q = filter == null ? "" : filter.trim().toLowerCase(Locale.ROOT);

        for (int i = 0; i < cachedChats.length(); i++) {
            JSONObject chat = cachedChats.optJSONObject(i);
            if (chat == null) continue;

            String id = chat.optString("id");
            String title = chat.optString("title", "Новый чат");

            if (!q.isEmpty() && !title.toLowerCase(Locale.ROOT).contains(q)) continue;

            TextView row = tv(title, 15, BLACK, false);
            row.setSingleLine(true);
            row.setPadding(dp(12), 0, dp(10), 0);

            if (id.equals(currentChatId)) row.setBackground(round(0xffeeeeee, 10));

            row.setOnClickListener(v -> {
                hideDrawer();
                openChat(id, title);
            });

            row.setOnLongClickListener(v -> {
                showChatRowMenu(id, title);
                return true;
            });

            drawerChats.addView(row, new LinearLayout.LayoutParams(-1, dp(46)));
        }
    }

    private void showChatRowMenu(String id, String title) {
        LinearLayout sheet = baseSheet(title);

        LinearLayout rename = actionRow(LineIconView.EDIT, "Переименовать", null);
        LinearLayout trash = actionRow(LineIconView.TRASH, "Удалить", null);

        sheet.addView(rename, new LinearLayout.LayoutParams(-1, dp(56)));
        sheet.addView(trash, new LinearLayout.LayoutParams(-1, dp(56)));

        rename.setOnClickListener(v -> {
            dismissSheet();
            renameChat(id, title);
        });

        trash.setOnClickListener(v -> {
            dismissSheet();
            deleteChat(id);
        });

        showSheet(sheet);
    }

    private void renameChat(String id, String oldTitle) {
        EditText e = authField("Название");
        e.setText(oldTitle);
        e.setSelection(e.length());

        new AlertDialog.Builder(this)
                .setTitle("Переименовать")
                .setView(e)
                .setPositiveButton("Сохранить", (d, w) -> io.execute(() -> {
                    try {
                        JSONObject body = new JSONObject().put("title", e.getText().toString());
                        request("PATCH", "/v1/chats/" + id, body, true);
                        if (id.equals(currentChatId)) {
                            currentChatTitle = e.getText().toString();
                        }
                        loadChats();
                    } catch (Exception ex) {
                        ui.post(() -> toast(errorText(ex)));
                    }
                }))
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void deleteChat(String id) {
        io.execute(() -> {
            try {
                request("DELETE", "/v1/chats/" + id, null, true);

                if (id.equals(currentChatId)) {
                    currentChatId = null;
                    currentChatTitle = "Новый чат";
                    ui.post(() -> {
                        headerTitle.setText("ReVerfyx AI");
                        showEmpty();
                    });
                }

                loadChats();
            } catch (Exception e) {
                ui.post(() -> toast(errorText(e)));
            }
        });
    }

    private void createChat() {
        typing.setVisibility(View.VISIBLE);

        io.execute(() -> {
            try {
                JSONObject res = request(
                        "POST",
                        "/v1/chats",
                        new JSONObject().put("title", "Новый чат"),
                        true
                );

                currentChatId = res.getString("id");
                currentChatTitle = "Новый чат";

                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    messages.removeAllViews();
                    pendingFileId = null;
                    pendingFileName = null;
                    updateAttachment();
                    composer.setText("");
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
        currentChatTitle = title;
        typing.setVisibility(View.VISIBLE);

        io.execute(() -> {
            try {
                JSONObject res = request(
                        "GET",
                        "/v1/chats/" + id + "/messages",
                        null,
                        true
                );

                JSONArray data = res.getJSONArray("data");

                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    renderMessages(data);
                });
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    toast(errorText(e));
                });
            }
        });
    }

    private void renderMessages(JSONArray data) {
        messages.removeAllViews();

        if (data.length() == 0) {
            showEmpty();
            return;
        }

        for (int i = 0; i < data.length(); i++) {
            JSONObject msg = data.optJSONObject(i);
            if (msg == null) continue;
            addMessageView(
                    msg.optString("role"),
                    msg.optString("content"),
                    false
            );
        }

        scrollBottom();
    }

    private void addMessageView(String role, String content, boolean animate) {
        if ("assistant".equals(role)
                && content.startsWith("[image:")
                && content.endsWith("]")) {
            String path = content.substring(7, content.length() - 1);
            addImageMessage(path);
            return;
        }

        boolean user = "user".equals(role);

        LinearLayout row = new LinearLayout(this);
        row.setGravity(user ? Gravity.END : Gravity.START);
        row.setPadding(0, dp(7), 0, dp(7));

        LinearLayout bubbleWrap = new LinearLayout(this);
        bubbleWrap.setOrientation(LinearLayout.VERTICAL);
        bubbleWrap.setPadding(
                user ? dp(14) : dp(2),
                user ? dp(10) : dp(4),
                user ? dp(14) : dp(2),
                user ? dp(10) : dp(4)
        );

        if (user) bubbleWrap.setBackground(round(0xffeeeeee, 20));

        TextView body = tv(content, 16, BLACK, false);
        body.setTextIsSelectable(true);
        body.setLineSpacing(0, 1.08f);
        bubbleWrap.addView(body, new LinearLayout.LayoutParams(-1, -2));

        if (!user) {
            LinearLayout actions = new LinearLayout(this);
            actions.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            actions.setPadding(0, dp(5), 0, 0);

            FrameLayout copy = iconButton(LineIconView.FILE, 34, 19);
            actions.addView(copy, new LinearLayout.LayoutParams(dp(34), dp(34)));
            bubbleWrap.addView(actions, new LinearLayout.LayoutParams(-1, dp(38)));

            copy.setOnClickListener(v -> copyText(content));
        }

        int maxWidth = (int) (
                getResources().getDisplayMetrics().widthPixels *
                        (user ? .82f : .94f)
        );

        LinearLayout.LayoutParams bubbleLp = new LinearLayout.LayoutParams(maxWidth, -2);
        row.addView(bubbleWrap, bubbleLp);
        messages.addView(row, new LinearLayout.LayoutParams(-1, -2));

        body.setOnLongClickListener(v -> {
            copyText(content);
            return true;
        });

        if (animate) scrollBottom();
    }

    private void copyText(String content) {
        ClipboardManager cm =
                (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("ReVerfyx AI", content));
        toast("Скопировано");
    }

    private void addImageMessage(String path) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(2), dp(8), dp(2), dp(8));

        TextView label = tv("Изображение", 13, MUTED, false);
        box.addView(label, new LinearLayout.LayoutParams(-1, dp(28)));

        ImageView image = new ImageView(this);
        image.setAdjustViewBounds(true);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setBackground(round(SOFT, 18));
        box.addView(image, new LinearLayout.LayoutParams(-1, dp(320)));

        messages.addView(box, new LinearLayout.LayoutParams(-1, -2));

        io.execute(() -> {
            try {
                Bitmap b = downloadBitmap(path);
                ui.post(() -> image.setImageBitmap(b));
            } catch (Exception e) {
                ui.post(() -> label.setText("Ошибка изображения"));
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
                JSONObject res = request(
                        "POST",
                        "/v1/chats",
                        new JSONObject().put("title", "Новый чат"),
                        true
                );

                currentChatId = res.getString("id");
                currentChatTitle = "Новый чат";

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
        final String fileId = pendingFileId;
        final String fileName = pendingFileName;

        pendingFileId = null;
        pendingFileName = null;
        updateAttachment();

        composer.setText("");

        String visible = content;
        if (fileName != null) {
            visible += (visible.isEmpty() ? "" : "\n") + "📎 " + fileName;
        }

        addMessageView("user", visible, true);
        typing.setVisibility(View.VISIBLE);

        io.execute(() -> {
            try {
                int maxTokens = "Pro".equals(currentMode)
                        ? 1024
                        : ("Thinking".equals(currentMode) ? 768 : 384);

                JSONObject body = new JSONObject()
                        .put("content", content)
                        .put("max_tokens", maxTokens);

                if (fileId != null) {
                    body.put("file_ids", new JSONArray().put(fileId));
                }

                JSONObject res = request(
                        "POST",
                        "/v1/chats/" + currentChatId + "/messages",
                        body,
                        true
                );

                String answer = res.getString("content");

                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView("assistant", answer, true);
                });

                loadChats();
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView(
                            "assistant",
                            "Ошибка: " + errorText(e),
                            true
                    );
                });
            }
        });
    }

    private void imageDialog() {
        EditText prompt = authField("Опишите изображение");
        prompt.setSingleLine(false);
        prompt.setMinLines(3);
        prompt.setMaxLines(5);

        new AlertDialog.Builder(this)
                .setTitle("Создать изображение")
                .setView(prompt)
                .setPositiveButton(
                        "Создать",
                        (d, w) -> generateImage(prompt.getText().toString().trim())
                )
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void generateImage(String prompt) {
        if (prompt.isEmpty()) return;

        if (currentChatId == null) {
            typing.setVisibility(View.VISIBLE);

            io.execute(() -> {
                try {
                    JSONObject res = request(
                            "POST",
                            "/v1/chats",
                            new JSONObject().put("title", "Новый чат"),
                            true
                    );

                    currentChatId = res.getString("id");
                    currentChatTitle = "Новый чат";

                    ui.post(() -> generateImage(prompt));
                } catch (Exception e) {
                    ui.post(() -> {
                        typing.setVisibility(View.GONE);
                        toast(errorText(e));
                    });
                }
            });
            return;
        }

        addMessageView("user", "Создай изображение: " + prompt, true);
        typing.setVisibility(View.VISIBLE);

        io.execute(() -> {
            try {
                int steps = "Pro".equals(currentMode)
                        ? 64
                        : ("Thinking".equals(currentMode) ? 48 : 32);

                JSONObject body = new JSONObject()
                        .put("prompt", prompt)
                        .put("steps", steps)
                        .put("chat_id", currentChatId);

                JSONObject res = request(
                        "POST",
                        "/v1/images/generations",
                        body,
                        true
                );

                String path = res.getJSONArray("data")
                        .getJSONObject(0)
                        .getString("url");

                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addImageMessage(path);
                    scrollBottom();
                });

                loadChats();
            } catch (Exception e) {
                ui.post(() -> {
                    typing.setVisibility(View.GONE);
                    addMessageView(
                            "assistant",
                            "Ошибка генерации: " + errorText(e),
                            true
                    );
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

    private void pickPhoto() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.setType("image/*");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(i, PICK_PHOTO);
    }

    private void startSpeech() {
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            );
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
            i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Говорите");
            startActivityForResult(i, SPEECH);
        } catch (Exception e) {
            toast("Голосовой ввод недоступен");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (resultCode != RESULT_OK || data == null) return;

        if (requestCode == SPEECH) {
            ArrayList<String> values =
                    data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);

            if (values != null && !values.isEmpty()) {
                composer.setText(values.get(0));
                composer.setSelection(composer.length());
            }
            return;
        }

        if (requestCode == PICK_FILE || requestCode == PICK_PHOTO) {
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

                if (raw.length > 12 * 1024 * 1024) {
                    throw new RuntimeException("Файл больше 12 МБ");
                }

                JSONObject body = new JSONObject()
                        .put("name", name)
                        .put("mime", mime)
                        .put(
                                "data_base64",
                                Base64.encodeToString(raw, Base64.NO_WRAP)
                        );

                if (currentChatId != null) {
                    body.put("chat_id", currentChatId);
                }

                JSONObject res = request(
                        "POST",
                        "/v1/files",
                        body,
                        true
                );

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
            attachLabel.setText("📎 " + pendingFileName + "   ×");
            attachLabel.setOnClickListener(v -> {
                pendingFileId = null;
                pendingFileName = null;
                updateAttachment();
            });
        }
        updateSendState();
    }

    private String fileName(Uri uri) {
        String name = "file.bin";

        android.database.Cursor c =
                getContentResolver().query(uri, null, null, null, null);

        if (c != null) {
            try {
                int index = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0 && c.moveToFirst()) name = c.getString(index);
            } finally {
                c.close();
            }
        }

        return name;
    }

    private void shareCurrentChat() {
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("text/plain");
        i.putExtra(Intent.EXTRA_TEXT, "ReVerfyx AI — " + currentChatTitle);
        startActivity(Intent.createChooser(i, "Поделиться"));
    }

    private void logout() {
        io.execute(() -> {
            try {
                request("POST", "/v1/auth/logout", new JSONObject(), true);
            } catch (Exception ignored) {
            }

            token = "";
            username = "";
            prefs.edit().remove("token").remove("username").apply();
            ui.post(this::showAuth);
        });
    }

    private JSONObject request(
            String method,
            String path,
            JSONObject body,
            boolean auth
    ) throws Exception {
        HttpURLConnection c =
                (HttpURLConnection) new URL(GATEWAY + path).openConnection();

        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setRequestMethod(method);
        c.setRequestProperty("Accept", "application/json");

        if (auth && !token.isEmpty()) {
            c.setRequestProperty("Authorization", "Bearer " + token);
        }

        if (body != null) {
            byte[] raw = body.toString().getBytes(StandardCharsets.UTF_8);
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            c.setFixedLengthStreamingMode(raw.length);

            try (OutputStream out = c.getOutputStream()) {
                out.write(raw);
            }
        }

        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300
                ? c.getInputStream()
                : c.getErrorStream();

        String response = readString(stream);
        c.disconnect();

        if (code < 200 || code >= 300) {
            throw new RuntimeException("HTTP " + code + ": " + response);
        }

        return response.isEmpty()
                ? new JSONObject()
                : new JSONObject(response);
    }

    private Bitmap downloadBitmap(String path) throws Exception {
        HttpURLConnection c =
                (HttpURLConnection) new URL(GATEWAY + path).openConnection();

        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setRequestProperty("Authorization", "Bearer " + token);

        int code = c.getResponseCode();

        if (code != 200) {
            String message = readString(c.getErrorStream());
            c.disconnect();
            throw new RuntimeException("HTTP " + code + ": " + message);
        }

        Bitmap bitmap;
        try (InputStream in = c.getInputStream()) {
            bitmap = BitmapFactory.decodeStream(in);
        }

        c.disconnect();

        if (bitmap == null) {
            throw new RuntimeException("Некорректное изображение");
        }

        return bitmap;
    }

    private static String readString(InputStream in) throws Exception {
        if (in == null) return "";
        return new String(
                readBytes(in, 4 * 1024 * 1024),
                StandardCharsets.UTF_8
        );
    }

    private static byte[] readBytes(InputStream in, int max) throws Exception {
        try (
                InputStream src = in;
                ByteArrayOutputStream out = new ByteArrayOutputStream()
        ) {
            byte[] buffer = new byte[8192];
            int n;

            while ((n = src.read(buffer)) >= 0) {
                out.write(buffer, 0, n);
                if (out.size() > max) break;
            }

            return out.toByteArray();
        }
    }

    private void scrollBottom() {
        if (messagesScroll != null) {
            messagesScroll.post(() ->
                    messagesScroll.fullScroll(View.FOCUS_DOWN)
            );
        }
    }

    private void toast(String value) {
        Toast.makeText(this, value, Toast.LENGTH_LONG).show();
    }

    private static String errorText(Exception e) {
        String s = e.getMessage();
        return s == null || s.isEmpty()
                ? e.getClass().getSimpleName()
                : s;
    }

    private static boolean isAuthError(Exception e) {
        String s = e.getMessage();
        return s != null && s.contains("HTTP 401");
    }

    private void forceLogin() {
        token = "";
        username = "";
        prefs.edit().remove("token").remove("username").apply();
        showAuth();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }
}
