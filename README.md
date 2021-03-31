[![Build and smoke test](https://github.com/hartwork/binary-gentoo/actions/workflows/smoke_test.yml/badge.svg)](https://github.com/hartwork/binary-gentoo/actions/workflows/smoke_test.yml)

# About

**binary-gentoo**
is a collection of
simple
CLI tools
to help **build Gentoo packages on a non-Gentoo Linux host**, primarily.
A typical scenario is operation of an
**_active_ [Gentoo binary package host](https://wiki.gentoo.org/wiki/Binary_package_guide#Setting_up_a_binary_package_host)**
 — an active "binhost".

*Secondarily*, **binary-gentoo** can also build Gentoo packages on a Gentoo host
with Docker isolation and a full `emerge` perspective
(while not affecting your host system).

There currently four CLI tools
that follow the [Unix philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)
and are meant to be combined using a glue language like Bash:

- `gentoo-local-queue` – Manages simple file-based push/pop build task queues
- `gentoo-package-build` – Builds a Gentoo package with Docker isolation
- `gentoo-tree-diff` – Lists packages/versions/revisions that one portdir has over another
- `gentoo-tree-sync` – Brings a given portdir directory up to date

**binary-gentoo**
is software libre licensed under the `GNU Affero GPL version 3 or later` license.


# Design Decisions

- All code in **binary-gentoo** must work on a non-Gentoo Linux machine,
  provided that it has Docker installed and working internet access

- If dependency problems block a package from being built,
  there should be a log showing that problem.
  Hence the dedicated round of `emerge --pretend [..]` before the actual build.

- Big packages like Chromium need a pile of RAM and CPU time.
  Therefore, the build defaults to `MAKETOPTS=-j1`
  the package of interest is emerged separate from it dependencies.
  That allows to build e.g. a package of Chromium in a VM with only 8 GB of RAM.

- With regard to dependency constraints,
  some packages can be *built* without conflicts but not be *installed* without conflicts.
  Hence the default is to only install dependencies, but not the package of interest.
