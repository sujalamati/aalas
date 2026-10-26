import json
import unittest
from urllib.parse import urlparse, parse_qs

from app.services.jobs_provider import Query, normalize_job, parse_job_description, parse_job_list


class JobsProviderTests(unittest.TestCase):
    def test_url_maps_supported_filters(self):
        query = Query({
            "keyword": "software engineer",
            "location": "Bengaluru",
            "dateSincePosted": "past Week",
            "jobType": "full time",
            "remoteFilter": "remote",
            "salary": "100000",
            "experienceLevel": "entry level",
            "limit": "25",
            "page": "1",
            "sortBy": "recent",
        })
        parsed = urlparse(query.url(0))
        params = parse_qs(parsed.query)
        self.assertEqual(params["keywords"], ["software engineer"])
        self.assertEqual(params["location"], ["Bengaluru"])
        self.assertEqual(params["f_TPR"], ["r604800"])
        self.assertEqual(params["f_JT"], ["F"])
        self.assertEqual(params["f_WT"], ["2"])
        self.assertEqual(params["f_SB2"], ["4"])
        self.assertEqual(params["f_E"], ["2"])
        self.assertEqual(params["start"], ["25"])
        self.assertEqual(params["sortBy"], ["DD"])

    def test_parse_listing_card(self):
        html = '''<ul><li>
          <h3 class="base-search-card__title">Software Engineer</h3>
          <a class="base-search-card__subtitle">Acme</a>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-10-24"></time>
          <span class="job-search-card__salary-info">₹12L - ₹18L</span>
          <a class="base-card__full-link" href="/jobs/view/123"></a>
          <img class="artdeco-entity-image" data-delayed-url="https://example.com/logo.png">
          <span class="job-search-card__listdate">1 day ago</span>
        </li></ul>'''
        jobs = parse_job_list(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["position"], "Software Engineer")
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertEqual(jobs[0]["date"], "2026-10-24")
        self.assertEqual(jobs[0]["jobUrl"], "https://www.linkedin.com/jobs/view/123")
        self.assertEqual(jobs[0]["salary"], "₹12L - ₹18L")

    def test_parse_full_description_from_jobposting_jsonld(self):
        payload = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Backend Engineer",
            "description": "<p>Build reliable services.</p><h2>Requirements</h2><ul><li>Python</li><li>PostgreSQL</li></ul>",
        }
        html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head></html>'
        description = parse_job_description(html)
        self.assertIn("Build reliable services.", description)
        self.assertIn("Requirements", description)
        self.assertIn("Python", description)
        self.assertIn("PostgreSQL", description)
        self.assertIn("•", description)

    def test_parse_description_from_visible_html_fallback(self):
        html = '<div class="show-more-less-html__markup"><p>Primary duties include testing.</p></div>'
        description = parse_job_description(html)
        self.assertIn("Primary duties include testing.", description)

    def test_missing_salary_is_not_specified(self):
        normalized = normalize_job({"position": "Engineer", "company": "Acme", "jobUrl": "https://example.com/job"})
        self.assertEqual(normalized["salary_text"], "Not specified")
        self.assertIsNone(normalized["salary_min"])
        self.assertIsNone(normalized["salary_max"])


if __name__ == "__main__":
    unittest.main()
