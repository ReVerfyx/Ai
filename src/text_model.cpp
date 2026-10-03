#include "text_model.hpp"
#include <filesystem>
#include <iostream>
#include <iterator>
#include <numeric>

namespace reai {

TextModel::TextModel(uint32_t hidden, uint32_t seed): hidden_(hidden) {
    if (hidden_ == 0) throw std::runtime_error("hidden must be > 0");
    std::mt19937 rng(seed);
    wxh_.resize(static_cast<size_t>(hidden_) * VOCAB);
    whh_.resize(static_cast<size_t>(hidden_) * hidden_);
    why_.resize(static_cast<size_t>(VOCAB) * hidden_);
    bh_.assign(hidden_, 0.0f);
    by_.assign(VOCAB, 0.0f);
    fill_normal(wxh_, rng, 0.02f);
    fill_normal(whh_, rng, 0.02f / std::sqrt(static_cast<float>(hidden_)));
    fill_normal(why_, rng, 0.02f / std::sqrt(static_cast<float>(hidden_)));
}

Vec TextModel::step(uint8_t token, const Vec& hprev, Vec* logits) const {
    Vec h(hidden_, 0.0f);
    for (uint32_t i = 0; i < hidden_; ++i) {
        float s = wxh_[static_cast<size_t>(i) * VOCAB + token] + bh_[i];
        const size_t row = static_cast<size_t>(i) * hidden_;
        for (uint32_t j = 0; j < hidden_; ++j) s += whh_[row + j] * hprev[j];
        h[i] = std::tanh(s);
    }
    if (logits) {
        logits->assign(VOCAB, 0.0f);
        for (uint32_t o = 0; o < VOCAB; ++o) {
            float s = by_[o];
            const size_t row = static_cast<size_t>(o) * hidden_;
            for (uint32_t j = 0; j < hidden_; ++j) s += why_[row + j] * h[j];
            (*logits)[o] = s;
        }
    }
    return h;
}

void TextModel::train_file(const std::string& path, int epochs, int seq_len, float lr, const std::string& save_path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open corpus: " + path);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(in)), {});
    if (data.size() < static_cast<size_t>(seq_len + 2)) throw std::runtime_error("corpus is too small");

    Vec gwxh(wxh_.size()), gwhh(whh_.size()), gwhy(why_.size()), gbh(bh_.size()), gby(by_.size());
    AdamState awxh(wxh_.size()), awhh(whh_.size()), awhy(why_.size()), abh(bh_.size()), aby(by_.size());

    std::mt19937 rng(12345);
    std::uniform_int_distribution<size_t> start_dist(0, data.size() - static_cast<size_t>(seq_len) - 2);
    const size_t steps_per_epoch = std::max<size_t>(1, std::min<size_t>(2000, data.size() / static_cast<size_t>(seq_len)));

    for (int epoch = 1; epoch <= epochs; ++epoch) {
        double epoch_loss = 0.0;
        for (size_t iter = 0; iter < steps_per_epoch; ++iter) {
            std::fill(gwxh.begin(), gwxh.end(), 0.0f);
            std::fill(gwhh.begin(), gwhh.end(), 0.0f);
            std::fill(gwhy.begin(), gwhy.end(), 0.0f);
            std::fill(gbh.begin(), gbh.end(), 0.0f);
            std::fill(gby.begin(), gby.end(), 0.0f);

            const size_t pos = start_dist(rng);
            std::vector<Vec> hs(static_cast<size_t>(seq_len) + 1, Vec(hidden_, 0.0f));
            std::vector<Vec> probs(static_cast<size_t>(seq_len));
            std::vector<uint8_t> xs(static_cast<size_t>(seq_len)), ys(static_cast<size_t>(seq_len));

            for (int t = 0; t < seq_len; ++t) {
                xs[t] = data[pos + static_cast<size_t>(t)];
                ys[t] = data[pos + static_cast<size_t>(t) + 1];
                Vec logits;
                hs[t + 1] = step(xs[t], hs[t], &logits);
                probs[t] = softmax(logits);
                epoch_loss += -std::log(std::max(probs[t][ys[t]], 1e-12f));
            }

            Vec dhnext(hidden_, 0.0f);
            for (int t = seq_len - 1; t >= 0; --t) {
                Vec dy = probs[t];
                dy[ys[t]] -= 1.0f;
                for (uint32_t o = 0; o < VOCAB; ++o) {
                    gby[o] += dy[o];
                    const size_t row = static_cast<size_t>(o) * hidden_;
                    for (uint32_t j = 0; j < hidden_; ++j) gwhy[row + j] += dy[o] * hs[t + 1][j];
                }

                Vec dh = dhnext;
                for (uint32_t j = 0; j < hidden_; ++j) {
                    float s = 0.0f;
                    for (uint32_t o = 0; o < VOCAB; ++o) s += why_[static_cast<size_t>(o) * hidden_ + j] * dy[o];
                    dh[j] += s;
                }
                Vec dhraw(hidden_);
                for (uint32_t i = 0; i < hidden_; ++i) {
                    dhraw[i] = (1.0f - hs[t + 1][i] * hs[t + 1][i]) * dh[i];
                    gbh[i] += dhraw[i];
                    gwxh[static_cast<size_t>(i) * VOCAB + xs[t]] += dhraw[i];
                    const size_t row = static_cast<size_t>(i) * hidden_;
                    for (uint32_t j = 0; j < hidden_; ++j) gwhh[row + j] += dhraw[i] * hs[t][j];
                }
                std::fill(dhnext.begin(), dhnext.end(), 0.0f);
                for (uint32_t j = 0; j < hidden_; ++j) {
                    float s = 0.0f;
                    for (uint32_t i = 0; i < hidden_; ++i) s += whh_[static_cast<size_t>(i) * hidden_ + j] * dhraw[i];
                    dhnext[j] = s;
                }
            }

            const float inv = 1.0f / static_cast<float>(seq_len);
            for (auto* g : {&gwxh, &gwhh, &gwhy, &gbh, &gby}) {
                for (auto& x : *g) x *= inv;
                clip_grad(*g, 1.0f);
            }
            adam_update(wxh_, gwxh, awxh, lr);
            adam_update(whh_, gwhh, awhh, lr);
            adam_update(why_, gwhy, awhy, lr);
            adam_update(bh_, gbh, abh, lr);
            adam_update(by_, gby, aby, lr);
        }
        const double avg = epoch_loss / static_cast<double>(steps_per_epoch * static_cast<size_t>(seq_len));
        std::cerr << "[text] epoch " << epoch << "/" << epochs << " loss=" << avg << "\n";
        if (!save_path.empty()) save(save_path);
    }
}

std::string TextModel::generate(const std::string& prompt, int tokens, float temperature, int top_k, uint32_t seed) const {
    std::mt19937 rng(seed);
    Vec h(hidden_, 0.0f), logits;
    uint8_t current = prompt.empty() ? static_cast<uint8_t>(' ') : static_cast<uint8_t>(prompt[0]);
    if (!prompt.empty()) {
        for (unsigned char c : prompt) {
            current = c;
            h = step(current, h, &logits);
        }
    } else {
        h = step(current, h, &logits);
    }
    std::string out = prompt;
    for (int i = 0; i < tokens; ++i) {
        auto p = softmax(logits, temperature);
        int next = sample_discrete(std::move(p), rng, top_k);
        out.push_back(static_cast<char>(next));
        current = static_cast<uint8_t>(next);
        h = step(current, h, &logits);
    }
    return out;
}

void TextModel::save(const std::string& path) const {
    const auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot save model: " + path);
    const char magic[8] = {'R','E','A','I','T','X','T','1'};
    out.write(magic, sizeof(magic));
    write_u32(out, hidden_);
    write_vec(out, wxh_); write_vec(out, whh_); write_vec(out, why_); write_vec(out, bh_); write_vec(out, by_);
}

TextModel TextModel::load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open model: " + path);
    char magic[8]{}; in.read(magic, sizeof(magic));
    if (std::string(magic, 8) != "REAITXT1") throw std::runtime_error("bad text checkpoint");
    uint32_t hidden = read_u32(in);
    TextModel m(hidden, 1);
    m.wxh_ = read_vec(in); m.whh_ = read_vec(in); m.why_ = read_vec(in); m.bh_ = read_vec(in); m.by_ = read_vec(in);
    return m;
}

} // namespace reai
