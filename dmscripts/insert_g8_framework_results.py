# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from dmscripts.framework_utils import has_supplier_submitted_services, set_framework_result

FRAMEWORK_SLUG = 'g-cloud-8'

CORRECT_DECLARATION_RESPONSE_MUST_BE_TRUE = ["termsOfParticipation",
                                             "termsAndConditions",
                                             "readUnderstoodGuidance",
                                             "understandTool",
                                             "understandHowToAskQuestions",
                                             "servicesHaveOrSupport",
                                             "canProvideCloudServices",
                                             "skillsAndResources",
                                             "accuratelyDescribed",
                                             "proofOfClaims",
                                             "MI",
                                             "equalityAndDiversity",
                                             ]
CORRECT_DECLARATION_RESPONSE_MUST_BE_YES_OR_NA = ["employersInsurance"]
CORRECT_DECLARATION_RESPONSE_MUST_BE_FALSE = ["conspiracyCorruptionBribery",
                                              "fraudAndTheft",
                                              "terrorism",
                                              "organisedCrime",
                                              ]

CORRECT_DECLARATION_RESPONSE_SHOULD_BE_FALSE = ["taxEvasion",
                                                "environmentalSocialLabourLaw",
                                                "bankrupt",
                                                "graveProfessionalMisconduct",
                                                "distortingCompetition",
                                                "conflictOfInterest",
                                                "distortedCompetition",
                                                "significantOrPersistentDeficiencies",
                                                "seriousMisrepresentation",
                                                "witheldSupportingDocuments",
                                                "influencedContractingAuthority",
                                                "confidentialInformation",
                                                "misleadingInformation",
                                                "unspentTaxConvictions",
                                                "GAAR",
                                                ]

MITIGATING_FACTORS = ["mitigatingFactors", "mitigatingFactors2"]

FAIL = "Fail"
PASS = "Pass"
DISCRETIONARY = "Discretionary"


def check_declaration_answers(declaration):
    if declaration['status'] != 'complete':
        return FAIL

    result = PASS
    for (field_name) in declaration:
        if (field_name in CORRECT_DECLARATION_RESPONSE_MUST_BE_TRUE
           and declaration[field_name] is not True):
            print(" Question {} must be True but is {}".format(field_name, declaration[field_name]))
            result = FAIL

        if (field_name in CORRECT_DECLARATION_RESPONSE_MUST_BE_FALSE
           and declaration[field_name] is not False):
            print(" Question {} must be False but is {}".format(field_name, declaration[field_name]))
            result = FAIL

        if (field_name in CORRECT_DECLARATION_RESPONSE_SHOULD_BE_FALSE
           and declaration[field_name] is not False):
            print(" Question {} should be False but is {}".format(field_name, declaration[field_name]))
            if result == PASS:
                result = DISCRETIONARY

        if (field_name in CORRECT_DECLARATION_RESPONSE_MUST_BE_YES_OR_NA
           and declaration[field_name] not in ["Yes", "Not applicable"]):
            print(" Question {} has the wrong answer: {}".format(field_name, declaration[field_name]))
            result = FAIL

    return result


def process_g8_results(client, user):

    g8_registered_suppliers = client.get_interested_suppliers(FRAMEWORK_SLUG).get('interestedSuppliers', None)

    for supplier_id in g8_registered_suppliers:
        print("SUPPLIER: {}".format(supplier_id))
        declaration = client.get_supplier_declaration(supplier_id, FRAMEWORK_SLUG)['declaration']
        declaration_result = check_declaration_answers(declaration) if declaration else FAIL
        supplier_has_submitted_services = has_supplier_submitted_services(client, FRAMEWORK_SLUG, supplier_id)
        if declaration_result == PASS and supplier_has_submitted_services:
            print("  PASSED")
            res = set_framework_result(client, FRAMEWORK_SLUG, supplier_id, True, user)
            print(res)

        elif declaration_result == DISCRETIONARY and supplier_has_submitted_services:
            print("  DISCRETIONARY")
            # No-op here: leave result as NULL in the database
        else:
            print("  FAILED")
            res = set_framework_result(client, FRAMEWORK_SLUG, supplier_id, False, user)
            print(res)