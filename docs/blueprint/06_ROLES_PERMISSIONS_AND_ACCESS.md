# Roles, Permissions & Access

Backend RBAC is authoritative. UI hiding is not authorization.

Suggested organization roles (implementation templates, not literal HPE role names):
- Organization Owner
- Organization Admin
- Operations Manager
- Asset Manager
- Maintenance Planner
- Maintenance Supervisor
- Technician
- Stores Manager
- Service Manager
- Client/Requester
- Auditor/Report Consumer

Permission examples:
`organization.view/create/update`
`user.view/create/update`
`role.manage`
`site.view/create/update`
`asset.view/create/update`
`asset.history.view`
`incident.view/create/triage/approve/reject/create_work_order`
`work_order.view/plan/assign/dispatch/start/hold/complete/review/close`
`checklist.execute`
`inventory.view/reserve/issue/return`
`sla.view/manage`
`portal.request.create/view`
`report.view`
`audit.view/export`

Authorization decision:
`identity + org membership + permission + tenant object + scope + valid state`

Test every sensitive endpoint with:
- allowed role;
- wrong role;
- unauthenticated;
- correct role/wrong organization;
- correct org/wrong site/object scope;
- invalid state.

Super Admin is platform-level, not automatically a tenant role.
