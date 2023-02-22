################################################################################
# Filename:    ConfigureEx.py                                                  #
# License:     Public Domain                                                   #
# Author:      New Rupture Systems                                             #
# Description: Defines functions and methods for using the Extended            #
#              Configuration tool.                                             #
################################################################################
import os
import os.path
import struct
from SCons.Script import *
from SCons.SConf import progress_display
from SCons.SConf import SetProgressDisplay

# Display function (may be disabled in class "ConfExBase")
def _ConfExDisplay(msg):
   print(msg)

ConfExDebug = _ConfExDisplay


#
# Validate linker. Linker is considered valid if an attempt to link a test file
# is successful. In addition, the output file created by the linker may be
# validated if the parameters 'output_format' and 'output_isa' are set (either
# explicitly or via the default arguments). The special (default) value
# '<target>' mat be specified for either parameter which will resolve to the
# current target object format and target ISA respectively.
#
# INPUT : context - SCons Configure() test context
#         src_build - Input to test linker. May be a known string (in which
#                     case a pre-defined link using a known input component will
#                     be used) or a callable (which must return a list of
#                     objects that will attempt to be linked together)
#         output_format - Expected linker output file format (or '<target>')
#         output_isa - Expected linker output file ISA (or '<target>')
# OUTPUT: [Return] - int(True) if linker valid, int(False) otherwise
#
def CheckLink(context, output_format = "<target>", output_isa = "<target>",
              src_build = "C"):
   src_ext = {"C" : ("\nint main()\n{\n    return 0;\n}\n", ".c")}
   file_format = ("PE", "ELF")
   file_isa = ("x86", "x86_64", "AVR")
   isa_suffix = {file_isa[0] : "32",
                 file_isa[1] : "64"}
   elf_isa = {0  : "None",
              3  : file_isa[0],
              62 : file_isa[1],
              83 : file_isa[2]}

   pe_isa = {0    : "None",
            332   : file_isa[0],
            34404 : file_isa[1]}
   link_file = None
   check_passed = False

   # Resolve parameters
   if output_format == "<target>":
      if "TARGET_OBJFMT" in context.env:
         output_format = context.env["TARGET_OBJFMT"]
      else:
         raise ValueError("Unable to determine target output format")
   if output_isa == "<target>":
      if "TARGET_ARCH_TYPE" in context.env:
         output_isa = context.env["TARGET_ARCH_TYPE"]
      else:
         raise ValueError("Unable to determine target output ISA")

   # Check parameters
   if ((not callable(src_build)) and
       (src_build not in src_ext.keys())):
         raise ValueError("Specified source build unknown")
   if (output_format and
       (output_format not in file_format)):
      raise ValueError("Target output object format unknown")
   if (output_isa and
       (output_isa not in file_isa)):
      raise ValueError("Target output ISA format unknown")

   if output_format:
      isa = (isa_suffix[output_isa] if output_isa in isa_suffix else "")
      fmt = "({0}{1}{2}) ".format((output_isa + "-") if output_isa else "",
                                   output_format, isa)
   else:
      fmt = ""

   context.Message("Checking whether the linker " + fmt + "works... ")

   try:
      if callable(src_build):
         # Try to build up an action string to link all objects together. Given
         # the large variety of ways that LINKCOM can be specified the below is
         # a hopeful attempt at covering the most common "plain string" case
         action = str(context.env["LINKCOM"])
         sources = ""
         objs = src_build(context)

         for obj in objs:
            sources += (" " + str(obj))

         action = action.replace("$SOURCES", sources)
         builder = Builder(action = action)
         context.env.Append(BUILDERS = {'CustomProgram' : builder})
         linked = context.TryBuild(context.env.CustomProgram)
      else:
         linked = context.TryLink(src_ext[src_build][0], src_ext[src_build][1])

      if linked:
         if (not output_format and
             not output_isa):
            check_passed = True
         else:
            link_file = open(str(context.lastTarget), "rb")
            magic_header = link_file.read(4)
            if magic_header == b"\x7F\x45\x4C\x46":
               # Executable and Linkable Format (ELF)
               while True:
                  if (output_format and
                      output_format != file_format[1]):
                     break
                  if not output_isa:
                     check_passed = True
                     break
                  link_file.seek(5)
                  (endian, ) = struct.unpack(">B", link_file.read(1))
                  if ((endian != 1) and
                      (endian != 2)):
                     break
                  ec = "<" if (endian == 1) else ">"
                  link_file.seek(20)
                  (version, ) = struct.unpack(ec + "I", link_file.read(4))
                  if version != 1:
                     break
                  link_file.seek(18)
                  (isa, ) = struct.unpack(ec + "H", link_file.read(2))
                  if ((isa not in elf_isa) or
                      (elf_isa[isa] != output_isa)):
                     break
                  check_passed = True
                  break
            elif magic_header[:2] == b"\x4D\x5A":
               # Portable Executable (PE)
               while True:
                  link_file.seek(60)
                  (pe_offset, ) = struct.unpack("<I", link_file.read(4))
                  link_file.seek(pe_offset)
                  magic_header = link_file.read(4)
                  if ((magic_header != b"\x50\x45\x00\x00") or
                      (output_format and
                       (output_format != file_format[0]))):
                     break
                  if not output_isa:
                     check_passed = True
                     break
                  (isa, ) = struct.unpack("<H", link_file.read(2))
                  if ((isa not in pe_isa) or
                      (pe_isa[isa] != output_isa)):
                     break
                  check_passed = True
                  break
   except:
      pass
   finally:
      if link_file:
         link_file.close()

   context.Result(int(check_passed))
   return int(check_passed)


