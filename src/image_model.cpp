#include "image_model.hpp"
#include <filesystem>
#include <iostream>
#include <sstream>

namespace reai {

static uint64_t fnv1a(const unsigned char* p, size_t n) {
    uint64_t h = 1469598103934665603ULL;
    for (size_t i = 0; i < n; ++i) { h ^= p[i]; h *= 1099511628211ULL; }
    return h;
}

ImageModel::ImageModel(uint32_t width, uint32_t height, uint32_t hidden, uint32_t seed)
    : width_(width), height_(height), hidden_(hidden), dim_(width * height * 3) {
    if (!width_ || !height_ || !hidden_) throw std::runtime_error("invalid image model size");
    const size_t input = static_cast<size_t>(dim_) + 1 + CONDITION;
    w1_.resize(static_cast<size_t>(hidden_) * input);
    b1_.assign(hidden_, 0.0f);
    w2_.resize(static_cast<size_t>(dim_) * hidden_);
    b2_.assign(dim_, 0.0f);
    std::mt19937 rng(seed);
    fill_normal(w1_, rng, 0.02f / std::sqrt(static_cast<float>(input)));
    fill_normal(w2_, rng, 0.02f / std::sqrt(static_cast<float>(hidden_)));
}

Vec ImageModel::condition(const std::string& text) {
    Vec c(CONDITION, 0.0f);
    const auto* p = reinterpret_cast<const unsigned char*>(text.data());
    if (text.empty()) return c;
    for (size_t ngram = 1; ngram <= 3; ++ngram) {
        if (text.size() < ngram) continue;
        for (size_t i = 0; i + ngram <= text.size(); ++i) {
            const uint64_t h = fnv1a(p + i, ngram);
            const size_t idx = static_cast<size_t>(h % CONDITION);
            c[idx] += (h & 0x100) ? 1.0f : -1.0f;
        }
    }
    double norm = 0.0;
    for (float x : c) norm += x * x;
    norm = std::sqrt(norm);
    if (norm > 0.0) for (auto& x : c) x = static_cast<float>(x / norm);
    return c;
}

Vec ImageModel::forward(const Vec& noisy, float sigma, const Vec& cond, Vec* hidden_act) const {
    if (noisy.size() != dim_) throw std::runtime_error("bad image vector size");
    const size_t input = static_cast<size_t>(dim_) + 1 + CONDITION;
    Vec in(input);
    std::copy(noisy.begin(), noisy.end(), in.begin());
    in[dim_] = sigma;
    std::copy(cond.begin(), cond.end(), in.begin() + dim_ + 1);
    Vec h(hidden_);
    for (uint32_t i = 0; i < hidden_; ++i) {
        float s = b1_[i];
        const size_t row = static_cast<size_t>(i) * input;
        for (size_t j = 0; j < input; ++j) s += w1_[row + j] * in[j];
        h[i] = std::tanh(s);
    }
    Vec out(dim_);
    for (uint32_t o = 0; o < dim_; ++o) {
        float s = b2_[o];
        const size_t row = static_cast<size_t>(o) * hidden_;
        for (uint32_t j = 0; j < hidden_; ++j) s += w2_[row + j] * h[j];
        out[o] = std::tanh(s);
    }
    if (hidden_act) *hidden_act = std::move(h);
    return out;
}

static std::string read_ppm_token(std::istream& in) {
    std::string s;
    while (in >> s) {
        if (!s.empty() && s[0] == '#') { std::string rest; std::getline(in, rest); continue; }
        return s;
    }
    return {};
}

Vec ImageModel::load_ppm_resized(const std::string& path, uint32_t w, uint32_t h) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open image: " + path);
    const std::string magic = read_ppm_token(in);
    if (magic != "P6" && magic != "P3") throw std::runtime_error("only PPM P6/P3 supported: " + path);
    int sw = std::stoi(read_ppm_token(in));
    int sh = std::stoi(read_ppm_token(in));
    int maxv = std::stoi(read_ppm_token(in));
    if (sw <= 0 || sh <= 0 || maxv <= 0 || maxv > 255) throw std::runtime_error("invalid PPM header");
    std::vector<unsigned char> raw(static_cast<size_t>(sw) * sh * 3);
    if (magic == "P6") {
        in.get();
        in.read(reinterpret_cast<char*>(raw.data()), static_cast<std::streamsize>(raw.size()));
        if (in.gcount() != static_cast<std::streamsize>(raw.size())) throw std::runtime_error("truncated PPM");
    } else {
        for (auto& px : raw) px = static_cast<unsigned char>(std::stoi(read_ppm_token(in)) * 255 / maxv);
    }
    Vec out(static_cast<size_t>(w) * h * 3);
    for (uint32_t y = 0; y < h; ++y) for (uint32_t x = 0; x < w; ++x) {
        const uint32_t sx = static_cast<uint32_t>((static_cast<uint64_t>(x) * sw) / w);
        const uint32_t sy = static_cast<uint32_t>((static_cast<uint64_t>(y) * sh) / h);
        for (int c = 0; c < 3; ++c) {
            unsigned char v = raw[(static_cast<size_t>(sy) * sw + sx) * 3 + c];
            out[(static_cast<size_t>(y) * w + x) * 3 + c] = static_cast<float>(v) / 127.5f - 1.0f;
        }
    }
    return out;
}

void ImageModel::save_ppm(const std::string& path, const Vec& img, uint32_t w, uint32_t h) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot save image: " + path);
    out << "P6\n" << w << " " << h << "\n255\n";
    for (float x : img) {
        unsigned char v = static_cast<unsigned char>(std::lround((clipf(x, -1.0f, 1.0f) + 1.0f) * 127.5f));
        out.write(reinterpret_cast<const char*>(&v), 1);
    }
}

