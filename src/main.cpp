#include "image_model.hpp"
#include "text_model.hpp"
#include "sparse_text_model.hpp"
#include "unicode_text_model.hpp"
#include <cstdlib>
#include <iostream>
#include <string>

using namespace reai;

static void help() {
    std::cout <<
R"(ReVerfyx AI - from-scratch CPU research core

Commands:
  reai text-init <model.bin> [hidden]
  reai text-train <model.bin> <corpus.txt> [epochs] [seq_len] [lr]
  reai text-generate <model.bin> <prompt> [tokens] [temperature] [top_k]
  reai sparse-init <model.bin> [dim=256] [experts=192] [ff=512] [seed]
  reai sparse-train <model.bin> <corpus.txt> [epochs] [seq_len] [lr]
  reai sparse-generate <model.bin> <prompt> [tokens] [temperature] [top_k]
  reai sparse-info <model.bin>
  reai unicode-init <model.bin> <corpus.txt> [vocab=1024] [dim=128] [experts=64] [ff=256] [seed]
  reai unicode-train <model.bin> <corpus.txt> [epochs] [seq_len] [lr]
  reai unicode-generate <model.bin> <prompt> [tokens] [temperature] [top_k]
  reai unicode-info <model.bin>
  reai image-init <model.bin> [size] [hidden]
  reai image-train <model.bin> <manifest.tsv> [epochs] [lr]
  reai image-generate <model.bin> <prompt> <out.ppm> [steps]

Image manifest format:
  relative/or/absolute/image.ppm<TAB>caption

No pretrained model or third-party ML runtime is used.
)";
}

