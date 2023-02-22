################################################################################
# Filename:    InstallEx.py                                                    #
# License:     Public Domain                                                   #
# Author:      New Rupture Systems                                             #
# Description: Defines functions and methods for using the Extended            #
#              Installation tool.                                              #
################################################################################
import os
import platform
from SCons.Script import *


#
# Initialize default installation directories.
#
# INPUT : prefix - Sandbox top-level directory
#         project - Name of project being installed
#         install_platform - Platform install is occuring on
#         install_type - Type of installation
# OUTPUT: [Return] - Initialized default install directory paths (dictionary)
#
def init_install_dirs(prefix, project, install_platform, install_type):
   base_dirs = {"BIN" : ["INSTALLBINDIR",
                         Dir(prefix).Dir("bin"),
                         "Install directory for binaries (prefix/bin)"],
                "LIB|SHLIB" : ["INSTALLLIBDIR",
                               Dir(prefix).Dir("lib"),
                               "Install directory for libraries (prefix/lib)"],
                "DATA" : ["INSTALLDATADIR",
                          Dir(prefix).Dir("share"),
                          "Install directory for data (prefix/share)"],
                "CFG" : ["INSTALLCFGDIR",
                         Dir(prefix).Dir("etc"),
                         "Install directory for configuration (prefix/etc)"],
                "DOC" : ["INSTALLDOCDIR",
                         Dir(prefix).Dir("doc"),
                         "Install directory for documentation (prefix/doc)"],
                "INC" : ["INSTALLINCDIR",
                         Dir(prefix).Dir("include"),
                         "Install directory for C headers (prefix/include)"]}

   if install_platform is not None:
      if "linux" in install_platform.lower():
         # Based on Linux FHS (v3.0)
         linux_dirs = {"BIN" : Dir("/").Dir("usr").Dir("bin"),
                       "LIB|SHLIB" : Dir("/").Dir("usr").Dir("lib"),
                       "DATA" : Dir("/").Dir("usr").Dir("share"),
                       "CFG" : Dir("/").Dir("etc"),
                       "DOC" : Dir("/").Dir("usr").Dir("share").Dir("doc"),
                       "MAN" : ["INSTALLMANDIR",
                                Dir("/").Dir("usr").Dir("share").Dir("man"),
                                "Install directory for manuals (prefix/man)"],
                       "INC" : Dir("/").Dir("usr").Dir("include")}

         if install_type == "user":
            # Based on the freedesktop XDG Base Directory Specification(v0.8)
            home = Dir(os.environ.get("HOME", "/tmp"))
            xdg = {"XDG_DATA_HOME" : home.Dir(".local").Dir("share"),
                   "XDG_CONFIG_HOME" : home.Dir(".config")}

            # Get XDG install-relevant variables
            for d in xdg:
               if ((d in os.environ) and
                   (str(os.environ))):
                  xdg[d] = os.environ[d]

            linux_user_dirs = {"BIN" : home.Dir(".local").Dir("bin"),
                               "DATA" : xdg["XDG_DATA_HOME"],
                               "CFG" : xdg["XDG_CONFIG_HOME"]}

            # Update linux directories with user-specific ones
            for d in linux_user_dirs:
               linux_dirs[d] = linux_user_dirs[d]
         elif install_type == "local":
            # Based on Linux FHS (v3.0)
            local_prefix = Dir("/").Dir("usr").Dir("local")
            local_dirs = {"BIN" : Dir(local_prefix).Dir("bin"),
                          "LIB|SHLIB" : Dir(local_prefix).Dir("lib"),
                          "DATA" : Dir(local_prefix).Dir("share"),
                          "CFG" : Dir(local_prefix).Dir("etc"),
                          "DOC" : Dir(local_prefix).Dir("share").Dir("doc"),
                          "MAN" : ["INSTALLMANDIR",
                                   Dir(local_prefix).Dir("man"),
                                  "Install directory for manuals (prefix/man)"],
                          "INC" : Dir(local_prefix).Dir("include")}
            linux_dirs = local_dirs

         # A project/package specific sub-directory is recommended (for every
         # directory, excluding BIN/MAN)
         if project:
            for d in linux_dirs:
               if d not in ("BIN", "MAN"):
                  pd = Dir(project, linux_dirs[d])
                  linux_dirs[d] = pd

         # Update base directories with Linux-specific ones
         for d in linux_dirs:
            if d in base_dirs:
               base_dirs[d][1] = linux_dirs[d]
            else:
               base_dirs[d] = linux_dirs[d]
      else:
         raise NotImplementedError("Non-Linux platforms")

   return base_dirs


