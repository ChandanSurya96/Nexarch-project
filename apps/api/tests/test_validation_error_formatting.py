"""Validation errors must reach the user as a sentence, not a Python repr.

Every route used to pass `str(exc.messages)` into the error envelope, so the
register form rendered
`{'password': ['Password must contain at least one letter and one digit.']}`
— braces, quotes and brackets included — on the first screen a new user sees.

The end-to-end test is the one that matters: it asserts against the real
`POST /auth/register` response, so re-introducing `str(...)` at any call site
fails here rather than only being caught by eye in a browser.
"""

from __future__ import annotations

from app.utils.responses import format_validation_error

REGISTER_URL = "/api/v1/auth/register"


class TestFormatValidationError:
    def test_field_named_in_the_message_is_not_prefixed(self):
        messages = {"password": ["Password must contain at least one letter and one digit."]}
        assert (
            format_validation_error(messages)
            == "Password must contain at least one letter and one digit."
        )

    def test_generic_message_gains_its_field_name(self):
        messages = {"email": ["Missing data for required field."]}
        assert format_validation_error(messages) == "Email: Missing data for required field."

    def test_underscored_field_names_are_humanised(self):
        messages = {"display_name": ["Longer than maximum length 50."]}
        assert format_validation_error(messages) == "Display name: Longer than maximum length 50."

    def test_multiple_fields_are_joined_in_a_stable_order(self):
        messages = {"email": ["Not a valid email address."], "username": ["Too short."]}
        # Sorted, so the message doesn't reorder between requests for the same
        # input — otherwise an assertion on it would be flaky.
        #
        # Note the asymmetry, which is the prefixing heuristic working rather
        # than a bug: "Not a valid email address." already names its field, so
        # prefixing would give the stutter "Email: Not a valid email address.",
        # while "Too short." carries no subject and needs one.
        assert format_validation_error(messages) == (
            "Not a valid email address. Username: Too short."
        )

    def test_nested_schema_errors_stay_flat(self):
        messages = {"filters": {"strategy": ["Unknown category."]}}
        assert format_validation_error(messages) == "Filters: Strategy: Unknown category."

    def test_non_dict_input_degrades_rather_than_raising(self):
        assert format_validation_error("boom") == "boom"
        assert format_validation_error({}) == "Invalid request."

    def test_output_never_contains_python_repr_punctuation(self):
        messages = {"password": ["Password must contain at least one letter and one digit."]}
        formatted = format_validation_error(messages)
        for ch in ("{", "}", "[", "]", "'"):
            assert ch not in formatted


class TestRegisterSurfacesReadableValidationErrors:
    def test_weak_password_message_is_a_sentence(self, client):
        resp = client.post(
            REGISTER_URL,
            json={
                "email": "someone@example.com",
                "password": "nodigitshere",
                "username": "someone",
            },
        )
        assert resp.status_code == 400
        message = resp.get_json()["error"]["message"]
        assert message == "Password must contain at least one letter and one digit."
        # The regression this file exists for.
        assert "{" not in message and "[" not in message