#
# Validate that the specified environment key (which is assumed to be a list of
# valid directories) contains the specified value (i.e. Is file in one of the
# listed directories?).
#
# INPUT : context - SCons Configure() test context
#         key - Key containing a list of directories to search for value in
#         value - Value to search for in each directory
# OUTPUT: [Return] - int(True) if key contains value, int(False) otherwise
#
def CheckDirContains(context, key, value):
   check_passed = False

   context.Message("Checking if '{0}' is present... ".format(value))

   try:
      if key in context.env:
         dirs = context.env[key]
         for d in dirs:
            files = next(os.walk(d))[2]
            for f in files:
               if f.find(value) != -1:
                  check_passed = True
                  break
   except:
      pass

   context.Result(int(check_passed))
   return int(check_passed)


#
# Validate that the component value matches the expected value.
#
# INPUT : context - SCons Configure() test context
#         component - Component to validate value
#         value - Expected value of component
# OUTPUT: [Return] - int(True) if key contains value, int(False) otherwise
#
def CheckComponentValue(context, component, value):
   check_passed = False

   context.Message("Checking if '{0}' is '{1}'... ".format(component, value))

   try:
      if ((component in context.env.Dictionary()) and
          (context.env[component] == value)):
            check_passed = True
   except:
      pass

   context.Result(int(check_passed))
   return int(check_passed)


#
# Class describing modifications made to a specified environment by a specified
# function. Only environment keys set (that are not filtered out by the
# optionally supplied filter function) are tracked.
#
class ConfExEnvironmentModifier(object):
   def __init__(self, modifier, key_filter = None):
      self._keys_modified = set()
      self._key_filter = key_filter
      self._hook_values = []

      self.__enable_hooks(True)

      # Execute environment modifier function (saving return value)
      self.ModifierResult = modifier()
      self.Modifications = tuple(self._keys_modified)

      self.__enable_hooks(False)

   def __enable_hooks(self, enable):
      # 'public' environment dictionary methods to hook
      # Note: Some (possibly relevant) public methods are not hooked, but this
      #       list is expected to capture the majority (ideally all) of the
      #       keys modified in expected usage scenarios of this class
      hooks = (("Environment.__setitem__", self.__key_set),
               ("Environment.Append", self.__keys_append),
               ("Environment.AppendUnique", self.__keys_append_unique),
               ("Environment.AppendENVPath", self.__key_append_env),
               ("Environment.Prepend", self.__keys_prepend),
               ("Environment.PrependUnique", self.__keys_prepend_unique),
               ("Environment.PrependENVPath", self.__key_prepend_env),
               ("Environment.Replace", self.__keys_replace))

      for hook in hooks:
         if enable:
            # Hook methods (to track keys modified)
            self._hook_values.append(eval(hook[0]))
            exec(hook[0] + " = self._hook(eval(hook[0]), hook[1])")
         else:
            # Remove hooks (restore original values)
            exec(hook[0] + " = self._hook_values.pop(0)")


   def __key_modified(self, key):
      if self._key_filter and self._key_filter(key):
         self._keys_modified.add(key)

   def __key_set(self, env_self, key, item):
      self.__key_modified(key)

   def __keys_append(self, env_self, **kw):
      for key in kw.keys():
         self.__key_modified(key)

   def __keys_append_unique(self, env_self, delete_existing = 0, **kw):
      for key in kw.keys():
         # Note: A unique check (that is explicitly expected from this method)
         #       is being skipped so as not to have to rely on the SCons
         #       implmentation of such. This may lead to false-positives for
         #       functionality using this class.
         self.__key_modified(key)

   def __key_append_env(self, env_self, name, newpath, envname = "ENV",
                        sep = ":", delete_existing = 1):
      self.__key_modified(envname)

   def __keys_prepend(self, env_self, **kw):
      for key in kw.keys():
         self.__key_modified(key)

   def __keys_prepend_unique(self, env_self, delete_existing = 0, **kw):
      for key in kw.keys():
         # Note: [See note in 'self.keysAppendUnique']
         self.__key_modified(key)

   def __key_prepend_env(self, env_self, name, newpath, envname = "ENV",
                         sep = ":", delete_existing = 1):
      self.__key_modified(envname)

   def __keys_replace(self, env_self, **kw):
      for key in kw.keys():
         self.__key_modified(key)

   def _hook(self, func, hookfunc):
       def hooked_func(*args, **kwargs):
           hookfunc(*args, **kwargs)
           return func(*args, **kwargs)
       return hooked_func


