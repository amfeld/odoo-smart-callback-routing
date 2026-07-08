# odoo-smart-callback-routing

Temporary **callback-affinity routing** between **3CX V20** and **Odoo 19**: when an
external contact calls back, the call preferably rings the employee (3CX extension)
who last called that contact — temporary, TTL-based, non-blocking.

This repository contains the Odoo module [`smart_callback_routing/`](smart_callback_routing/).
See the module's [README](smart_callback_routing/README.md) for features, API and
configuration, and [`docs/`](smart_callback_routing/docs/) for the full 3CX setup guide.

## Requirements

- Odoo 19 — **Community or Enterprise** (no Enterprise dependencies)
- Depends on `base`, `base_setup`, `hr` (all Community)
- 3CX V20 self-hosted with Call Processing Scripts (for the inbound routing script)

## Installation

Clone the repository into your Odoo addons path and install the module:

```bash
git clone https://github.com/amfeld/odoo-smart-callback-routing.git
# add the repo directory to your Odoo `addons_path`, then:
#   Apps → Update Apps List → install "Smart Callback Routing (3CX)"
```

## How it works

1. An employee dials an external contact — 3CX reports the outbound event to Odoo,
   which stores a TTL-based mapping `phone number → extension`.
2. When the contact calls back, the 3CX inbound call-processing script queries the
   routing API; on a valid mapping the mapped extension rings first, otherwise the
   normal queue routing applies.
3. Routing never blocks: on any error or timeout the API answers `default`, so no
   call is ever lost. A global kill switch pauses sticky routing without touching 3CX.

## License

[AGPL-3.0](LICENSE) — © AMF.
