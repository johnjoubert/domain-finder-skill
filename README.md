# Domain Finder Skill

A portable [Agent Skills](https://agentskills.io/) skill for generating brand names under an exact `.com` constraint and screening candidates through Verisign RDAP.

It is client-agnostic: the skill is plain Markdown plus a dependency-free Python script. Any agent that supports the Agent Skills directory format—or can read a `SKILL.md` file and execute local scripts—can use it.

The checker classifies each candidate as:

- `registered` — Verisign returned HTTP 200;
- `no_rdap_record` — Verisign returned HTTP 404;
- `unknown` — the result was not safe to classify;
- `invalid` — the input was not a legal `.com` label and was not queried.

A 404 is a strong registry-screening signal, **not** a purchase guarantee or trademark clearance.

## Use as an agent skill

The self-contained skill directory is:

```text
skills/domain-finder/
```

Point your agent's skill installer at that directory, or copy it into the skills directory used by your client:

```bash
cp -R skills/domain-finder /path/to/your-agent/skills/domain-finder
```

The exact installation command and destination vary by agent. The portable contract is the folder itself:

```text
domain-finder/
├── SKILL.md
├── LICENSE
├── references/
│   ├── candidate-generation-and-ranking.md
│   └── verisign-rdap-domain-screening.md
└── scripts/
    └── check_com_domains.py
```

Example request:

```text
Use the domain-finder skill to generate names for a lightweight customer-support app. Exact .com only.
```

## Run the checker directly

```bash
python skills/domain-finder/scripts/check_com_domains.py \
  --available-only \
  candidate-one candidate-two candidate-three
```

From a candidate file:

```bash
python skills/domain-finder/scripts/check_com_domains.py \
  --file candidates.txt \
  --json \
  --output domain-results.json
```

From stdin:

```bash
printf 'candidate-one\ncandidate-two\n' | \
  python skills/domain-finder/scripts/check_com_domains.py --json
```

The checker has no third-party Python dependencies.

## Options

```text
--file PATH          newline-delimited candidate file
--workers N          concurrent checks; default 8, maximum 16
--attempts N         attempts for transient failures; default 3
--available-only     show only no-RDAP-record results
--json               print structured JSON
--output PATH        write structured JSON to a file
--version            print the script version
```

Invalid labels are recorded in the result set and do not abort the batch. The process exits `2` if any result remains `unknown`, making it safe to use in automation without silently treating network failures as availability. `invalid` does not use that exit code.

## Requirements

- Python 3.10 or newer
- Outbound HTTPS access to `rdap.verisign.com`

## Test

```bash
python -m unittest discover -s tests -v
```

## License

MIT
