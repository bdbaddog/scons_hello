################################################################################
# Filename:    InstallEx.py                                                    #
# License:     Public Domain                                                   #
# Author:      New Rupture Systems                                             #
# Description: Defines the BuildMeUp method (via the BuildMeUp tool).          #
################################################################################
import os
import sys
import platform
try:
   # If threading is supported, use a Global Script Lock (GSL)
   import threading
   GSL = threading.Lock()
except ImportError:
   class DummyScriptLock(object):
      def acquire(self):
         pass

      def release(self):
         pass
   GSL = DummeyScriptLock()
from SCons.Script import *


#
# Class describing a module interrogator that extracts help related information.
# This information is then used to build an appropriate help message.
#
class ModuleHelp(object):
   @staticmethod
   def _format_vars_help(*args, **kwargs):
      opt = kwargs["opt"] if ("opt" in kwargs) else args[1]
      help = kwargs["help"] if ("help" in kwargs) else args[2]

      if help:
         pad = (" " * (20 - len(opt)))
         line = "  {0}{1}{2}\n".format(opt, pad, help)
      else:
         line = ""
      return line

   @staticmethod
   def _default_opts_GenerateHelpText(default_opts):
      help = ""
      for opt in default_opts:
         if len(opt[0]) < 30:
            pad = (" " * (30 - len(opt[0])))
         else:
            pad = ("\n" + (" " * 32))
         help += ("  {0}{1}{2}\n".format(opt[0], pad, opt[1]))
      return help

   def __init__(self, env, default_opts, default_vars, target_platforms,
                actions):
      self._env = env
      self._deps = {}
      self._opts = ""
      self._vars = ""
      self._mods = ""
      self._opts = ModuleHelp._default_opts_GenerateHelpText(default_opts)
      default_vars.FormatVariableHelpText = ModuleHelp._format_vars_help
      self._vars = default_vars.GenerateHelpText(env)
      self._target_platforms = target_platforms
      self._actions = actions

      # Add help about special variable PLATFORM
      v = ModuleHelp._format_vars_help(env, "PLATFORM", "SCons build platform")
      self._vars = (v + self._vars)

   def Process(self, module):
      if "options-variables" in self._actions:
         help = module.Options.GenerateHelpText()
         if help:
            self._opts += ("'{0}' options:\n".format(module.Name))
            self._opts += help
         help = module.Variables.GenerateHelpText()
         if help:
            self._vars += ("'{0}' variables:\n".format(module.Name))
            self._vars += help
      if "modules" in self._actions:
         self._mods += "  {0}\n".format(module.Name)
         self._mods += "    Path: {0}\n".format(os.path.relpath(module.Path,
                                                Dir("#").abspath))
         self._mods += "    Description: {0}\n".format(module.Description)
      if "dependencies" in self._actions:
         for dep_type in module.Dependencies:
            deps = module.Dependencies[dep_type]
            dep_type = dep_type.title()
            if dep_type not in self._deps:
               self._deps[dep_type] = set()
            self._deps[dep_type].update(deps)

   def GetResult(self):
      msg = ""
      if "options-variables" in self._actions:
         msg = "usage: scons [OPTION] [TARGET] ...\n"
         msg += "\nLocal options:\n"
         msg += self._opts
         msg += "\nLocal variables:\n"
         msg += self._vars
         msg += "\nKnown target platforms:\n"
         for tp in self._target_platforms:
            if len(tp) < 10:
               pad = (" " * (10 - len(tp)))
            msg += ("  {0}{1} - {2}\n".format(tp, pad,
                                                 self._target_platforms[tp][0]))
      if "modules" in self._actions:
         msg += "Modules:\n"
         msg += self._mods
      if "dependencies" in self._actions:
         msg += "Dependencies:\n"
         for dep_type in self._deps:
            msg += "  {0}:\n".format(dep_type)
            for dep in self._deps[dep_type]:
               msg += "    {0}\n".format(dep)
      return msg