int main(int argc, char** argv) {
    try {
        if (argc < 2) { help(); return 0; }
        const std::string cmd = argv[1];
        if (cmd == "text-init") {
            if (argc < 3) throw std::runtime_error("text-init needs model path");
            const uint32_t h = argc > 3 ? static_cast<uint32_t>(std::stoul(argv[3])) : 128;
            TextModel(h).save(argv[2]);
            std::cout << "created random text model: " << argv[2] << "\n";
        } else if (cmd == "text-train") {
            if (argc < 4) throw std::runtime_error("text-train needs model and corpus");
            auto model = TextModel::load(argv[2]);
            const int epochs = argc > 4 ? std::stoi(argv[4]) : 1;
            const int seq = argc > 5 ? std::stoi(argv[5]) : 64;
            const float lr = argc > 6 ? std::stof(argv[6]) : 0.001f;
            model.train_file(argv[3], epochs, seq, lr, argv[2]);
        } else if (cmd == "text-generate") {
            if (argc < 4) throw std::runtime_error("text-generate needs model and prompt");
            auto model = TextModel::load(argv[2]);
            const int tokens = argc > 4 ? std::stoi(argv[4]) : 200;
            const float temp = argc > 5 ? std::stof(argv[5]) : 0.9f;
            const int topk = argc > 6 ? std::stoi(argv[6]) : 40;
            std::cout << model.generate(argv[3], tokens, temp, topk, static_cast<uint32_t>(std::random_device{}())) << "\n";
        } else if (cmd == "sparse-init") {
            if (argc < 3) throw std::runtime_error("sparse-init needs model path");
            const uint32_t dim = argc > 3 ? static_cast<uint32_t>(std::stoul(argv[3])) : 256;
            const uint32_t experts = argc > 4 ? static_cast<uint32_t>(std::stoul(argv[4])) : 192;
            const uint32_t ff = argc > 5 ? static_cast<uint32_t>(std::stoul(argv[5])) : 512;
            const uint32_t seed = argc > 6 ? static_cast<uint32_t>(std::stoul(argv[6])) : 1337;
            SparseTextModel model(dim, experts, ff, seed);
            model.save(argv[2]);
            std::cout << "created sparse text model: " << argv[2]
                      << " params=" << model.parameter_count() << "\n";
        } else if (cmd == "sparse-train") {
            if (argc < 4) throw std::runtime_error("sparse-train needs model and corpus");
            auto model = SparseTextModel::load(argv[2]);
            const int epochs = argc > 4 ? std::stoi(argv[4]) : 1;
            const int seq = argc > 5 ? std::stoi(argv[5]) : 48;
            const float lr = argc > 6 ? std::stof(argv[6]) : 0.0003f;
            model.train_file(argv[3], epochs, seq, lr, argv[2]);
        } else if (cmd == "sparse-generate") {
            if (argc < 4) throw std::runtime_error("sparse-generate needs model and prompt");
            auto model = SparseTextModel::load(argv[2]);
            const int tokens = argc > 4 ? std::stoi(argv[4]) : 200;
            const float temp = argc > 5 ? std::stof(argv[5]) : 0.9f;
            const int topk = argc > 6 ? std::stoi(argv[6]) : 40;
            std::cout << model.generate(argv[3], tokens, temp, topk,
                                        static_cast<uint32_t>(std::random_device{}())) << "\n";
        } else if (cmd == "sparse-info") {
            if (argc < 3) throw std::runtime_error("sparse-info needs model path");
            auto model = SparseTextModel::load(argv[2]);
            std::cout << "engine=sparse-moe"
                      << " params=" << model.parameter_count()
                      << " dim=" << model.dim()
                      << " experts=" << model.experts()
                      << " ff=" << model.ff() << "\n";
        } else if (cmd == "unicode-init") {
            if (argc < 4) throw std::runtime_error("unicode-init needs model and corpus");
            const uint32_t vocab = argc > 4 ? static_cast<uint32_t>(std::stoul(argv[4])) : 1024;
            const uint32_t dim = argc > 5 ? static_cast<uint32_t>(std::stoul(argv[5])) : 128;
            const uint32_t experts = argc > 6 ? static_cast<uint32_t>(std::stoul(argv[6])) : 64;
            const uint32_t ff = argc > 7 ? static_cast<uint32_t>(std::stoul(argv[7])) : 256;
            const uint32_t seed = argc > 8 ? static_cast<uint32_t>(std::stoul(argv[8])) : 1337;
            auto model = UnicodeTextModel::create_from_corpus(argv[3], vocab, dim, experts, ff, seed);
            model.save(argv[2]);
            std::cout << "created unicode text model: " << argv[2]
                      << " params=" << model.parameter_count()
                      << " vocab=" << model.vocab_size() << "\n";
        } else if (cmd == "unicode-train") {
            if (argc < 4) throw std::runtime_error("unicode-train needs model and corpus");
            auto model = UnicodeTextModel::load(argv[2]);
            const int epochs = argc > 4 ? std::stoi(argv[4]) : 1;
            const int seq = argc > 5 ? std::stoi(argv[5]) : 48;
            const float lr = argc > 6 ? std::stof(argv[6]) : 0.0005f;
            model.train_file(argv[3], epochs, seq, lr, argv[2]);
        } else if (cmd == "unicode-generate") {
            if (argc < 4) throw std::runtime_error("unicode-generate needs model and prompt");
            auto model = UnicodeTextModel::load(argv[2]);
            const int tokens = argc > 4 ? std::stoi(argv[4]) : 200;
            const float temp = argc > 5 ? std::stof(argv[5]) : 0.85f;
            const int topk = argc > 6 ? std::stoi(argv[6]) : 40;
            std::cout << model.generate(argv[3], tokens, temp, topk,
                                        static_cast<uint32_t>(std::random_device{}())) << "\n";
        } else if (cmd == "unicode-info") {
            if (argc < 3) throw std::runtime_error("unicode-info needs model path");
            auto model = UnicodeTextModel::load(argv[2]);
            std::cout << "engine=unicode-moe"
                      << " params=" << model.parameter_count()
                      << " vocab=" << model.vocab_size()
                      << " dim=" << model.dim()
                      << " experts=" << model.experts()
                      << " ff=" << model.ff() << "\n";
        } else if (cmd == "image-init") {
            if (argc < 3) throw std::runtime_error("image-init needs model path");
            const uint32_t sz = argc > 3 ? static_cast<uint32_t>(std::stoul(argv[3])) : 32;
            const uint32_t h = argc > 4 ? static_cast<uint32_t>(std::stoul(argv[4])) : 256;
            ImageModel(sz, sz, h).save(argv[2]);
            std::cout << "created random image model: " << argv[2] << "\n";
        } else if (cmd == "image-train") {
            if (argc < 4) throw std::runtime_error("image-train needs model and manifest");
            auto model = ImageModel::load(argv[2]);
            const int epochs = argc > 4 ? std::stoi(argv[4]) : 1;
            const float lr = argc > 5 ? std::stof(argv[5]) : 0.0005f;
            model.train_manifest(argv[3], epochs, lr, argv[2]);
        } else if (cmd == "image-generate") {
            if (argc < 5) throw std::runtime_error("image-generate needs model, prompt and output");
            auto model = ImageModel::load(argv[2]);
            const int steps = argc > 5 ? std::stoi(argv[5]) : 24;
            model.generate(argv[3], argv[4], steps, static_cast<uint32_t>(std::random_device{}()));
            std::cout << "saved " << argv[4] << "\n";
        } else {
            help(); return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 2;
    }
    return 0;
}