#
# Class describing a ConfExError exception (thrown when ConfExBase.Find()
# results in an error). See applicable method below.
#
class ConfExError(Exception):
   def __init__(self, error, ctx = None):
      self.Error = error
      self.Description = error

      if ctx is not None:
         name = ctx
         if error == "ToolNotFound":
            self.Description = ("No tool found that provides a suitable '" +
                                name + "'")
         elif error == "LibraryNotFound":
            self.Description = ("Library '" + name + "' not found")
         elif error == "ProgramNotFound":
            self.Description = ("External program '" + name + "' not found")
         elif error == "RequirementNotMet":
            self.Description = ("Requires '" + name + "' support")

      super(ConfExError, self).__init__(self.Description)


#
# Class describing a valid environment augment specification.
#
class ConfExSpecification(object):
   def __init__(self, name, component, check, depends):
      # 'name' may be a single string for display purposes. If unspecified, one
      # is generated.
      if name:
         self.Name = name
      elif component:
         if type(component) is str:
            self.Name = component
         else:
            try:
               _ = iter(component)
               self.Name = str(next(iter(component)))
            except:
               self.Name = str(component)
      elif check:
         self.Name = "[Check]"
      else:
         self.Name = "[Dependency]"

      # 'component' may be a single string (environment component) or a list of
      # strings (all of which will be checked individually, each as a component,
      # with one being chosen to be used).
      if component:
         try:
            _ = iter(component)
            if type(component) is str:
               raise TypeError()
         except TypeError:
            self.Components = (component,)
         else:
            self.Components = tuple(component)
      else:
         self.Components = None

      # 'check' may be a single function or a list of functions. Any checks
      # specified must pass for a component to be considered valid.
      if check:
         try:
            _ = iter(check)
         except TypeError:
            self.Checks = (check,)
         else:
            self.Checks = tuple(check)
      else:
         self.Checks = None

      # 'depends' may be a single spec object (a single component dependency) or
      # a list of spec objects (specifying multiple component dependencies)
      if depends:
         try:
            _ = iter(depends)
         except TypeError:
            self.Dependencies = (depends,)
         else:
            self.Dependencies = tuple(depends)
      else:
         self.Dependencies = None

   def __str__(self):
      return self.Name


#
# Class describing an environment augment (i.e. An augment specification that
# has been or will be fulfilled before being applied to the environment)
#
class ConfExEnvironmentAugment(object):
   def __init__(self, spec):
      self.Specification = spec
      self.Tool = None
      self.Component = None
      self.Valid = False


