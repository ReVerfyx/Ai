#pragma once
#include "math.hpp"
#include <cstdint>
#include <string>

namespace reai {

class SparseTextModel {
public:
    static constexpr uint32_t VOCAB = 256;

    SparseTextModel(uint32_t dim = 256, uint32_t experts = 192,
                    uint32_t ff = 512, uint32_t seed = 1337);

    void train_file(const std::string& path, int epochs, int seq_len,
                    float lr, const std::string& save_path);
    std::string generate(const std::string& prompt, int tokens,
                         float temperature, int top_k, uint32_t seed) const;

    void save(const std::string& path) const;
    static SparseTextModel load(const std::string& path);

    uint64_t parameter_count() const;
    uint32_t dim() const { return dim_; }
    uint32_t experts() const { return experts_; }
    uint32_t ff() const { return ff_; }

private:
    struct LoadTag {};
    explicit SparseTextModel(LoadTag) {}

    uint32_t dim_ = 0;
    uint32_t experts_ = 0;
    uint32_t ff_ = 0;

    Vec emb_;      // VOCAB x dim
    Vec whh_;      // dim x dim
    Vec bh_;       // dim
    Vec why_;      // VOCAB x dim
    Vec by_;       // VOCAB

    Vec w1_;       // experts x ff x dim
    Vec b1_;       // experts x ff
    Vec w2_;       // experts x dim x ff
    Vec b2_;       // experts x dim

    uint32_t route(uint8_t token, uint8_t prev, const Vec& hprev) const;
    Vec step(uint8_t token, uint8_t prev, const Vec& hprev,
             Vec* logits = nullptr, uint32_t* expert_out = nullptr,
             Vec* base_out = nullptr, Vec* z_out = nullptr) const;
};

} // namespace reai
