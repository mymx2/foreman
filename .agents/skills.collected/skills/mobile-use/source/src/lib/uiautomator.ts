// Parse an Android UIAutomator XML dump into a flat element list and resolve
// semantic selectors against it. Pure string/XML handling; no device calls.
import type { Observation, Selector, UiElement } from "./types.ts";
import { cliError } from "./types.ts";

interface Bounds {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

interface ParsedElement extends UiElement {
  contentDesc?: string;
  text?: string;
  clickable: boolean;
  enabled: boolean;
  center: { x: number; y: number };
  bounds: Bounds;
  interactive: boolean;
}

const INTERACTIVE_CLASSES =
  /button|edittext|checkbox|radio|switch|imagebutton|spinner|seekbar|tab|menuitem|link/i;

export function parseUiAutomatorXml(xml: string): ParsedElement[] {
  const elements: ParsedElement[] = [];
  let index = 0;
  const nodePattern = /<node\b([^>]*?)\/?>(?![\s\S]*?<\/node>)|<node\b([^>]*?)>/g;
  let match: RegExpExecArray | null;
  while ((match = nodePattern.exec(xml)) !== null) {
    const attrs = match[1] ?? match[2] ?? "";
    const element = elementFromAttributes(attrs, index);
    index += 1;
    if (element) elements.push(element);
  }
  return elements;
}

function elementFromAttributes(attrs: string, ordinal: number): ParsedElement | undefined {
  const read = (name: string): string => {
    const found = new RegExp(`${name}="([^"]*)"`).exec(attrs);
    return found ? decodeXml(found[1]) : "";
  };
  const box = parseBounds(read("bounds"));
  if (!box) return undefined;
  const className = read("class");
  const identifier = read("resource-id");
  const label = read("text") || read("content-desc");
  const clickable = read("clickable") === "true";
  const enabled = read("enabled") !== "false";
  const interactive =
    clickable || INTERACTIVE_CLASSES.test(className) || Boolean(identifier) || Boolean(label);
  return Object.freeze({
    ref: `e${ordinal}`,
    identifier: identifier || undefined,
    label: label || undefined,
    contentDesc: read("content-desc") || undefined,
    text: read("text") || undefined,
    role: classToRole(className),
    type: className || undefined,
    clickable,
    enabled,
    center: Object.freeze({
      x: Math.round((box.left + box.right) / 2),
      y: Math.round((box.top + box.bottom) / 2),
    }),
    bounds: box,
    interactive,
  });
}

function classToRole(className: string): string | undefined {
  if (!className) return undefined;
  const short = className.split(".").pop() ?? className;
  return short.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
}

function parseBounds(bounds: string): Bounds | undefined {
  const found = /\[(\d+),(\d+)\]\[(\d+),(\d+)\]/.exec(bounds);
  if (!found) return undefined;
  const [, left, top, right, bottom] = found.map(Number);
  return Object.freeze({ left, top, right, bottom });
}

function decodeXml(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

export function resolveSelector(elements: ParsedElement[], selector: Selector): ParsedElement {
  const matches = elements.filter((element) => matchesSelector(element, selector));
  if (matches.length === 0) {
    throw cliError(
      "phone.selector.not-found",
      "No element matched the selector. Re-observe and refine the selector.",
    );
  }
  if (matches.length > 1) {
    // For input actions a clickable target is always preferable to a static
    // label node that merely sits inside it (Compose text inside a button).
    const actionable = matches.filter((element) => element.clickable);
    if (actionable.length === 1) return actionable[0];
    const error = cliError(
      "phone.selector.ambiguous",
      `Selector matched ${matches.length} elements. Add an identifier or more constraints.`,
    );
    error.details = Object.freeze({ candidates: matches.slice(0, 10).map(summarizeCandidate) });
    throw error;
  }
  return matches[0];
}

export function matchesSelector(element: UiElement, selector: Selector): boolean {
  if (selector.ref) return element.ref === selector.ref;
  if (selector.identifier) {
    if (
      !(
        element.identifier === selector.identifier ||
        element.identifier?.endsWith(`/${selector.identifier}`)
      )
    )
      return false;
  }
  if (selector.label) {
    const needle = selector.label.toLowerCase();
    const hay = [element.label, element.text, element.contentDesc]
      .filter(Boolean)
      .map((value) => (value as string).toLowerCase());
    if (!hay.some((value) => value === needle || value.includes(needle))) return false;
  }
  if (selector.role) {
    if (!element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
  }
  if (selector.type) {
    if (!element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
  }
  return true;
}

function summarizeCandidate(element: UiElement): Partial<UiElement> {
  return Object.freeze({
    ref: element.ref,
    identifier: element.identifier,
    label: element.label,
    role: element.role,
    type: element.type,
  });
}

export function buildObservation(
  elements: UiElement[],
  platform: string,
  source: string,
): Observation {
  return Object.freeze({
    uiRevision: Date.now(),
    snapshotId: `snap-${Date.now()}`,
    platform,
    source,
    elementCount: elements.length,
    truncated: false,
    elements: Object.freeze(
      elements.map((element) =>
        Object.freeze({
          ref: element.ref,
          identifier: element.identifier,
          label: element.label,
          role: element.role,
          type: element.type,
          clickable: element.clickable,
          enabled: element.enabled,
          center: element.center,
        }),
      ),
    ) as unknown as UiElement[],
  });
}
