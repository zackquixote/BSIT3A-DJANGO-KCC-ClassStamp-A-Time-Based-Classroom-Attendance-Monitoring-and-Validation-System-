"""
# // ==============================================================================
# // KCC CLASSSTAMP - JSON SCRIPT ISLAND SERIALIZER
# // ==============================================================================
# // Subsystem: Template Data Handoff
# // Description: Serializes a value for the `<script type="application/json">`
# //   islands the admin pages read from the DOM. Those islands render with
# //   `|safe`, so autoescaping is off and the serializer has to close the one hole
# //   HTML has: the `</` that ends the element.
# // Reference: docs/09_SECURITY_AUDIT_2026-11-14.md
# // ==============================================================================
"""

import json


def script_json(payload) -> str:
    """
    // [Escaped JSON Island] json.dumps escapes quotes but leaves '</' intact, so a
    // value such as '</script><script>…' would end the island early and the rest of
    // the payload would be parsed as markup. Rewriting '</' as '<\\/' is a JSON
    // escape every parser undoes, and it keeps the closing tag out of the document
    // source entirely.
    """
    return json.dumps(payload).replace('</', '<\\/')
