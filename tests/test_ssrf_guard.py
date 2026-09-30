"""SSRF guard for untrusted listing image URLs (vision.download_image)."""
from deal_radar import vision


def test_literal_private_ips_rejected():
    for u in ("http://127.0.0.1/x.jpg", "http://203.0.113.5/x.jpg",
              "http://192.0.2.1/x.jpg", "http://172.16.0.1/x.jpg",
              "http://169.254.169.254/latest/meta-data/", "http://[::1]/x.jpg",
              "ftp://example.com/x.jpg", "file:///etc/passwd", "not-a-url"):
        assert vision.safe_image_url(u) is None, u


def test_public_shape_passes_guard_without_network(monkeypatch):
    monkeypatch.setattr(vision.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert vision.safe_image_url("https://www.example.com/img.jpg") == "https://www.example.com/img.jpg"


def test_dns_to_private_rejected(monkeypatch):
    monkeypatch.setattr(vision.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    assert vision.safe_image_url("https://evil.example.com/img.jpg") is None


def test_dns_failure_rejected(monkeypatch):
    def boom(*a, **k):
        raise OSError("no dns")

    monkeypatch.setattr(vision.socket, "getaddrinfo", boom)
    assert vision.safe_image_url("https://down.example.com/img.jpg") is None


def test_download_blocks_without_fetch(monkeypatch):
    def boom_client(*a, **k):
        raise AssertionError("no network expected")

    monkeypatch.setattr(vision.httpx, "Client", boom_client)
    assert vision.download_image("http://198.51.100.7/pic.jpg") is None
