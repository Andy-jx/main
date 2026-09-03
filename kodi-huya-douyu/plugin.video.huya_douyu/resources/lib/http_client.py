# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def request(url, method="GET", data=None, headers=None, timeout=15):
    merged = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    if headers:
        merged.update(headers)

    payload = None
    if data is not None:
        if isinstance(data, dict):
            payload = urlencode(data).encode("utf-8")
            merged.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = data

    req = Request(url, data=payload, headers=merged, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, resp.headers


def get_text(url, headers=None, timeout=15):
    return request(url, headers=headers, timeout=timeout)[0]


def get_json(url, headers=None, timeout=15):
    text, _ = request(url, headers=headers, timeout=timeout)
    return json.loads(text)


def get_json_with_headers(url, headers=None, timeout=15):
    text, response_headers = request(url, headers=headers, timeout=timeout)
    return json.loads(text), response_headers


def post_form_json(url, data, headers=None, timeout=15):
    text, _ = request(url, method="POST", data=data, headers=headers, timeout=timeout)
    return json.loads(text)
