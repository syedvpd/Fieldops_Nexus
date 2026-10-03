# SaaS Tenancy & Organization

## Architecture decision

FieldOps Nexus is one multi-tenant SaaS ERP. The application is shared; operational data is tenant-isolated.

## Platform level

Super Admin:
- create/onboard organizations;
- activate/suspend;
- platform settings;
- platform monitoring;
- platform audit.

The exact Super Admin UI is an implementation decision; HPE does not prescribe it.

## Organization level

Organization Owner/Admin:
- organization settings;
- users;
- roles;
- permissions;
- sites;
- zones;
- operational configuration;
- asset/maintenance/field-service administration.

## Onboarding

Recommended:
1. Super Admin clicks Create Organization.
2. Enters organization details.
3. Enters initial owner/admin details.
4. System creates organization.
5. System invites/activates owner/admin.
6. Owner sets password/activates account.
7. Owner enters organization dashboard.
8. Owner configures users, roles and sites.
9. Organization begins asset/operations setup.

Prefer invite/activation rather than showing plaintext passwords.

## Do not create module accounts

Wrong:
`Organization -> Asset account -> WO account -> Inventory account`

Correct:
`Organization -> Users -> Roles -> Permissions -> actions/data scope`

## Tenant isolation

Every tenant-owned record must be linked directly or indirectly to an Organization.

Every request must validate:
- authenticated identity;
- organization membership;
- permission;
- object belongs to organization;
- site/object scope where applicable;
- workflow state permits action.

A user must not access another organization's data by changing an ID or URL.

## Organization structure

`Organization -> Site -> Zone/Building/Service Area -> Asset`

One organization can have many sites, zones and assets.

## Users

`User -> Organization Membership -> Role(s) -> Permissions`

Roles can be organization-wide or site-scoped.

## Client/requester

Authenticated, organization-scoped, restricted to permitted requests/assets/status.

## Important distinction

HPE does not explicitly prescribe:
- exact onboarding UI;
- exact credential/invitation mechanism;
- exact role names;
- exact tenant middleware.

Those are FieldOps Nexus implementation decisions.
