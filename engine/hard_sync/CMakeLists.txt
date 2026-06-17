cmake_minimum_required(VERSION 3.16)
project(chilli_hard_sync CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(chilli_engine INTERFACE)
target_include_directories(chilli_engine INTERFACE include)

add_executable(chilli_tests tests/hard_sync_test.cpp)
target_link_libraries(chilli_tests PRIVATE chilli_engine)

if (MSVC)
    target_compile_options(chilli_tests PRIVATE /permissive- /W4)
else()
    target_compile_options(chilli_tests PRIVATE -Wall -Wextra)
endif()

enable_testing()
add_test(NAME chilli_tests COMMAND chilli_tests)
