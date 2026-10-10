import base64
import hashlib
import hmac

from jobsearcher.sources.finn_sig import HMAC_KEY, finn_gw_key, sign_url


def _ref(msg: bytes) -> str:
    return base64.b64encode(hmac.new(HMAC_KEY, msg, hashlib.sha512).digest()).decode()


def test_known_vector():
    # Value verified against the live gateway on 2026-10-10 (same key and message format).
    sig = finn_gw_key(
        "GET", "/search/SEARCH_ID_JOB_FULLTIME", "client=android-finn&location=0.20001", "Search-Quest-JB"
    )
    assert sig == "KE+mk/F/f6hyoKOjFHpK5SZv2RHOhFYfKfDsuwfNav/36Jlf/NC968QKFyT1tRe5Dr8CpaTx/YE2BBA9oRqlyw=="


def test_message_format():
    assert finn_gw_key("get", "/a/b", "x=1", "SVC", b"body") == _ref(b"GET;/a/b?x=1;SVC;body")
    assert finn_gw_key("GET", "/a", "", "SVC") == _ref(b"GET;/a;SVC;")


def test_root_path_is_empty():
    assert finn_gw_key("GET", "/", "", "") == _ref(b"GET;;;")


def test_sign_url_uses_encoded_query():
    url = "https://appsgw.finn.no/search/X?client=android-finn&q=summer+jobb&location=1.20001.20061"
    assert sign_url("GET", url, "S") == finn_gw_key(
        "GET", "/search/X", "client=android-finn&q=summer+jobb&location=1.20001.20061", "S"
    )
