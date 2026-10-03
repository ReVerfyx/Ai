#pragma once
#include "math.hpp"
#include <string>

namespace reai {

class TextModel {
public:
    static constexpr uint32_t VOCAB = 256;

    explicit TextModel(uint32_t hidden = 128, uint32_t seed = 1337);
    void train_file(const std::string& path, int epochs, int seq_len, float lr, const std::string& save_path);
    std::string generate(const std::string& prompt, int tokens, float temperature, int top_k, uint32_t seed) const;
    void save(const std::string& path) const;
    static TextModel load(const std::string& path);
    uint32_t hidden_size() const { return hidden_; }

private:
    uint32_t hidden_ = 0;
    Vec wxh_, whh_, why_, bh_, by_;

    Vec step(uint8_t token, const Vec& hprev, Vec* logits = nullptr) const;
};

} // namespace reai
