# Contributing to Strop

Bug reports, documentation corrections, and focused pull requests are welcome.
Read the [support matrix](docs/SUPPORT.md) first. Catalog layouts do not establish
tested hardware support, and the [2.0 roadmap](ROADMAP_2.0.md) describes planned work.

## Report a problem

Use the [bug-report template](https://github.com/dedmo399/strop/issues/new/choose).
Include the Strop version, installation method, Linux and desktop versions,
device model, backend version, steps to reproduce, and expected and actual results.
State whether the problem occurs on the supported configuration.

Remove personal information from screenshots, logs, and preset files before
posting them. Follow [SECURITY.md](SECURITY.md) for suspected vulnerabilities.

## Propose a change

For a large feature or a change in hardware support, open an issue to discuss
scope first. Create a branch for a focused change and open a pull request against
`main`; contributors without write access can use a fork. Explain the problem,
the resulting behavior, and how you verified it. Update documentation when
behavior changes. Do not commit generated packages, personal presets, or logs.

Contributions must be compatible with the project's
[GPL-3.0-or-later license](LICENSES.md). Preserve third-party notices and identify
the source of reused material. AI-assisted contributions require the same review
and verification as other contributions; describe substantial AI assistance in
the pull request.

## Development and validation

Use the platform and runtime dependencies in [SUPPORT.md](docs/SUPPORT.md).
The [CI workflow](.github/workflows/ci.yml) is the reference for system packages
and checks. From the repository root, run the core tests with:

```bash
PYTHONPATH=. python3 -m pytest -q tests
```

D-Bus and GUI tests are opt-in and skipped by that command. To run them with
the required D-Bus, GTK, Xvfb, and xauth packages installed:

```bash
dbus-run-session -- env PYTHONPATH=. STROP_TEST_DBUS=1 python3 -m pytest -q tests/test_tray_dbus.py
dbus-run-session -- xvfb-run -a env PYTHONPATH=. STROP_TEST_GUI=1 GDK_BACKEND=x11 GSK_RENDERER=cairo GTK_A11Y=none python3 -m pytest -q tests/test_gui.py
```

CI also runs backend validation with input-remapper 2.2.0 and
`STROP_REQUIRE_INPUT_REMAPPER=1`. To check packaging, run `./build_deb.sh`.
Source archives include only Git-tracked files from a checkout. Add new project
files to Git before building. Extracted source releases carry a file manifest
for rebuilding without Git; unrelated local files are excluded in either case.

Automated checks do not replace testing remapping on the relevant physical
device. Report which checks you ran and any hardware testing still needed.
