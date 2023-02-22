################################################################################
# Filename:    Modularity.py                                                   #
# License:     Public Domain                                                   #
# Author:      New Rupture Systems                                             #
# Description: Defines functions and methods for using the Modularity tool.    #
################################################################################
try:
   # Python 3.3+ 
   from collections.abc import Mapping
except ImportError:
   from collections import Mapping
from SCons.Script import *


#
# Class describing module options. Module options are added in a defined modules
# OPTIONS stage. The 'Add' methods parameters are similiar to the standard
# 'AddOption' parameters, with the addition that 'dest' may be None, in which
# case the options value is stored in the environment (keyed to the uppercase
# option name(s)).
#
class ModuleOptions(Mapping):
   _opt_idx = 0

   @staticmethod
   def _format_help(*args, **kwargs):
      opt = kwargs["opt"] if ("opt" in kwargs) else args[1]
      help = kwargs["help"] if ("help" in kwargs) else args[2]

      if len(opt) < 30:
         pad = (" " * (30 - len(opt)))
      else:
         pad = ("\n" + (" " * 30))
      line = ("  {0}{1}{2}\n".format(opt, pad, help))
      return line

   @staticmethod
   def _get_value_factory(dest):
      def _get_opt():
         value = GetOption(dest)
         return value
      return _get_opt

   def __init__(self):
      self.FormatOptionHelpText = ModuleOptions._format_help
      self._options = {}
      self._help = []

   def __len__(self):
      return len(self._options)

   def __getitem__(self, key):
      if key in self._options:
         value = self._options[key]()
      else:
         for dest in self._options:
            if type(dest) is tuple:
               if key in dest:
                  value = self._options[dest]()
                  break
         else:
            value = GetOption(key)
      return value

   def __iter__(self):
      return self.__gen_list()

   def Clone(self):
      # Not quite a deep-copy clone, clone copies don't update '_help'
      # variable with parent values (which means they will not appear in the
      # Help options for this module)
      clone = ModuleOptions()
      clone._options = dict(self._options)
      return clone

   def Add(self, *args, **kwargs):
      dest = None
      val = None

      # Fixup destination if storing in Environment dictionary
      if ("dest" in kwargs) and not kwargs["dest"]:
         dest = "__env_add_opt_dest__"
         kwargs["dest"] = dest

      # Call AddOption() with proper args
      prefix_names = []
      for arg in args:
         prefix_names.append("--" + arg)
      AddOption(*prefix_names, **kwargs)

      # Save prefix names and value for later retrieval
      if dest:
         # Key for each arg (make key uppercase to be proper)
         dest = []
         for arg in args:
            dest.append(arg.upper())

         dest = tuple(dest)
         placeholder = ("__opt_env_dest__" + str(ModuleOptions._opt_idx))
         ModuleOptions._opt_idx += 1
         get = ModuleOptions._get_value_factory(placeholder)
      elif "dest" in kwargs:
         dest = kwargs["dest"]
         get = ModuleOptions._get_value_factory(dest)
      self._options[dest] = get

      # Save option name(s) and help text for later generation
      opt_names = ""
      for i in range(len(prefix_names)):
         opt_names += prefix_names[i]
         if "metavar" in kwargs:
            opt_names += ("=" + kwargs["metavar"])
         if i < (len(prefix_names) - 1):
            opt_names += ", "
      option = (opt_names, kwargs["help"] if ("help" in kwargs) else "")
      self._help.append(option)

   def Apply(self, env):
      for dest in self._options:
         if type(dest) is tuple:
            for d in dest:
               env[d] = self._options[dest]()

   def GenerateHelpText(self, sort = None):
      help_txt = ""

      if sort is not None:
         raise NotImplementedError("Option sorting")

      for opt in self._help:
         help_txt += self.FormatOptionHelpText(opt = opt[0], help = opt[1])
      return help_txt

   def __gen_list(self):
      for o in self._options:
         yield o


