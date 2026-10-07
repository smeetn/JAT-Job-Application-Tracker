from playwright.sync_api import sync_playwright

from app.browser.form_preparer import (
    find_application_link,
    is_browser_preparation_allowed,
    is_trusted_application_url,
    prepare_application_page,
)


def test_browser_preparation_only_allows_ready_to_apply_jobs():
    assert is_browser_preparation_allowed("READY_TO_APPLY")
    assert not is_browser_preparation_allowed("PREPARING")
    assert not is_browser_preparation_allowed("SUBMITTED")
    assert not is_browser_preparation_allowed("ALREADY_APPLIED")


def test_local_form_fills_known_fields_skips_risky_answers_and_never_submits(tmp_path):
    cv_path = tmp_path / "DATA_ENGINEERING_CV.docx"
    cv_path.write_bytes(b"test cv file")
    package = {
        "cover_letter": "Draft letter for the role.",
        "answers": [
            {
                "question_id": "motivation",
                "question": "Why are you interested in this role?",
                "answer": "I am interested in the data engineering role.",
                "human_review_required": False,
                "approval_status": "DRAFT",
            },
            {
                "question_id": "salary_expectation",
                "question": "What are your salary expectations?",
                "answer": "UNKNOWN",
                "human_review_required": True,
                "approval_status": "DRAFT",
            },
            {
                "question_id": "years_experience",
                "question": "How many years of relevant experience do you have?",
                "answer": "Approximately 2 years, based on the candidate profile.",
                "human_review_required": False,
                "approval_status": "DRAFT",
            },
        ],
    }
    markup = """
    <form id="application">
      <label for="first">First name</label><input id="first" name="first_name">
      <label for="last">Last name</label><input id="last" name="last_name">
      <label for="email">Email address</label><input id="email" name="email" type="email">
      <label for="motivation">Why are you interested in this role?</label><textarea id="motivation" name="motivation"></textarea>
    <label for="letter">Cover letter</label><textarea id="letter" name="cover_letter"></textarea>
    <label for="years">Years of relevant experience</label><input id="years" name="years_experience" type="number">
      <label for="salary">Salary expectations</label><input id="salary" name="salary">
      <label for="authorization">Are you authorized to work in Italy?</label><input id="authorization" name="work_authorization">
      <label for="cv">Upload resume</label><input id="cv" name="resume" type="file">
      <label><input id="consent" type="checkbox"> I certify that all information is true</label>
      <button id="submit" type="submit">Submit application</button>
    </form>
    <script>document.querySelector('form').addEventListener('submit', event => { event.preventDefault(); window.didSubmit = true; });</script>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(markup)
        result = prepare_application_page(
            page,
            package,
            candidate_data={
                "first_name": "Smeet",
                "last_name": "Nilvarna",
                "email": "smeet@example.test",
                "phone": "+39 000 000 0000",
            },
            cv_path=cv_path,
        )

        assert page.locator("#first").input_value() == "Smeet"
        assert page.locator("#last").input_value() == "Nilvarna"
        assert page.locator("#email").input_value() == "smeet@example.test"
        assert page.locator("#motivation").input_value() == "I am interested in the data engineering role."
        assert page.locator("#letter").input_value() == "Draft letter for the role."
        assert page.locator("#years").input_value() == "2"
        assert page.locator("#salary").input_value() == ""
        assert page.locator("#authorization").input_value() == ""
        assert page.locator("#consent").is_checked() is False
        assert page.locator("#cv").evaluate("element => element.files[0].name") == cv_path.name
        assert page.evaluate("window.didSubmit || false") is False
        assert result["submission_performed"] is False
        assert "salary" in " ".join(result["skipped_fields"]).lower()
        assert "authorization" in " ".join(result["skipped_fields"]).lower()
        browser.close()


def test_apply_link_only_accepts_same_employer_or_known_ats_domain():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<a href="https://attacker.example/apply">Apply now</a>')

        result = find_application_link(page, "https://careers.acme.example/jobs/123")

        assert result is None
        page.set_content(
            '<a href="/apply">Apply for this job</a>'
            '<a href="https://attacker.example/apply">Apply now</a>'
        )
        result = find_application_link(page, "https://careers.acme.example/jobs/123")
        assert result == {
            "url": "https://careers.acme.example/apply",
            "label": "apply for this job",
        }
        page.set_content('<a href="https://attacker.co.uk/apply">Apply now</a>')
        assert find_application_link(page, "https://careers.acme.co.uk/jobs/123") is None
        browser.close()


def test_official_apply_url_accepts_known_ats_but_rejects_untrusted_host():
    job_url = "https://careers.nttdata.com/global/en/job/123"

    assert is_trusted_application_url(
        job_url,
        "https://careers.nttdata.com/global/en/hvhapply?jobSeqNo=123",
    )
    assert is_trusted_application_url(job_url, "https://acme.myworkdayjobs.com/acme/apply")
    assert not is_trusted_application_url(job_url, "https://attacker.example/apply")


def test_newsletter_form_is_not_treated_as_a_job_application(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            '<form><label for="email">Email newsletter</label>'
            '<input id="email" name="email" type="email"></form>'
        )

        result = prepare_application_page(
            page,
            {"answers": []},
            candidate_data={"email": "smeet@example.test"},
            cv_path=None,
        )

        assert result["form_detected"] is False
        assert page.locator("#email").input_value() == ""
        assert result["submission_performed"] is False
        browser.close()


def test_localized_application_form_ignores_separate_login_and_select_controls(tmp_path):
        cv_path = tmp_path / "DATA_ENGINEERING_CV.docx"
        cv_path.write_bytes(b"test cv")
        markup = """
        <div id="login">
            <label for="login-email">Email</label><input id="login-email" type="email">
            <label for="password">Password</label><input id="password" type="password">
        </div>
        <div id="application">
            <label for="firstName">Nombre</label><input id="firstName" name="firstName">
            <label for="lastName">Apellidos</label><input id="lastName" name="lastName">
            <label for="personEmail">Correo electrónico</label><input id="personEmail" name="personEmail" type="email">
            <label for="phone">Teléfono</label><input id="phone" name="phone" type="tel">
            <label for="speciality">Especialidad</label><select id="speciality"><option value="">Seleccionar</option></select>
            <label for="experience">Experiencia</label><select id="experience"><option value="">Seleccionar</option></select>
            <label for="cv">Cargar archivos</label><input id="cv" name="curriculumVitae" type="file">
            <label><input id="consent" type="checkbox"> Acepto la política de privacidad</label>
        </div>
        """

        with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(markup)
                result = prepare_application_page(
                        page,
                        {"answers": []},
                        candidate_data={
                                "first_name": "Smeet",
                                "last_name": "Nilvarna",
                                "email": "smeet@example.test",
                                "phone": "+39 000 000 0000",
                        },
                        cv_path=cv_path,
                )

                assert page.locator("#firstName").input_value() == "Smeet"
                assert page.locator("#lastName").input_value() == "Nilvarna"
                assert page.locator("#personEmail").input_value() == "smeet@example.test"
                assert page.locator("#phone").input_value() == "+39 000 000 0000"
                assert page.locator("#login-email").input_value() == ""
                assert page.locator("#password").input_value() == ""
                assert page.locator("#speciality").input_value() == ""
                assert page.locator("#experience").input_value() == ""
                assert page.locator("#consent").is_checked() is False
                assert result["cv_uploaded"] is True
                assert result["submission_performed"] is False
                browser.close()
