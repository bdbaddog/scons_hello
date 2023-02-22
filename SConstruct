################################################################################
# Filename:    SConstruct                                                      #
# License:     Public Domain                                                   #
# Author:      New Rupture Systems                                             #
# Description: Build script to build the classic Hello World program.          #
################################################################################
env = DefaultEnvironment(tools = [],
                         platform = ARGUMENTS.get("PLATFORM", None))
env.Tool("bmu", toolpath = [Dir("#").Dir("tools").Dir("scons")])

# Project name
PROJECT = "hello"

# Initial project modules (Name, SConscript path, Description)
MODULES = (("hello", Dir("src").Dir("hello"), "Hello World program."),
           ("goodbye", Dir("src").Dir("goodbye"), "Goodbye World program"))

# Known target platforms (Name : (Description, (TARGET_values ...)))
TARGET_PLATFORMS = {"Linux" : ("Generic x86-64 GNU/Linux OS",
                               {"TARGET_ARCH_TYPE" : "x86_64",
                                "TARGET_ARCH" : "x86_64",
                                "TARGET_OS_TYPE" : "Linux",
                                "TARGET_OS" : "GNU/Linux",
                                "TARGET_OS_KERNEL" : "Linux",
                                "TARGET_OBJFMT" : "ELF",
                                "TARGET_SUPPORT" : "posix.1-2008"}),
                    "Windows" : ("x86-64 Microsoft Windows 10 OS",
                                 {"TARGET_VENDOR" : "Microsoft",
                                  "TARGET_ARCH_TYPE" : "x86_64",
                                  "TARGET_ARCH" : "x86_64",
                                  "TARGET_OS_TYPE" : "Windows",
                                  "TARGET_OS" : "Windows 10",
                                  "TARGET_OS_KERNEL" : "NT",
                                  "TARGET_OBJFMT" : "PE",
                                  "TARGET_SUPPORT" : "bsd_socks"}),
                  "Custom" : ("Custom platform (set TARGET_* variables)", None)}

env.BuildMeUp(PROJECT, MODULES, TARGET_PLATFORMS)
