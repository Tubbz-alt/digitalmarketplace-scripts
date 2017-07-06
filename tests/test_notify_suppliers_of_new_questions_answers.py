import mock
import pytest
from freezegun import freeze_time

from datetime import datetime

from dmscripts.notify_suppliers_of_new_questions_answers import (
    main,
    get_live_briefs_with_new_questions_and_answers_between_two_dates,
    get_ids_of_suppliers_who_started_applying,
    get_ids_of_suppliers_who_asked_a_clarification_question,
    get_ids_of_interested_suppliers_for_briefs,
    get_supplier_email_addresses_by_supplier_id,
    invert_a_dictionary_so_supplier_id_is_key_and_brief_id_is_value,
    create_context_for_supplier
)

ALL_BRIEFS = [
    # a brief with no questions
    {"id": 0, "clarificationQuestions": []},

    # a brief with a question outside of the date range
    {"id": 1, "clarificationQuestions": [{"publishedAt": "2017-03-22T06:00:00.669156Z"}]},

    # a brief with two questions outside of the date range
    {"id": 2, "clarificationQuestions": [
        {"publishedAt": "2017-03-21T06:00:00.669156Z"},
        {"publishedAt": "2017-03-22T06:00:00.669156Z"}
    ]},

    # a brief with a question inside of the date range
    {"id": 3, "clarificationQuestions": [{"publishedAt": "2017-03-23T06:00:00.669156Z"}]},

    # a brief with two questions inside of the date range
    {"id": 4, "clarificationQuestions": [
        {"publishedAt": "2017-03-22T18:00:00.669156Z"},
        {"publishedAt": "2017-03-23T06:00:00.669156Z"}
    ]},

    # a brief with two questions, one of them outside the range and one inside the range
    {"id": 5, "clarificationQuestions": [
        {"publishedAt": "2017-03-22T06:00:00.669156Z"},
        {"publishedAt": "2017-03-23T06:00:00.669156Z"}
    ]},

    # a brief with questions over the weekend
    {"id": 6, "clarificationQuestions": [
        {"publishedAt": "2017-03-17T18:00:00.669156Z"},
        {"publishedAt": "2017-03-18T06:00:00.669156Z"},
        {"publishedAt": "2017-03-19T06:00:00.669156Z"},  # Sunday
        {"publishedAt": "2017-03-20T06:00:00.669156Z"},
    ]}
]

FILTERED_BRIEFS = [ALL_BRIEFS[3], ALL_BRIEFS[4], ALL_BRIEFS[5]]


def test_get_live_briefs_with_new_questions_and_answers_between_two_dates():
    data_api_client = mock.Mock()

    data_api_client.find_briefs_iter.return_value = iter(ALL_BRIEFS)
    briefs = get_live_briefs_with_new_questions_and_answers_between_two_dates(
        data_api_client, datetime(2017, 3, 22, hour=8), datetime(2017, 3, 23, hour=8)
    )
    data_api_client.find_briefs_iter.assert_called_once_with(status="live", human=True)
    assert briefs == FILTERED_BRIEFS


@pytest.mark.parametrize("brief,brief_responses,expected_result", [
    (FILTERED_BRIEFS[0], {"briefResponses": [{"briefId": FILTERED_BRIEFS[0]["id"], "supplierId": 11111}]}, [11111]),
    (
        FILTERED_BRIEFS[1],
        {
            "briefResponses": [
                {"briefId": FILTERED_BRIEFS[1]["id"], "supplierId": 11111},
                {"briefId": FILTERED_BRIEFS[1]["id"], "supplierId": 11112}]
        },
        [11111, 11112]
    ),
    (FILTERED_BRIEFS[2], {"briefResponses": []}, []),
])
def test_get_ids_of_suppliers_who_started_applying(brief, brief_responses, expected_result):
    data_api_client = mock.Mock()
    data_api_client.find_brief_responses.return_value = brief_responses

    assert get_ids_of_suppliers_who_started_applying(data_api_client, brief) == expected_result


@pytest.mark.parametrize("brief,audit_events,expected_result", [
    (
        FILTERED_BRIEFS[0],
        {"auditEvents": [
            {"data": {"briefId": FILTERED_BRIEFS[0]["id"], "question": "can you help me?", "supplierId": 11111}},
            {"data": {"briefId": FILTERED_BRIEFS[0]["id"], "question": "please can you help me?", "supplierId": 11111}},
            {"data": {"briefId": FILTERED_BRIEFS[0]["id"], "question": "can you help me?", "supplierId": 11112}}
        ]},
        [11111, 11111, 11112]
    ), (
        FILTERED_BRIEFS[1],
        {"auditEvents": [{
            "data": {
                "briefId": FILTERED_BRIEFS[1]["id"],
                "question": "can you help me?",
                "supplierId": 11111
            }
        }]},
        [11111]
    ),
    (FILTERED_BRIEFS[2], {"auditEvents": []}, []),
])
def test_get_ids_of_suppliers_who_asked_a_clarification_question(brief, audit_events, expected_result):
    data_api_client = mock.Mock()
    data_api_client.find_audit_events.return_value = audit_events

    assert get_ids_of_suppliers_who_asked_a_clarification_question(data_api_client, brief) == expected_result


