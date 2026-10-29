"""Offline transport-contract tests. No credential or Freelancer network access."""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
import unittest

from src.connections.freelancer_readonly import (
    FreelancerReadAdapter, FreelancerReadError, build_read_request, tool_specs,
)

TOKEN = "synthetic-token-NOT-A-CREDENTIAL"


class Response:
    def __init__(self, result=None, status=200, raw=None):
        self.status_code = status
        self.content = raw if raw is not None else json.dumps(
            {"status": "success", "result": result}).encode()


class FakeFactory:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
        self.calls, self.factories = [], []

    def __call__(self, record, *, headers):
        self.factories.append((record.copy(), headers.copy()))
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, url, *, params):
        self.calls.append(("GET", url, params.copy()))
        if self.error:
            raise self.error
        return self.response


def invoke(operation, arguments, response, environment="sandbox"):
    fake = FakeFactory(response)
    adapter = FreelancerReadAdapter(TOKEN, environment=environment, _client_factory_override=fake)
    return asyncio.run(adapter.read(operation, arguments)), fake


class ReadContractTests(unittest.TestCase):
    def test_account_identity_projection(self):
        result, fake = invoke("account.read", {}, Response({"id": 7, "username": "fixture",
            "display_name": "Synthetic", "email": "private@example.invalid", "balance": 30}))
        self.assertEqual(result["data"], {"id": 7, "username": "fixture", "display_name": "Synthetic"})
        self.assertTrue(result["untrusted_remote_data"])
        self.assertEqual(fake.calls[0][1], "https://www.freelancer-sandbox.com/api/users/0.1/self/")
        self.assertNotIn(TOKEN, repr(result))

    def test_header_only_and_pinned_record(self):
        _, fake = invoke("account.read", {}, Response({"id": 7}), "production")
        record, headers = fake.factories[0]
        self.assertEqual(headers["Freelancer-OAuth-V1"], TOKEN)
        self.assertNotIn("Authorization", headers)
        self.assertFalse(record["allow_private"])
        self.assertEqual(record["url"], "https://www.freelancer.com/api/users/0.1/self/")
        self.assertNotIn(TOKEN, str(fake.calls))

    def test_projects_include_nonactive_by_default(self):
        rows = [{"id": 1, "status": "awarded", "budget": {"minimum": 30, "maximum": 250},
                 "currency": {"code": "EUR"}, "bid_avg": 99}]
        result, fake = invoke("projects.search", {"query": "ordenar Excel"}, Response({"projects": rows}))
        self.assertTrue(fake.calls[0][1].endswith("/projects/all/"))
        self.assertEqual(result["data"]["projects"][0]["status"], "awarded")
        self.assertNotIn("bid_avg", result["data"]["projects"][0])

    def test_active_is_explicit(self):
        _, fake = invoke("projects.search", {"query": "PDF", "active_only": True}, Response({"projects": []}))
        self.assertTrue(fake.calls[0][1].endswith("/projects/active/"))

    def test_project_id_and_scope(self):
        result, fake = invoke("project.read", {"project_id": 15}, Response({"id": 15, "title": "Fixture"}))
        self.assertEqual(result["data"]["id"], 15)
        self.assertTrue(fake.calls[0][1].endswith("/projects/15/"))

    def test_thread_metadata_no_preview_or_attachments(self):
        result, fake = invoke("threads.list", {}, Response({"threads": [
            {"id": 8, "context": 15, "last_message": "private", "attachments": ["secret"]}]}))
        self.assertEqual(result["data"]["threads"], [{"id": 8, "context": 15}])
        self.assertEqual(fake.calls[0][2], {"count": 10})

    def test_one_selected_thread(self):
        result, fake = invoke("messages.read", {"thread_id": 8}, Response({"messages": [
            {"id": 2, "thread_id": 8, "message": "Synthetic message", "attachment_url": "private"}]}))
        self.assertEqual(fake.calls[0][2], {"threads[]": [8], "limit": 10, "offset": 0})
        self.assertNotIn("attachment_url", result["data"]["messages"][0])
        self.assertNotIn("is_read", fake.calls[0][2])

    def test_unknown_write_operations_have_no_transport(self):
        fake = FakeFactory(Response({"id": 7}))
        adapter = FreelancerReadAdapter(TOKEN, _client_factory_override=fake)
        for operation in ("bid.create", "message.send", "payment.release", "mark_read", "GET", "https://evil.invalid"):
            with self.subTest(operation=operation), self.assertRaises(FreelancerReadError):
                asyncio.run(adapter.read(operation, {}))
        self.assertEqual(fake.calls, [])
        self.assertEqual(fake.factories, [])

    def test_extra_parameters_denied(self):
        for extra in ("url", "method", "headers", "credential", "token", "approved", "mark_as_read"):
            with self.subTest(extra=extra), self.assertRaises(FreelancerReadError):
                build_read_request("account.read", {extra: True})

    def test_invalid_ids(self):
        for value in (True, False, 0, -1, 1.0, "1", "../1", 2**53, None):
            for operation, field in (("project.read", "project_id"), ("messages.read", "thread_id")):
                with self.subTest(value=value, operation=operation), self.assertRaises(FreelancerReadError):
                    build_read_request(operation, {field: value})

    def test_pagination_bounds(self):
        for field, values in (("limit", (0, 21, True, "5", 1.0)), ("offset", (-1, 5001, False))):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(FreelancerReadError):
                    build_read_request("projects.search", {"query": "PDF", field: value})

    def test_thread_count_bounds(self):
        for value in (0, 21, True, 1.0):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                build_read_request("threads.list", {"count": value})

    def test_query_validation(self):
        for value in ("", "  ", "x" * 201, "x\r\ny", "x\x00", "x\x7f", None, 15):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                build_read_request("projects.search", {"query": value})

    def test_active_strict_boolean(self):
        for value in (0, 1, "false", None):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                build_read_request("projects.search", {"query": "PDF", "active_only": value})

    def test_missing_or_nonobject_arguments(self):
        for value in (None, [], "{}", True):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                build_read_request("account.read", value)
        with self.assertRaises(FreelancerReadError):
            build_read_request("messages.read", {})

    def test_credential_validation(self):
        for value in ("", "x\ny", "x y", "é", "x" * 8193, None):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                FreelancerReadAdapter(value)

    def test_environment_validation(self):
        for value in ("http://localhost", "https://www.freelancer.com", "prod", None, []):
            with self.subTest(value=value), self.assertRaises(FreelancerReadError):
                FreelancerReadAdapter(TOKEN, environment=value)

    def test_secret_not_in_repr(self):
        self.assertNotIn(TOKEN, repr(FreelancerReadAdapter(TOKEN)))

    def test_secret_in_query_denied_before_transport(self):
        fake = FakeFactory()
        with self.assertRaisesRegex(FreelancerReadError, "credential_in_arguments"):
            asyncio.run(FreelancerReadAdapter(TOKEN, _client_factory_override=fake).read("projects.search", {"query": TOKEN}))
        self.assertEqual(fake.calls, [])

    def test_credential_echo_rejected(self):
        with self.assertRaisesRegex(FreelancerReadError, "credential_in_response"):
            invoke("account.read", {}, Response({"id": 7, "username": TOKEN}))

    def test_escaped_credential_echo_rejected(self):
        escaped = "".join("\\u%04x" % ord(c) for c in TOKEN)
        raw = ('{"status":"success","result":{"id":7,"username":"' + escaped + '"}}').encode()
        with self.assertRaisesRegex(FreelancerReadError, "credential_in_response"):
            invoke("account.read", {}, Response(raw=raw))

    def test_http_errors_sanitized_and_not_retried(self):
        for status, code in ((301, "redirect_denied"), (401, "authentication_failed"),
                             (403, "access_denied"), (404, "not_found"), (429, "rate_limited"),
                             (500, "http_error"), (204, "http_error")):
            fake = FakeFactory(Response(status=status, raw=TOKEN.encode()))
            with self.subTest(status=status), self.assertRaisesRegex(FreelancerReadError, code) as caught:
                asyncio.run(FreelancerReadAdapter(TOKEN, _client_factory_override=fake).read("account.read", {}))
            self.assertNotIn(TOKEN, str(caught.exception))
            self.assertEqual(len(fake.calls), 1)

    def test_exception_does_not_disclose_token(self):
        fake = FakeFactory(error=RuntimeError("transport leaked " + TOKEN))
        with self.assertRaisesRegex(FreelancerReadError, "transport_or_response_error") as caught:
            asyncio.run(FreelancerReadAdapter(TOKEN, _client_factory_override=fake).read("account.read", {}))
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(len(fake.calls), 1)

    def test_timeout_is_explicit(self):
        fake = FakeFactory(error=TimeoutError())
        with self.assertRaisesRegex(FreelancerReadError, "timeout"):
            asyncio.run(FreelancerReadAdapter(TOKEN, _client_factory_override=fake).read("account.read", {}))

    def test_cancel_propagates(self):
        fake = FakeFactory(error=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(FreelancerReadAdapter(TOKEN, _client_factory_override=fake).read("account.read", {}))

    def test_bounded_response(self):
        with self.assertRaisesRegex(FreelancerReadError, "response_too_large"):
            invoke("account.read", {}, Response(raw=b" " * (2 * 1024 * 1024 + 1)))

    def test_invalid_json_envelopes(self):
        for raw in (b'[]', b'{}', b'{"status":"error","result":{"id":7}}', b'<html>error</html>',
                    b'{"status":"success","result":NaN}',
                    b'{"status":"success","result":{"id":7},"result":{"id":8}}'):
            with self.subTest(raw=raw), self.assertRaises(FreelancerReadError):
                invoke("account.read", {}, Response(raw=raw))

    def test_malformed_collections_fail_closed(self):
        for result in ({}, {"projects": None}, {"projects": ["bad"]},
                       {"projects": [{"id": True}]}, {"projects": [{"title": "missing id"}]}):
            with self.subTest(result=result), self.assertRaises(FreelancerReadError):
                invoke("projects.search", {"query": "PDF"}, Response(result))

    def test_collection_limit_enforced(self):
        with self.assertRaises(FreelancerReadError):
            invoke("projects.search", {"query": "PDF", "limit": 1}, Response({"projects": [{"id": 1}, {"id": 2}]}))

    def test_response_project_scope(self):
        with self.assertRaisesRegex(FreelancerReadError, "response_scope_mismatch"):
            invoke("project.read", {"project_id": 1}, Response({"id": 2}))

    def test_response_message_scope(self):
        for value in (None, 9, "8", True):
            with self.subTest(value=value), self.assertRaisesRegex(FreelancerReadError, "response_scope_mismatch"):
                invoke("messages.read", {"thread_id": 8}, Response({"messages": [{"id": 1, "thread_id": value}]}))

    def test_empty_lists_valid_not_successful_job_claim(self):
        result, _ = invoke("projects.search", {"query": "PDF"}, Response({"projects": []}))
        self.assertEqual(result["data"], {"projects": []})
        self.assertNotIn("connected", result)
        self.assertNotIn("receipt_id", result)
        self.assertNotIn("delivered", result)

    def test_all_descriptors_read_only_and_independent(self):
        descriptors = tool_specs()
        self.assertEqual(len(descriptors), 5)
        self.assertTrue(all(x["effect"] == "READ" for x in descriptors))
        self.assertTrue(all(x["input_schema"]["additionalProperties"] is False for x in descriptors))
        descriptors[0]["name"] = "message.send"
        self.assertEqual(tool_specs()[0]["name"], "account.read")

    def test_no_write_transport_or_file_api(self):
        import src.connections.freelancer_readonly as module
        tree = ast.parse(Path(module.__file__).read_text())
        called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(called & {"post", "put", "patch", "delete", "request", "write_text", "write_bytes"})
        self.assertIn("get", called)


if __name__ == "__main__":
    unittest.main()
