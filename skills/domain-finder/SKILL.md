---
name: domain-finder
description: Use when generating product or company names that require an exact .com domain. Generate candidates, screen them in bulk with the included Verisign RDAP script, recheck finalists, and report registry evidence without overstating availability or trademark safety.
license: MIT
compatibility: Requires Python 3.10+ and outbound HTTPS access to rdap.verisign.com.
metadata:
  author: domain-finder-contributors
  version: "1.0.0"
---

# Domain Finder

## Overview

Use a domain-first naming loop: generate broadly, screen exact `.com` candidates with the bundled deterministic script, then spend judgment only on names that survive registry screening.

The script queries Verisign, the `.com` registry operator. HTTP 404 means there is no current RDAP registration record. It does **not** guarantee that a registrar will sell the domain, that the price is standard, or that the name is legally safe.

## When to Use

Use this skill when:

- a product, company, app, or feature needs a name;
- the exact `.com` materially constrains the choice;
- a large candidate list needs fast deterministic screening;
- finalists need fresh registry evidence before a decision.

Do not use it as trademark clearance, registrar purchase confirmation, DNS diagnosis, or social-handle checking.

## Workflow

### 1. Lock the naming constraints

Capture:

- the product's job and audience;
- the emotional promise;
- literal, metaphorical, and outcome territories;
- pronunciation and spelling constraints;
- forbidden themes and misleading category implications;
- the required TLD.

If the user requires `.com`, do not silently substitute `.ai`, `.io`, `.app`, `.co`, or domain hacks.

**Complete when:** the candidate brief states the product, audience, desired tone, exclusions, and exact-domain rule.

### 2. Generate a broad candidate corpus

Generate candidates across independent families:

- product object + outcome;
- product object + motion or direction;
- role or guidance metaphors;
- short compounds;
- pronounceable coined blends;
- a strong favorite plus an honest modifier such as `get`, `use`, `app`, or `coach`.

Write one candidate per line. Keep generation separate from ranking; do not burn model calls checking names one at a time.

**Complete when:** the file contains a deduplicated, varied corpus rather than minor variations of one idea.

### 3. Run the bundled checker

Resolve this skill's installed directory and run:

```bash
python <skill-dir>/scripts/check_com_domains.py \
  --file /absolute/path/candidates.txt \
  --json \
  --output /absolute/path/domain-results.json
```

For a quick shortlist:

```bash
python <skill-dir>/scripts/check_com_domains.py \
  --available-only \
  --json \
  candidate-one candidate-two candidate-three
```

The script accepts positional names, `--file`, or stdin; normalizes names and URLs; deduplicates them; uses bounded concurrency; retries transient failures; and preserves unresolved checks as `unknown`.

Interpret results exactly:

| Result | Meaning |
|---|---|
| `registered` / HTTP 200 | A current `.com` registry record exists |
| `no_rdap_record` / HTTP 404 | No current Verisign RDAP record; likely unregistered |
| `unknown` | Network, rate-limit, service, or unexpected-response failure |

Never convert `unknown` into a positive availability claim.

**Complete when:** every candidate is classified and the unknown count is zero, or unknowns are explicitly excluded from ranking.

### 4. Run a second creative pass

Study the strongest 404 survivors, identify which semantic families survived, create a sharper second batch around those families, and run the same script again. First-pass survivors are often technically usable but bland.

**Complete when:** the best candidates have survived both taste filtering and fresh RDAP screening.

### 5. Rank only the survivors

Score finalists on:

1. pronunciation after hearing the name once;
2. spelling after hearing it once;
3. product and emotional fit;
4. distinctiveness without synthetic awkwardness;
5. visual identity fit;
6. room to expand;
7. absence of misleading implications.

Use the hearing test: can someone hear it once, type the domain, and say it naturally in “I use ___” and “Go to ___.com”?

**Complete when:** the shortlist has one leader, one distinctive alternative, and—when useful—one modifier-domain route preserving the strongest brand.

### 6. Recheck finalists immediately

Run the exact finalist list through the script again immediately before reporting. Registration can change between the first batch and the decision.

Then separate these claims:

1. no current Verisign RDAP record;
2. registrable at a registrar;
3. trademark clearance;
4. handles, store names, and company-name availability.

**Complete when:** every recommended domain has a fresh timestamped result and the report states which later checks remain outstanding.

## Reporting Format

Lead with the practical verdict:

- **Best exact-domain brand** — `example.com`
- **Most distinctive alternative** — `example.com`
- **Best modifier route** — `example.com`, when relevant

For each, include fit, downside, and narrow registry language such as:

> `<candidate>.com` returned HTTP 404 from Verisign RDAP at the recorded check time. That is a strong signal that no current registry record exists, subject to registrar and trademark confirmation.

Report batch counts and unknowns. Attach the JSON output when the full evidence is useful; do not dump hundreds of rejected names into the chat.

## Common Pitfalls

1. **Calling a 404 “available.”** Say “no current Verisign RDAP record” and require registrar confirmation.
2. **Using DNS as registration proof.** A registered domain may have no DNS records; query the registry.
3. **Using registrar search pages for bulk screening.** They are slow and mixed with aftermarket inventory and upsells.
4. **Ranking before screening.** The domain filter should remove most candidates before expensive taste work.
5. **Quietly broadening the TLD.** Respect an exact `.com` constraint.
6. **Inventing trademark or handle safety.** Those are separate checks.
7. **Failing open on network errors.** Keep errors as `unknown`; rerun or exclude them.

## Included Files

- [Verisign RDAP checker](scripts/check_com_domains.py) — dependency-free bulk `.com` screening.
- [Verisign RDAP evidence guide](references/verisign-rdap-domain-screening.md) — endpoint semantics and final confirmation.
- [Candidate generation and ranking guide](references/candidate-generation-and-ranking.md) — naming families and taste filters.

Some skill clients copy only support files explicitly linked from `SKILL.md`; keep these links intact.

## Verification Checklist

- [ ] Candidate constraints and exact TLD are explicit
- [ ] The bundled script—not DNS or memory—performed the registry checks
- [ ] Unknown results were retried or excluded
- [ ] Finalists were freshly rechecked
- [ ] HTTP 404 evidence is described narrowly
- [ ] Registrar, pricing, trademark, and handle checks remain separate
- [ ] The machine-readable result includes the check timestamp
