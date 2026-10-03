#include "sparse_text_model.hpp"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <iterator>
#include <random>

namespace reai {

static constexpr float EXPERT_SCALE = 0.25f;

SparseTextModel::SparseTextModel(uint32_t dim, uint32_t experts,
                                 uint32_t ff, uint32_t seed)
    : dim_(dim), experts_(experts), ff_(ff) {
    if (!dim_ || !experts_ || !ff_) throw std::runtime_error("invalid sparse model shape");

    std::mt19937 rng(seed);
    emb_.resize(static_cast<size_t>(VOCAB) * dim_);
    whh_.resize(static_cast<size_t>(dim_) * dim_);
    bh_.assign(dim_, 0.0f);
    why_.resize(static_cast<size_t>(VOCAB) * dim_);
    by_.assign(VOCAB, 0.0f);

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

uint64_t SparseTextModel::parameter_count() const {
    return static_cast<uint64_t>(emb_.size()) + whh_.size() + bh_.size() +
           why_.size() + by_.size() + w1_.size() + b1_.size() +
           w2_.size() + b2_.size();
}

uint32_t SparseTextModel::route(uint8_t token, uint8_t prev, const Vec& hprev) const {
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

Vec SparseTextModel::step(uint8_t token, uint8_t prev, const Vec& hprev,
                          Vec* logits, uint32_t* expert_out,
                          Vec* base_out, Vec* z_out) const {
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
        logits->assign(VOCAB, 0.0f);
        for (uint32_t o = 0; o < VOCAB; ++o) {
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

void SparseTextModel::train_file(const std::string& path, int epochs, int seq_len,
                                 float lr, const std::string& save_path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open corpus: " + path);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(in)), {});
    if (data.size() < static_cast<size_t>(seq_len + 2))
        throw std::runtime_error("corpus is too small");

    // Shared gradients are small. Expert parameters are updated sparsely in-place
    // so a ~50M model does not need another ~50M gradient buffer.
    Vec gemb(emb_.size()), gwhh(whh_.size()), gbh(bh_.size());
    Vec gwhy(why_.size()), gby(by_.size());

    std::mt19937 rng(12345);
    std::uniform_int_distribution<size_t> start_dist(
        1, data.size() - static_cast<size_t>(seq_len) - 2);

    // CPU-friendly training budget. Capacity is large, active compute is sparse.
    const size_t natural = data.size() / static_cast<size_t>(std::max(1, seq_len));
    const size_t steps_per_epoch = std::max<size_t>(1, std::min<size_t>(48, natural));

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
            std::vector<uint8_t> xs(static_cast<size_t>(seq_len));
            std::vector<uint8_t> prevs(static_cast<size_t>(seq_len));
            std::vector<uint8_t> ys(static_cast<size_t>(seq_len));

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
                for (uint32_t o = 0; o < VOCAB; ++o) {
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

                // Backprop through W2, then sparse SGD update.
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

                // ReLU + W1.
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
                    float s = 0.0f;
                    for (uint32_t i = 0; i < dim_; ++i)
                        s += whh_[static_cast<size_t>(i) * dim_ + j] * dhraw[i];
                    dhnext[j] = s;
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
        std::cerr << "[sparse-text] epoch " << epoch << "/" << epochs
                  << " loss=" << avg
                  << " params=" << parameter_count()
                  << " active_expert_params~" << (2ULL * ff_ * dim_)
                  << "\n";

        if (!save_path.empty()) save(save_path);
    }
}

std::string SparseTextModel::generate(const std::string& prompt, int tokens,
                                      float temperature, int top_k,
                                      uint32_t seed) const {
    std::mt19937 rng(seed);
    Vec h(dim_, 0.0f), logits;
    uint8_t prev = static_cast<uint8_t>(' ');
    uint8_t current = static_cast<uint8_t>(' ');

    if (!prompt.empty()) {
        for (unsigned char c : prompt) {
            current = c;
            h = step(current, prev, h, &logits);
            prev = current;
        }
    } else {
        h = step(current, prev, h, &logits);
        prev = current;
    }

    std::string out = prompt;
    for (int i = 0; i < tokens; ++i) {
        auto p = softmax(logits, temperature);
        const int next = sample_discrete(std::move(p), rng, top_k);
        out.push_back(static_cast<char>(next));
        current = static_cast<uint8_t>(next);
        h = step(current, prev, h, &logits);
        prev = current;
    }
    return out;
}

void SparseTextModel::save(const std::string& path) const {
    const auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);

    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot save model: " + path);

    const char magic[8] = {'R','E','A','I','S','P','2','1'};
    out.write(magic, sizeof(magic));
    write_u32(out, dim_);
    write_u32(out, experts_);
    write_u32(out, ff_);
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

SparseTextModel SparseTextModel::load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open sparse model: " + path);

    char magic[8]{};
    in.read(magic, sizeof(magic));
    if (std::string(magic, 8) != "REAISP21")
        throw std::runtime_error("bad sparse text checkpoint");

    const uint32_t dim = read_u32(in);
    const uint32_t experts = read_u32(in);
    const uint32_t ff = read_u32(in);

    SparseTextModel m;
    m.dim_ = dim;
    m.experts_ = experts;
    m.ff_ = ff;
    m.emb_ = read_vec(in);
    m.whh_ = read_vec(in);
    m.bh_ = read_vec(in);
    m.why_ = read_vec(in);
    m.by_ = read_vec(in);
    m.w1_ = read_vec(in);
    m.b1_ = read_vec(in);
    m.w2_ = read_vec(in);
    m.b2_ = read_vec(in);
    return m;
}

} // namespace reai
