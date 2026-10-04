#include "unicode_text_model.hpp"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <random>
#include <unordered_map>
#include <unordered_set>

namespace reai {

static constexpr float EXPERT_SCALE = 0.25f;

static std::vector<uint32_t> utf8_decode(const std::string& s) {
    std::vector<uint32_t> out;
    size_t i = 0;
    while (i < s.size()) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) {
            out.push_back(c);
            ++i;
            continue;
        }

        uint32_t cp = 0;
        size_t need = 0;
        if ((c & 0xE0) == 0xC0) { cp = c & 0x1F; need = 1; }
        else if ((c & 0xF0) == 0xE0) { cp = c & 0x0F; need = 2; }
        else if ((c & 0xF8) == 0xF0) { cp = c & 0x07; need = 3; }
        else {
            out.push_back(0xFFFD);
            ++i;
            continue;
        }

        if (i + need >= s.size()) {
            out.push_back(0xFFFD);
            break;
        }

        bool ok = true;
        for (size_t j = 1; j <= need; ++j) {
            const unsigned char cc = static_cast<unsigned char>(s[i + j]);
            if ((cc & 0xC0) != 0x80) { ok = false; break; }
            cp = (cp << 6) | (cc & 0x3F);
        }

        if (!ok ||
            (need == 1 && cp < 0x80) ||
            (need == 2 && cp < 0x800) ||
            (need == 3 && cp < 0x10000) ||
            cp > 0x10FFFF ||
            (cp >= 0xD800 && cp <= 0xDFFF)) {
            out.push_back(0xFFFD);
            ++i;
            continue;
        }

        out.push_back(cp);
        i += need + 1;
    }
    return out;
}

