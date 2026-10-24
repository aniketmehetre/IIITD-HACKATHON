"""Intake Agent for candidate ingestion, SSRF validation, normalization, and QR decoding.

Conforms strictly to Section 4 specifications:
- Extracts URLs and UPI IDs from message lures.
- Normalizes URLs: strips tracking parameters, lowercases hostnames, flags IDN/Punycode homographs.
- Blocks localhost, link-local, private IP ranges (SSRF protection), and file:// URIs.
- Decodes QR image uploads via OpenCV QRCodeDetector, parsing upi://pay payloads.
"""

import ipaddress
import re
import urllib.parse
from dataclasses import dataclass, field

import cv2
import numpy as np

# Tracking parameters to strip from normalized URLs
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
    "_hsenc",
    "mc_cid",
    "mc_eid",
}

# Regex for URLs in unstructured text
URL_REGEX = re.compile(
    r"(?:https?://|www\.)[a-zA-Z0-9.\-_]+(?::\d+)?(?:/[^\s<>'\"`{}|\^~\[\]]*)?",
    re.IGNORECASE,
)

# Regex for Indian UPI Virtual Payment Addresses (VPAs)
UPI_REGEX = re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z0-9.\-_]{2,64}\b")


@dataclass
class IntakeResult:
    """Normalized structured output from Intake Agent processing."""

    input_type: str  # link | message | qr_image
    raw_input: str
    normalized_url: str | None = None
    domain: str | None = None
    is_idn: bool = False
    is_ip: bool = False
    extracted_upi_ids: list[str] = field(default_factory=list)
    input_payee: str | None = None
    error: str | None = None


def validate_and_normalize_url(url: str) -> tuple[str, str, bool, bool]:
    """Validates and normalizes target URL, rejecting SSRF targets and stripping tracking params.

    Returns:
        (normalized_url, domain, is_idn, is_ip)

    Raises:
        ValueError on SSRF attempts, invalid schemes, or unparseable URLs.
    """
    cleaned = url.strip()
    if not cleaned.startswith(("http://", "https://")):
        if cleaned.startswith("www."):
            cleaned = "https://" + cleaned
        else:
            raise ValueError(
                f"Invalid URL scheme in '{url}'. Only http:// and https:// are accepted."
            )

    try:
        parsed = urllib.parse.urlsplit(cleaned)
    except Exception as exc:
        raise ValueError(f"Malformed URL: {exc}") from exc

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Forbidden scheme '{parsed.scheme}'. Only http and https allowed.")

    host = parsed.hostname
    if not host:
        raise ValueError("URL must include a valid hostname.")

    host_lower = host.lower()

    # SSRF Protection: Reject localhost, loopbacks, link-locals, and private subnets
    if host_lower in ("localhost", "localhost.localdomain") or host_lower.endswith(".localhost"):
        raise ValueError(
            f"Host '{host}' resolves to forbidden loopback/localhost (SSRF protection)."
        )

    is_ip = False
    try:
        ip_obj = ipaddress.ip_address(host_lower)
        is_ip = True
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or str(ip_obj) == "0.0.0.0"
        ):
            raise ValueError(
                f"IP address '{host}' belongs to forbidden private or link-local range (SSRF protection)."
            )
    except ValueError as e:
        if "forbidden" in str(e):
            raise
        # Not an IP literal, standard hostname

    # IDN / Punycode homograph detection
    is_idn = "xn--" in host_lower or any(ord(c) > 127 for c in host_lower)

    # Strip tracking parameters and rebuild query
    query_parts = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [(k, v) for k, v in query_parts if k.lower() not in TRACKING_PARAMS]
    new_query = urllib.parse.urlencode(filtered_query)

    port_part = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    path_part = parsed.path if parsed.path else "/"

    normalized = urllib.parse.urlunsplit(
        (parsed.scheme.lower(), f"{host_lower}{port_part}", path_part, new_query, "")
    )
    return normalized, host_lower, is_idn, is_ip


