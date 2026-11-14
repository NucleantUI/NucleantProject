"""The Python layer — transferred from ksproject, switched off for now.

A NucleantUI app is pure Swift today; Python returns later as a layer on top
(PyNucleantUI). Everything ksproject did for embedded CPython lives here
unchanged in spirit:

* ``pip_install``   — ``uv pip install --python-platform … --target site_packages``,
  plus the ``.java/.libs/.kotlin/.gradle`` dot-dirs of local path deps;
* ``site_packages`` — per-ABI / per-slice site_packages for Gradle and Xcode;
* ``cpython_android`` — CPython for Android (prebuilt wheel, python.org
  binary, or a source cross-build);
* ``python_apple``  — BeeWare's Python.xcframework;
* ``python_version`` — the ``.python-version`` pin and supported versions;
* ``collect_gradle_configs`` — ``.gradle/*.json`` from site-packages.

Nothing imports these unless ``NucleantToml.python_enabled`` — which needs both
``PYTHON_SUPPORT_ENABLED`` (in ``nucleant_toml``) and ``[python] enabled``.
"""
