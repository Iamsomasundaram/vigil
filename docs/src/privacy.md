---
title: "Privacy and safe logging"
summary: Redact emails, IP addresses and secrets before they reach a prompt or a log, and understand what pattern matching cannot catch.
section: Foundations
order: 9
---

# Privacy and safe logging

**The question this page answers:** how do I stop sensitive data from leaking into model prompts and log files?

AI systems create two quiet leaks. The first is **prompts**: whatever you send goes to an outside provider. The second is **logs**: debugging output tends to record everything, and logs are widely shared and kept for a long time. A key pasted into a prompt or a customer email left in a log can end up somewhere you never intended.

{{flow: Raw text | Redact ~ replace sensitive patterns | Safe text ~ for prompts and logs}}

The F15 module, `levels/foundations/privacy.py`, redacts a small set of common patterns. It runs offline.

> **Warning** This is a **teaching-grade, pattern-based** redactor. It catches the formats it knows and nothing else. It is **not** a compliance tool, and it must not be your only protection for personal data. The limits are listed plainly below.

## What it looks for

Each rule is a name, a regular expression and a placeholder:

{{include levels/foundations/privacy.py#_PATTERNS}}

| Rule | Catches | Becomes |
| --- | --- | --- |
| `email` | Typical email addresses | `<REDACTED_EMAIL>` |
| `ipv4` | Four dotted groups of digits | `<REDACTED_IP>` |
| `api_key` | Strings starting `sk-` or `pk-` followed by 16 or more characters | `<REDACTED_KEY>` |
| `token` | `token`, `secret` or `password`, then `:` or `=`, then a value | `<REDACTED_SECRET_FIELD>` |
| card (a separate step) | 13 to 19 digits, spaces or dashes allowed, that pass the **Luhn check** | `<REDACTED_CARD>` |

The card rule is a function, not just a pattern, because a long number is only treated as a card if it passes the Luhn checksum. `order 1234 5678 9012 3456 shipped` fails the check and is left alone, which avoids redacting every long number.

## Redacting text

{{include levels/foundations/privacy.py#redact_text}}

It applies each rule in turn and records *what kind* of thing it found and how many, never the value itself. Recording the type and count lets you monitor leaks without writing the secret into a report.

Running the built-in demo sentence gives this redacted text, and four findings (one each of email, IP, key and secret field):

```text
Contact <REDACTED_EMAIL> from <REDACTED_IP> with <REDACTED_SECRET_FIELD> and key <REDACTED_KEY>
```

## Redacting logs

Log entries are usually nested: dictionaries inside lists inside dictionaries. This helper walks the whole structure and redacts every string it finds, leaving numbers and other values alone:

{{include levels/foundations/privacy.py#safe_log_snapshot}}

The pattern to adopt: **never log a raw payload; log a redacted snapshot of it.**

## What it does NOT catch

Be precise about the gaps, because a false sense of safety is worse than none. I ran this check offline:

- **Names, addresses and phone numbers.** The sentence `Call Alice Smith on 555-0100, card 4111 1111 1111 1111` comes back as `Call Alice Smith on 555-0100, card <REDACTED_CARD>`. The card number is caught, but the person's name and the phone number pass straight through. Detecting those needs a named-entity model, not a regex.
- **Secrets in other formats.** Only keys shaped like `sk-` or `pk-` and fields named token, secret or password are matched. A cloud key with a different prefix, or a password written as plain prose, is not.
- **IPv6 addresses.** Only the dotted IPv4 form is matched.
- **Context.** It cannot tell that a free-text sentence describes a person.
- **Over-matching.** The IPv4 rule matches any four dotted number groups, so some version numbers can be redacted.

Real deployments combine pattern rules with a dedicated PII-detection service, access controls, retention limits and policy review. This page teaches the habit and the mechanism.

> **Tip** The safest data is data you never send. Before redacting, ask whether the model needs the sensitive value at all. Often a placeholder like `<CUSTOMER_ID>` is enough for the task.

## Run it

```bash
python levels/foundations/privacy.py
python levels/foundations/privacy.py "Mail ops@example.com about 10.1.2.3"
```

You should see a JSON report with the input length, whether anything changed, the findings, the redacted text and a redacted copy of a sample log payload. The same report is available from the API as `POST /foundations/privacy/redact`.

## Try it

> **Try it** 1) Run it on a sentence containing a person's name and a phone number and confirm they are not caught. 2) Add a new rule to `_PATTERNS` for a pattern you care about (for example, a UK postcode) and re-run. 3) Build a nested dictionary with a secret three levels deep and check `safe_log_snapshot` finds it.

## Common mistakes

- **Trusting redaction to be complete.** It only knows its patterns.
- **Redacting only prompts.** Logs, traces and error messages leak too.
- **Logging the finding's value.** Record the type and count, not the secret.
- **Redacting after sending.** It must happen *before* the data leaves your system.
- **Skipping the question of whether the data is needed at all.**

## Check yourself

??? Why does the report store the type and count of each finding but not the matched text?
    Writing the secret into the report would recreate the leak you were trying to prevent.

??? Does this module protect a customer's name?
    No. It matches emails, IPv4 addresses, certain key formats, secret-looking fields and Luhn-valid card numbers. Names, addresses and phone numbers pass through.

??? Where must redaction happen to be effective?
    Before the data is sent to the model provider or written to a log.

Next: [Responsible AI](responsible-ai.md) looks at harmful content and unfair outcomes.
