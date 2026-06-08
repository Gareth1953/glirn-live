import unittest

from agent_safety_gate import ALLOW, BLOCK, REQUEST_APPROVAL, evaluate_agent_action


class AgentSafetyGateTests(unittest.TestCase):
    def base_payload(self, **overrides):
        payload = {
            "action_type": "send_email",
            "recipient_type": "internal",
            "subject": "Draft",
            "body": "Internal draft only.",
            "customer_facing": False,
            "contains_money_claim": False,
            "contains_private_data": False,
            "contains_legal_advice": False,
            "contains_medical_advice": False,
            "contains_regulated_financial_advice": False,
            "spends_money": False,
            "changes_vendor": False,
            "publishes_content": False,
            "executes_workflow": False,
            "human_approved_already": False,
        }
        payload.update(overrides)
        return payload

    def assert_safety_defaults(self, result):
        self.assertFalse(result["capital_execution"])
        self.assertFalse(result["autonomous_execution"])
        self.assertEqual(result["safe_default"], "do_not_execute")

    def test_internal_draft_is_allowed(self):
        result = evaluate_agent_action(self.base_payload())

        self.assertEqual(result["decision"], ALLOW)
        self.assertFalse(result["approval_required"])
        self.assertFalse(result["blocked"])
        self.assert_safety_defaults(result)

    def test_customer_email_requests_approval(self):
        result = evaluate_agent_action(self.base_payload(
            recipient_type="customer",
            customer_facing=True,
        ))

        self.assertEqual(result["decision"], REQUEST_APPROVAL)
        self.assertTrue(result["approval_required"])
        self.assertIn("customer_facing_action", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_already_approved_customer_email_is_allowed(self):
        result = evaluate_agent_action(self.base_payload(
            recipient_type="customer",
            customer_facing=True,
            human_approved_already=True,
        ))

        self.assertEqual(result["decision"], ALLOW)
        self.assert_safety_defaults(result)

    def test_legal_advice_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(contains_legal_advice=True))

        self.assertEqual(result["decision"], BLOCK)
        self.assertTrue(result["blocked"])
        self.assertIn("legal_advice", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_medical_advice_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(contains_medical_advice=True))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("medical_advice", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_regulated_financial_advice_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(
            contains_regulated_financial_advice=True,
        ))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("regulated_financial_advice", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_spending_money_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(spends_money=True))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("capital_impact", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_vendor_change_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(changes_vendor=True))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("vendor_change", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_internal_private_data_requests_approval(self):
        result = evaluate_agent_action(self.base_payload(contains_private_data=True))

        self.assertEqual(result["decision"], REQUEST_APPROVAL)
        self.assertIn("private_data", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_customer_private_data_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(
            recipient_type="customer",
            customer_facing=True,
            contains_private_data=True,
        ))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("private_data", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_customer_money_claim_requests_approval(self):
        result = evaluate_agent_action(self.base_payload(
            recipient_type="customer",
            customer_facing=True,
            contains_money_claim=True,
        ))

        self.assertEqual(result["decision"], REQUEST_APPROVAL)
        self.assertIn("money_claim", result["reason_codes"])
        self.assert_safety_defaults(result)

    def test_unsupported_action_type_is_blocked(self):
        result = evaluate_agent_action(self.base_payload(action_type="execute_payment"))

        self.assertEqual(result["decision"], BLOCK)
        self.assertIn("unsupported_action_type", result["reason_codes"])
        self.assert_safety_defaults(result)


if __name__ == "__main__":
    unittest.main()