#
# Class describing module variables. Module variables are added in a defined
# modules OPTIONS stage. The 'Add' methods parameters are similiar to the
# standard 'variables.Add' object parameters, with the additional keyword 'dest'
# being available to specify a key name to retrieve the variables value (via the
# 'env.GetVariable' method).
#
class ModuleVariables(Mapping):
   @staticmethod
   def _format_help(*args, **kwargs):
      opt = kwargs["opt"] if ("opt" in kwargs) else args[1]
      help = kwargs["help"] if ("help" in kwargs) else args[2]

      if help:
         pad = (" " * (20 - len(opt)))
         line = "  {0}{1}{2}\n".format(opt, pad, help)
      else:
         line = ""
      return line

   @staticmethod
   def _get_env_var_factory(values):
      def _get_var(env, key):
         return values[key]
      return _get_var

   def __init__(self):
      self.FormatVariableHelpText = ModuleVariables._format_help
      self._variables = Variables()
      self._env_vars = []
      self._internal_vars = {}
      self._values_read = False
      self._values = {}

   def __len__(self):
      return len(self._values)

   def __getitem__(self, key):
      if self._values_read is False:
         self.__read_values()
      return self._values[key]

   def __iter__(self):
      if self._values_read is False:
         self.__read_values()
      return self.__gen_list()

   def Clone(self):
      # Not quite a deep-copy clone, clone copies don't update their Variables
      # object with parent values (which means they will not appear in the
      # variable Help or Unknown-determination for this module)
      clone = ModuleVariables()

      if self._values_read is False:
         self.__read_values()

      clone._internal_vars = dict(self._internal_vars)
      clone._env_vars = list(self._env_vars)
      clone._values = dict(self._values)
      return clone

   def Add(self, *args, **kwargs):
      key = kwargs["key"] if ("key" in kwargs) else args[0]
      dest = None

      # If using variable 'convience' functions, tuple returned may not have
      # been explicitly expanded into 'args', so we'll do it here
      if type(key) is not str:
         args = key
         key = args[0]

      # Fixup kwargs
      if "dest" in kwargs:
         dest = kwargs["dest"]
         del kwargs["dest"]

      # Call Add() with proper args
      self._variables.Add(*args, **kwargs)

      # Store key name in appropriate list
      if dest:
         self._internal_vars[dest] = key
      else:
         self._env_vars.append(key)

      # Reset values variable so newly added variables are extracted
      self._values_read = False

   def Apply(self, env):
      if self._values_read is False:
         self.__read_values()

      # Add 'env.GetVariable' method for alternatively retrieving variables
      method = ModuleVariables._get_env_var_factory(self._values)
      env.AddMethod(method, "GetVariable")

      # Apply variables to environment
      for v in self._env_vars:
         env[v] = self._values[v]

   def GenerateHelpText(self, sort = None):
      env = DefaultEnvironment()
      self._variables.FormatVariableHelpText = self.FormatVariableHelpText
      return self._variables.GenerateHelpText(env, sort)

   def UnknownVariables(self):
      return self._variables.UnknownVariables()

   def __gen_list(self):
      for v in self._values:
         yield v

   def __read_values(self):
      env = Environment(tools = [])

      # Spill variables into an environment and extract their values
      self._variables.Update(env)

      # Save and update internal variables values
      for v in self._internal_vars:
         value = env[self._internal_vars[v]]
         self._values[v] = value

      # Save environment variables values
      for v in self._env_vars:
         self._values[v] = (env[v] if (v in env) else None)

      self._values_read = True


