import { describe, expect, it } from "vite-plus/test";
import {
  buildObservation,
  matchesSelector,
  parseUiAutomatorXml,
  resolveSelector,
} from "../src/lib/uiautomator.ts";

const SAMPLE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]" clickable="false" enabled="true">
    <node index="0" text="Login" resource-id="com.example:id/login" class="android.widget.Button" bounds="[100,1200][980,1400]" clickable="true" enabled="true"/>
    <node index="1" text="" resource-id="com.example:id/username" class="android.widget.EditText" bounds="[100,800][980,1000]" clickable="true" enabled="true" content-desc="Username field"/>
    <node index="2" text="Settings" resource-id="" class="android.widget.TextView" bounds="[900,100][1000,200]" clickable="false" enabled="true"/>
  </node>
</hierarchy>`;

describe("parseUiAutomatorXml", () => {
  it("parses all nodes with bounds", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    expect(elements).toHaveLength(4);
  });

  it("computes element center from bounds", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    const login = elements.find((e) => e.identifier === "com.example:id/login");
    expect(login?.center).toEqual({ x: 540, y: 1300 });
  });

  it("derives role from class name", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    const login = elements.find((e) => e.identifier === "com.example:id/login");
    expect(login?.role).toBe("button");
  });

  it("falls back to content-desc for label when text is empty", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    const username = elements.find((e) => e.identifier === "com.example:id/username");
    expect(username?.label).toBe("Username field");
  });

  it("marks interactive elements (clickable, has-id, or has-label)", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    expect(elements.filter((e) => e.interactive)).toHaveLength(3);
    const frame = elements.find((e) => e.type === "android.widget.FrameLayout");
    expect(frame?.interactive).toBe(false);
  });
});

describe("resolveSelector", () => {
  const elements = parseUiAutomatorXml(SAMPLE_XML);

  it("resolves by full identifier", () => {
    const el = resolveSelector(elements, { identifier: "com.example:id/login" });
    expect(el.ref).toBeDefined();
    expect(el.role).toBe("button");
  });

  it("resolves by identifier suffix", () => {
    const el = resolveSelector(elements, { identifier: "login" });
    expect(el.identifier).toBe("com.example:id/login");
  });

  it("resolves by label", () => {
    const el = resolveSelector(elements, { label: "Username" });
    expect(el.identifier).toBe("com.example:id/username");
  });

  it("throws not-found when nothing matches", () => {
    try {
      resolveSelector(elements, { label: "nonexistent-xyz" });
      expect.unreachable();
    } catch (error) {
      expect((error as { code?: string }).code).toBe("phone.selector.not-found");
    }
  });

  it("prefers the clickable element when several match", () => {
    const xml = `<hierarchy>
      <node text="确定" resource-id="" class="android.widget.Button" bounds="[0,0][200,100]" clickable="true" enabled="true"/>
      <node text="确定" resource-id="" class="android.widget.TextView" bounds="[50,25][150,75]" clickable="false" enabled="true"/>
    </hierarchy>`;
    const els = parseUiAutomatorXml(xml);
    const el = resolveSelector(els, { label: "确定" });
    expect(el.clickable).toBe(true);
    expect(el.role).toBe("button");
  });

  it("throws ambiguous when multiple non-clickable match", () => {
    const xml = `<hierarchy>
      <node text="X" resource-id="" class="android.widget.TextView" bounds="[0,0][10,10]" clickable="false" enabled="true"/>
      <node text="X" resource-id="" class="android.widget.TextView" bounds="[20,20][30,30]" clickable="false" enabled="true"/>
    </hierarchy>`;
    const els = parseUiAutomatorXml(xml);
    try {
      resolveSelector(els, { label: "X" });
      expect.unreachable();
    } catch (error) {
      const e = error as { code?: string; details?: { candidates?: unknown[] } };
      expect(e.code).toBe("phone.selector.ambiguous");
      expect(e.details?.candidates).toHaveLength(2);
    }
  });
});

describe("matchesSelector", () => {
  it("matches by ref exactly", () => {
    const el = parseUiAutomatorXml(SAMPLE_XML)[0];
    expect(matchesSelector(el, { ref: el.ref })).toBe(true);
    expect(matchesSelector(el, { ref: "e999" })).toBe(false);
  });
});

describe("buildObservation", () => {
  it("builds an observation with element count and platform", () => {
    const elements = parseUiAutomatorXml(SAMPLE_XML);
    const obs = buildObservation(elements, "android", "uiautomator");
    expect(obs.platform).toBe("android");
    expect(obs.source).toBe("uiautomator");
    expect(obs.elementCount).toBe(4);
    expect(obs.truncated).toBe(false);
    expect(obs.elements).toHaveLength(4);
  });
});
