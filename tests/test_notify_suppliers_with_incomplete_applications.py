from logging import Logger
import mock
import pytest
from freezegun import freeze_time

from dmutils.email import DMNotifyClient
from dmapiclient import DataAPIClient
from dmscripts.notify_suppliers_with_incomplete_applications import (
    notify_suppliers_with_incomplete_applications,
    MESSAGES,
)
from dmtestutils.api_model_stubs import FrameworkStub


FRAMEWORK_SUPPLIERS_TEST_CASES = [
    [
        # input
        [{
            'supplierId': 0,
            'applicationCompanyDetailsConfirmed': True,
            'declaration': {'status': 'complete', 'primaryContactEmail': 'abc@example.com'}
        }],
        ['abc@example.com', ],  # output, list of email addresses
        '',  # output, expected message fragment
    ],
    [
        # input
        [{
            'supplierId': 1,
            'applicationCompanyDetailsConfirmed': True,
            'declaration': {'status': 'started', 'primaryContactEmail': 'abc@example.com'}
        }],
        ['abc@example.com', ],  # output, list of email addresses
        MESSAGES['incomplete_declaration'],  # output, expected message fragment
    ],
    [
        # input
        [{
            'supplierId': 2,
            'applicationCompanyDetailsConfirmed': True,
            'declaration': {'status': 'started'}
        }],
        [],  # output, list of email addresses
        MESSAGES['incomplete_declaration'],  # output, expected message fragment
    ],
    [
        # input
        [{
            'supplierId': 3,
            'applicationCompanyDetailsConfirmed': True,
            'declaration': {}
        }],
        [],  # output, list of email addresses
        MESSAGES['incomplete_declaration'],  # output, expected message fragment
    ],
    [
        # input
        [{
            'supplierId': 7,
            'applicationCompanyDetailsConfirmed': None,
            'declaration': {}
        }],
        [],  # output, list of email addresses
        # output, expected message fragment
        MESSAGES['unconfirmed_company_details'] + MESSAGES['incomplete_declaration'],
    ],
]

DRAFT_SERVICES_TEST_CASES = [
    [
        # input
        [],
        # output, email message fragment
        MESSAGES['no_services'],
    ],
    [
        [{'status': 'not-submitted'}],
        # output, email message fragment
        MESSAGES['no_services'],
    ],
    [
        [{'status': 'submitted'}, {'status': 'not-submitted'}],
        # output, email message fragment
        MESSAGES['unsubmitted_services'].format(1),
    ],
    [
        [{'status': 'submitted'}],
        # output, email message fragment
        '',
    ],
]

USERS_TEST_CASES = [
    [
        # input
        {'users': []},
        # output, expected number of emails to send
        [],
    ],
    [
        # input
        {'users': [{'active': False, 'emailAddress': 'abc@abc.com'}, {'active': True, 'emailAddress': 'efg@efg.com'}]},
        # output, list of email addresses
        ['efg@efg.com', ],
    ],
]

message_test_cases = []
for fs in FRAMEWORK_SUPPLIERS_TEST_CASES:
    for ds in DRAFT_SERVICES_TEST_CASES:
        for u in USERS_TEST_CASES:
            expected_message = fs[2] + ds[1]
            expected_mails = fs[1] + u[1] if expected_message else []
            message_test_cases.append(
                (  # draft_services_case, framework_supplier_case, users_case, expected_mails, expected_message
                    ds[0], fs[0], u[0], expected_mails, expected_message,
                )
            )


