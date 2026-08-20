from src.gmail.client import _is_pdf_part, _walk_parts


def test_walk_parts_flattens_nested_mime_tree():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain"},
                    {"mimeType": "text/html"},
                ],
            },
            {
                "mimeType": "application/pdf",
                "filename": "HDFC_Statement.pdf",
                "body": {"attachmentId": "abc123"},
            },
        ],
    }

    flattened = _walk_parts(payload)
    mime_types = [p.get("mimeType") for p in flattened]

    assert "application/pdf" in mime_types
    assert len(flattened) == 5  # root + 2 nested alt parts + alt wrapper + pdf part


def test_is_pdf_part_matches_by_filename_or_mimetype():
    assert _is_pdf_part({"filename": "statement.PDF"}) is True
    assert _is_pdf_part({"mimeType": "application/pdf"}) is True
    assert _is_pdf_part({"mimeType": "text/html", "filename": ""}) is False


def test_deeply_nested_pdf_is_found():
    payload = {
        "parts": [
            {
                "parts": [
                    {
                        "parts": [
                            {"mimeType": "application/pdf", "filename": "deep.pdf", "body": {"attachmentId": "x"}},
                        ]
                    }
                ]
            }
        ]
    }
    found = [p for p in _walk_parts(payload) if _is_pdf_part(p)]
    assert len(found) == 1
    assert found[0]["filename"] == "deep.pdf"
