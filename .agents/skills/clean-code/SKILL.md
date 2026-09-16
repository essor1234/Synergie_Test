---
name: clean-code
description: Apply readable naming, small focused functions, explicit errors, and maintainable tests when changing Bright Path Python code.
---

# Bright Path clean code

- Use intention-revealing `snake_case` names for functions and `PascalCase` names for classes.
- Keep functions focused on one operation and avoid boolean control flags.
- Separate commands that change state from queries that return state.
- Keep side effects visible and localized in API, UI, and storage modules.
- Raise specific exceptions instead of returning error codes or `None` for failures.
- Delete dead code instead of commenting it out.
- Write fast, independent, repeatable tests around observable behavior.
- Prefer composition over inheritance and do not create a class when a small function is clearer.