class TestNotifySuppliersWithIncompleteApplications:

    def setup(self):
        self.data_api_client_mock = mock.create_autospec(DataAPIClient)
        self.data_api_client_mock.get_framework.return_value = FrameworkStub(
            applications_close_at="2025-07-01T16:00:00.000000Z",
            status="open"
        ).single_result_response()

        self.logging_mock = mock.create_autospec(Logger, instance=True)

    @pytest.mark.parametrize(
        'draft_services_case,framework_supplier_case,users_case,expected_mails,expected_message', message_test_cases
    )
    @mock.patch('dmscripts.notify_suppliers_with_incomplete_applications.scripts_notify_client', autospec=True)
    def test_message_combinations(
        self, mail_client_constructor_mock,
        draft_services_case, framework_supplier_case, users_case, expected_mails, expected_message
    ):
        """
        Test if the correct number of emails are sent and with the correct message.
        """
        self.data_api_client_mock.find_draft_services_iter.return_value = draft_services_case
        self.data_api_client_mock.find_framework_suppliers_iter.return_value = framework_supplier_case
        self.data_api_client_mock.find_users.return_value = users_case

        mail_client_mock = mail_client_constructor_mock.return_value = mock.Mock(spec=DMNotifyClient)
        mail_client_mock.logger = mock.Mock(spec=Logger)

        with freeze_time('2025-06-24 16:00:00'):
            # Test localisation during BST, 1 week before the deadline
            notify_suppliers_with_incomplete_applications(
                'g-cloud-10', self.data_api_client_mock, 'notify_api_key', False, self.logging_mock
            )

        assert mail_client_mock.send_email.call_count == len(expected_mails)
        for i, call in enumerate(mail_client_mock.send_email.call_args_list):
            assert call[0][2]['message'] == expected_message
            assert call[0][2]['framework_name'] == "G-Cloud 10"
            assert call[0][2]['framework_slug'] == "g-cloud-10"
            assert call[0][2]['application_deadline'] == "5pm BST, Tuesday 1 July 2025"
            assert call[0][0] == expected_mails[i]

    @pytest.mark.parametrize(
        'draft_services_case,framework_supplier_case,users_case,expected_mails,expected_message', message_test_cases
    )
    @mock.patch('dmscripts.notify_suppliers_with_incomplete_applications.scripts_notify_client', autospec=True)
    def test_emails_only_sent_to_restricted_set_of_supplier_ids(
        self, mail_client_constructor_mock,
        draft_services_case, framework_supplier_case, users_case, expected_mails, expected_message
    ):
        """
        Test if the correct number of emails are sent and with the correct message.
        """
        self.data_api_client_mock.find_draft_services_iter.return_value = draft_services_case
        self.data_api_client_mock.find_framework_suppliers_iter.return_value = framework_supplier_case
        self.data_api_client_mock.find_users.return_value = users_case

        mail_client_mock = mail_client_constructor_mock.return_value = mock.Mock(spec=DMNotifyClient)
        mail_client_mock.logger = mock.Mock(spec=Logger)

        # First three supplier IDs from FRAMEWORK_SUPPLIERS_TEST_CASES above
        failed_supplier_ids = [0, 1, 2]

        notify_suppliers_with_incomplete_applications(
            'g-cloud-10',
            self.data_api_client_mock,
            'notify_api_key',
            False,
            self.logging_mock,
            supplier_ids=failed_supplier_ids
        )

        if framework_supplier_case[0]['supplierId'] in failed_supplier_ids:
            # Only supplierIDs 0, 1 and 2 should have received emails
            assert mail_client_mock.send_email.call_count == len(expected_mails)
        else:
            assert mail_client_mock.send_email.call_count == 0

    @pytest.mark.parametrize('framework_status', ['coming', 'pending', 'standstill', 'live', 'expired'])
    def test_notify_suppliers_with_incomplete_applications_fails_for_non_open_frameworks(self, framework_status):
        self.data_api_client_mock.get_framework.return_value = FrameworkStub(
            applications_close_at="2025-07-01T16:00:00.000000Z",
            status=framework_status
        ).single_result_response()

        with pytest.raises(ValueError) as exc:
            notify_suppliers_with_incomplete_applications(
                'g-cloud-10', self.data_api_client_mock, 'notify_api_key', False, self.logging_mock
            )

        assert str(exc.value) == "Suppliers cannot amend applications unless the framework is open."