#
# Class that encapsulates a standard environment (allowing for caching and other
# optimizations).
#
class ConfExEnvironment(object):
   @staticmethod
   def _isComponentKey(key):
      is_component = True

      # Skip 'TOOLS' key, private keys and keys that end with 'PREFIX',
      # 'SUFFIX', 'FLAGS', 'COM' or 'VERSION'
      if (key == "TOOLS" or
         key.startswith("_") or
         not key.isupper() or
         key.endswith("PREFIX") or
         key.endswith("SUFFIX") or
         key.endswith("FLAGS") or
         key.endswith("COM") or
         key.endswith("VERSION")):
         is_component = False
      return is_component

   def __init__(self, env):
      ConfExDebug("> Creating a configuration environment...")
      self.Tools = env["TOOLS"]
      self._base = env
      self._current = env.Clone()
      self._augments = []
      self._cache = ConfExCache.Get(self, self._base)
      self.__applied_tools = []
      self.__applied_checks = []
      self.__pre_applied = False

   def AddAugment(self, spec):
      added = False
      augments = self._clone_augments(self._augments)
      augment = ConfExEnvironmentAugment(spec)
      change = []
      changes = []

      ConfExDebug("- Augmenting environment with '{0}'..."
         .format(str(augment.Specification)))

      # Apply any pre-configure environment variables
      if ((self.__pre_applied is False) and
          (ConfExBase._ENVPre is not None)):
         for key in ConfExBase._ENVPre:
            self._current[key] = ConfExBase._ENVPre[key]
         self.__pre_applied = True

      # Add augment to environment
      augments.append(augment)

      if spec.Components is None:
         do_loop = False
         if not self._validate_augments(augments):
            self._augments = augments
            added = True
      else:
         # Resolve component (to ensure it will be part of environment)
         ConfExDebug("-- Setting augment component...")
         do_loop = self._set_component(augment)

      while (len(changes) or do_loop):
         # Skip (empty) change list on first iteration
         if do_loop:
            do_loop = False
         else:
            last_change = change
            change = changes.pop()
            change_delta = ([], [])

            ConfExDebug("-- Reconfiguring augment(s)...")

            # Get delta of last change and current change lists
            for change_offset in [(change, 1), (last_change, -1)]:
               offset = change_offset[1]
               for augment in change_offset[0]:
                  try:
                     # Try to increment change augment (if already present)
                     idx = change_delta[0].index(augment)
                     change_delta[1][idx] += offset

                     # Remove augments that resolve to being unchanged
                     if change_delta[1][idx] == 0:
                        del change_delta[0][idx]
                        del change_delta[1][idx]
                  except ValueError:
                     # Augment not present, add (with specified offset)
                     change_delta[0].append(augment)
                     change_delta[1].append(offset)

            # Apply change delta
            no_component = False
            for i in range(len(change_delta[0])):
               augment = change_delta[0][i]
               offset = change_delta[1][i]
               if not self._set_component(augment, offset):
                  no_component = True
                  break
            if no_component:
               # Update change to what was actually set
               change = list(last_change)
               for x in range(i):
                  augment = change_delta[0][x]
                  offset = change_delta[1][x]
                  for _ in range(abs(offset)):
                     if offset > 0:
                        change.append(augment)
                     else:
                        change.remove(augment)
               continue

         # Order augments (to ensure each is applied in the correct order) and
         # validate augments (to ensure the underlying specification is met)
         conflicting_augments = self._order_augments(augments)
         conflicting_augments = (conflicting_augments or
                                 self._validate_augments(augments))
         if conflicting_augments:
            for augment in conflicting_augments:
               new_change = list(change)
               new_change.append(augment)
               changes.append(new_change)
            continue

         self._augments = augments
         added = True
         break

      if added:
         ConfExDebug("- Environment augmented")
      else:
         ConfExDebug("! Environment augmentation failed")
      return added

   def Detect(self, tool):
      # Note: The below logic could use 'self._apply_env([tool], True)' to gain
      # the benefits that such functionality offers. However, a specifc "detect"
      # environment is being utilized below. The reasons for such are two-fold;
      # Firstly, a workaround (which requires a duplicate Tool application) is
      # being utilized, and second, this method is called to acertain a Tools
      # additions (of which some or none may not be applicable)

      args = {"tools" : [tool]}
      if self._cache.Toolpath:
         args["toolpath"] = self._cache.Toolpath

      # Record number of tools already in environment
      if self._base["TOOLS"]:
         orig_tools_len = len(self._base["TOOLS"])
      else:
         orig_tools_len = 0

      # Apply tool to environment (tracking tool modifications)
      mod = ConfExEnvironmentModifier(lambda : self._base.Clone(**args),
                                      ConfExEnvironment._isComponentKey)

      # Get tools/components added to environment
      env_clone = mod.ModifierResult
      tools = env_clone["TOOLS"]
      components = dict.fromkeys(mod.Modifications, ["no_overlap"])

      # WORKAROUND: Re-apply tool (to determine which components can overlap).
      #             Above also calls for exact apply to have single tool only
      del args["tools"]
      args["tool"] = tool
      mod = ConfExEnvironmentModifier(lambda : env_clone.Tool(**args),
                                      ConfExEnvironment._isComponentKey)

      # Remove flag from components that can overlap (other tool components)
      components.update(dict.fromkeys(mod.Modifications, []))

      # Return tool(s) and components detected
      return (tools[orig_tools_len:], components)

   def Finalize(self):
      tools = []
      checks = []

      ConfExDebug("- Finalizing environment...")

      # Add all augments tools and checks
      for augment in self._augments:
         if augment.Tool:
            tools.append(augment.Tool)
         if augment.Specification.Checks:
            checks.extend(augment.Specification.Checks)

      # Apply all changes to environment and ensure it contains exactly the
      # tools needed
      self._apply_env(tools, True, None, checks)

      # Apply any post-configure environment variables
      if ConfExBase._ENVPost is not None:
         for key in ConfExBase._ENVPost:
            self._current[key] = ConfExBase._ENVPost[key]
      ConfExDebug("> Environment configured")
      return self._current

   def _clone_augments(self, augments):
      cloned_augments = []

      for augment in augments:
         new_augment = ConfExEnvironmentAugment(augment.Specification)
         new_augment.Component = augment.Component
         new_augment.Tool = augment.Tool
         new_augment.Valid = augment.Valid
         cloned_augments.append(new_augment)

      return cloned_augments

   def _set_component(self, augment, offset = 0):
      component_set = False
      offset = [offset]
      ref_component = augment.Component
      components = augment.Specification.Components
      sources = ["LOCAL", "TOOL"]

      # Reverse sources list if traversing backwards
      if offset[0] < 0:
         sources.reverse()

      if augment.Tool:
         src_start = sources.index("TOOL")
      else:
         src_start = sources.index("LOCAL")

      # Cycle through available sources trying to set augment component
      for src in sources[src_start:]:
         if src == "LOCAL":
            # Check local environment for a specification component
            component = self.__set_component_local(components,
                                                   ref_component,
                                                   offset)
            if component:
               tool = None
               component_set = True
               break
            else:
               ref_component = components[0]
         if src == "TOOL":
            # Get a tool that provides a specification component
            component_tool = self._cache.GetTool(components,
                                                 ref_component,
                                                 augment.Tool,
                                                 offset)
            if component_tool:
               component = component_tool[0]
               tool = component_tool[1]
               component_set = True
               break
            else:
               ref_component = components[len(components) - 1]

      if component_set:
         augment.Component = component
         augment.Tool = tool
         augment.Valid = False
         ConfExDebug("-- Using component '{0}{1}'"
            .format((str(augment.Tool) + ":") if augment.Tool else "",
                    str(augment.Component)))
      else:
         ConfExDebug("-! No component found for augment")

      return component_set

   def _order_augments(self, augments):
      ordered = []
      incompatibility = None

      ConfExDebug("-- Ordering environment augments...")

      # Reverse augment list order. If there are no actual re-orderings below
      # the resultant (ordered) list will be the same as the input (augment)
      # list (which, when augments are validated, allows for fewer environment
      # resets to occur, and thus less Tool and Check re-applications)
      augments.reverse()

      try:
         for augment in augments:
            active_idx = 0
            overlap_component = None

            if (augment.Tool and
                "no_overlap" in self._cache.Components[augment.Tool]
                                                      [augment.Component]):
                  overlap_component = augment

            # Find proper position for augment component to be "active"
            tool_present = False
            for i in range(len(ordered)):
               # Check if augments tool has already been specified
               if augment.Tool and (augment.Tool == ordered[i].Tool):
                  if not tool_present:
                     tool_present = True
                     active_idx = i
                  continue

               # Check if augment tool overlaps the current ordered component
               if (augment.Tool and
                  ordered[i].Component in self._cache.Components[augment.Tool]):
                  overlap_component = ordered[i]

               # Check if augment component is not active
               if (ordered[i].Tool and
                  augment.Component in self._cache.Components[ordered[i].Tool]):
                  if overlap_component or tool_present:
                     incompatibility = (augment, ordered[i])
                     raise ConfExError("IncompatibleAugments")
                  else:
                     active_idx = (i + 1)

            ordered.insert(active_idx, augment)
      except ConfExError:
         pass
      else:
         del augments[:]
         augments.extend(ordered)

      if incompatibility:
         ConfExDebug("-! Incompatible augments")

      return incompatibility

   def _validate_augments(self, augments):
      invalid_augments = []
      tools = []
      checks = []
      depends_checks = []

      ConfExDebug("-- Validating augmented environment...")

      # Apply currently invalid augments to environment and run checks
      for augment in augments:
         dependency_augment = False
         if augment.Valid:
            for depends in augments:
               if (not depends.Valid and
                   depends.Specification.Dependencies and
                   augment.Specification in depends.Specification.Dependencies):
                  dependency_augment = True
                  break
            if not dependency_augment:
               continue

         if augment.Tool:
            tools.append(augment.Tool)
         if augment.Specification.Checks:
            if dependency_augment:
               depends_checks.extend(augment.Specification.Checks)
            else:
               checks.extend(augment.Specification.Checks)

      failed_checks = self._apply_env(tools, False, checks, depends_checks)

      # Mark invalid augments (where one or more checks failed)
      for augment in augments:
         augment.Valid = True
         if (failed_checks and
             augment.Specification.Checks):
            for check in failed_checks:
               if check in augment.Specification.Checks:
                  augment.Valid = False

         if not augment.Valid:
            invalid_augments.append(augment)

      if invalid_augments:
         ConfExDebug("-! Invalid augment(s)")

      return invalid_augments

   def _apply_env(self, tools, exact, req_checks = None, opt_checks = None):
      reset = False
      args = {}
      failed_checks = []
      expected = -1

      if self._cache.Toolpath:
         args["toolpath"] = self._cache.Toolpath

      tools = tuple(tools)
      append = len(tools)
      if req_checks:
         req_checks = tuple(req_checks)

      # If an exact application is required the environment may not have any
      # additional tools then what is specified by the provided tools list
      if exact:
         for tool in self.__applied_tools:
            if tool not in tools:
               reset = True
               break

      # Find starting index in tool list of tools that need to be applied (if
      # these tools can be applied to the current environment, i.e. appended)
      if not reset:
         for i in range(len(tools)):
            try:
               actual = self.__applied_tools.index(tools[i])
               if ((i == 0) and
                   ((len(tools) > 1) or
                   (actual == (len(self.__applied_tools) - 1)))):
                  expected = actual

               if actual == expected:
                  expected += 1
               else:
                  # Tool found, but out of order
                  reset = True
                  break
            except ValueError:
               # Check if first tool has not yet been found in applied list
               if expected == -1:
                  append = 0
               else:
                  # Check if all found previous tools were at end of list
                  if expected == len(self.__applied_tools):
                     # Set start of tools append index (if not already set)
                     if append == len(tools):
                        append = i
                  else:
                     reset = True
                     break

      if reset:
         self.__reset_environment()
         start = 0
      else:
         start = append

      # Apply tools
      expected_len = (len(self._current["TOOLS"]) + 1)
      for i in range(start, len(tools)):
         args["tool"] = tools[i]
         self.__applied_tools.append(tools[i])
         self._current.Tool(**args)

         # Check if additional tools were added (and remove names if they were)
         actual_len = len(self._current["TOOLS"])
         if actual_len != expected_len:
            self._current["TOOLS"] = self._current["TOOLS"][:expected_len]

         expected_len += 1

      # Create a Configure() context and run checks
      args = {}
      if ConfExBase._CustomTests is not None:
         args["custom_tests"] = ConfExBase._CustomTests
      if ConfExBase._Conf_dir is not None:
         args["conf_dir"] = ConfExBase._Conf_dir
      if ConfExBase._Log_file is not None:
         args["log_file"] = ConfExBase._Log_file
      if ((ConfExBase._Config_h is not None) and
          (exact is True)):
         # config.h is only written out on last (exact) run
         args["config_h"] = ConfExBase._Config_h
      ConfExBase._Configure = self._current.Configure(**args)

      all_checks = ((req_checks, True), (opt_checks, False))
      for checks_type in all_checks:
         checks = checks_type[0]
         required = checks_type[1]
         if checks:
            for check in checks:
               if check not in self.__applied_checks:
                  self.__applied_checks.append(check)
               else:
                  if not required:
                     continue

               result = check()
               if ((result == False) or
                   ((type(result) is str) and
                    (result != ""))):
                  failed_checks.append(check)

      self._current = ConfExBase._Configure.Finish()
      ConfExBase._Configure = None
      return failed_checks

   def __set_component_local(self, components, ref_component, offset):
      component = None
      forward = True if (offset[0] >= 0) else False

      if ref_component:
         component_idx = components.index(ref_component)
      else:
         component_idx = 0

      while ((component_idx >= 0) and
             (component_idx < len(components))):
         if (components[component_idx] in self._base.Dictionary()):
            if offset[0] < 0:
               offset[0] += 1
            elif offset[0] > 0:
               offset[0] -= 1
            else:
               component = components[component_idx]
               break

         if forward:
            component_idx += 1
         else:
            component_idx -= 1

      return component

   def __reset_environment(self):
      ConfExDebug("- Resetting environment...")
      self._current = self._base.Clone()
      self.__applied_tools = []
      self.__applied_checks = []
      self.__pre_applied = True
      if ConfExBase._ENVPre is not None:
         for key in ConfExBase._ENVPre:
            self._current[key] = ConfExBase._ENVPre[key]


