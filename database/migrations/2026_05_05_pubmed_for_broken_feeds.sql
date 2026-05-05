-- ============================================================================
-- Migration: Switch broken / oversized feeds to PubMedScraper
-- ============================================================================
-- Run this once against your Supabase project.
--
-- Why each is being changed:
--
-- 1. JAMIA (Journal of the American Medical Informatics Association)
--    Old RSS URL: https://academic.oup.com/rss/site_5383/3335.xml
--    Status: returns HTTP 404 (URL no longer maintained by OUP)
--
-- 2. British Journal of Surgery
--    Old RSS URL: https://academic.oup.com/rss/site_5571/3574.xml
--    Status: returns HTTP 404 (BJS publisher arrangement changed in 2023)
--
-- 3. Annals of Surgery
--    Old RSS URL: https://journals.lww.com/.../feed.aspx?FeedType=CurrentIssue
--    Status: returns HTTP 403 (LWW blocks server-side requests)
--
-- 4. Gastroenterology
--    Old RSS URL: https://www.gastrojournal.org/current.rss
--    Status: 9 MB feed, 6500+ entries (annual DDW conference abstract dump).
--            Feed cap in code now prevents crashes, but PubMed gives cleaner
--            data and avoids reprocessing the same archive every run.
--
-- All four are reliably indexed in PubMed by ISSN, so the PubMedScraper
-- works without any further config beyond setting `scraper_class` and
-- nulling `rss_url`.
-- ============================================================================

-- 1. JAMIA  (ISSN 1067-5027)
UPDATE journals
SET scraper_class = 'PubMedScraper',
    rss_url = NULL,
    publisher_type = 'pubmed',
    url = 'https://pubmed.ncbi.nlm.nih.gov/',
    updated_at = NOW()
WHERE name = 'Journal of the American Medical Informatics Association'
   OR issn = '1067-5027';

-- 2. British Journal of Surgery  (ISSN 0007-1323)
UPDATE journals
SET scraper_class = 'PubMedScraper',
    rss_url = NULL,
    publisher_type = 'pubmed',
    url = 'https://pubmed.ncbi.nlm.nih.gov/',
    updated_at = NOW()
WHERE name = 'British Journal of Surgery'
   OR issn = '0007-1323';

-- 3. Annals of Surgery  (ISSN 0003-4932)
UPDATE journals
SET scraper_class = 'PubMedScraper',
    rss_url = NULL,
    publisher_type = 'pubmed',
    url = 'https://pubmed.ncbi.nlm.nih.gov/',
    updated_at = NOW()
WHERE name = 'Annals of Surgery'
   OR issn = '0003-4932';

-- 4. Gastroenterology  (ISSN 0016-5085)
UPDATE journals
SET scraper_class = 'PubMedScraper',
    rss_url = NULL,
    publisher_type = 'pubmed',
    url = 'https://pubmed.ncbi.nlm.nih.gov/',
    updated_at = NOW()
WHERE name = 'Gastroenterology'
   OR issn = '0016-5085';

-- Verify
SELECT name, issn, scraper_class, rss_url
FROM journals
WHERE name IN (
    'Journal of the American Medical Informatics Association',
    'British Journal of Surgery',
    'Annals of Surgery',
    'Gastroenterology'
)
ORDER BY name;
