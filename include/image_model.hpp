#pragma once
#include "math.hpp"
#include <string>
#include <vector>

namespace reai {

struct ImageSample {
    std::string path;
    std::string caption;
};

class ImageModel {
public:
    static constexpr uint32_t CONDITION = 64;
    ImageModel(uint32_t width = 32, uint32_t height = 32, uint32_t hidden = 256, uint32_t seed = 1337);

    void train_manifest(const std::string& manifest, int epochs, float lr, const std::string& save_path);
    void generate(const std::string& prompt, const std::string& out_path, int steps, uint32_t seed) const;
    void save(const std::string& path) const;
    static ImageModel load(const std::string& path);

private:
    uint32_t width_ = 0, height_ = 0, hidden_ = 0, dim_ = 0;
    Vec w1_, b1_, w2_, b2_;

    static Vec condition(const std::string& text);
    Vec forward(const Vec& noisy, float sigma, const Vec& cond, Vec* hidden_act = nullptr) const;
    static Vec load_ppm_resized(const std::string& path, uint32_t w, uint32_t h);
    static void save_ppm(const std::string& path, const Vec& img, uint32_t w, uint32_t h);
};

} // namespace reai
