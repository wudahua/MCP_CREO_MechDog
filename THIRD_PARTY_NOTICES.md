# Third-party components and external prerequisites

## Bundled component

`native/third_party/json.hpp` is nlohmann/json 3.12.0, licensed under MIT.
Copyright: Niels Lohmann and contributors. The original notice and full license
are retained in `native/third_party/LICENSE.nlohmann-json` and in the header.
Upstream: https://github.com/nlohmann/json/tree/v3.12.0

## Installed Python dependencies

The official MCP Python SDK and its dependencies are installed from the versions
in `requirements.lock.txt`. Their source and installed environments are not
bundled in this repository. Each dependency retains its own license and notices.

## PTC software

Creo Parametric, Creo Toolkit headers/libraries, templates, runtime binaries and
license files are external prerequisites supplied by the user's PTC installation.
They are not covered by this project's MIT license and are not distributed in
the source package. `native/constants.inc` is generated locally from installed
SDK names during setup; it is excluded from the public source package.

Users must follow their PTC agreements for development and use. Distribution of
compiled Toolkit applications requires the applicable PTC unlocking and license
procedures. See:
https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/user_guide/Unlocking_a_Creo_Toolkit_Application.html

MCP_CREO_MechDog is an independent project and is not an official PTC product.

## Separate reference seed library

The optional `MCP_CREO_MechDog-0.2.4-seed-library.zip` contains project-created
native Blend reference models, a manifest, a path resolver and documentation.
Project-authored geometry and accompanying project files are provided under MIT;
the seed package retains its own `LICENSE` and states the scope of that grant.
These are project test references, not a redistributed PTC example-model library.
No Creo installation, Toolkit headers/libraries, application binaries or license
files are included. The project license grants no rights to PTC software or
other third-party materials. Target-machine runtime requirements still apply.
