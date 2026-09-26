package gate4_test

import data.gate4
import rego.v1

test_protected_label_is_denied if {
    result := gate4.decision with input as {
        "labels": ["Confidential (Personal Data)"],
        "protected_label": "Confidential (Personal Data)",
    }
    result == {
        "decision": "deny",
        "reason": "protected_label_denied",
    }
}

test_other_label_is_allowed if {
    result := gate4.decision with input as {
        "labels": ["Internal Use Only"],
        "protected_label": "Confidential (Personal Data)",
    }
    result == {
        "decision": "allow",
        "reason": "label_allowed",
    }
}

test_confirmed_unlabeled_is_allowed if {
    result := gate4.decision with input as {
        "labels": [],
        "protected_label": "Confidential (Personal Data)",
    }
    result == {
        "decision": "allow",
        "reason": "unlabeled_allowed",
    }
}