#
# Class describing an installer. An installer takes added targets and installs
# them to the appropriate location. How a target is installed is dependent on
# the type of target or if a specific command has been provided to perform the
# installation.
#
class InstallerBase(object):
   @staticmethod
   def _cmd_action_factory(env, cmd, dest, target, force, silent):
      def _cmd(target, source, env):
         try:
            rtn = cmd(dest, target, silent)
            if rtn is not True:
               if type(rtn) is str:
                  error = rtn
               else:
                  error = "Install command returned non-True result"
               rtn = False
         except Exception as e:
            rtn = False
            error = str(e)

         if not rtn:
            print("Error: " + error)

         if force:
            return 0
         else:
            return (0 if rtn else 1)
      return env.Action(_cmd, cmdstr = None)

   def __init__(self, env, variables, force, silent):
      self._env = env
      self._force = force
      self._silent = silent
      self._targets = []

      # Installer builds upon the SCons provided 'install' tool
      env.Tool("install")

      # Project name may be incorporated into platform install path
      if "INSTALLPROJECT" in env:
         project = str(env["INSTALLPROJECT"])
      elif "PROJECT" in env:
         project = str(env["PROJECT"])
      else:
         project = None

      # Installation type (i.e. where things should go):
      # 'sandbox' : Install to the specified prefix or (if a prefix is 
      #             unspecified) the top-level directory
      # 'user'    : Install to a user-specific location
      # 'local'   : Install to an unmanaged system-wide location
      # 'system'  : Install to a managed system-wide location
      if "INSTALLTYPE" in env:
         install_type = str(env["INSTALLTYPE"])
         if install_type.lower() not in ("sandbox", "user", "local", "system"):
            raise ValueError("Invalid INSTALLTYPE specified")
      else:
         install_type = "sandbox"

      # The platform on which this install is occuring
      if "INSTALLPLATFORM" in env:
         install_platform = str(env["INSTALLPLATFORM"])
      else:
         install_platform = None
         if install_type != "sandbox":
            install_platform = platform.system().lower()

      # Install sandbox prefix
      if "PREFIX" in env:
         prefix = env["PREFIX"]
      else:
         prefix = Dir("#")

      entries = init_install_dirs(prefix, project, install_platform,
                                  install_type)

      # Update variables object with install-relevant variables
      for e in entries:
         variables.Add(entries[e][0], entries[e][2], entries[e][1].abspath)
      variables.Update(env)

      self._dir_entries = entries

   @property
   def Targets(self):
      return tuple(self._targets)

   def Add(self, **kwargs):
      env = self._env
      force = self._force
      silent = self._silent

      if "name" in kwargs:
         name = kwargs["name"]
      else:
         name = None
      if "cmd" in kwargs:
         cmd = kwargs["cmd"]
      else:
         cmd = None

      # Process each (target_type : target) pair
      for key in kwargs:
         if ((key == "name") or
             (key == "cmd")):
            continue

         dest = self._get_dest(key)
         target = kwargs[key]
         if ((dest is None) and
             (cmd is None)):
            s = "Don't know how to install target of type '{0}'".format(key)
            raise ValueError(s)

         if "INSTALLMODE" in env:
            install_mode = env["INSTALLMODE"]
         else:
            install_mode = "auto"
         if "INSTALLCMDDIR" in env:
            install_dir = env["INSTALLCMDDIR"]
         else:
            install_dir = Dir("#").Dir(".sconinstall_cmds")

         if install_mode == "cache":
            if name is None:
               name = str(Flatten(target)[0])
            if cmd is not None:
               name = ("__install_" + name)
               target = File(name, install_dir)
            else:
               target = Dir(dest).File(name)
         else:
            if cmd is not None:
               if name is None:
                  name = str(Flatten(target)[0])
               name = ("__install_" + name)
               install_cmd = cmd
               install_file = File(name, install_dir)
               action = InstallerBase._cmd_action_factory(env, install_cmd,
                                                    dest, target, force, silent)
               target = env.Command(install_file, target, [action,
                                                           Touch(install_file)])
            else:
               if key == "SHLIB":
                  if name is None:
                     dest = Dir(dest)
                  else:
                     dest = Dir(dest).File(name)
                  target = InstallVersionedLib(target = dest, source = target)
               elif name is not None:
                  dest = Dir(dest).File(name)
                  target = InstallAs(target = dest, source = target)
               else:
                  dest = Dir(dest)
                  target = Install(target = dest, source = target)

            if install_mode == "force":
               env.AlwaysBuild(target)

      self._targets.append(target)

   def _get_dest(self, target_type):
      entries = self._dir_entries
      dest = None
      for e in entries:
         target_types = e.split("|")
         if target_type in target_types:
            var = entries[e][0]
            if var in self._env:
               dest = self._env[var]
            else:
               dest = entries[e][1]

      return dest


def Installer(env, variables, force, silent):
   # Create Installer base object
   return InstallerBase(env, variables, force, silent)


def generate(env):
   env.AddMethod(Installer, "Installer")


def exists(env):
   return True
