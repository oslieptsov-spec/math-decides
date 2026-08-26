"""The structured output contract handed to the model.

Status fields are echoed, not authored. The model is asked to repeat what the
receipt already says so that any divergence is mechanically detectable — an
enum keeps a status well-formed, but only comparison against the receipt keeps
it true.

Free prose carries no status literals. Statuses live in structured fields and
nowhere else, which turns "did the model quietly call a withheld output ready"
from a reading-comprehension problem into a string search.
"""
from gate import domain

OUTPUT_NAMES = sorted(domain.OUTPUTS)
LAW_NAMES = sorted(domain.LAWS)
STATUS_NAMES = list(domain.STATUSES)


def explanation_schema(output_names=None):
    """The contract for one receipt.

    Coverage is enforced here rather than requested in the prompt: the outputs
    array is pinned to exactly the receipt's outputs, so an answer that drops
    one cannot be decoded at all. Whatever the schema can enforce is one fewer
    thing the post-validator has to catch after the fact.
    """
    names = sorted(output_names or OUTPUT_NAMES)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "outputs", "unlock", "unreachable", "next_questions"],
        "properties": {
            "summary": {"type": "string"},
            "outputs": {
                "type": "array",
                "minItems": len(names),
                "maxItems": len(names),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "status", "restated_reason"],
                    "properties": {
                        "name": {"type": "string", "enum": names},
                        "status": {"type": "string", "enum": STATUS_NAMES},
                        "restated_reason": {"type": "string"},
                    },
                },
            },
            "unlock": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["output", "declare"],
                    "properties": {
                        "output": {"type": "string", "enum": names},
                        "declare": {"type": "array",
                                    "items": {"type": "string", "enum": LAW_NAMES}},
                    },
                },
            },
            "unreachable": {"type": "array",
                            "items": {"type": "string", "enum": names}},
            "next_questions": {"type": "array", "items": {"type": "string"}},
        },
    }


SYSTEM_PROMPT = (
    "You restate a machine-produced receipt for an engineer who has not seen it.\n"
    "The receipt is the only source of truth. You have no authority over it.\n"
    "\n"
    "What to write:\n"
    "- summary: two or three sentences. Say how many outputs computed and how\n"
    "  many were withheld, quote the computed values with their units, and name\n"
    "  the single thing standing between the caller and the rest.\n"
    "- restated_reason: explain the status in your own words, for this specific\n"
    "  output. Do not copy the receipt's wording back.\n"
    "- next_questions: what the caller should decide next, phrased as questions.\n"
    "\n"
    "Rules:\n"
    "- Repeat every status exactly as the receipt gives it. Never change one.\n"
    "- Quote only numbers that appear in the receipt. Round if you like, but\n"
    "  never past two significant digits, and invent nothing.\n"
    "- Paraphrase every status in plain words. Never quote a raw status code in\n"
    "  summary, restated_reason or next_questions: those fields are English and\n"
    "  the status field already carries the code. Say that an output was\n"
    "  computed; that it is withheld until the missing laws are declared; or\n"
    "  that it is withheld because no closing relation exists.\n"
    "- An output the receipt marks as having no closing relation cannot be\n"
    "  released by any declaration. Never ask which law it needs and never\n"
    "  suggest one; the honest question is whether such a relation can be\n"
    "  defined at all, or whether the output should leave the scope.\n"
    "- If the receipt does not support a statement, leave the statement out."
)


def user_prompt(receipt_json):
    return f"Receipt:\n{receipt_json}\n\nRestate this receipt."
