#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import eozilla


def test_eozilla_is_complete():
    eozilla_content = dir(eozilla)
    assert "appligator" in eozilla_content
    assert "cuiman" in eozilla_content
    assert "gavicore" in eozilla_content
    assert "procodile" in eozilla_content
    assert "wraptile" in eozilla_content
