"""Unit tests and compliance linter for synthetic scam funnels (Section 3).

Verifies safety rules, legal disclaimers, noindex tags, and payee alignment:
1. Every fixture contains the mandatory safety disclaimer.
2. Every fixture contains the meta robots noindex tag.
3. Every scam fixture uses exclusively the @stingtest fake UPI domain (never real bank handles).
4. variant_a1 and variant_a2 share the exact same payee (rewards.payout@stingtest).
5. variant_b1 uses a distinct payee (fastrecharge.cashier@stingtest).
6. variant_c1 is strictly benign with no UPI VPAs or payment forms.
"""

import re
from pathlib import Path

MANDATORY_DISCLAIMER = "Synthetic STING test funnel - not a real service. Do not pay."
FORBIDDEN_REAL_PSP_SUFFIXES = [
    "@okhdfcbank",
    "@okaxis",
    "@oksbi",
    "@okicici",
    "@paytm",
    "@ybl",
    "@ibl",
    "@apl",
    "@upi",
]


def get_funnels_dir() -> Path:
    test_dir = Path(__file__).resolve().parent
    repo_root = test_dir.parent.parent
    funnels_dir = repo_root / "fixtures" / "funnels"
    assert funnels_dir.exists(), f"Funnels directory not found at {funnels_dir}"
    return funnels_dir


def test_every_funnel_fixture_has_disclaimer_and_noindex():
    """Verify all HTML fixtures include safety disclaimer and robots noindex."""
    funnels_dir = get_funnels_dir()
    html_files = list(funnels_dir.glob("*/*.html"))
    assert len(html_files) >= 10, f"Expected at least 10 HTML files, found {len(html_files)}"

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        assert MANDATORY_DISCLAIMER in content, (
            f"Missing mandatory disclaimer in {html_file.relative_to(funnels_dir)}"
        )
        assert 'content="noindex' in content or "content='noindex" in content, (
            f"Missing robots noindex tag in {html_file.relative_to(funnels_dir)}"
        )


def test_scam_fixtures_use_only_stingtest_fake_upi_suffix():
    """Verify scam funnels only contain @stingtest UPI handles and zero real banking PSPs."""
    funnels_dir = get_funnels_dir()
    scam_html_files = [f for f in funnels_dir.glob("*/*.html") if "variant_c1" not in str(f)]

    for html_file in scam_html_files:
        content = html_file.read_text(encoding="utf-8")

        # Must not contain any real production PSP handles
        for bad_suffix in FORBIDDEN_REAL_PSP_SUFFIXES:
            assert bad_suffix not in content.lower(), (
                f"Forbidden real PSP suffix {bad_suffix} found in public fixture {html_file}"
            )

        # If any UPI handle is present, it MUST end in @stingtest
        upi_matches = re.findall(r"[\w.-]+@[\w.-]+", content)
        for match in upi_matches:
            if not match.endswith("example.com") and not match.startswith("team@"):
                assert match.endswith("@stingtest"), (
                    f"Unexpected UPI domain in {html_file}: {match} (must end in @stingtest)"
                )


def test_payee_relationships_between_variants():
    """Verify variant_a1 and variant_a2 share Payee A, while variant_b1 uses Payee B."""
    funnels_dir = get_funnels_dir()

    pay_a1 = (funnels_dir / "variant_a1" / "pay.html").read_text(encoding="utf-8")
    pay_a2 = (funnels_dir / "variant_a2" / "pay.html").read_text(encoding="utf-8")
    pay_b1 = (funnels_dir / "variant_b1" / "pay.html").read_text(encoding="utf-8")

    def extract_vpa(html_text: str) -> str:
        match = re.search(r"[\w.-]+@stingtest", html_text)
        assert match, "Could not find @stingtest VPA in pay.html"
        return match.group(0)

    vpa_a1 = extract_vpa(pay_a1)
    vpa_a2 = extract_vpa(pay_a2)
    vpa_b1 = extract_vpa(pay_b1)

    assert vpa_a1 == "rewards.payout@stingtest"
    assert vpa_a2 == "rewards.payout@stingtest"
    assert vpa_b1 == "fastrecharge.cashier@stingtest"

    # Core clustering invariant: a1 and a2 share Payee A; b1 differs
    assert vpa_a1 == vpa_a2, "variant_a1 and variant_a2 must share the same payee"
    assert vpa_a1 != vpa_b1, "variant_a1 and variant_b1 must have different payees"


def test_variant_c1_is_strictly_benign():
    """Verify variant_c1 contains no payment, no forms, and no UPI handles."""
    funnels_dir = get_funnels_dir()
    c1_html = (funnels_dir / "variant_c1" / "index.html").read_text(encoding="utf-8")

    assert "@stingtest" not in c1_html
    assert "upi://" not in c1_html
    assert "<form" not in c1_html
    assert "payment" not in c1_html.lower()
