# Workflows & Cross-Module Flows

## Organization
`Super Admin -> Organization -> Owner/Admin -> Users/Roles -> Sites -> Operations`

## Asset setup
`Organization -> Site -> Zone -> Asset Category -> Asset -> Documents/Meter/Status`

## Hierarchy
`Asset -> Parent/Assembly -> Component -> Replaceable Part`

## Reactive breakdown
`NEW -> TRIAGED -> APPROVED/REJECTED -> WORK ORDER CREATED -> IN SERVICE -> RESOLVED -> CONFIRMED -> CLOSED`

M05 Service Request and M06 Work Order are separate state machines.

## Work Order
`DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN PROGRESS -> ON HOLD -> IN PROGRESS -> COMPLETED -> SUPERVISOR REVIEW -> CLOSED`

## PM
`SCHEDULED -> DUE -> GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED -> NEXT CYCLE`

## Technician
`Assigned WO -> Start -> Asset/Site -> Checklist -> Inspection -> Notes -> Attachments -> Parts -> Labor/Time -> Resolution -> Evidence -> Complete`

## Inventory
`REQUESTED -> RESERVED -> ISSUED -> CONSUMED`
or `REQUESTED -> RESERVED -> ISSUED -> RETURNED`
then `RECONCILED`.

Every stock-changing action creates StockMovement.

## SLA
`Request/WO -> SLA -> response timer -> response -> resolution timer -> completion -> breach/success`

Pause only in configured states.

## Warranty
`Asset -> coverage -> Request/WO -> eligibility -> covered/non-covered handling -> expiry/renewal`

## QR
`Asset -> opaque QR -> label -> scan -> Asset Profile -> Service Event`

## Client
`Client -> Request -> Status -> Schedule -> Technician -> Resolution -> Confirmation -> Closed`

## Dashboard
`Real transactions -> PostgreSQL -> aggregations -> role-scoped dashboard`

## Audit
Critical create/update/transition/approval/assignment/inventory/closure/export/permission actions produce audit evidence.

## Seven final journeys

1. Site -> asset hierarchy -> status/change history.
2. PM -> scheduler -> WO -> technician -> checklist -> parts -> labor -> completion -> verification -> next cycle.
3. Breakdown -> triage -> approval -> WO -> assignment -> dispatch -> execution -> review -> closure.
4. High priority -> SLA -> escalation -> resolution.
5. WO -> part request -> reservation -> issue -> consume/return -> reconcile.
6. QR -> asset -> service event -> request/incident -> WO.
7. Client request -> technician completion -> confirmation -> closure -> audit/dashboard.
