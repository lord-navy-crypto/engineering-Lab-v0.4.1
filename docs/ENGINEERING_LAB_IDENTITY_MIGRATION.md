# Engineering Lab identity migration

The application formerly surfaced the display name **Physical Lab**. The product is now **Engineering Lab**.

## Current migration policy

- User-facing application name: `Engineering Lab`
- Main window title: `Engineering Lab`
- Scientific role: `scientific-computation-and-evidence-core`
- BetterBoard remains the `real-world-ingress`
- OpenPenguin remains the `local-ai-advisory-layer`

The existing Tauri bundle identifier is intentionally retained for now:

```text
com.lordnavy.physicallab
```

Changing the bundle identifier is a separate migration because operating systems may treat the new identifier as a different application, which can affect upgrade continuity, permissions, persisted app state, and existing user data locations.

Internal Python module names beginning with `physical_lab_` are also retained as compatibility namespaces during the transition. New user-facing copy and LabBridge schemas should use **Engineering Lab** unless they are explicitly describing a legacy compatibility contract.

A future identifier/module-namespace migration should include explicit data-path migration and backward-compatibility tests rather than a global search/replace.
