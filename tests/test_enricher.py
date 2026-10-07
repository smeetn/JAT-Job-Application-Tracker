from app.extraction.enricher import merge_scraped_description


def test_scrape_enrichment_adds_longer_description_and_detected_skills():
    job = {
        "title": "Data Engineer",
        "full_job_description": "Short search snippet.",
        "technologies": [],
    }

    enriched = merge_scraped_description(
        job,
        "Build Python and SQL ETL pipelines. Use Airflow to maintain data warehouse models and data quality.",
    )

    assert enriched["enrichment_status"] == "scraped"
    assert "Airflow" in enriched["technologies"]
    assert "Python" in enriched["technologies"]
    assert len(enriched["full_job_description"]) > len(job["full_job_description"])


def test_scrape_enrichment_does_not_replace_better_existing_description():
    existing = "Existing detailed job description. " * 10
    job = {"full_job_description": existing, "technologies": ["SQL"]}

    enriched = merge_scraped_description(job, "Short scrape")

    assert enriched["full_job_description"] == existing
    assert enriched["technologies"] == ["SQL"]


def test_multi_location_italy_posting_overrides_milan_search_hint():
    existing = "Milan search snippet. " * 50
    job = {
        "title": "Data Engineer",
        "location": "Milan, Italy",
        "country": "Italy",
        "full_job_description": existing,
        "technologies": [],
    }

    enriched = merge_scraped_description(
        job,
        "This job is available in 10 locations. The position is based in Italy with multiple locations available.",
    )

    assert enriched["location"] == "Italy"


def test_multi_location_posting_without_a_listed_region_stays_unknown():
    job = {
        "title": "Azure Data Engineer",
        "location": "Milan, Italy",
        "country": "Italy",
        "full_job_description": "Search snippet mentioning Milan.",
        "technologies": [],
    }

    enriched = merge_scraped_description(
        job,
        "This job is available in 10 locations. See all locations.",
    )

    assert enriched["location"] == "UNKNOWN"
    assert enriched["country"] == "UNKNOWN"


def test_scraped_page_heading_replaces_search_result_headline():
    job = {
        "title": "Azure Data Engineer job in Milan, Italy | Data and Analytics jobs at NTT Data",
        "full_job_description": "Short search snippet.",
        "technologies": [],
    }

    enriched = merge_scraped_description(
        job,
        "# Azure Data Engineer This job is available in 10 locations. See all locations.",
    )

    assert enriched["title"] == "Azure Data Engineer"


def test_scraped_apply_link_is_saved_separately_from_job_identity_url():
    job = {
        "title": "Azure Data Engineer",
        "application_url": "https://careers.nttdata.com/global/en/job/123/Azure-Data-Engineer",
        "full_job_description": "Short listing text.",
        "technologies": [],
    }

    enriched = merge_scraped_description(
        job,
        '[Apply now](https://careers.nttdata.com/global/en/hvhapply?jobSeqNo=NTT123 "Apply now")',
    )

    assert enriched["application_url"] == job["application_url"]
    assert enriched["application_form_url"] == "https://careers.nttdata.com/global/en/hvhapply?jobSeqNo=NTT123"
