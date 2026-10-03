package studio.reverfyx.ai;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String PREFS = "reai";
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final JSONArray conversation = new JSONArray();

    private EditText serverInput;
    private EditText keyInput;
    private EditText chatInput;
    private EditText imagePrompt;
    private TextView transcript;
    private TextView status;
    private ImageView imageView;
    private ProgressBar progress;
    private LinearLayout chatPanel;
    private LinearLayout imagePanel;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        loadSettings();
        showChat();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView label(String text, float size) {
        TextView v = new TextView(this);
        v.setText(text);
        v.setTextSize(size);
        return v;
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        return b;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(12), dp(14), dp(12));

        TextView title = label("ReVerfyx AI 0.0.2", 24);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        TextView subtitle = label("Свой AI на твоём VPS", 13);
        subtitle.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(subtitle, new LinearLayout.LayoutParams(-1, -2));

        serverInput = new EditText(this);
        serverInput.setHint("http://VPS_IP:8080");
        serverInput.setSingleLine(true);
        root.addView(serverInput, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout authRow = new LinearLayout(this);
        authRow.setOrientation(LinearLayout.HORIZONTAL);
        keyInput = new EditText(this);
        keyInput.setHint("API key");
        keyInput.setSingleLine(true);
        keyInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        authRow.addView(keyInput, new LinearLayout.LayoutParams(0, -2, 1f));

        Button save = button("Сохранить");
        save.setOnClickListener(v -> saveSettings());
        authRow.addView(save, new LinearLayout.LayoutParams(-2, -2));
        root.addView(authRow, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout tabs = new LinearLayout(this);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        Button chatTab = button("Чат");
        Button imageTab = button("Фото");
        chatTab.setOnClickListener(v -> showChat());
        imageTab.setOnClickListener(v -> showImages());
        tabs.addView(chatTab, new LinearLayout.LayoutParams(0, -2, 1f));
        tabs.addView(imageTab, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(tabs, new LinearLayout.LayoutParams(-1, -2));

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));

        chatPanel = new LinearLayout(this);
        chatPanel.setOrientation(LinearLayout.VERTICAL);

        ScrollView scroll = new ScrollView(this);
        transcript = label("AI готов. Напиши сообщение.\n", 16);
        transcript.setPadding(dp(4), dp(8), dp(4), dp(8));
        scroll.addView(transcript, new ScrollView.LayoutParams(-1, -2));
        chatPanel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout sendRow = new LinearLayout(this);
        sendRow.setOrientation(LinearLayout.HORIZONTAL);
        chatInput = new EditText(this);
        chatInput.setHint("Сообщение...");
        chatInput.setMaxLines(4);
        sendRow.addView(chatInput, new LinearLayout.LayoutParams(0, -2, 1f));
        Button send = button("➤");
        send.setOnClickListener(v -> sendChat());
        sendRow.addView(send, new LinearLayout.LayoutParams(dp(64), -2));
        chatPanel.addView(sendRow, new LinearLayout.LayoutParams(-1, -2));
        content.addView(chatPanel, new FrameLayout.LayoutParams(-1, -1));

        imagePanel = new LinearLayout(this);
        imagePanel.setOrientation(LinearLayout.VERTICAL);
        imagePanel.setPadding(0, dp(8), 0, 0);

        imagePrompt = new EditText(this);
        imagePrompt.setHint("Что нарисовать?");
        imagePrompt.setMinLines(2);
        imagePrompt.setMaxLines(5);
        imagePanel.addView(imagePrompt, new LinearLayout.LayoutParams(-1, -2));

        Button generate = button("Сгенерировать изображение");
        generate.setOnClickListener(v -> generateImage());
        imagePanel.addView(generate, new LinearLayout.LayoutParams(-1, -2));

        progress = new ProgressBar(this);
        progress.setIndeterminate(true);
        progress.setVisibility(View.GONE);
        imagePanel.addView(progress, new LinearLayout.LayoutParams(-1, -2));

        status = label("", 14);
        imagePanel.addView(status, new LinearLayout.LayoutParams(-1, -2));

        imageView = new ImageView(this);
        imageView.setAdjustViewBounds(true);
        imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imagePanel.addView(imageView, new LinearLayout.LayoutParams(-1, 0, 1f));
        content.addView(imagePanel, new FrameLayout.LayoutParams(-1, -1));

        setContentView(root);
    }

    private void loadSettings() {
        SharedPreferences p = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        serverInput.setText(p.getString("server", "http://10.0.2.2:8080"));
        keyInput.setText(p.getString("key", ""));
    }

    private void saveSettings() {
        String server = normalizedServer();
        getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString("server", server)
                .putString("key", keyInput.getText().toString().trim())
                .apply();
        Toast.makeText(this, "Сохранено", Toast.LENGTH_SHORT).show();
    }

    private String normalizedServer() {
        String s = serverInput.getText().toString().trim();
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s;
    }

    private void showChat() {
        if (chatPanel == null) return;
        chatPanel.setVisibility(View.VISIBLE);
        imagePanel.setVisibility(View.GONE);
    }

    private void showImages() {
        chatPanel.setVisibility(View.GONE);
        imagePanel.setVisibility(View.VISIBLE);
    }

    private void appendChat(String who, String text) {
        transcript.append("\n" + who + ": " + text + "\n");
    }

    private void sendChat() {
        final String text = chatInput.getText().toString().trim();
        if (text.isEmpty()) return;
        final String server = normalizedServer();
        if (server.isEmpty()) {
            Toast.makeText(this, "Укажи адрес VPS", Toast.LENGTH_SHORT).show();
            return;
        }

        chatInput.setText("");
        appendChat("Ты", text);
        try {
            conversation.put(new JSONObject().put("role", "user").put("content", text));
        } catch (Exception e) {
            appendChat("Ошибка", e.getMessage());
            return;
        }

        io.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("messages", conversation);
                body.put("max_tokens", 384);
                body.put("temperature", 0.85);
                body.put("top_k", 40);

                JSONObject res = new JSONObject(postJson(server + "/v1/chat/completions", body.toString()));
                String answer = res.getJSONArray("choices")
                        .getJSONObject(0)
                        .getJSONObject("message")
                        .getString("content");

                conversation.put(new JSONObject().put("role", "assistant").put("content", answer));
                main.post(() -> appendChat("AI", answer));
            } catch (Exception e) {
                main.post(() -> appendChat("Ошибка", readableError(e)));
            }
        });
    }

    private void generateImage() {
        final String promptText = imagePrompt.getText().toString().trim();
        final String server = normalizedServer();
        if (promptText.isEmpty()) return;
        if (server.isEmpty()) {
            Toast.makeText(this, "Укажи адрес VPS", Toast.LENGTH_SHORT).show();
            return;
        }

        progress.setVisibility(View.VISIBLE);
        status.setText("Генерация...");
        imageView.setImageDrawable(null);

        io.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("prompt", promptText);
                body.put("steps", 32);
                JSONObject res = new JSONObject(postJson(server + "/v1/images/generations", body.toString()));
                String relative = res.getJSONArray("data").getJSONObject(0).getString("url");
                Bitmap bitmap = downloadBitmap(server + relative);
                main.post(() -> {
                    progress.setVisibility(View.GONE);
                    status.setText("Готово");
                    imageView.setImageBitmap(bitmap);
                });
            } catch (Exception e) {
                main.post(() -> {
                    progress.setVisibility(View.GONE);
                    status.setText("Ошибка: " + readableError(e));
                });
            }
        });
    }

    private String postJson(String target, String json) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(target).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        String key = keyInput.getText().toString().trim();
        if (!key.isEmpty()) c.setRequestProperty("X-API-Key", key);
        c.setDoOutput(true);

        byte[] body = json.getBytes(StandardCharsets.UTF_8);
        c.setFixedLengthStreamingMode(body.length);
        try (OutputStream out = c.getOutputStream()) {
            out.write(body);
        }

        int code = c.getResponseCode();
        InputStream in = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        String response = readString(in);
        c.disconnect();
        if (code < 200 || code >= 300) {
            throw new RuntimeException("HTTP " + code + ": " + response);
        }
        return response;
    }

    private Bitmap downloadBitmap(String target) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(target).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        String key = keyInput.getText().toString().trim();
        if (!key.isEmpty()) c.setRequestProperty("X-API-Key", key);
        int code = c.getResponseCode();
        if (code != 200) {
            String msg = readString(c.getErrorStream());
            c.disconnect();
            throw new RuntimeException("HTTP " + code + ": " + msg);
        }
        Bitmap bmp;
        try (InputStream in = c.getInputStream()) {
            bmp = BitmapFactory.decodeStream(in);
        }
        c.disconnect();
        if (bmp == null) throw new RuntimeException("Не удалось открыть PNG");
        return bmp;
    }

    private static String readString(InputStream in) throws Exception {
        if (in == null) return "";
        try (InputStream src = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = src.read(buf)) >= 0) out.write(buf, 0, n);
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static String readableError(Exception e) {
        String s = e.getMessage();
        return s == null || s.isEmpty() ? e.getClass().getSimpleName() : s;
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }
}
