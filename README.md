This is a GitHub mirror of the [scons_hello repository](https://chiselapp.com/user/simplejack/repository/scons_hello/home).

---

## BuildMeUp

Hey Buttercup, let me tell you of an over-complicated SCons 'Hello World!'.

## Why?

I wanted to demonstrate some tools I wrote for SCons that assist me in building my projects. I wrote these tools with the following criteria in mind:

* Work with (as oppose to against) the standard SCons build flow
* Lazy evaluation (i.e. evaluate only what is needed, when it's needed)
* Be consistent (i.e. minimal changes needed to fill in a new project template)
* Portability (i.e. Structure such that future extensability is natural)

## What?

SCons tools (copied to an appropriate location and invoked as any other Tool):

* Modularity (modularity.py) - Modular, structured, hieraricheal division of build into discrete modules.
* ConfigureEx (configureex.py) - Environment configuration based on what tools are available.
* InstallEx (installex.py) - Installation based on file type (to default platform locations)
* BuildMeUp (bmu.py) - My style of SCons build using the above tools


