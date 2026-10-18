# RFP AI Labeling Guide (v0.1)

Purpose: create ground-truth labels of the requirements in the tuning tenders (t01-t04), so the extractor can be tuned and scored. The held-out tenders (t05, t06) are labeled later, with the same rules, and are never used for tuning.

Golden rule: **if a bidder could lose marks, be disqualified, or be in breach of contract by ignoring a sentence, it is a requirement.**

## 1. Unit of labeling

One row per requirement.
- Usually one sentence. If a requirement spans two sentences, make one row and join the text.
- A table line item that specifies something the vendor must supply = one row. Ignore pricing columns.
- Several separate obligations in one sentence ("shall do A and shall do B") stay one row unless the types differ.

## 2. What counts as a requirement

Label it if it obliges the **bidder, vendor, consultant or contractor** to do, provide, be or accept something, or it states a consequence for the bid.

Binding words: `shall`, `must`, `required`, `is/are to`, `shall not`, imperatives ("Submit...").

| Word | Rule |
|---|---|
| `will` | Binding when the bidder/vendor is the subject ("the vendor will supply OEM material"). Not binding when the agency is the subject. |
| `should` | `mandatory = no` by default. Use `yes` only if the tender says non-compliance leads to rejection or loss of marks. |
| `may`, `preferably` | `mandatory = no` |

**Do not label:**
- Obligations of the procuring agency ("the agency will provide building plans").
- Definitions, background, general descriptions.
- Blank form templates and placeholders (TECH-1 layout, "[Enter source of funds]").
- Pricing tables and quantities with no specification.
- Standard ITB / GCC clauses shared across tenders (see section 7), unless the Data Sheet changes them for this tender.

## 3. Columns

```
tender_id,page,section,text,type,mandatory,knockout,knockout_type,scored_criterion,marks,notes
```

**type**
- `technical`: specifications, scope, deliverables, quality standards
- `eligibility`: registration, licenses, tax status, experience, blacklisting, nationality, key-expert qualifications
- `compliance`: laws, codes, standards, HSE, integrity pact
- `commercial`: price rules, payment, warranty, validity, bid security, taxes, delivery time
- `submission`: forms, documents, format, deadline, portal, copies
- `evaluation`: how bids are scored: criteria, weights, minimum thresholds

**mandatory**: `yes` / `no` / `conditional` (applies only if something else is true, such as "if a JV").

**knockout**: `yes` if failing it means rejection, disqualification, "non-responsive", "not evaluated" or ineligibility.
**knockout_type**:
- `missing_document`: a required document or form is absent (bid security, securing declaration, power of attorney)
- `eligibility`: bidder does not meet the eligibility criteria
- `threshold`: below a minimum score or minimum experience
- `process`: late bid, wrong channel, financial information in the technical proposal

If the requirement and its consequence are in different sentences, label both rows `knockout = yes` and say which row they connect to in `notes`.

**scored_criterion**: `yes` if the text assigns marks. Put the numeric value in `marks`.

## 4. Worked examples

| Sentence (paraphrased) | type | mandatory | knockout | scored |
|---|---|---|---|---|
| A proposal without the securing declaration is rejected as non-responsive. | submission | yes | yes / missing_document | no |
| The consultant must appear on FBR's Active Taxpayers List. | eligibility | yes | yes / eligibility | no |
| Minimum technical score is 70 out of 100. | evaluation | yes | yes / threshold | no |
| Work Plan carries 9 marks. | evaluation | no | no | yes, marks = 9 |
| The vendor will provide one year of support. | commercial | yes | no | no |
| The agency will provide the architectural drawings. | skip (agency duty) | | | |
| Bidders should submit a project organogram. | submission | no | no | no |

## 5. Special cases

- **Repeated lots (t06):** label a unique requirement once and put `lots: all` or the lot number in `notes`.
- **Cross-references ("as per specification DS-01:2026"):** label the sentence and add `external_ref` to `notes`.
- **Contradictions (for example, Rules 2004 vs 2026 in the same document):** label both and add `conflict` to `notes`.
- **Corrigenda:** treat their text like the rest of the document.
- **Unsure?** Label it, set `notes = unsure`, and decide later. Don't skip silently.

## 6. Process

1. **Pilot on t03** (6 pages). Label it, wait a day, and relabel 10 random rows without looking. If you disagree with yourself on more than 1 in 10, fix the wording of the guide.
2. Label t04, then t01, then t02.
3. When you change a rule, check earlier tenders against it.
4. Record which page ranges you labeled for each tender in a `scope` note, so the evaluation only scores those pages.
5. Version the guide at the top. Never edit labels in place without noting why.

## 7. Scope (which sections to label)

Label: invitation/advertisement, Data Sheet (BDS/PDS), eligibility, evaluation criteria, scope of work / TOR / specifications, submission requirements, special conditions.
Skip: standard Instructions to Bidders / General Conditions text, blank forms, annexed price schedules.

Note the page ranges per tender once you have chosen them. The extractor should learn to ignore the boilerplate, and your scope note is what lets the eval measure that.
