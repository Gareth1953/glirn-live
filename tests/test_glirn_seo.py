import unittest
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient

import app
from glirn_seo import PUBLIC_BASE_URL, PUBLIC_PAGE_PATHS, generate_robots_txt, generate_sitemap_xml


class SeoGenerationTests(unittest.TestCase):
    def test_sitemap_contains_every_public_page(self):
        root = ElementTree.fromstring(generate_sitemap_xml())
        namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [
            element.text
            for element in root.findall("sitemap:url/sitemap:loc", namespace)
        ]

        self.assertEqual(
            locations,
            [f"{PUBLIC_BASE_URL}{path}" for path in PUBLIC_PAGE_PATHS],
        )
        self.assertIn(f"{PUBLIC_BASE_URL}/", locations)
        self.assertIn(f"{PUBLIC_BASE_URL}/services.html", locations)
        self.assertIn(f"{PUBLIC_BASE_URL}/intelligence-review.html", locations)

        public_directory = Path(app.BASE_DIR) / "public"
        public_html_pages = {
            path.name
            for path in public_directory.glob("*.html")
            if not path.name.startswith("google")
        }
        sitemap_html_pages = {
            "index.html" if path == "/" else Path(path).name
            for path in PUBLIC_PAGE_PATHS
        }
        self.assertEqual(sitemap_html_pages, public_html_pages)

        self.assertEqual(
            (public_directory / "sitemap.xml").read_text(encoding="utf-8"),
            generate_sitemap_xml(),
        )

    def test_robots_txt_allows_indexing_and_links_sitemap(self):
        self.assertEqual(
            generate_robots_txt(),
            "User-agent: *\n"
            "Allow: /\n\n"
            "Sitemap: https://glirn-live.onrender.com/sitemap.xml\n",
        )


class SeoPublicRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)

    def test_sitemap_is_publicly_accessible(self):
        response = self.client.get("/sitemap.xml")
        static_response = self.client.get("/public/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("https://glirn-live.onrender.com/", response.text)
        self.assertEqual(static_response.status_code, 200)
        self.assertEqual(static_response.text, response.text)
        for path in PUBLIC_PAGE_PATHS:
            local_path = "/public/" if path == "/" else f"/public{path}"
            public_response = self.client.get(local_path)
            self.assertEqual(public_response.status_code, 200, path)

    def test_robots_txt_is_publicly_accessible(self):
        response = self.client.get("/robots.txt")
        static_response = self.client.get("/public/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertEqual(response.text, generate_robots_txt())
        self.assertEqual(static_response.status_code, 200)
        self.assertEqual(static_response.text, response.text)
        self.assertEqual(
            (Path(app.BASE_DIR) / "public" / "robots.txt").read_text(encoding="utf-8"),
            generate_robots_txt(),
        )


if __name__ == "__main__":
    unittest.main()
