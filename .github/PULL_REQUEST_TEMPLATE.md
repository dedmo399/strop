## Description
<!-- Provide a clear summary of the change, bug fix, or feature being introduced. -->

## Motivation & Context
<!-- Why is this change required? What issue or roadmap milestone does it address? (e.g. Closes #123) -->

## How Has This Been Tested?
<!-- Describe the tests you ran to verify your changes. Include hardware tested if applicable. -->
- [ ] Core unit tests pass (`python3 -m pytest -q tests`)
- [ ] D-Bus / Tray integration tests pass (`dbus-run-session -- env STROP_TEST_DBUS=1 python3 -m pytest -q tests/test_tray_dbus.py`)
- [ ] Source compilation & desktop validation pass (`python3 -m py_compile ... && desktop-file-validate strop.desktop`)
- [ ] Tested on target hardware (Razer Tartarus Pro / BlackWidow V3 / Naga Trinity or simulation)

## Checklist
- [ ] My code adheres to the project's [CONTRIBUTING.md](https://github.com/dedmo399/strop/blob/main/CONTRIBUTING.md) guidelines.
- [ ] I have updated documentation ([README.md](https://github.com/dedmo399/strop/blob/main/README.md), [docs/SUPPORT.md](https://github.com/dedmo399/strop/blob/main/docs/SUPPORT.md), or [CHANGELOG.md](https://github.com/dedmo399/strop/blob/main/CHANGELOG.md)) if behavior changed.
- [ ] I have preserved third-party license notices and my contribution is licensed under GNU GPL-3.0-or-later.
- [ ] If AI assistance was substantially involved, I have reviewed the code for correctness.