@mock.patch(
    'dmscripts.notify_suppliers_of_new_questions_answers.get_ids_of_suppliers_who_asked_a_clarification_question',
    autospec=True
)
@mock.patch('dmscripts.notify_suppliers_of_new_questions_answers.get_ids_of_suppliers_who_started_applying', autospec=True)
def test_get_ids_of_interested_suppliers_for_briefs(
    get_ids_of_suppliers_who_started_applying,
    get_ids_of_suppliers_who_asked_a_clarification_question
):
    briefs = FILTERED_BRIEFS

    get_ids_of_suppliers_who_started_applying.side_effect = (
        [11111, 11112],
        [11111],
        []
    )

    get_ids_of_suppliers_who_asked_a_clarification_question.side_effect = (
        [11111, 11111, 11113],
        [],
        [11111, 11112]
    )

    briefs_and_suppliers = get_ids_of_interested_suppliers_for_briefs(mock.Mock(), briefs)

    expected_result = {
        11111: [FILTERED_BRIEFS[0]["id"], FILTERED_BRIEFS[1]["id"], FILTERED_BRIEFS[2]["id"]],
        11112: [FILTERED_BRIEFS[0]["id"], FILTERED_BRIEFS[2]["id"]],
        11113: [FILTERED_BRIEFS[0]["id"]]
    }

    for brief_id, supplier_ids in briefs_and_suppliers.items():
        assert brief_id in expected_result.keys()
        assert sorted(supplier_ids) == expected_result[brief_id]


def test_invert_a_dictionary_so_supplier_id_is_key_and_brief_id_is_value():
    dictionary_to_invert = {
        FILTERED_BRIEFS[0]["id"]: [11111, 11112, 11113],
        FILTERED_BRIEFS[1]["id"]: [11111],
        FILTERED_BRIEFS[2]["id"]: [11111, 11112]
    }

    expected_result = {
        11111: [FILTERED_BRIEFS[0]["id"], FILTERED_BRIEFS[1]["id"], FILTERED_BRIEFS[2]["id"]],
        11112: [FILTERED_BRIEFS[0]["id"], FILTERED_BRIEFS[2]["id"]],
        11113: [FILTERED_BRIEFS[0]["id"]]
    }

    assert invert_a_dictionary_so_supplier_id_is_key_and_brief_id_is_value(dictionary_to_invert) == expected_result


def test_get_supplier_email_addresses_by_supplier_id():
    data_api_client = mock.Mock()
    data_api_client.find_users.return_value = {
        'users': [
            {'id': 1, 'emailAddress': 'bananas@example.com'},
            {'id': 2, 'emailAddress': 'mangoes@example.com'},
            {'id': 3, 'emailAddress': 'guava@example.com'}
        ]
    }

    assert get_supplier_email_addresses_by_supplier_id(data_api_client, 1) == [
        'bananas@example.com', 'mangoes@example.com', 'guava@example.com'
    ]
    assert data_api_client.find_users.call_args == mock.call(supplier_id=1)


def test_create_context_for_supplier():
    list_of_brief_ids = [FILTERED_BRIEFS[0]["id"], FILTERED_BRIEFS[1]["id"], FILTERED_BRIEFS[2]["id"]]

    expected_result = {}
    assert create_context_for_supplier(list_of_brief_ids) == None


@pytest.mark.parametrize("number_of_days,start_date,end_date", [
    (1, datetime(2017, 4, 18, hour=8), datetime(2017, 4, 19, hour=8)),
    (3, datetime(2017, 4, 16, hour=8), datetime(2017, 4, 19, hour=8))
])
@mock.patch(
    'dmscripts.notify_suppliers_of_new_questions_answers.get_ids_of_interested_suppliers_for_briefs',
    autospec=True
)
@mock.patch(
    'dmscripts.notify_suppliers_of_new_questions_answers.get_live_briefs_with_new_questions_and_answers_between_two_dates',
    autospec=True
)
def test_main_calls_functions(
    get_live_briefs_with_new_questions_and_answers_between_two_dates,
    get_ids_of_interested_suppliers_for_briefs,
    number_of_days,
    start_date,
    end_date
):
    with freeze_time('2017-04-19 08:00:00'):
        api_client = mock.MagicMock()
        main(api_client, number_of_days)
        assert get_live_briefs_with_new_questions_and_answers_between_two_dates.call_args_list == [
            mock.call(api_client, start_date, end_date)
        ]