void ImageModel::train_manifest(const std::string& manifest, int epochs, float lr, const std::string& save_path) {
    std::ifstream in(manifest);
    if (!in) throw std::runtime_error("cannot open manifest: " + manifest);
    const std::filesystem::path base = std::filesystem::absolute(std::filesystem::path(manifest)).parent_path();
    std::vector<ImageSample> samples;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') continue;
        const auto tab = line.find('\t');
        if (tab == std::string::npos) continue;
        std::filesystem::path p = line.substr(0, tab);
        if (p.is_relative()) p = base / p;
        samples.push_back({p.string(), line.substr(tab + 1)});
    }
    if (samples.empty()) throw std::runtime_error("manifest has no samples");

    const size_t input_dim = static_cast<size_t>(dim_) + 1 + CONDITION;
    Vec gw1(w1_.size()), gb1(b1_.size()), gw2(w2_.size()), gb2(b2_.size());
    AdamState aw1(w1_.size()), ab1(b1_.size()), aw2(w2_.size()), ab2(b2_.size());
    std::mt19937 rng(424242);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::uniform_real_distribution<float> sd(0.05f, 1.0f);

    for (int epoch = 1; epoch <= epochs; ++epoch) {
        std::shuffle(samples.begin(), samples.end(), rng);
        double loss_sum = 0.0;
        size_t seen = 0;
        for (const auto& sample : samples) {
            Vec target;
            try { target = load_ppm_resized(sample.path, width_, height_); }
            catch (const std::exception& e) { std::cerr << "[image] skip " << e.what() << "\n"; continue; }
            const float sigma = sd(rng);
            Vec noisy(dim_);
            for (uint32_t i = 0; i < dim_; ++i) noisy[i] = target[i] + sigma * nd(rng);
            Vec cond = condition(sample.caption), h;
            Vec pred = forward(noisy, sigma, cond, &h);

            Vec input(input_dim);
            std::copy(noisy.begin(), noisy.end(), input.begin());
            input[dim_] = sigma;
            std::copy(cond.begin(), cond.end(), input.begin() + dim_ + 1);
            std::fill(gw1.begin(), gw1.end(), 0.0f); std::fill(gb1.begin(), gb1.end(), 0.0f);
            std::fill(gw2.begin(), gw2.end(), 0.0f); std::fill(gb2.begin(), gb2.end(), 0.0f);

            Vec dh(hidden_, 0.0f);
            for (uint32_t o = 0; o < dim_; ++o) {
                const float err = pred[o] - target[o];
                loss_sum += err * err;
                const float dpre = (2.0f * err / static_cast<float>(dim_)) * (1.0f - pred[o] * pred[o]);
                gb2[o] += dpre;
                const size_t row = static_cast<size_t>(o) * hidden_;
                for (uint32_t j = 0; j < hidden_; ++j) {
                    gw2[row + j] += dpre * h[j];
                    dh[j] += w2_[row + j] * dpre;
                }
            }
            for (uint32_t j = 0; j < hidden_; ++j) {
                const float dpre = dh[j] * (1.0f - h[j] * h[j]);
                gb1[j] += dpre;
                const size_t row = static_cast<size_t>(j) * input_dim;
                for (size_t k = 0; k < input_dim; ++k) gw1[row + k] += dpre * input[k];
            }
            for (auto* g : {&gw1, &gb1, &gw2, &gb2}) clip_grad(*g, 1.0f);
            adam_update(w1_, gw1, aw1, lr); adam_update(b1_, gb1, ab1, lr);
            adam_update(w2_, gw2, aw2, lr); adam_update(b2_, gb2, ab2, lr);
            ++seen;
        }
        std::cerr << "[image] epoch " << epoch << "/" << epochs << " mse="
                  << (seen ? loss_sum / static_cast<double>(seen * dim_) : 0.0) << "\n";
        if (!save_path.empty()) save(save_path);
    }
}

void ImageModel::generate(const std::string& prompt, const std::string& out_path, int steps, uint32_t seed) const {
    steps = std::max(2, steps);
    std::mt19937 rng(seed);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    Vec x(dim_); for (auto& v : x) v = nd(rng);
    const Vec cond = condition(prompt);
    for (int s = steps; s >= 1; --s) {
        const float sigma = static_cast<float>(s) / static_cast<float>(steps);
        const float next_sigma = static_cast<float>(s - 1) / static_cast<float>(steps);
        Vec clean = forward(x, sigma, cond, nullptr);
        const float blend = 1.0f - next_sigma / std::max(sigma, 1e-6f);
        for (uint32_t i = 0; i < dim_; ++i) {
            x[i] = (1.0f - blend) * x[i] + blend * clean[i];
            if (s > 1) x[i] += nd(rng) * (sigma - next_sigma) * 0.08f;
        }
    }
    save_ppm(out_path, x, width_, height_);
}

void ImageModel::save(const std::string& path) const {
    const auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot save model: " + path);
    const char magic[8] = {'R','E','A','I','I','M','G','1'};
    out.write(magic, sizeof(magic));
    write_u32(out, width_); write_u32(out, height_); write_u32(out, hidden_);
    write_vec(out, w1_); write_vec(out, b1_); write_vec(out, w2_); write_vec(out, b2_);
}

ImageModel ImageModel::load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot open model: " + path);
    char magic[8]{}; in.read(magic, sizeof(magic));
    if (std::string(magic, 8) != "REAIIMG1") throw std::runtime_error("bad image checkpoint");
    const uint32_t w = read_u32(in), h = read_u32(in), hidden = read_u32(in);
    ImageModel m(w, h, hidden, 1);
    m.w1_ = read_vec(in); m.b1_ = read_vec(in); m.w2_ = read_vec(in); m.b2_ = read_vec(in);
    return m;
}

} // namespace reai