#
# Class describing a cache of tools configured for use with a specific
# environment
#
class ConfExCache(object):
   _EnvironmentCache = []
   Tools = None
   Toolpath = None

   @staticmethod
   def Get(env, ref_key):
      found_cache = None

      for key, cache in ConfExCache._EnvironmentCache:
         if key == ref_key:
            found_cache = cache
            break

      if found_cache is None:
         cache = ConfExCache(env)
         ConfExCache._EnvironmentCache.append((ref_key, cache))
      else:
         cache = found_cache

      return cache

   def __init__(self, env):
      self._env = env
      self.Tools = ConfExCache.Tools
      self.Toolpath = ConfExCache.Toolpath
      self.Components = {}

      if self.Tools is None:
         self.Tools = list()
      else:
         self.Tools = list(self.Tools)

      if self.Toolpath is None:
         self.Toolpath = tuple()
      else:
         self.Toolpath = tuple(self.Toolpath)

      if env.Tools:
         self.Tools += list(env.Tools)

      self.Tools = list(self.Tools)

      if __name__ in self.Tools:
         # Remove 'ConfigureEx' tool (reinitializing this module while
         # running causes issues)
         self.Tools.remove(__name__)

   def AddTool(self, tool):
      if tool not in self.Tools:
         self.Tools.append(tool)

      tools_stack = [[tool]]
      tool_idx = self.Tools.index(tool)
      offset = 0

      while len(tools_stack):
         tools = tools_stack.pop(0)
         tool_idx -= offset

         while len(tools):
            tool = tools.pop(0)

            try:
               orig_idx = self.Tools.index(tool)
               if orig_idx > tool_idx:
                  # Remove tool at current position and re-insert
                  del self.Tools[orig_idx]
                  raise ValueError()
            except ValueError:
               # Insert newly identified tool
               self.Tools.insert(tool_idx, tool)

            if tool not in self.Components:
               # Get tool components and tools (if tool is in fact a toolchain)
               toolchain, components = self._env.Detect(tool)
               self.Components[tool] = components

               if len(toolchain) > 1:
                  # Save tools on stack to process after
                  tools_stack.insert(0, tools)

                  # Process new toolchain
                  tools = toolchain
                  offset = len(tools)

   def GetTool(self, components, ref_component, ref_tool, offset):
      tool_set = None
      forward = True if (offset[0] >= 0) else False

      if len(self.Tools):
         # Set starting values
         if ref_component:
            component_idx = components.index(ref_component)
         else:
            component_idx = 0
         if ref_tool:
            tool_idx = self.Tools.index(ref_tool)
         else:
            tool_idx = 0

         # Cycle through tools
         while not tool_set:
            if ((tool_idx < 0) or
                (tool_idx >= len(self.Tools))):
               break

            tool = self.Tools[tool_idx]
            if tool not in self.Components:
               # Add unused/unknown tool to cache
               self.AddTool(tool)
               continue

            # Cycle through components
            while ((component_idx >= 0) and
                   (component_idx < len(components))):
               component = components[component_idx]
               if component in self.Components[tool]:
                  # Skip 'offset' number of matches
                  if offset[0] < 0:
                     offset[0] += 1
                  elif offset[0] > 0:
                     offset[0] -= 1
                  else:
                     tool_set = (component, tool)
                     break

               if forward:
                  component_idx += 1
               else:
                  component_idx -= 1

            if forward:
               tool_idx += 1
               component_idx = 0
            else:
               tool_idx -= 1
               component_idx = (len(components) - 1)

      return tool_set