#
# Class describing a modules output. Each output is bound to a specific target
# and classified as a specific target type (BIN/DOC/LIB/etc.).
#
class ModuleOutput(object):
   def __init__(self, module, target_type, target):
      self._module = module
      self._target_type = target_type
      self._target = target
      self._installed = False

   def __str__(self):
      return str(Flatten(self._target)[0])

   def Clone(self, module):
      clone = ModuleOutput(module, self._target_type, self._target)
      clone._installed = self._installed
      return clone

   def Test(self, name, cmd):
      self._module.Tests.Add(name, cmd, self._target)

   def Install(self, enable = True, name = None, cmd = None):
      if enable:
         args = {self._target_type : self._target}
         if ((name is None) and
             (cmd is None)):
            if not self._installed:
               # Plain target install
               self._module.Installables.Add(**args)
         else:
            if name is not None:
               args["name"] = name
            if cmd is not None:
               args["cmd"] = cmd

            # New name/command target install
            self._module.Installables.Add(**args)

      self._installed = True

   def InstallExtra(self, **kwargs):
      # This method is an alias for 'module.Installables.Add'
      self._module.Installables.Add(**kwargs)


#
# Class describing a module test. A Test is simply a function that returns True
# if its testing criteria is met. Otherwise a non-True value, string or
# exception is thrown. A Test dependency (or dependencies) may also be specified
# indicating targets required for the test to run.
#
class ModuleTest(object):
   def __init__(self, cmd, dependency):
      if not callable(cmd):
         raise ValueError("Test command not callable")
      else:
         self._cmd = cmd

      if dependency is None:
         self._dependencies = tuple()
      else:
         try:
            _ = iter(dependency)
            self._dependencies = dependency
         except TypeError:
            self._dependencies = (dependency,)

   def Execute(self, silent):
      return self._cmd(silent)

   def Dependencies(self):
      return self._dependencies


#
# Class describing a dictionary of outputs.
#
class ModuleOutputs(Mapping):
   def __init__(self, module):
      self._module = module
      self._outputs = {}

   def __getitem__(self, key):
      return self._outputs[key]

   def __len__(self):
      return len(self._outputs)

   def __iter__(self):
      return self.__gen_list()

   def Clone(self, module):
      clone = ModuleOutputs(module)
      for o in self._outputs:
         clone._outputs[o] = self._outputs[o].Clone(module)
      return clone

   def Add(self, **kwargs):
      if "name" in kwargs:
         name = kwargs["name"]
      else:
         name = None
      for key in kwargs:
         if key != "name":
            if not name:
               name = str(Flatten(kwargs[key])[0])

            if not all((c.isalnum() or (c == ".") or (c == "_")) for c in name):
               raise ValueError("Invalid Output name")
            if name in self._outputs:
               raise KeyError("Module already specifies an Output named '" +
                              name + "'")
            else:
               output = ModuleOutput(self._module, key, kwargs[key])
               self._outputs[name] = output

   def __gen_list(self):
      for o in self._outputs:
         yield o


#
# Class describing a dictionary of tests.
#
class ModuleTests(Mapping):
   def __init__(self):
      self._tests = {}

   def __getitem__(self, key):
      return self._tests[key]

   def __len__(self):
      return len(self._tests)

   def __iter__(self):
      return self.__gen_list()

   def Clone(self):
      clone = ModuleTests()
      clone._tests = dict(self._tests)
      return clone

   def Add(self, name, cmd, dependency = None):
      if ((not name) or
          (not all((c.isalnum() or (c == ".") or (c in "-_ ")) for c in name))):
         raise ValueError("Invalid Test name")

      test = ModuleTest(cmd, dependency)
      if name in self._tests:
         raise KeyError("Module already contains test named '{0}'".format(name))
      else:
         self._tests[name] = test

   def __gen_list(self):
      for t in self._tests:
         yield t


