from xml.etree.ElementTree import Element, SubElement, tostring


PUBLIC_BASE_URL = "https://glirn-live.onrender.com"
PUBLIC_PAGE_PATHS = (
    "/",
    "/about.html",
    "/services.html",
    "/intelligence-review.html",
    "/executive-search.html",
    "/contact.html",
    "/privacy.html",
    "/terms.html",
)


def generate_sitemap_xml() -> str:
    urlset = Element(
        "urlset",
        {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    )
    for path in PUBLIC_PAGE_PATHS:
        url = SubElement(urlset, "url")
        SubElement(url, "loc").text = f"{PUBLIC_BASE_URL}{path}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + tostring(
            urlset,
            encoding="unicode",
            short_empty_elements=True,
        )
        + "\n"
    )


def generate_robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {PUBLIC_BASE_URL}/sitemap.xml\n"
    )
