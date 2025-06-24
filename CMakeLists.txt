cmake_minimum_required(VERSION 3.10)
project(ReaperMutedTracksToggle)

# Set C++ standard
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Set the library prefix, which is common for both platforms
set(CMAKE_SHARED_LIBRARY_PREFIX "reaper_")

# Define common source files
set(SOURCE_FILES src/main.cpp)

# Define common include directories
include_directories(
    vendor/reaper-sdk-main/sdk
    vendor/reaper-sdk-main/reaper-plugins
    vendor/WDL-main/WDL
)

# --- Platform-specific configuration ---
if(APPLE)
    # macOS specific settings
    set(CMAKE_SHARED_LIBRARY_SUFFIX ".dylib")
    add_definitions(-DSWELL_PROVIDED_BY_APP -D_REAPER_PLUGIN_NO_INCLUDE_LOWLEVEL_FUNCTIONS)

    # Add SWELL for macOS (emulation layer)
    include_directories(vendor/WDL-main/WDL/swell)
    list(APPEND SOURCE_FILES
        vendor/WDL-main/WDL/swell/swell-generic-gdk.cpp
        vendor/WDL-main/WDL/swell/swell-misc-generic.cpp
        vendor/WDL-main/WDL/swell/swell-menu-generic.cpp
        vendor/WDL-main/WDL/swell/swell-wnd-generic.cpp
        vendor/WDL-main/WDL/swell/swell-appstub-generic.cpp
    )

    # Find and set link libraries for macOS
    find_library(COCOA_LIB Cocoa)
    find_library(ICARBON_LIB Carbon)
    find_library(IOKIT_LIB IOKit)
    set(LINK_LIBS ${COCOA_LIB} ${ICARBON_LIB} ${IOKIT_LIB})

elseif(WIN32)
    # Windows specific settings
    set(CMAKE_SHARED_LIBRARY_SUFFIX ".dll")
    # On Windows, we don't need SWELL because WDL uses native Windows APIs.
    # Visual Studio will handle linking standard system libraries like user32, gdi32, etc.
endif()

# Create the shared library (plugin) with explicit name
add_library(ReaperMutedTracksToggle SHARED ${SOURCE_FILES})

# Link platform-specific libraries
if(APPLE)
    target_link_libraries(ReaperMutedTracksToggle ${LINK_LIBS})
endif()

# Installation steps (optional, but good practice)
install(TARGETS ReaperMutedTracksToggle
    LIBRARY DESTINATION ${CMAKE_BINARY_DIR}
) 