#
# Class describing a dictionary of installables (targets that should be
# installed).
#
class ModuleInstallables(Mapping):
   def __init__(self):
      self._installables = {}
      self._num_installables = 0

   def __getitem__(self, key):
      return tuple(self._installables[key])

   def __len__(self):
      return self._num_installables

   def __iter__(self):
      return self.__gen_list()

   def Clone(self):
      clone = ModuleInstallables()
      for i in self._installables:
         clone._installables[i] = list(self._installables[i])
      clone._num_installables = self._num_installables
      return clone

   def Add(self, **kwargs):
      if "name" in kwargs:
         name = str(kwargs["name"])
      else:
         name = None
      if "cmd" in kwargs:
         cmd = kwargs["cmd"]
         if not callable(cmd):
            raise ValueError("Install command not callable")
      else:
         cmd = None
      for key in kwargs:
         if ((key != "name") and
             (key != "cmd")):

            target = kwargs[key]
            entry = (target, name, cmd)
            if key in self._installables:
               self._installables[key].append(entry)
            else:
               self._installables[key] = [entry]

            self._num_installables += 1

   def __gen_list(self):
      for i in self._installables:
         yield i


#
# Class describing a module descriptor. A module descriptor encapsulates a
# module declaration (module Name, Path and, optionally, Description).
class ModuleDescriptor(object):
   def __init__(self, name, path = None, description = None):
      try:
         _ = iter(name)
         if type(name) is str:
            raise TypeError()
         self.Name = name[0]
         self.Path = name[1]
         if len(name) > 2:
            self.Description = name[2]
         else:
            self.Description = None
      except TypeError:
         self.Name = name
         self.Path = path
         self.Description = description

      if self.Path is None:
         raise ValueError("Module definition file required")

      if not all((c.isalnum() or (c == ".") or (c == "_")) for c in self.Name):
         raise ValueError("Invalid module name")

      # Module path must be a Dir() Node
      if type(self.Path) is not type(Dir("#")):
         raise TypeError("Module path must be a File or Dir Node")
      else:
         self.Path = (self.Path.srcnode()).abspath

      if self.Description is None:
         self.Description = ""

