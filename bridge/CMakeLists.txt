cmake_minimum_required(VERSION 3.10)
project(dcbridge CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# SDK zip'i bridge/sdk/ içine çıkarılır; discordpp.h'nin yerini otomatik bul.
file(GLOB_RECURSE DISCORDPP_HEADER "${CMAKE_SOURCE_DIR}/sdk/*/discordpp.h")
if(NOT DISCORDPP_HEADER)
  message(FATAL_ERROR "Discord Social SDK bulunamadi. Zip'i bridge/sdk/ klasorune cikar.")
endif()
list(GET DISCORDPP_HEADER 0 DISCORDPP_HEADER)
get_filename_component(SDK_INCLUDE "${DISCORDPP_HEADER}" DIRECTORY)
get_filename_component(SDK_ROOT "${SDK_INCLUDE}" DIRECTORY)
message(STATUS "Discord Social SDK: ${SDK_ROOT}")

add_executable(dcbridge dcbridge.cpp)
target_include_directories(dcbridge PRIVATE "${SDK_INCLUDE}")
target_link_libraries(dcbridge PRIVATE "${SDK_ROOT}/lib/release/discord_partner_sdk.lib")
if(MSVC)
  target_compile_options(dcbridge PRIVATE /utf-8 /EHsc)
endif()
add_custom_command(TARGET dcbridge POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${SDK_ROOT}/bin/release/discord_partner_sdk.dll" "$<TARGET_FILE_DIR:dcbridge>")