#
# Class describing a module interrogator that extracts build related information
# which is then used to specify default module build objects.
#
class ModuleBuild(object):
   @staticmethod
   def _build_report_action_factory(env):
      def _build_report(target, source, env):
         errors = len(GetBuildFailures())
         report = (" Build Complete ({0} Errors) ".format(errors))
         pad1 = ("=" * ((50 - len(report)) // 2))
         pad2 = ("=" * (50 - (len(pad1) + len(report))))
         output = ("{0}{1}{2}\n".format(pad1, report, pad2))
         ModuleBuild._target_output_str(output)
         return 0
      return env.Action(_build_report, cmdstr = None)

   @staticmethod
   def _tests_report_action_factory(env, num_tests):
      def _tests_report(target, source, env):
         passed = env["TESTS_RESULTS"][0]
         failed = env["TESTS_RESULTS"][1]
         cached = (num_tests - (passed + failed))

         report = (" Tests Complete ({0} Passed, {1} Failed) ".format(
                                                                passed + cached,
                                                                        failed))

         if cached:
            cached = "  [{0} test(s) cached as PASSED]\n".format(cached)
         else:
            cached = ""

         pad1 = ("=" * ((50 - len(report)) // 2))
         pad2 = ("=" * (50 - (len(pad1) + len(report))))
         output = ("{0}{1}{2}{3}\n".format(cached, pad1, report, pad2))
         ModuleBuild._target_output_str(output)
         return 0
      return env.Action(_tests_report, cmdstr = None)

   @staticmethod
   def _install_report_action_factory(env):
      def _install_report(target, source, env):
         report = "  Install Complete  "
         pad1 = ("=" * ((50 - len(report)) // 2))
         pad2 = ("=" * (50 - (len(pad1) + len(report))))
         output = ("{0}{1}{2}\n".format(pad1, report, pad2))
         ModuleBuild._target_output_str(output)
         return 0
      return env.Action(_install_report, cmdstr = None)

   @staticmethod
   def _tests_start_action_factory(env, num_tests):
      def _tests_start(target, source, env):
         env["TESTS_RESULTS"] = [0, 0]
         output = "Running {0} test(s) ...\n".format(str(num_tests))
         ModuleBuild._target_output_str(output)
         return 0
      return env.Action(_tests_start, cmdstr = None)

   @staticmethod
   def _install_start_action_factory(env, num_outputs):
      def _install_start(target, source, env):
         output = "Installing {0} target(s) ...\n".format(str(num_outputs))
         ModuleBuild._target_output_str(output)
         return 0
      return env.Action(_install_start, cmdstr = None)

   @staticmethod
   def _test_action_factory(env, force, silent, mod_name, test_name, test):
      def _test(target, source, env):
         global GSL

         try:
            rtn = test(silent)
            if rtn is not True:
               if type(rtn) is str:
                  error = rtn
               else:
                  error = "Test returned non-True result"
               rtn = False
         except Exception as e:
            rtn = False
            error = str(e)

         output = "   {0} - [{1}] {2}\n".format("PASSED" if rtn else "FAILED",
                                                mod_name, test_name)
         if not rtn:
            output += ((" " * 6) + error + "\n")

         GSL.acquire()
         env["TESTS_RESULTS"][0 if rtn else 1] += 1
         ModuleBuild._target_output_str(output)
         GSL.release()

         if force:
            return 0
         else:
            return (0 if rtn else 1)
      return env.Action(_test, cmdstr = None)

   @staticmethod
   def _target_output_str(s):
      if not GetOption("silent"):
         sys.stdout.write(s)
         sys.stdout.flush()
      return 0

   def __init__(self, env, default_vars, installer, actions):
      self._env = env
      self._actions = actions
      self._test_targets = []
      self._installer = installer
      self._unknown_vars = list((default_vars.UnknownVariables()).keys())

   def Process(self, module):
      force = GetOption("ignore_errors")
      silent = GetOption("silent")
      env = self._env

      # Remove variables known by module from total unknown variables list
      module.Variables.Apply(self._env)
      module_unknowns = list((module.Variables.UnknownVariables()).keys())
      self._unknown_vars[:] = [var for var in self._unknown_vars
                               if var in module_unknowns]

      # Get any module outputs (at minimum to ensure any build targets are
      # specified for build)
      outputs = module.Outputs

      if "test" in self._actions:
         # Create an Action for each module test
         for test_name in module.Tests:
            test = module.Tests[test_name]
            name = "".join(["_" if not c.isalnum() else c for c in test_name])
            name = ("__test_" + module.Name + "__" + name)
            src = test.Dependencies()
            if not src:
               src = None
            test = test.Execute
            action = ModuleBuild._test_action_factory(env, force, silent,
                                               module.Name, test_name, test)

            if "TESTCMDDIR" in env:
               test_dir = env["TESTCMDDIR"]
            else:
               test_dir = Dir("#").Dir(".scontest_cmds")
            test_file = File(name, test_dir)

            if "TESTMODE" in env:
               test_mode = env["TESTMODE"]
            else:
               test_mode = "auto"

            if test_mode == "cache":
               target = test_file
            else:
               target = env.Command(test_file, src, [action, Touch(test_file)])
               if test_mode == "force":
                  env.AlwaysBuild(target)

            self._test_targets.append(target)
      if "install" in self._actions:
         for target_type in module.Installables:
            for entry in module.Installables[target_type]:
               target = entry[0]
               name = entry[1]
               cmd = entry[2]
               args = {target_type : target}
               if name is not None:
                  args["name"] = name
               if cmd is not None:
                  args["cmd"] = cmd
               self._installer.Add(**args)

   def GetResult(self):
      env = self._env

      # Using an Alias target here (as opposed to Command), as Alias targets are
      # not added as dependencies to implicit build targets
      action = ModuleBuild._build_report_action_factory(env)
      build_report = env.Alias("__build_report", None, action)
      env.AlwaysBuild(build_report)

      # Build report occurs after all regular targets have been built
      for target in BUILD_TARGETS:
         if ((str(target) != "test") and
             (str(target) != "install")):
            env.Requires(build_report, target)

      # Output a build report if either tests or an install will run
      if (("test" in self._actions) or
          ("install" in self._actions)):
         BUILD_TARGETS.extend(build_report)

      if "test" in self._actions:
         action = ModuleBuild._tests_start_action_factory(env,
                                                        len(self._test_targets))
         tests_start = env.Alias("__tests_start", None, action)
         action = ModuleBuild._tests_report_action_factory(env,
                                                        len(self._test_targets))
         tests_report = env.Alias("__tests_report", None, action)
         env.AlwaysBuild(tests_start)
         env.AlwaysBuild(tests_report)

         # Tests start after build report
         env.Requires(tests_start, build_report)
         for target in self._test_targets:
            env.Depends(target, tests_start)
            env.Depends(tests_report, target)
         env.Alias("test", [tests_start, tests_report])

      if "install" in self._actions:
         action = ModuleBuild._install_start_action_factory(env,
                                                   len(self._installer.Targets))
         install_start = env.Alias("__install_start", None, action)
         action = ModuleBuild._install_report_action_factory(env)
         install_report = env.Alias("__install_report", None, action)
         env.AlwaysBuild(install_start)
         env.AlwaysBuild(install_report)

         # Install starts after build report (and tests if any)
         if "test" in self._actions:
            env.Requires(install_start, tests_report)
         else:
            env.Requires(install_start, build_report)
         for target in self._installer.Targets:
            env.Depends(target, install_start)
            env.Depends(install_report, target)
         env.Alias("install", [install_start, install_report])

   def UnknownVariables(self):
      return self._unknown_vars


#
# Resolve name to one in specified list. Name is resolved to the first
# matching unambiguous name in the specified list (case-sensitivity is required
# only when the name would be ambiguous without it). If name cannot be resolved
# a NameError exception is raised.
#
# INPUT : name_type - Description of type of name to be resolved
#         name_list - List to resolve name against
#         unresolved_name - Name to resolve
# OUTPUT: [Return] - Resolved name
#
def resolve_name(name_type, name_list, unresolved_name):
   valid = False
   case_match = False
   match = False

   for n in name_list:
      if n.startswith(unresolved_name):
         if case_match:
            # Ambiguous name
            valid = False
            break
         else:
            valid = True
            case_match = True
            name = n
      elif ((not case_match) and
            (n.upper().startswith(unresolved_name.upper()))):
         if match == True:
            # Ambiguous name
            valid = False
         else:
            match = True
            valid = True
            name = n

   if not valid:
      if (case_match or match):
         error = "Ambiguous"
      else:
         error = "Unknown"

      raise NameError("{0} {1} '{2}'".format(error, name_type, unresolved_name))
   else:
      return name


#
# Initialize default options.
#
# INPUT : [None]
# OUTPUT: [Return] - Initialized default options
#
def init_default_options():
   # Local build options
   opts = (("--target=PLATFORM", "Specify target platform"),
           ("--variant=DIR", "Specify build directory"),
           ("--cache=DIR", "Specify build cache directory"),
           ("--prefix=DIR", "Specify installation directory"),
           ("--restrict=MODULES", "Restrict build to comma-separated modules "
                                   "list"),
           ("--tools=TOOLS", "Specify comma-separated list of build tools"),
           ("--with-debug", "Build with debugging information"),
           ("--verbose", "Build with verbose logging"),
           ("--test[=MODE]", "Run test(s), mode: [auto], force, cache"),
           ("--install[=MODE]", "Run install, mode: [auto], force, cache"),
           ("--help-dependencies", "Output module dependencies and exit"),
           ("--help-modules", "Output modules and exit"),
           ("--help", "Output this help message and exit"))

   AddOption("--target", dest = "target")
   AddOption("--variant", dest = "variant")
   AddOption("--cache", dest = "cache")
   AddOption("--prefix", dest = "prefix")
   AddOption("--restrict", dest = "restrict")
   AddOption("--tools", dest = "tools")
   AddOption("--with-debug", dest = "debug", action = "store_true")
   AddOption("--verbose", dest = "verbose", action = "store_true")
   AddOption("--test", dest = "test", nargs = "?", const = "auto")
   AddOption("--install", dest = "install", nargs = "?", const = "auto")
   AddOption("--help-modules", dest = "help-modules", action = "store_true")
   AddOption("--help-dependencies", dest = "help-dependencies",
             action = "store_true")

   return opts


#
# Initialize default Variables [object].
#
# INPUT : target_platforms - Known target platforms
# OUTPUT: [Return] - Initialized default Variables object
#
def init_default_variables(target_platforms):
   target_platform = None
   overrides = {}
   target_components = ("TARGET_VENDOR",
                        "TARGET_ARCH_TYPE",
                        "TARGET_ARCH",
                        "TARGET_OS_TYPE",
                        "TARGET_OS",
                        "TARGET_OS_VERSION",
                        "TARGET_OS_KERNEL",
                        "TARGET_OS_KERNEL_VERSION",
                        "TARGET_ABI",
                        "TARGET_LIBC",
                        "TARGET_OBJFMT",
                        "TARGET_SUPPORT")

   # Override options specifed on command-line
   if GetOption("target") is not None:
      try:
         target_platform = resolve_name("target platform",
                                        target_platforms.keys(),
                                        GetOption("target"))
      except NameError as error:
         silent = GetOption("silent")
         if not silent:
            print("Error: " + str(error))
         Exit(1)

      for key in target_components:
         if ((target_platforms[target_platform][1]) and
             (key in target_platforms[target_platform][1])):
            overrides[key] = target_platforms[target_platform][1][key]
         else:
            overrides[key] = ""

   # Override variables specified on command-line
   overrides.update(ARGUMENTS)

   # Create object to hold Variables
   variables = Variables(None, overrides)

   # Set default platform to current system
   target_platform = platform.system().lower()
   for tp in target_platforms:
      if tp.lower() == target_platform:
         target_platform = tp
         break
   else:
      # Can't resolve it, so take the 'first' target platform
      target_platform = tuple(target_platforms.values())[0]

   # Set default target platform variables
   for key in target_components:
      if ((target_platforms[target_platform][1]) and
          (key in target_platforms[target_platform][1])):
         default_value = target_platforms[target_platform][1][key]
      else:
         default_value = None
      variables.Add(key, "", default_value)

   return variables


#
# Callback executed when a command (buildling a target, performing an action,
# etc.) string should be output.
#
# INPUT : s - Command string to output
#         target - Target command string relates to
#         source - Source command string relates to
#         env - SCons environment
#
# OUTPUT: [None]
#
def output_command(*args, **kwargs):
   global GSL

   s = kwargs["s"] if ("s" in kwargs) else args[0]
   target = kwargs["target"] if ("target" in kwargs) else args[1]
   env = kwargs["env"] if ("env" in kwargs) else args[3]

   if env["VERBOSE"]:
      output = (s + "\n")
   else:
      if (not target or
          s.startswith("Chmod") or
          s.startswith("Copy") or
          s.startswith("Delete") or
          s.startswith("Mkdir") or
          s.startswith("Move") or
          s.startswith("Touch")):
         return

      # Max line is 80 characters
      if len(s) > (80 - len(" ...")):
         s = s[:(80 - len(" ..."))]
      output = (s + "\n")

   GSL.acquire()
   sys.stdout.write(output)
   sys.stdout.flush()
   GSL.release()


#
# Output a help message when an invalid option choice was specified.
#
# INPUT : option - Option string with bad choice
#         choices - Tuple of valid choices
# OUTPUT: [None]
#
def bad_optional_choice(option, choices):
   SetOption("help", True)
   help = "usage: scons [OPTION] [TARGET] ...\n"
   help += "\nError: --{0} optional argument must be one of {1}\n".format(
                                                           option, str(choices))
   Help(help)


##################################### Main #####################################
def BuildMeUp(env, project, modules, target_platforms):
   # Minimum required SCons version
   EnsureSConsVersion(3, 0, 1)

   # Needed tools (found in the required tools folder)
   tools = ("modularity", "configureex", "installex")
   for tool in tools:
      env.Tool(tool, toolpath = [Dir("#").Dir("tools").Dir("scons")])

   force = GetOption("ignore_errors")
   silent = GetOption("silent")

   # Initialize default options
   default_opts = init_default_options()

   # Initialize default variables
   default_vars = init_default_variables(target_platforms)

   # Handle '--test' and '--install' options
   choices = ("auto", "force", "cache")
   modes = {"test" : GetOption("test"), "install" : GetOption("install")}
   for opt_name in modes:
      mode = modes[opt_name]
      if mode is not None:
         if mode not in choices:
            bad_optional_choice(opt_name, choices)
            return
         if opt_name not in COMMAND_LINE_TARGETS:
            COMMAND_LINE_TARGETS.extend([opt_name])
            BUILD_TARGETS.extend([opt_name])

   # Update environment with default variables
   default_vars.Update(env)
   env.Replace(PROJECT_NAME = project,
               VERBOSE = bool(GetOption("verbose")),
               DEBUG = bool(GetOption("debug")),
               PRINT_CMD_LINE_FUNC = output_command,
               CONFIGURELOG = File(".sconf_log").abspath,
               CONFIGUREDIR = Dir(".sconf_tests").abspath,
               TESTMODE = modes["test"],
               INSTALLPROJECT = project,
               INSTALLMODE = modes["install"])

   # Switch to a variant build if scons is invoked from another directory
   directory = GetOption("directory")
   if directory:
      launch_dir = Dir(GetLaunchDir()).abspath
      if launch_dir != Dir("#").abspath:
         env.Replace(VARIANT = launch_dir)

   # Handle '--prefix' option
   prefix = GetOption("prefix")
   if prefix is not None:
      env.Replace(PREFIX = Dir(prefix).abspath)

   # Handle '--variant' option
   variant = GetOption("variant")
   if variant is not None:
      env.Replace(VARIANT = Dir(variant).abspath)

   # Handle '--cache' option
   cache = GetOption("cache")
   if cache is not None:
      env.CacheDir(Dir(cache).abspath)

   # Set file type command strings
   if not env["VERBOSE"]:
      env.Append(CCCOMSTR = "  CC $TARGET",
                 ASPPCOMSTR = "  AS $TARGET",
                 LINKCOMSTR = "  LD $TARGET")

   # Set SCons files location
   if "VARIANT" in env:
      variant = Dir(env["VARIANT"]).abspath
      env.Replace(CONFIGURELOG = Dir(variant).File(".sconf_log").abspath,
                  CONFIGUREDIR = Dir(variant).Dir(".sconf_tests").abspath,
                  TESTCMDDIR = Dir(variant).Dir(".scontest_cmds").abspath,
                  INSTALLCMDDIR = Dir(variant).Dir(".sconinstall_cmds").abspath)
      if "PREFIX" not in env:
         env.Replace(PREFIX = Dir(variant))
      env.SConsignFile(Dir(variant).File(".sconsign").abspath)
   else:
      env.SConsignFile(File(".sconsign").abspath)

   # Setup installer (may not be used, but variables should still be updated)
   installer = env.Installer(default_vars, force, silent)

   # Cache tools (for later build configurations)
   tools = GetOption("tools")
   if tools is None:
      tools = []
   else:
      tools = list(s.strip() for s in tools.split(","))
   tools.append("default")
   env.SetToolsCache(tools = tools,
                     toolpath = [Dir("#").Dir("tools").Dir("scons")])

   # Check for special targets 'test' and 'install'
   actions = []
   if "test" in COMMAND_LINE_TARGETS:
      actions.append("test")
   if "install" in COMMAND_LINE_TARGETS:
      actions.append("install")

   # Set module interrogator type (either help or build)
   if (GetOption("help") or
       GetOption("help-modules") or
       GetOption("help-dependencies")):
      if GetOption("help"):
         actions.append("options-variables")
      if GetOption("help-modules"):
         actions.append("modules")
      if GetOption("help-dependencies"):
         actions.append("dependencies")
      interrogator = ModuleHelp(env, default_opts, default_vars,
                                target_platforms, actions)
   else:
      interrogator = ModuleBuild(env, default_vars, installer, actions)

   # Build module tree
   try:
      restrict = GetOption("restrict")
      if restrict is not None:
         restrict = restrict.split(",")
      tree = env.ModuleTree(modules, interrogator.Process, force, restrict)
   except Exception as e:
      if not silent:
         print("Error: " + str(e))
      Exit(1)

   # Output help if requested and exit
   if type(interrogator) is ModuleHelp:
      SetOption("help", True)
      Help(interrogator.GetResult())
   else:
      # Special case, if special targets are the only command-line targets
      # specified, treat this like a DEFAULT_TARGETS build
      if COMMAND_LINE_TARGETS:
         specials = ("test", "install")
         n_specials = 0
         for s in specials:
            if s in COMMAND_LINE_TARGETS:
               n_specials = n_specials + 1
         if n_specials == len(COMMAND_LINE_TARGETS):
            BUILD_TARGETS.extend(DEFAULT_TARGETS)

      interrogator.GetResult()
      if not silent:
         # Warn about unknown variables
         for unknown in interrogator.UnknownVariables():
            print("Warning: ignoring unknown variable '{0}'".format(unknown))

         # Warn about module errors
         if tree.Errors:
            for mod in tree.Errors:
               print("Error::{0}: {1}".format(mod, tree.Errors[mod]))
            print("Warning: One or more modules reported errors, some targets "
                  "may not be built")


def generate(env):
   env.AddMethod(BuildMeUp, "BuildMeUp")


def exists(env):
   return True
