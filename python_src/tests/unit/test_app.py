import datetime
import os
import uuid

import pytest

from babymailgun import app as mailgun_app
import tests


class TestGetEnv(tests.TestBase):
    def test_get_env(self):
        os.environ["TEST_FOO"] = "Foo"
        assert mailgun_app.get_env("TEST_FOO") == "Foo"
        os.environ.pop("TEST_FOO", None)

    def test_get_env_key_not_found(self):
        with pytest.raises(mailgun_app.ConfigKeyNotFound):
            mailgun_app.get_env("TEST_FOO")


class TestEmailModel(tests.TestBase):
    def test_to_email_model(self):
        email_id = str(uuid.uuid4())
        email_dict = {"subject": "Subject",
                      "body": "buffalo" * 8,
                      "to": ["to@unittests.com"],
                      "cc": ["cc@unittests.com"],
                      "bcc": ["bcc@unittests.com"],
                      "from": "from@tester.me"}

        model = mailgun_app.to_email_model(email_id, email_dict)

        assert model["_id"] == email_id
        assert model["subject"] == email_dict["subject"]
        assert model["body"] == email_dict["body"]
        assert model["sender"] == email_dict["from"]

        # We can't mock built-ins so we're stuck asserting the type
        assert isinstance(model["created_at"], datetime.datetime)
        assert model["updated_at"] == datetime.datetime.fromtimestamp(0)
        assert model["status"] == "incomplete"
        assert model["reason"] == ""
        assert model["tries"] == 0
        assert model["worker_id"] is None

        expected_recipients = {
            "to@unittests.com": "to",
            "cc@unittests.com": "cc",
            "bcc@unittests.com": "bcc"}

        assert len(model["recipients"]) == len(expected_recipients)
        for recipient in model["recipients"]:
            assert recipient["address"] in expected_recipients
            assert recipient["type"] == \
                expected_recipients[recipient["address"]]
            assert recipient["status"] == 0
            assert recipient["reason"] == ""


class TestSetupApp(tests.TestBase):
    @pytest.fixture()
    def _envvars(self):
        yield
        os.environ.pop("DB_HOST", None)
        os.environ.pop("DB_PORT", None)
        os.environ.pop("DB_NAME", None)

    def test_setup_app_all_variables_provided(self, _envvars):
        os.environ["DB_HOST"] = "database"
        os.environ["DB_PORT"] = "27017"
        os.environ["DB_NAME"] = "testdb"

        with self.not_raises():
            mailgun_app.setup_app()

    def test_setup_missing_db_host(self, _envvars):
        os.environ["DB_PORT"] = "27017"
        os.environ["DB_NAME"] = "testdb"

        with pytest.raises(mailgun_app.ConfigKeyNotFound):
            mailgun_app.setup_app()

    def test_setup_missing_db_port(self, _envvars):
        os.environ["DB_HOST"] = "database"
        os.environ["DB_NAME"] = "testdb"

        with pytest.raises(mailgun_app.ConfigKeyNotFound):
            mailgun_app.setup_app()

    def test_setup_missing_db_name(self, _envvars):
        os.environ["DB_HOST"] = "database"
        os.environ["DB_PORT"] = "27017"

        with pytest.raises(mailgun_app.ConfigKeyNotFound):
            mailgun_app.setup_app()

    def test_setup_db_port_not_an_integer(self, _envvars):
        os.environ["DB_HOST"] = "database"
        os.environ["DB_PORT"] = "failport"
        os.environ["DB_NAME"] = "testdb"

        with pytest.raises(mailgun_app.ConfigTypeError):
            mailgun_app.setup_app()


class TestValidateEmail(tests.TestBase):
    @pytest.fixture()
    def email_dict(self):
        email_dict = {"subject": "Subject",
                      "body": "buffalo" * 8,
                      "to": ["to@unittests.com"],
                      "cc": ["cc@unittests.com"],
                      "bcc": ["bcc@unittests.com"],
                      "from": "from@tester.me"}
        return email_dict

    def test_validate_email(self, email_dict):
        with self.not_raises():
            mailgun_app.validate_email(email_dict)

    def test_validate_email_subject_too_long(self, email_dict):
        email_dict["subject"] = "A" * (mailgun_app.MAX_SUBJECT_LENGTH + 1)
        with pytest.raises(mailgun_app.SubjectTooLong):
            mailgun_app.validate_email(email_dict)

    def test_validate_email_too_many_recipients(self, email_dict):
        email_dict["to"] = ["to@unittests.com"] * 50
        email_dict["cc"] = ["cc@unittests.com"] * 50
        email_dict["bcc"] = ["bcc@unittests.com"] * 50

        with pytest.raises(mailgun_app.TooManyRecipients):
            mailgun_app.validate_email(email_dict)

    def test_validate_email_invalid_subject(self, email_dict):
        email_dict["subject"] = "{}"
        with pytest.raises(mailgun_app.InvalidSubject):
            mailgun_app.validate_email(email_dict)

    def test_validate_email_invalid_sender(self, email_dict):
        email_dict["from"] = "fffffffffffffff"
        with pytest.raises(mailgun_app.InvalidEmailAddress):
            mailgun_app.validate_email(email_dict)

    def test_validate_email_invalid_recipient(self, email_dict):
        email_dict["to"] = ["tsad;kfjasdfkjqwfg"]
        with pytest.raises(mailgun_app.InvalidEmailAddress):
            mailgun_app.validate_email(email_dict)

    def test_validate_email_body_too_long(self, email_dict):
        email_dict["body"] = "A" * (mailgun_app.MAX_BODY_LENGTH + 1)
        with pytest.raises(mailgun_app.BodyTooLong):
            mailgun_app.validate_email(email_dict)
