cmake_minimum_required(VERSION 3.16)
project(chilli_hard_sync CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(chilli_engine INTERFACE)
target_include_directories(chilli_engine INTERFACE include)

enable_testing()

function(chilli_add_test name source)
    add_executable(${name} ${source})
    target_link_libraries(${name} PRIVATE chilli_engine)
    if (MSVC)
        target_compile_options(${name} PRIVATE /permissive- /W4)
    else()
        target_compile_options(${name} PRIVATE -Wall -Wextra)
    endif()
    add_test(NAME ${name} COMMAND ${name})
endfunction()

chilli_add_test(chilli_tests tests/hard_sync_test.cpp)
chilli_add_test(resampler_tests tests/resampler_test.cpp)
chilli_add_test(asset_manager_tests tests/asset_manager_test.cpp)
chilli_add_test(routing_engine_tests tests/routing_engine_test.cpp)
chilli_add_test(wav_decoder_tests tests/wav_decoder_test.cpp)
chilli_add_test(voice_manager_tests tests/voice_manager_test.cpp)
