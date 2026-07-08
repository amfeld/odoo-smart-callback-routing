{
    'name': 'Smart Callback Routing (3CX)',
    'version': '19.0.2.0.1',
    'category': 'AMF',
    'application': True,
    'summary': 'Temporary callback-affinity routing between 3CX and Odoo: '
               'callbacks preferably ring the employee who called last.',
    'author': 'AMF',
    'license': 'AGPL-3',
    'website': 'https://github.com/amfeld/odoo-smart-callback-routing',
    'depends': [
        'base',
        'base_setup',   # res.config.settings view framework
        'hr',           # scr.extension.employee_id → hr.employee (optional mapping)
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/scheduled_actions.xml',
        'views/callback_route_views.xml',
        'views/extension_views.xml',
        'views/routing_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'description': """
Smart Callback Routing for 3CX + Odoo
=====================================

Routes incoming callbacks preferably to the internal employee (3CX extension)
who last tried to call the external contact ("Temporary Callback Affinity
Routing").

How it works
------------
1. An employee calls a contact (outbound from 3CX).
2. 3CX reports the outbound event to Odoo via HTTP.
3. Odoo stores a temporary, TTL-based mapping: phone number → extension.
4. When the contact calls back later, the 3CX call processing script queries
   the routing API.
5. If a valid mapping exists, the mapped extension rings first (with a
   configurable first-ring timeout); afterwards the queue fallback applies.

Properties
----------
* Temporary & TTL-based (default 2 h), no permanent CRM ownership.
* "Last Outbound Wins": the latest valid outbound mapping takes precedence.
* Non-blocking: routing never blocks — the fallback is always available.
* Multi-company aware (mapping per company).
* HTTP JSON API, authenticated via API key (optional HMAC signature).
* Automatic cleanup of expired mappings via cron (GDPR).

API endpoints
-------------
* ``POST /api/3cx/outbound``         — record outbound events
* ``POST /api/3cx/presence``         — update presence/registration
* ``POST /api/3cx/callback-routing`` — inbound routing lookup
""",
}