static void utf8_append(std::string& out, uint32_t cp) {
    if (cp == 0) return;
    if (cp <= 0x7F) {
        out.push_back(static_cast<char>(cp));
    } else if (cp <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp <= 0xFFFF) {
        if (cp >= 0xD800 && cp <= 0xDFFF) cp = 0xFFFD;
        out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp <= 0x10FFFF) {
        out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

static std::unordered_map<uint32_t, uint32_t>
make_index(const std::vector<uint32_t>& vocab) {
    std::unordered_map<uint32_t, uint32_t> index;
    index.reserve(vocab.size() * 2);
    for (uint32_t i = 0; i < vocab.size(); ++i) index[vocab[i]] = i;
    return index;
}

static std::vector<uint32_t>
build_vocab(const std::string& corpus_path, uint32_t limit) {
    if (limit < 256) throw std::runtime_error("unicode vocab must be >= 256");

    std::ifstream in(corpus_path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open corpus: " + corpus_path);
    std::string raw((std::istreambuf_iterator<char>(in)), {});
    const auto cps = utf8_decode(raw);

    std::unordered_map<uint32_t, uint64_t> freq;
    freq.reserve(4096);
    for (uint32_t cp : cps) {
        if (cp != 0 && cp != 0xFFFD) ++freq[cp];
    }

    std::vector<uint32_t> vocab;
    vocab.reserve(limit);
    std::unordered_set<uint32_t> seen;

    auto add = [&](uint32_t cp) {
        if (vocab.size() >= limit || seen.count(cp)) return;
        seen.insert(cp);
        vocab.push_back(cp);
    };

    add(0);      // unknown
    add('\n');
    add('\t');
    add(' ');

    for (uint32_t cp = 33; cp <= 126; ++cp) add(cp);
    for (uint32_t cp = 0x0400; cp <= 0x052F; ++cp) add(cp);

    std::vector<std::pair<uint32_t, uint64_t>> ranked(freq.begin(), freq.end());
    std::sort(ranked.begin(), ranked.end(), [](const auto& a, const auto& b) {
        if (a.second != b.second) return a.second > b.second;
        return a.first < b.first;
    });

    for (const auto& [cp, count] : ranked) {
        (void)count;
        add(cp);
        if (vocab.size() >= limit) break;
    }

    uint32_t filler = 0x0100u;
    while (vocab.size() < limit && filler <= 0x10FFFF) {
        if (!(filler >= 0xD800 && filler <= 0xDFFF)) add(filler);
        ++filler;
    }

    return vocab;
}

UnicodeTextModel::UnicodeTextModel(std::vector<uint32_t> vocab,
                                   uint32_t dim, uint32_t experts,
                                   uint32_t ff, uint32_t seed)
    : dim_(dim), experts_(experts), ff_(ff), vocab_(std::move(vocab)) {
    if (!dim_ || !experts_ || !ff_ || vocab_.size() < 2)
        throw std::runtime_error("invalid unicode model shape");

    std::mt19937 rng(seed);
    const size_t vocab_size = vocab_.size();

    emb_.resize(vocab_size * dim_);
    whh_.resize(static_cast<size_t>(dim_) * dim_);
    bh_.assign(dim_, 0.0f);
    why_.resize(vocab_size * dim_);
    by_.assign(vocab_size, 0.0f);

    w1_.resize(static_cast<size_t>(experts_) * ff_ * dim_);
    b1_.assign(static_cast<size_t>(experts_) * ff_, 0.0f);
    w2_.resize(static_cast<size_t>(experts_) * dim_ * ff_);
    b2_.assign(static_cast<size_t>(experts_) * dim_, 0.0f);

    fill_normal(emb_, rng, 0.035f);
    fill_normal(whh_, rng, 0.025f / std::sqrt(static_cast<float>(dim_)));
    fill_normal(why_, rng, 0.025f / std::sqrt(static_cast<float>(dim_)));
    fill_normal(w1_, rng, 0.02f / std::sqrt(static_cast<float>(dim_)));
    fill_normal(w2_, rng, 0.02f / std::sqrt(static_cast<float>(ff_)));
}

UnicodeTextModel UnicodeTextModel::create_from_corpus(
    const std::string& corpus_path, uint32_t vocab_size, uint32_t dim,
    uint32_t experts, uint32_t ff, uint32_t seed) {
    return UnicodeTextModel(
        build_vocab(corpus_path, vocab_size), dim, experts, ff, seed);
}

uint64_t UnicodeTextModel::parameter_count() const {
    return static_cast<uint64_t>(emb_.size()) + whh_.size() + bh_.size() +
           why_.size() + by_.size() + w1_.size() + b1_.size() +
           w2_.size() + b2_.size();
}

uint32_t UnicodeTextModel::route(uint32_t token, uint32_t prev,
                                 const Vec& hprev) const {
    uint32_t h = 2166136261u;
    h ^= token; h *= 16777619u;
    h ^= prev;  h *= 16777619u;
    if (!hprev.empty()) {
        const float a = std::fabs(hprev[0]);
        const float b = hprev.size() > 7 ? std::fabs(hprev[7]) : a;
        h ^= static_cast<uint32_t>(a * 1000003.0f);
        h *= 16777619u;
        h ^= static_cast<uint32_t>(b * 1000033.0f);
    }
    return h % experts_;
}

Vec UnicodeTextModel::step(uint32_t token, uint32_t prev, const Vec& hprev,
                           Vec* logits, uint32_t* expert_out,
                           Vec* base_out, Vec* z_out) const {
    if (token >= vocab_.size()) token = 0;
    if (prev >= vocab_.size()) prev = 0;

    Vec base(dim_, 0.0f);
    const size_t eoff = static_cast<size_t>(token) * dim_;
    for (uint32_t i = 0; i < dim_; ++i) {
        float s = emb_[eoff + i] + bh_[i];
        const size_t row = static_cast<size_t>(i) * dim_;
        for (uint32_t j = 0; j < dim_; ++j) s += whh_[row + j] * hprev[j];
        base[i] = std::tanh(s);
    }

    const uint32_t ex = route(token, prev, hprev);
    const size_t w1base = static_cast<size_t>(ex) * ff_ * dim_;
    const size_t b1base = static_cast<size_t>(ex) * ff_;
    const size_t w2base = static_cast<size_t>(ex) * dim_ * ff_;
    const size_t b2base = static_cast<size_t>(ex) * dim_;

    Vec z(ff_, 0.0f);
    for (uint32_t k = 0; k < ff_; ++k) {
        float s = b1_[b1base + k];
        const size_t row = w1base + static_cast<size_t>(k) * dim_;
        for (uint32_t j = 0; j < dim_; ++j) s += w1_[row + j] * base[j];
        z[k] = std::max(0.0f, s);
    }

    Vec h(dim_, 0.0f);
    for (uint32_t i = 0; i < dim_; ++i) {
        float s = b2_[b2base + i];
        const size_t row = w2base + static_cast<size_t>(i) * ff_;
        for (uint32_t k = 0; k < ff_; ++k) s += w2_[row + k] * z[k];
        h[i] = std::tanh(base[i] + EXPERT_SCALE * s);
    }

    if (logits) {
        logits->assign(vocab_.size(), 0.0f);
        for (uint32_t o = 0; o < vocab_.size(); ++o) {
            float s = by_[o];
            const size_t row = static_cast<size_t>(o) * dim_;
            for (uint32_t j = 0; j < dim_; ++j) s += why_[row + j] * h[j];
            (*logits)[o] = s;
        }
    }

    if (expert_out) *expert_out = ex;
    if (base_out) *base_out = std::move(base);
    if (z_out) *z_out = std::move(z);
    return h;
}

void UnicodeTextModel::train_file(const std::string& path, int epochs,
                                  int seq_len, float lr,
                                  const std::string& save_path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open corpus: " + path);
    std::string raw((std::istreambuf_iterator<char>(in)), {});
    const auto cps = utf8_decode(raw);
    const auto index = make_index(vocab_);

    std::vector<uint32_t> data;
    data.reserve(cps.size());
    for (uint32_t cp : cps) {
        auto it = index.find(cp);
        data.push_back(it == index.end() ? 0u : it->second);
    }

    if (data.size() < static_cast<size_t>(seq_len + 2))
        throw std::runtime_error("corpus is too small");

    Vec gemb(emb_.size()), gwhh(whh_.size()), gbh(bh_.size());
    Vec gwhy(why_.size()), gby(by_.size());

    std::mt19937 rng(12345);
    std::uniform_int_distribution<size_t> start_dist(
        1, data.size() - static_cast<size_t>(seq_len) - 2);

    const size_t natural = data.size() / static_cast<size_t>(std::max(1, seq_len));
    const size_t steps_per_epoch =
        std::max<size_t>(1, std::min<size_t>(256, natural));

    for (int epoch = 1; epoch <= epochs; ++epoch) {
        double epoch_loss = 0.0;

        for (size_t iter = 0; iter < steps_per_epoch; ++iter) {
            std::fill(gemb.begin(), gemb.end(), 0.0f);
            std::fill(gwhh.begin(), gwhh.end(), 0.0f);
            std::fill(gbh.begin(), gbh.end(), 0.0f);
            std::fill(gwhy.begin(), gwhy.end(), 0.0f);
            std::fill(gby.begin(), gby.end(), 0.0f);

            const size_t pos = start_dist(rng);

            std::vector<Vec> hs(static_cast<size_t>(seq_len) + 1, Vec(dim_, 0.0f));
            std::vector<Vec> bases(static_cast<size_t>(seq_len));
            std::vector<Vec> zs(static_cast<size_t>(seq_len));
            std::vector<Vec> probs(static_cast<size_t>(seq_len));
            std::vector<uint32_t> exs(static_cast<size_t>(seq_len));
            std::vector<uint32_t> xs(static_cast<size_t>(seq_len));
            std::vector<uint32_t> prevs(static_cast<size_t>(seq_len));
            std::vector<uint32_t> ys(static_cast<size_t>(seq_len));

            for (int t = 0; t < seq_len; ++t) {
                xs[t] = data[pos + static_cast<size_t>(t)];
                prevs[t] = data[pos + static_cast<size_t>(t) - 1];
                ys[t] = data[pos + static_cast<size_t>(t) + 1];

                Vec logits;
                hs[t + 1] = step(xs[t], prevs[t], hs[t], &logits,
                                 &exs[t], &bases[t], &zs[t]);
                probs[t] = softmax(logits);
                epoch_loss += -std::log(std::max(probs[t][ys[t]], 1e-12f));
            }

            Vec dhnext(dim_, 0.0f);

            for (int t = seq_len - 1; t >= 0; --t) {
                Vec dy = probs[t];
                dy[ys[t]] -= 1.0f;

                Vec dh = dhnext;
                for (uint32_t o = 0; o < vocab_.size(); ++o) {
                    gby[o] += dy[o];
                    const size_t row = static_cast<size_t>(o) * dim_;
                    for (uint32_t j = 0; j < dim_; ++j) {
                        gwhy[row + j] += dy[o] * hs[t + 1][j];
                        dh[j] += why_[row + j] * dy[o];
                    }
                }

                Vec dpre(dim_, 0.0f);
                for (uint32_t i = 0; i < dim_; ++i)
                    dpre[i] = (1.0f - hs[t + 1][i] * hs[t + 1][i]) * dh[i];

                const uint32_t ex = exs[t];
                const size_t w1base = static_cast<size_t>(ex) * ff_ * dim_;
                const size_t b1base = static_cast<size_t>(ex) * ff_;
                const size_t w2base = static_cast<size_t>(ex) * dim_ * ff_;
                const size_t b2base = static_cast<size_t>(ex) * dim_;

                Vec dz(ff_, 0.0f);
                Vec dhbase = dpre;

                for (uint32_t i = 0; i < dim_; ++i) {
                    const float dex = EXPERT_SCALE * dpre[i];
                    const size_t row = w2base + static_cast<size_t>(i) * ff_;
                    for (uint32_t k = 0; k < ff_; ++k)
                        dz[k] += w2_[row + k] * dex;
                }

                for (uint32_t i = 0; i < dim_; ++i) {
                    const float dex = EXPERT_SCALE * dpre[i];
                    const size_t row = w2base + static_cast<size_t>(i) * ff_;
                    for (uint32_t k = 0; k < ff_; ++k)
                        w2_[row + k] -= lr * clipf(dex * zs[t][k], -1.0f, 1.0f);
                    b2_[b2base + i] -= lr * clipf(dex, -1.0f, 1.0f);
                }

                for (uint32_t k = 0; k < ff_; ++k) {
                    if (zs[t][k] <= 0.0f) dz[k] = 0.0f;
                    const size_t row = w1base + static_cast<size_t>(k) * dim_;
                    for (uint32_t j = 0; j < dim_; ++j)
                        dhbase[j] += w1_[row + j] * dz[k];
                }

                for (uint32_t k = 0; k < ff_; ++k) {
                    if (dz[k] == 0.0f) continue;
                    const size_t row = w1base + static_cast<size_t>(k) * dim_;
                    for (uint32_t j = 0; j < dim_; ++j)
                        w1_[row + j] -= lr * clipf(dz[k] * bases[t][j], -1.0f, 1.0f);
                    b1_[b1base + k] -= lr * clipf(dz[k], -1.0f, 1.0f);
                }

                Vec dhraw(dim_, 0.0f);
                for (uint32_t i = 0; i < dim_; ++i) {
                    dhraw[i] = (1.0f - bases[t][i] * bases[t][i]) * dhbase[i];
                    gbh[i] += dhraw[i];
                    gemb[static_cast<size_t>(xs[t]) * dim_ + i] += dhraw[i];

                    const size_t row = static_cast<size_t>(i) * dim_;
                    for (uint32_t j = 0; j < dim_; ++j)
                        gwhh[row + j] += dhraw[i] * hs[t][j];
                }

                std::fill(dhnext.begin(), dhnext.end(), 0.0f);
                for (uint32_t j = 0; j < dim_; ++j) {
                    float v = 0.0f;
                    for (uint32_t i = 0; i < dim_; ++i)
                        v += whh_[static_cast<size_t>(i) * dim_ + j] * dhraw[i];
                    dhnext[j] = v;
                }
            }

            const float scale = lr / static_cast<float>(std::max(1, seq_len));
            for (size_t i = 0; i < emb_.size(); ++i) emb_[i] -= scale * clipf(gemb[i], -1.0f, 1.0f);
            for (size_t i = 0; i < whh_.size(); ++i) whh_[i] -= scale * clipf(gwhh[i], -1.0f, 1.0f);
            for (size_t i = 0; i < bh_.size(); ++i) bh_[i] -= scale * clipf(gbh[i], -1.0f, 1.0f);
            for (size_t i = 0; i < why_.size(); ++i) why_[i] -= scale * clipf(gwhy[i], -1.0f, 1.0f);
            for (size_t i = 0; i < by_.size(); ++i) by_[i] -= scale * clipf(gby[i], -1.0f, 1.0f);
        }

        const double avg = epoch_loss /
            static_cast<double>(steps_per_epoch * static_cast<size_t>(seq_len));
        std::cerr << "[unicode-text] epoch " << epoch << "/" << epochs
                  << " loss=" << avg
                  << " params=" << parameter_count()
                  << " vocab=" << vocab_.size()
                  << " steps=" << steps_per_epoch
                  << "\n";

        if (!save_path.empty()) save(save_path);
    }
}

std::string UnicodeTextModel::generate(const std::string& prompt, int tokens,
                                       float temperature, int top_k,
                                       uint32_t seed) const {
    const auto index = make_index(vocab_);
    const auto cps = utf8_decode(prompt);

    std::mt19937 rng(seed);
    Vec h(dim_, 0.0f), logits;
    uint32_t prev = 0;
    uint32_t current = 0;

    if (!cps.empty()) {
        for (uint32_t cp : cps) {
            auto it = index.find(cp);
            current = it == index.end() ? 0u : it->second;
            h = step(current, prev, h, &logits);
            prev = current;
        }
    } else {
        auto it = index.find(static_cast<uint32_t>(' '));
        current = it == index.end() ? 0u : it->second;
        h = step(current, prev, h, &logits);
        prev = current;
    }

    std::string out = prompt;
    for (int i = 0; i < tokens; ++i) {
        auto p = softmax(logits, temperature);
        const int next = sample_discrete(std::move(p), rng, top_k);
        const uint32_t token = next < 0 ? 0u : static_cast<uint32_t>(next);

        if (token < vocab_.size()) {
            uint32_t cp = vocab_[token];
            if (cp == 0) cp = '?';
            utf8_append(out, cp);
        }

        current = token;
        h = step(current, prev, h, &logits);
        prev = current;
    }

    return out;
}

void UnicodeTextModel::save(const std::string& path) const {
    const auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);

    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot save unicode model: " + path);

    const char magic[8] = {'R','E','A','I','U','C','5','1'};
    out.write(magic, sizeof(magic));
    write_u32(out, dim_);
    write_u32(out, experts_);
    write_u32(out, ff_);
    write_u32(out, static_cast<uint32_t>(vocab_.size()));
    for (uint32_t cp : vocab_) write_u32(out, cp);

    write_vec(out, emb_);
    write_vec(out, whh_);
    write_vec(out, bh_);
    write_vec(out, why_);
    write_vec(out, by_);
    write_vec(out, w1_);
    write_vec(out, b1_);
    write_vec(out, w2_);
    write_vec(out, b2_);
}

UnicodeTextModel UnicodeTextModel::load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open unicode model: " + path);

    char magic[8]{};
    in.read(magic, sizeof(magic));
    if (std::string(magic, 8) != "REAIUC51")
        throw std::runtime_error("bad unicode text checkpoint");

    UnicodeTextModel m(LoadTag{});
    m.dim_ = read_u32(in);
    m.experts_ = read_u32(in);
    m.ff_ = read_u32(in);
    const uint32_t vocab_size = read_u32(in);
    if (vocab_size < 2 || vocab_size > 65536)
        throw std::runtime_error("invalid unicode vocab size");

    m.vocab_.resize(vocab_size);
    for (auto& cp : m.vocab_) cp = read_u32(in);

    m.emb_ = read_vec(in);
    m.whh_ = read_vec(in);
    m.bh_ = read_vec(in);
    m.why_ = read_vec(in);
    m.by_ = read_vec(in);
    m.w1_ = read_vec(in);
    m.b1_ = read_vec(in);
    m.w2_ = read_vec(in);
    m.b2_ = read_vec(in);

    const size_t expected_emb = static_cast<size_t>(vocab_size) * m.dim_;
    if (m.emb_.size() != expected_emb || m.why_.size() != expected_emb ||
        m.by_.size() != vocab_size) {
        throw std::runtime_error("unicode checkpoint shape mismatch");
    }
    return m;
}

} // namespace reai
