cmake_minimum_required(VERSION 2.8.9)

project(UltrasoundCalibration)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://slicer.org/slicerWiki/index.php/Documentation/Nightly/Extensions/UltrasoundCalibration")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_CONTRIBUTORS "Matthew S. Holden (PerkLab, Queen's University)")
set(EXTENSION_DESCRIPTION "This extension contains various module for ultrasound calibration.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/UltrasoundCalibration.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/UltrasoundCalibration/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(PointerBasedUSCalibration)
add_subdirectory(ImagelessUSCalibration)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
