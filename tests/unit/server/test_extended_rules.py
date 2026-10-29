import json

import httpx
import pytest

from internal.crawler.evidence import EvidenceStore, decode_evidence, parse_networks, verify
from internal.crawler.rules import RULE_VERSION, RULES, coverage, identify

NEW_TOKENS = [
    "MistralAI-User",
    "MistralAI-Index",
    "MistralAI-Training",
    "Amazonbot",
    "Amzn-SearchBot",
    "Amzn-User",
    "DuckAssistBot",
]


@pytest.mark.parametrize("token", NEW_TOKENS)
def test_extended_identities_positive_and_negative(token):
    rule = identify(f"Mozilla/5.0 (compatible; {token.lower()}/1.0; +https://example.test/{token})")
    assert rule and rule.token == token
    assert identify(f"Not{token}Suffix/1") is None
    assert identify(f"Mozilla/5.0 (+https://example.test/{token})") is None
    assert rule.documentation_url.startswith("https://")
    assert next(row for row in coverage() if row["token"] == token)["rule_version"] == RULE_VERSION


def test_amazon_official_html_format_and_identity_binding(admin):
    rules = {rule.token: rule for rule in RULES}
    html = '<html><pre><code class="container">{&quot;prefixes&quot;:[{&quot;ip_prefix&quot;:&quot;203.0.113.0/24&quot;}]}</code></pre></html>'
    assert parse_networks(decode_evidence(html.encode(), rules["Amzn-SearchBot"])) == [
        "203.0.113.0/24"
    ]
    with pytest.raises(ValueError):
        decode_evidence(html.encode(), rules["MistralAI-User"])
    with pytest.raises(ValueError):
        decode_evidence((html + html).encode(), rules["Amzn-SearchBot"])
    store = EvidenceStore(admin.app.state.database)
    store.save(rules["MistralAI-User"], {"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]}, now=100)
    assert (
        verify(rules["MistralAI-User"], "203.0.113.9", "trusted", store.snapshot(), 101)[
            "verification"
        ]
        == "verified"
    )
    assert (
        verify(rules["MistralAI-Index"], "203.0.113.9", "trusted", store.snapshot(), 101)[
            "verification"
        ]
        == "evidence_unavailable"
    )
    assert (
        verify(rules["MistralAI-Training"], "203.0.113.9", "trusted", store.snapshot(), 101)[
            "verification"
        ]
        == "ua_only"
    )


def test_extended_refresh_accepts_official_feed_shapes(admin):
    store = EvidenceStore(admin.app.state.database)

    def respond(request):
        if request.url.host == "developer.amazon.com":
            return httpx.Response(
                200, text='<pre><code>{"prefixes":[{"ip_prefix":"203.0.113.0/24"}]}</code></pre>'
            )
        return httpx.Response(200, json={"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        store.refresh(client)
    snapshots = store.snapshot()
    for token in NEW_TOKENS:
        rule = next(rule for rule in RULES if rule.token == token)
        if rule.evidence_url:
            assert json.loads(snapshots[token]["networks_json"]) == ["203.0.113.0/24"]
            assert snapshots[token]["available"] == 1


@pytest.mark.parametrize("token", NEW_TOKENS)
def test_new_identity_ingest_keeps_verification_independent(admin, make_batch, headers, token):
    response = admin.post(
        "/api/collector/batches", json=make_batch(ua=token + "/1.0"), headers=headers
    )
    assert response.status_code == 200
    record = admin.get("/api/events").json()["items"][0]
    assert record["crawler"] == token and record["rule_version"] == RULE_VERSION
    assert record["verification"] == (
        "ua_only" if token == "MistralAI-Training" else "evidence_unavailable"
    )
    assert record["masked_ip"] == "203.0.113.*"
