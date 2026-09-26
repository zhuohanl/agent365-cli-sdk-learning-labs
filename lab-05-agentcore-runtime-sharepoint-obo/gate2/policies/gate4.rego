package gate4

import rego.v1

default decision := {
    "decision": "deny",
    "reason": "policy_default_deny",
}

decision := {
    "decision": "deny",
    "reason": "protected_label_denied",
} if {
    protected := lower(input.protected_label)
    some label in input.labels
    lower(label) == protected
}

decision := {
    "decision": "allow",
    "reason": "label_allowed",
} if {
    input.protected_label != ""
    count(input.labels) > 0
    not protected_label_present
}

decision := {
    "decision": "allow",
    "reason": "unlabeled_allowed",
} if {
    input.protected_label != ""
    count(input.labels) == 0
}

protected_label_present if {
    protected := lower(input.protected_label)
    some label in input.labels
    lower(label) == protected
}
