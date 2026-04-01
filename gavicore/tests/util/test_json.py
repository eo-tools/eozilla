#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime

from gavicore.util.json import JsonDateCodec, JsonIdentityCodec


def test_json_identity_codec():
    c = JsonIdentityCodec()
    assert c.from_json(None) is None
    assert c.from_json(True) is True
    assert c.to_json(3) == 3


def test_json_date_codec():
    c = JsonDateCodec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json(datetime.date(2026, 4, 1)) == "2026-04-01"
    assert c.from_json("2026-04-01") == datetime.date(2026, 4, 1)
