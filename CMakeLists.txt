cmake_minimum_required(VERSION 3.16)
project(ReVerfyxAI LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(reai
    src/main.cpp
    src/text_model.cpp
    src/sparse_text_model.cpp
    src/unicode_text_model.cpp
    src/image_model.cpp
)

target_include_directories(reai PRIVATE include)
if (MSVC)
    target_compile_options(reai PRIVATE /O2 /W4)
else()
    target_compile_options(reai PRIVATE -O3 -Wall -Wextra -Wpedantic)
endif()
