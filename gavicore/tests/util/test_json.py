#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime

from gavicore.util.json import (
    JsonBase64Codec,
    JsonDateCodec,
    JsonDateTimeCodec,
    JsonIdentityCodec,
    JsonTimeCodec,
)


def test_json_identity_codec():
    c = JsonIdentityCodec()
    assert c.from_json(None) is None
    assert c.from_json(True) is True
    assert c.to_json(3) == 3


def test_json_base64_codec():
    c = JsonBase64Codec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json("¡Adios!") == "wqFBZGlvcyE="
    assert c.from_json("wqFBZGlvcyE=") == b"\xc2\xa1Adios!"
    assert c.to_json(b"\xc2\xa1Adios!") == "wqFBZGlvcyE="


def test_json_datetime_codec():
    c = JsonDateTimeCodec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json(datetime.datetime(2026, 4, 1, 10, 20, 56)) == "2026-04-01T10:20:56"
    assert c.from_json("2026-04-01T10:20:56") == datetime.datetime(
        2026, 4, 1, 10, 20, 56
    )


def test_json_date_codec():
    c = JsonDateCodec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json(datetime.date(2026, 4, 1)) == "2026-04-01"
    assert c.from_json("2026-04-01") == datetime.date(2026, 4, 1)


def test_json_time_codec():
    c = JsonTimeCodec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json(datetime.time(12, 10, 32)) == "12:10:32"
    assert c.from_json("12:10:32") == datetime.time(12, 10, 32)