#
# Class used to configure an environment (object returned by env.ConfigureEx()).
# Returned object, attempts to provide access to the standard Configure() check
# methods, allowing these methods to be specified as "checks" when calling the
# applicable functions.
# Note: Similiar to the standard Configure() object, only a single instance of
#       this class may be used at a time.
#
class ConfExBase(object):
   _Active = False
   _Configure = None
   _ENVPre = None
   _ENVPost = None
   _CustomTests = None
   _Conf_dir = None
   _Log_file = None
   _Config_h = None

   def __init__(self, env, custom_tests, conf_dir, log_file, config_h, listing,
                debug):
      # Enforce singleton property of this class/object
      if ConfExBase._Active:
         raise RuntimeError("ConfigureEx context already active")
      else:
         ConfExBase._Active = True

      self.__listing = listing
      self.__debug = debug

      # Add default custom tests
      default_tests = {"CheckLink" : CheckLink,
                       "CheckDirContains" : CheckDirContains,
                       "CheckComponentValue" : CheckComponentValue}
      ConfExBase._CustomTests = default_tests

      if custom_tests:
         ConfExBase._CustomTests.update(custom_tests)
      if conf_dir:
         ConfExBase._Conf_dir = conf_dir
      if log_file:
         ConfExBase._Log_file = log_file
      if config_h:
         ConfExBase._Config_h = config_h

      # Don't create environment if simply listing
      if listing is None:
         self.__env = self.__wrap(lambda : ConfExEnvironment(env))

   def __getattr__(self, name):
      # Resolve standard Configure() lookups
      # Note: If the lookup is made outside a Configure() being active
      #       i.e. outside FindComponent() and friends, the lookup resolves
      #       to a Require() call
      def _check(*args, **kwargs):
         if ConfExBase._Configure is None:
            self.Require(lambda: _check(*args, **kwargs))
         else:
            f = getattr(ConfExBase._Configure, name)
            return f(*args, **kwargs)
      return _check

   @property
   def CustomTests(self):
      return dict(ConfExBase._CustomTests)

   @CustomTests.setter
   def CustomTests(self, tests):
      ConfExBase._CustomTests.update(tests)

   @property
   def ConfDir(self):
      return ConfExBase._Conf_dir

   @ConfDir.setter
   def ConfDir(self, d):
      ConfExBase._Conf_dir = d

   @property
   def LogFile(self):
      return ConfExBase._Log_file

   @LogFile.setter
   def LogFile(self, f):
      ConfExBase._Log_file = f

   @property
   def Config_h(self):
      return ConfExBase._Config_h

   @Config_h.setter
   def Config_h(self, f):
      ConfExBase._Config_h = f

   def ENVPre(self, **kwargs):
      if ConfExBase._ENVPre is None:
         ConfExBase._ENVPre = kwargs
      else:
         ConfExBase._ENVPre.update(kwargs)

   def ENVPost(self, **kwargs):
      if ConfExBase._ENVPost is None:
         ConfExBase._ENVPost = kwargs
      else:
         ConfExBase._ENVPost.update(kwargs)

   def Require(self, check, name = None):
      if not check:
         raise ValueError("Requirement check not specified")

      if not self.__is_listing("REQUIRES", name):
         call = lambda : self.__find(name, None, check, None)
         spec = self.__wrap(call)
         if not spec:
            raise ConfExError("RequirementNotMet", name)
         else:
            return spec

   def FindComponent(self, component, check = None, name = None,
                     depends = None):
      if not component:
         raise ValueError("Component not specified")

      if not self.__is_listing("COMPONENT", name):
         call = lambda : self.__find(name, component, check, depends)
         spec = self.__wrap(call)
         if not spec:
            raise ConfExError("ToolNotFound", name)
         else:
            return spec

   def FindLibrary(self, name, check = None, depends = None):
      if not name:
         raise ValueError("Library name not specified")

      if not self.__is_listing("LIBRARY", name):
         if not check:
            component = "LIBPATH"
            check = [lambda : self.CheckDirContains(component, name)]
         else:
            component = None
            try:
               _ = iter(check)
            except TypeError:
               check = (check,)

         call = lambda : self.__find(name, component, check, depends)
         spec = self.__wrap(call)
         if not spec:
            raise ConfExError("LibraryNotFound", name)
         else:
            return spec

   def FindProgram(self, name, check = None):
      if not name:
         raise ValueError("Program name not specified")

      if not self.__is_listing("PROGRAM", name):
         checks = [lambda : self.CheckProg(name)]
         if check:
            try:
               _ = iter(check)
               checks.extend(check)
            except TypeError:
               checks.append(check)

         spec = self.__wrap(lambda : self.__find(name, "ENV", checks))
         if not spec:
            raise ConfExError("ProgramNotFound", name)
         else:
            return spec

   def Finish(self):
      # Finalize environment (ensure all tools are applied)
      if self.__listing is None:
         env = self.__wrap(lambda : self.__env.Finalize())
      else:
         env = None
      ConfExBase._Active = False
      return env

   def __wrap(self, func):
      global progress_display
      global ConfExDebug

      # Disable output if not debugging
      if not self.__debug:
         local_display = ConfExDebug
         super_display = progress_display
         ConfExDebug = lambda msg: None
         SetProgressDisplay(self.__nullDisplay)

      result = func()

      # Restore output
      if not self.__debug:
         ConfExDebug = local_display
         SetProgressDisplay(super_display)

      return result

   def __find(self, name, component, check = None, depends = None):
      # Component specification
      spec = ConfExSpecification(name, component, check, depends)

      # Add new environment augment (to provide component)
      if not self.__env.AddAugment(spec):
         spec = None

      return spec

   def __is_listing(self, class_type = None, name = None):
      if self.__listing is not None:
         if ((class_type is not None) and
             (name is not None)):
            if class_type in self.__listing:
               self.__listing[class_type].append(name)
            else:
               self.__listing[class_type] = [name]

      return (False if (self.__listing is None) else True)

   def __nullDisplay(self, output, append_newline):
      # No output, i.e. sinking all output nowhere
      pass


def SetToolsCache(env, tools = None, toolpath = None):
   if tools:
      try:
         _ = iter(tools)
         if type(tools) is str:
            raise TypeError()
      except TypeError:
         tools = (tools,)

   if toolpath:
      try:
         _ = iter(toolpath)
         if type(toolpath) is str:
            raise TypeError()
      except TypeError:
         toolpath = (toolpath,)

   ConfExCache.Tools = tools
   ConfExCache.Toolpath = toolpath


def ConfigureEx(env,
                custom_tests = {},
                conf_dir = "$CONFIGUREDIR",
                log_file = "$CONFIGURELOG",
                config_h = None,
                listing = None,
                debug = False):
   # Create ConfigureEx base object
   return ConfExBase(env, custom_tests, conf_dir, log_file, config_h, listing,
                     debug)


def generate(env):
   env.AddMethod(SetToolsCache, "SetToolsCache")
   env.AddMethod(ConfigureEx, "ConfigureEx")


def exists(env):
   return True
