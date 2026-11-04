## Table

- Use the following rules **only when there is no predefined Table component or Table frame** in the design system or document.
- Table responsive multi screen design: Unless specifically defined, when converting a wide multi-column table to a mobile version, consider using cards instead of table

### Table Structure
- A table consists of:
  - A **header row** containing titles for each column.
  - One or more **data rows**.
  - If the user does not specify data, generate **dummy placeholder values** for each cell.

### Table Cells
- Each **cell** is represented as a **frame node**.
- When designing from scratch, a cell may contain:
  - A **text node** with `textGrowth: fixed-width`, or
  - Another **component or node** (e.g., label, button, etc.), if explicitly requested by the user.

### Table Layout Rules
- **Cell frame**
  - `width: fixed`
  - `height: fill_container` when the row is fixed; `hug_contents` when the row grows with text.
- **Row frame**
  - Contains multiple cell frames.
  - `width: fill_container`
  - `height: fixed` only when every column's longest real value fits on one line at the minimum column width; otherwise use `hug_contents` (and set cell `height` to `hug_contents`) so rows grow with wrapped text.
  - `children`: cell frames

### Cell Text Containment (Design-time only)

- Fixed column widths plus single-line text is valid only when every real value fits within its column at the minimum width; a short fixture passing is not proof.
- Declare the minimum column width, the allowed number of lines, and the source of the longest real value (for example a field length cap) before choosing `fixed`.
- If the longest real value is unknown, default to `height: hug_contents` (with cell `height: hug_contents`) rather than `fixed`.
- If a value does not fit, wrap it (row height grows with content) or explicitly declare truncation/omission; never let text paint into the neighboring cell.

**Verification recipe:** use the longest real value from the field spec at the minimum supported table width; the minimum width must be declared in the design notes. If it is not declared, stop and ask for the narrowest supported width; if the delivery spec already defines one, use it and record it. Read cell width, row/text height, and `textAutoResize` via `batch_read`; pass when the text fits on one line or the row height grows / truncation is declared. A short fixture passing is not evidence.