#
# Class describing a module. A module encapsulates the information provided by
# a module declaration and its eventual definition. Additional module details
# are added in each stage when the module is interrogated.
#
class Module(object):
   UseConfigureEx = False

   @staticmethod
   def _env_set_output(env, **kwargs):
      env["__module_outputs__"].Add(**kwargs)

   def __init__(self, env, new_submodule, interrogator, descriptor, **kwargs):
      self.Name = descriptor.Name
      self.Path = descriptor.Path
      self.Description = descriptor.Description
      self._env = env
      self._new_submodule = new_submodule
      self._interrogator = interrogator
      self._submodules = {}
      self._opts = None
      self._vars = None
      self._deps = None
      self._outputs = None
      self._tests = None
      self._installables = None
      self._inherited_stages = {}
      self._stages = {}
      self._env_configured = False
      self._defined = False
      self._selected = (False if (interrogator is None) else True)

      # Update 'module' variable to current module
      Export(module = self)
      Import("module")

      # Define module
      if "defined" in kwargs:
         del kwargs["defined"]
         self.Define(**kwargs)
      else:
         self.__read_module()

   def __str__(self):
      return self.Name

   @property
   def Options(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._opts is None: 
         if "OPTIONS" in self._inherited_stages:
            (self._opts, self._vars) = self._inherited_stages["OPTIONS"]()
         else:    
            self._opts = ModuleOptions()
            self._vars = ModuleVariables()
         self._get_opts()
      return self._opts

   @property
   def Variables(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._vars is None:
         if "OPTIONS" in self._inherited_stages:
            (self._opts, self._vars) = self._inherited_stages["OPTIONS"]()
         else:
            self._opts = ModuleOptions()
            self._vars = ModuleVariables()
         self._get_opts()
      return self._vars

   @property
   def Dependencies(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._deps is None:
         if "CONFIGURATION" in self._inherited_stages:
            (deps, conf) = self._inherited_stages["CONFIGURATION"]
            self._deps = deps()
         else:
            self._deps = {}
         self._get_deps()
      return self._deps

   @property
   def Outputs(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._outputs is None:
         if "CONFIGURATION" in self._inherited_stages:
            (deps, conf) = self._inherited_stages["CONFIGURATION"]
            self._env = conf()
         if "BUILD" in self._inherited_stages:
            self._outputs = self._inherited_stages["BUILD"](self)
         else:
            self._outputs = ModuleOutputs(self)
         self._get_outputs()
      return self._outputs

   @property
   def Tests(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._tests is None:
         if "TEST" in self._inherited_stages:
            self._tests = self._inherited_stages["TEST"]()
         else:
            self._tests = ModuleTests()
         self._get_tests()
      return self._tests

   @property
   def Installables(self):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")
      if self._installables is None:
         if "INSTALL" in self._inherited_stages:
            self._installables = self._inherited_stages["INSTALL"]()
         else:
            self._installables = ModuleInstallables()
         self._get_installables()
      return self._installables

   @property
   def Selected(self):
      return self._selected

   def Export(self, *args):
      if self._defined is False:
         raise RuntimeError(self.Name + ": Module not yet defined")

      exports = {"OPTIONS" : (lambda : (self.Options.Clone(),
                                        self.Variables.Clone())),
                 "CONFIGURATION" : (lambda : dict(self.Dependencies),
                                    lambda : self.__configure()),
                 "BUILD" : (lambda module: self.Outputs.Clone(module)),
                 "TEST" : (lambda : self.Tests.Clone()),
                 "INSTALL" : (lambda : self.Installables.Clone())}

      if ((len(args) == 1) and
          (args[0] == "*")):
         result = dict(exports)
      else:
         result = {}
         for arg in args:
            stage = arg.upper()
            if stage in exports:
               result[stage] = exports[stage]
            else:
               raise ValueError(self.Name + ": Unknown export stage")
      return result

   def Define(self, **kwargs):
      if self._defined is True:
         raise RuntimeError(self.Name + ": Module already defined")

      known_stages = ("OPTIONS", "CONFIGURATION", "BUILD", "TEST", "INSTALL")

      # Process callbacks and special keywords
      for key in kwargs:
         stage = key.upper()
         if stage in known_stages:
            if not callable(kwargs[key]):
               raise RuntimeError(self.Name + ": Stage not callable")
            else:
               self._stages[stage] = kwargs[key]
         elif key == "inherit":
            inherit = kwargs[key]
            if callable(inherit):
               inherit = kwargs[key]()
            if type(inherit) is not dict:
               raise TypeError(self.Name + ": Expected exported dictionary")
            else:
               self._inherited_stages = inherit
         else:
            raise KeyError(self.Name + ": Unknown stage '" + str(key) + "'")
      self._defined = True

      # Call interrogater method to extract required information
      if self._interrogator is not None:
         self._interrogator(self)

      # Add any new submodules to tree
      for descriptor in self._submodules:
         kwargs = self._submodules[descriptor]
         if kwargs is None:
            kwargs = {}
         else:
            kwargs["defined"] = True
         self._new_submodule(descriptor, **kwargs)

      # Restore the global variable 'module' (if a submodule changed it)
      Export(module = self)
      Import("module")

   def DeclareSubmodule(self, name, path = None, description = None):
      if self._defined is True:
         raise RuntimeError(self.Name + ": Submodules already declared")

      try:
         _ = iter(name)
         if type(name) is str:
            raise TypeError()
         else:
            submodule_descriptors = name
      except TypeError:
         submodule_descriptors = ((name, path, description),)

      for descriptor in submodule_descriptors:
         descriptor = ModuleDescriptor(descriptor)
         if descriptor in self._submodules:
            raise KeyError(self.Name + ": Submodule already declared")
         else:
            self._submodules[descriptor] = None

   def DefineSubmodule(self, name, description = None, **kwargs):
      if self._defined is True:
         raise RuntimeError(self.Name + ": Submodules already defined")

      descriptor = ModuleDescriptor(name, Dir("#"), description)
      descriptor.Path = self.Path

      if descriptor in self._submodules:
         raise KeyError(self.Name + ": Submodule already declared")

      # Handle 'inherit' keyword convenience types
      # inherit = "STAGE" OR
      # inherit = ["STAGE", ...] OR
      # inherit = True
      if "inherit" in kwargs:
         inherit = kwargs["inherit"]
         if type(inherit) is bool:
            inherit_stages = ("*",)
         elif type(inherit) is str:
            inherit_stages = (inherit,)
         else:
            try:
               _ = iter(inherit)
               inherit_stages = inherit
            except TypeError:
               inherit_stages = None
         if inherit_stages is not None:
            kwargs["inherit"] = lambda : self.Export(*inherit_stages)

      self._submodules[descriptor] = kwargs

   def _get_opts(self):
      if "OPTIONS" in self._stages:
         call = lambda : self._stages["OPTIONS"](self._opts, self._vars)
         self.__call_stage(call)

   def _get_deps(self):
      if (("CONFIGURATION" in self._stages) and
          (Module.UseConfigureEx)):
         try:
            conf = self._env.ConfigureEx(listing = self._deps)
            call = lambda : self._stages["CONFIGURATION"](conf)
            self.__call_stage(call)
         finally:
            conf.Finish()

   def _get_outputs(self):
      if "BUILD" in self._stages:
         self.__configure()
         self.Options.Apply(self._env)
         self.Variables.Apply(self._env)

         # Add 'env.ModuleOutput' method for specifying module outputs
         self._env["__module_outputs__"] = self._outputs
         self._env.AddMethod(Module._env_set_output, "ModuleOutput")

         call = lambda : self._stages["BUILD"](self._env)
         self.__call_stage(call)

   def _get_tests(self):
      if "TEST" in self._stages:
         # Access property to ensure outputs are known
         call = lambda : self._stages["TEST"](self.Outputs)
         self.__call_stage(call)

   def _get_installables(self):
      if "INSTALL" in self._stages:
         # Access property to ensure outputs are known
         call = lambda : self._stages["INSTALL"](self.Outputs)
         self.__call_stage(call)

      # A default Install() call occurs for all Outputs which haven't
      # previously called Install(). If Install() had been previously called
      # for an Output, the below call is treated as a no-op.
      for output in self.Outputs:
         self._outputs[output].Install()

   def __configure(self):
      if not self._env_configured:
         self._env_configured = True
         if "CONFIGURATION" in self._stages:
            try:
               if Module.UseConfigureEx:
                  conf = self._env.ConfigureEx()
               else:
                  conf = self._env.Configure()
               self._stages["CONFIGURATION"](conf)
            finally:
               self._env = conf.Finish()
         else:
            env = self._env.Clone()
            self._env = env
      return self._env

   def __call_stage(self, func):
      # Assign the global variable 'module' to be whatever module is currrently
      # executing this stage
      Export(module = self)
      Import("module")
      result = func()
      return result

   def __variant_sub_dir(self, src_dir):
      ref_dir = Dir("#").File("_").abspath
      for i in range(len(src_dir)):
         if src_dir[i] != ref_dir[i]:
            break
      return src_dir[i:]

   def __read_module(self):
      # Read (execute) module
      args = {}
      if (("VARIANT" in self._env)):
         sub_dir = self.__variant_sub_dir(self.Path)
         args["variant_dir"] = Dir(sub_dir, self._env["VARIANT"]).abspath
         if "DUPSRC" in self._env:
            args["duplicate"] = self._env["DUPSRC"]

      self._env.SConscript(dirs=[self.Path], **args)

      if not self._defined:
         raise RuntimeError((self.Name, + ": Module missing definition"))


#
# Class describing a module tree. A module tree is grown (walked) from the
# initially provided module descriptors (triplets) and any subsequent submodules
# declared/defined by these modules. Modules that are selected (as determined by
# the module selectors in 'restrict') are passed to the provided interrogator
# function where the required information can be extracted.
#
class ModuleTreeBase(object):
   def __init__(self, env, module_descriptors, interrogator, force, restrict):
      self.Errors = {}
      self._env = env
      self._interrogator = interrogator
      self._current_descriptor = None
      self._new_descriptors = []
      self._force = force

      # Prefer ConfigureEx if tool present in environment
      for tool in env["TOOLS"]:
         if str(tool).lower().endswith("configureex"):
            Module.UseConfigureEx = True
            break

      # Convert module descriptors in list to proper object
      initial_descriptors = []
      for descriptor in module_descriptors:
         initial_descriptors.append(ModuleDescriptor(descriptor))

      # Set restrict argument (if not provided, entire tree is built)
      if restrict is None:
         self._module_selectors = (":",)
      else:
         try:
            _ = iter(restrict)
            if type(restrict) is str:
               raise TypeError()
            self._module_selectors = restrict
         except TypeError:
            self._module_selectors = (restrict,)

      # Walk tree from initial (seed) module descriptors
      path = [iter(initial_descriptors)]
      while True:
         try:
            self._current_descriptor = next(path[-1])
            (follow, selected) = self._analyze(self._current_descriptor.Name)

            if follow or selected:
               self._create_module(self._current_descriptor, selected)
               if follow and self._new_descriptors:
                  # Decend down branch
                  path.append(iter(self._new_descriptors))
                  self._new_descriptors = []
         except StopIteration:
            path.pop()
            if not path:
               # Complete, tree walked
               break

   def _create_module(self, descriptor, selected, m_kwargs = {}):
      try:
         # Create module from descriptor
         Module(self._env, self.__new_submodule,
                (self._interrogator if selected else None), descriptor,
                **m_kwargs)
      except Exception as error:
         if self._force:
            self.Errors[descriptor.Name] = str(error)
         else:
            raise error

   def _analyze(self, name):
      follow = False
      selected = False
      name = name.split(":")

      # Check if any module selector matches the name given (or an expected
      # decendant thereof)
      for ms in self._module_selectors:
         fnpos = iter(name)
         wildcard = False
         ms = tuple(s.strip() for s in ms.split(":"))
         for m in ms:
            if m:
               try:
                  while True:
                     if m == next(fnpos):
                        wildcard = False
                        break
                     elif not wildcard:
                        raise RuntimeError("Module/submodules not selected")
               except StopIteration:
                  # Module is within selection path (not selected, but a
                  # descendant module will be, so follow this module to it)
                  follow = True
                  break
               except RuntimeError:
                  # Module and any submodules are not selected
                  break
            else:
               wildcard = True
         else:
            # All modules in selector are within path
            if wildcard:
               follow = True
               selected = True
            else:
               try:
                  m = next(fnpos)
               except StopIteration:
                  selected = True

      return (follow, selected)

   def __new_submodule(self, descriptor, **kwargs):
      # Modify name to include lineage (i.e. path from tree root)
      descriptor.Name = (self._current_descriptor.Name + ":" + descriptor.Name)

      if descriptor.Path == self._current_descriptor.Path:
         # Submodule is within the same file as module currently being read, so
         # if needed, create it now to be defined in the same context
         (follow, selected) = self._analyze(descriptor.Name)
         if selected:
            self._create_module(descriptor, selected, kwargs)            
      else:
         # Defer submodule creation until parent finishes
         self._new_descriptors.append(descriptor)


def ModuleTree(env,
               module_descriptors,
               interrogator,
               force = False,
               restrict = None):
   # Create ModuleTree base object
   return ModuleTreeBase(env, module_descriptors, interrogator, force, restrict)


def generate(env):
   env.AddMethod(ModuleTree, "ModuleTree")


def exists(env):
   return True