def extract_from_message(text: str) -> tuple[str | None, list[str]]:
    """Extracts candidate URLs and UPI IDs from message text and selects the primary URL."""
    urls = URL_REGEX.findall(text)
    primary_url = None

    for raw_url in urls:
        candidate = raw_url if raw_url.startswith("http") else f"https://{raw_url}"
        try:
            norm_url, _, _, _ = validate_and_normalize_url(candidate)
            primary_url = norm_url
            break
        except ValueError:
            continue

    # Extract UPI IDs
    upi_matches = UPI_REGEX.findall(text)
    # Deduplicate while preserving order and filter common false positives
    unique_upis: list[str] = []
    for item in upi_matches:
        cleaned_item = item.strip().lower()
        if (
            cleaned_item not in unique_upis
            and not cleaned_item.endswith((".com", ".org", ".net", ".edu", ".gov"))
            and "@" in cleaned_item
        ):
            unique_upis.append(item.strip())

    return primary_url, unique_upis


def decode_qr_image(image_bytes: bytes) -> tuple[str, str | None, str]:
    """Decodes QR code from binary image bytes using OpenCV.

    Returns:
        (payload_type, input_payee, payload_text) where payload_type is 'upi' or 'url'.
    """
    if not image_bytes:
        raise ValueError("Empty image data provided for QR decode.")

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Uploaded file is not a valid or decodable PNG/JPEG image.")

    detector = (
        cv2.QRCodeDetectorAruco() if hasattr(cv2, "QRCodeDetectorAruco") else cv2.QRCodeDetector()
    )
    decoded_text, points, _ = detector.detectAndDecode(img)

    if not decoded_text or not decoded_text.strip():
        # Fallback to standard detector
        std_detector = cv2.QRCodeDetector()
        decoded_text, _, _ = std_detector.detectAndDecode(img)

    if not decoded_text or not decoded_text.strip():
        raise ValueError("No readable QR code found in the uploaded image.")

    payload = decoded_text.strip()

    # Case 1: UPI Intent QR (upi://pay?pa=...&pn=...)
    if payload.lower().startswith("upi://pay"):
        parsed_uri = urllib.parse.urlparse(payload)
        qs = urllib.parse.parse_qs(parsed_uri.query)
        pa = qs.get("pa", [None])[0]
        return "upi", pa, payload

    # Case 2: Web URL QR
    if payload.lower().startswith(("http://", "https://", "www.")):
        return "url", None, payload

    # Default payload
    return "raw", None, payload


def process_intake(
    input_type: str,
    raw_input: str,
    image_bytes: bytes | None = None,
) -> IntakeResult:
    """Main Intake processor implementing Section 4 ingestion logic."""
    if len(raw_input) > 5000:
        raise ValueError(
            f"Raw input length ({len(raw_input)}) exceeds 5000 character maximum limit."
        )

    # 1. QR Image Intake
    if input_type == "qr_image":
        if not image_bytes:
            raise ValueError("QR image intake requires binary image bytes.")
        qr_kind, extracted_payee, qr_payload = decode_qr_image(image_bytes)

        if qr_kind == "upi":
            return IntakeResult(
                input_type="qr_image",
                raw_input=qr_payload,
                input_payee=extracted_payee,
                extracted_upi_ids=[extracted_payee] if extracted_payee else [],
            )

        if qr_kind == "url":
            norm_url, domain, is_idn, is_ip = validate_and_normalize_url(qr_payload)
            return IntakeResult(
                input_type="qr_image",
                raw_input=qr_payload,
                normalized_url=norm_url,
                domain=domain,
                is_idn=is_idn,
                is_ip=is_ip,
            )

        return IntakeResult(
            input_type="qr_image",
            raw_input=qr_payload,
        )

    # 2. Direct Link Intake
    if input_type == "link":
        norm_url, domain, is_idn, is_ip = validate_and_normalize_url(raw_input)
        return IntakeResult(
            input_type="link",
            raw_input=raw_input,
            normalized_url=norm_url,
            domain=domain,
            is_idn=is_idn,
            is_ip=is_ip,
        )

    # 3. Message Intake
    if input_type == "message":
        primary_url, upi_ids = extract_from_message(raw_input)
        norm_url, domain, is_idn, is_ip = (None, None, False, False)
        if primary_url:
            norm_url, domain, is_idn, is_ip = validate_and_normalize_url(primary_url)

        return IntakeResult(
            input_type="message",
            raw_input=raw_input,
            normalized_url=norm_url,
            domain=domain,
            is_idn=is_idn,
            is_ip=is_ip,
            extracted_upi_ids=upi_ids,
            input_payee=upi_ids[0] if upi_ids else None,
        )

    raise ValueError(f"Unsupported input_type '{input_type}'. Must be link, message, or qr_image.")
