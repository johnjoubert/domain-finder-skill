# Verisign RDAP `.com` screening

## Endpoint

For an exact `.com` candidate, query:

```text
https://rdap.verisign.com/com/v1/domain/{label}.com
```

Verisign is the `.com` registry operator. This avoids registrar search pages, aftermarket offers, and upsell noise during high-volume name generation.

## Interpretation

| Response | Screening meaning | Safe reporting language |
|---|---|---|
| HTTP 200 | Current registry record exists | Registered/taken |
| HTTP 404 | No current RDAP registry record | No RDAP record; likely unregistered |
| 429/5xx | Rate limit or transient service failure | Unknown; retry |
| Any other result | Not a clean availability signal | Unknown |

Do not use failed DNS resolution as a substitute. A registered domain may have no useful DNS records, and DNS does not prove registrability.

## Final confirmation

Before committing to a finalist:

1. Requery Verisign RDAP immediately.
2. Attempt normal-price registration at a reputable registrar.
3. Confirm the domain is not reserved, unexpectedly premium-priced, or blocked.
4. Run separate trademark, company-name, store, and social-handle checks as required.
5. Do not publish launch material until control of the domain is confirmed.

## Batch discipline

- Normalize to one `.com` label per line.
- Deduplicate before requesting.
- Use moderate concurrency; the script defaults to eight workers and caps at sixteen.
- Retry only transient statuses and transport failures.
- Preserve unresolved results as `unknown`.
- Recheck the final shortlist because registration state can change quickly.
