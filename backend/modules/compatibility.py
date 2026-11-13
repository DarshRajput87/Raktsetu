"""Blood group compatibility as hash maps: recipient group -> donor groups to try, in order."""

BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
COMPONENTS = ["whole_blood", "red_cells", "platelets", "plasma"]

# Shelf life in days, used when a donation creates a new unit.
SHELF_LIFE_DAYS = {"whole_blood": 35, "red_cells": 42, "platelets": 5, "plasma": 365}

# Red cells / whole blood. The exact group comes first so it is used before the
# scarcer universal donor; O- is last because every other group can use it.
COMPATIBLE: dict[str, list[str]] = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

# Plasma is the reverse: AB plasma has no antibodies and suits everyone, so it
# is tried last. Rh is ignored for plasma, as is usual practice.
PLASMA_COMPATIBLE: dict[str, list[str]] = {
    "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+": ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"],
    "A-": ["A-", "A+", "AB-", "AB+"],
    "A+": ["A+", "A-", "AB+", "AB-"],
    "B-": ["B-", "B+", "AB-", "AB+"],
    "B+": ["B+", "B-", "AB+", "AB-"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+", "AB-"],
}


def compatible_groups(group: str, component: str) -> list[str]:
    """Donor groups a recipient of `group` can receive, in the order to try them.

    One dict lookup: O(1).

    Simplification: platelets use the red-cell table. In practice platelets are
    less strict (ABO-identical is preferred but other groups are often
    acceptable), so this errs on the safe side.
    """
    if component not in COMPONENTS:
        raise ValueError(f"unknown component: {component}")
    table = PLASMA_COMPATIBLE if component == "plasma" else COMPATIBLE
    if group not in table:
        raise ValueError(f"unknown blood group: {group}")
    return list(table[group])
