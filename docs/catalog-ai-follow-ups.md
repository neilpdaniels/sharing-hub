# Catalogue AI follow-ups

These are deliberately separate from category review, so a category suggestion
is never used as a reason to block a member from the rest of Rentalution.

## 1. Category-suggestion user and IP bans

- Add a **category-suggestion-only** ban record first: user, optional IP/CIDR,
  reason, staff member, expiry and audit timestamps.
- Check it before accepting the suggestion form and return a neutral response.
- Treat client IPs correctly behind Cloudflare/Nginx: the current category
  quota uses Nginx's overwritten `X-Real-IP`, while Gunicorn is bound to
  localhost in production so users cannot forge it. Never accept an arbitrary
  client-sent `X-Forwarded-For` value.
- Do not make it a global account/IP ban without a separate moderation policy,
  appeal route and false-positive handling for shared household/mobile IPs.

## 2. Catalogue-health review (implemented)

- The admin-triggered, optionally scheduled review now uses product/listing
  counts, completed-rental and transaction demand, category depth, search
  terms, unanswered suggestions and current attribute values.
- It can recommend evidence-backed pruning/merges for stale, thin leaf
  categories; splitting truly broad categories; or a filter attribute when a
  distinction (such as power source) should not fragment the tree.
- CrewAI's two reviewers must agree before a recommendation is routine. Every
  change remains human-approved; the admin can apply a safe tree change or
  create the recommended filter attribute.
