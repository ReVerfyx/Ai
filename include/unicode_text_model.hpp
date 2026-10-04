#pragma once
#include "math.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace reai {

class UnicodeTextModel {
public:
    UnicodeTextModel(std::vector<uint32_t> vocab,
                     uint32_t dim = 128,
                     uint32_t experts = 64,
                     uint32_t ff = 256,
                     uint32_t seed = 1337);

    static UnicodeTextModel create_from_corpus(const std::string& corpus_path,
                                                uint32_t vocab_size = 1024,
                                                uint32_t dim = 128,
                                                uint32_t experts = 64,
                                                uint32_t ff = 256,
                                                uint32_t seed = 1337);

    void train_file(const std::string& path, int epochs, int seq_len,
                    float lr, const std::string& save_path);
    std::string generate(const std::string& prompt, int tokens,
                         float temperature, int top_k, uint32_t seed) const;

    void save(const std::string& path) const;
    static UnicodeTextModel load(const std::string& path);

    uint64_t parameter_count() const;
    uint32_t dim() const { return dim_; }
    uint32_t experts() const { return experts_; }
    uint32_t ff() const { return ff_; }
    uint32_t vocab_size() const { return static_cast<uint32_t>(vocab_.size()); }

private:
    struct LoadTag {};
    explicit UnicodeTextModel(LoadTag) {}

    uint32_t dim_ = 0;
    uint32_t experts_ = 0;
    uint32_t ff_ = 0;
    std::vector<uint32_t> vocab_;

    Vec emb_;
    Vec whh_;
    Vec bh_;
    Vec why_;
    Vec by_;

    Vec w1_;
    Vec b1_;
    Vec w2_;
    Vec b2_;

    uint32_t route(uint32_t token, uint32_t prev, const Vec& hprev) const;
    Vec step(uint32_t token, uint32_t prev, const Vec& hprev,
             Vec* logits = nullptr, uint32_t* expert_out = nullptr,
             Vec* base_out = nullptr, Vec* z_out = nullptr) const;
};

} // namespace reai
