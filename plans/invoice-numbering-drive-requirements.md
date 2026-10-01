# Requirements: invoice-numbering-drive

Source: `jf-ceo/sgept-backoffice/invoicing/261001-drive-reconciliation.md`, section "Proposed fix", approved for backlog by Johannes on 1 October 2026. Verdicts ruled at G1 the same day.

| ID | Requirement | Source / Owner | Verdict | Why |
|---|---|---|---|---|
| R1 | The next invoice number is the highest number across the Drive invoicing folder and the local invoicing folder, plus one. | Johannes | KEEP | Local-only numbering caused the 26015 duplicate. |
| R2 | The generator refuses a number already used by another local folder or present on Drive without a local copy; regenerating the same invoice still works. | Johannes | KEEP | Stops a duplicate at the moment it would be created. |
| R3 | The macOS sync uploads through the Drive API; the Drive for desktop folder is no longer read. | Johannes | KEEP | The Mac folder showed 6 of 142 invoice folders on 1 October. |
| R4 | One command files an invoice made outside the generator (Word, Metis) locally and on Drive in one step. | Johannes (restored at G1) | KEEP | Hand-made invoices (IMF 26025, MSF 26031, AUS DFAT 26015) reached only one side. |
| R5 | Each number assignment reports numbers present on one side only and numbers used by more than one folder. | Johannes | KEEP | Drift becomes visible at the natural cadence of new invoices. |
| R6 | The check compares the number printed inside each PDF or docx with its folder number. | Johannes | CUT | The generator's read-back checks the printed number; R2 removes the reason for hand renames. |
| R7 | The reconciliation runs before every number assignment. | Johannes | KEEP | Satisfied by R5 living inside the next-number command. |
| R8 | The check runs weekly on Metis. | Johannes (restored at G1) | KEEP | Catches drift in months without new invoices. |
| R9 | The check produces a register export that answers the bookkeeper's questions. | Johannes (restored at G1) | KEEP | Gives Kropf a status list instead of email rounds. |
| R10 | `/invoice`, `/invoice-nipo`, the governance rule and the Metis invoice handler take the number from the new command. | agent-inferred | KEEP | Without adoption R1 is never used. |

Add-back: cut 4, restored 3 = 75%

## Out of Scope

- R6, the printed-number check. Accepted cost: a hand rename like Hinrich (folder 26013, document 26012) goes unnoticed.
- Renumbering or reissuing any invoice already sent.
- The 2025 numbers, including the 25020 clash in the bookkeeper's register.
- Committing Metis-generated draft invoices back to jf-private (a draft is not on Drive until approved).
- Changing invoice templates, amounts, bank details or the 9-point read-back.
