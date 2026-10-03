#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace reai {

using Vec = std::vector<float>;

inline float clipf(float x, float lo, float hi) { return std::max(lo, std::min(hi, x)); }

inline void fill_normal(Vec& v, std::mt19937& rng, float scale) {
    std::normal_distribution<float> d(0.0f, scale);
    for (auto& x : v) x = d(rng);
}

inline std::vector<float> softmax(const Vec& logits, float temperature = 1.0f) {
    if (logits.empty()) return {};
    temperature = std::max(temperature, 1e-4f);
    float m = logits[0] / temperature;
    for (float x : logits) m = std::max(m, x / temperature);
    Vec p(logits.size());
    double sum = 0.0;
    for (size_t i = 0; i < logits.size(); ++i) {
        p[i] = std::exp(logits[i] / temperature - m);
        sum += p[i];
    }
    if (sum <= 0.0) return Vec(logits.size(), 1.0f / static_cast<float>(logits.size()));
    for (auto& x : p) x = static_cast<float>(x / sum);
    return p;
}

inline int sample_discrete(Vec p, std::mt19937& rng, int top_k = 0) {
    if (top_k > 0 && top_k < static_cast<int>(p.size())) {
        std::vector<size_t> idx(p.size());
        for (size_t i = 0; i < idx.size(); ++i) idx[i] = i;
        std::partial_sort(idx.begin(), idx.begin() + top_k, idx.end(),
            [&](size_t a, size_t b){ return p[a] > p[b]; });
        std::vector<char> keep(p.size(), 0);
        for (int i = 0; i < top_k; ++i) keep[idx[i]] = 1;
        float s = 0.0f;
        for (size_t i = 0; i < p.size(); ++i) {
            if (!keep[i]) p[i] = 0.0f;
            s += p[i];
        }
        if (s > 0.0f) for (auto& x : p) x /= s;
    }
    std::discrete_distribution<int> d(p.begin(), p.end());
    return d(rng);
}

inline void write_u32(std::ofstream& out, uint32_t x) { out.write(reinterpret_cast<const char*>(&x), sizeof(x)); }
inline uint32_t read_u32(std::ifstream& in) { uint32_t x{}; in.read(reinterpret_cast<char*>(&x), sizeof(x)); return x; }
inline void write_vec(std::ofstream& out, const Vec& v) {
    uint64_t n = v.size(); out.write(reinterpret_cast<const char*>(&n), sizeof(n));
    out.write(reinterpret_cast<const char*>(v.data()), static_cast<std::streamsize>(v.size() * sizeof(float)));
}
inline Vec read_vec(std::ifstream& in) {
    uint64_t n{}; in.read(reinterpret_cast<char*>(&n), sizeof(n));
    if (n > (1ULL << 34)) throw std::runtime_error("checkpoint vector too large");
    Vec v(static_cast<size_t>(n));
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(v.size() * sizeof(float)));
    return v;
}

struct AdamState {
    Vec m, v;
    uint64_t step = 0;
    explicit AdamState(size_t n = 0): m(n, 0.0f), v(n, 0.0f) {}
};

inline void adam_update(Vec& w, const Vec& g, AdamState& st, float lr,
                        float beta1 = 0.9f, float beta2 = 0.999f, float eps = 1e-8f) {
    if (st.m.size() != w.size()) st = AdamState(w.size());
    st.step++;
    const float b1c = 1.0f - std::pow(beta1, static_cast<float>(st.step));
    const float b2c = 1.0f - std::pow(beta2, static_cast<float>(st.step));
    for (size_t i = 0; i < w.size(); ++i) {
        st.m[i] = beta1 * st.m[i] + (1.0f - beta1) * g[i];
        st.v[i] = beta2 * st.v[i] + (1.0f - beta2) * g[i] * g[i];
        const float mh = st.m[i] / b1c;
        const float vh = st.v[i] / b2c;
        w[i] -= lr * mh / (std::sqrt(vh) + eps);
    }
}

inline void clip_grad(Vec& g, float max_abs = 5.0f) {
    for (auto& x : g) x = clipf(x, -max_abs, max_abs);
}

} // namespace reai
