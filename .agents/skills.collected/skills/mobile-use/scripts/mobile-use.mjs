#!/usr/bin/env node
import { n as isRecord, t as cliError } from "./types-C-qb0oHH.mjs";
import { constants, realpathSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { access, mkdir, readFile, readdir, rm, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { execFile, execFileSync } from "node:child_process";
import os, { homedir, platform, tmpdir } from "node:os";
//#region \0rolldown/runtime.js
var __defProp = Object.defineProperty;
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) __defProp(target, name, {
		get: all[name],
		enumerable: true
	});
	if (!no_symbols) __defProp(target, Symbol.toStringTag, { value: "Module" });
	return target;
};
//#endregion
//#region src/lib/exec.ts
const isWindows = platform() === "win32";
const exeSuffix = isWindows ? ".exe" : "";
function hostPlatform() {
	return platform();
}
async function runTool(file, args = [], options = {}) {
	const timeoutMs = options.timeoutMs ?? 6e4;
	return new Promise((resolvePromise, rejectPromise) => {
		execFile(file, args, {
			timeout: timeoutMs,
			maxBuffer: options.maxBuffer ?? 16777216,
			windowsHide: true
		}, (error, stdout, stderr) => {
			if (error) {
				rejectPromise(cliError(options.errorCode ?? "device.tool.failed", `${path.basename(file)} ${args.join(" ")} failed: ${stderr?.trim() || error.message}`));
				return;
			}
			resolvePromise({
				stdout,
				stderr
			});
		});
	});
}
async function runToolRaw(file, args = [], options = {}) {
	const timeoutMs = options.timeoutMs ?? 6e4;
	return new Promise((resolvePromise, rejectPromise) => {
		execFile(file, args, {
			timeout: timeoutMs,
			maxBuffer: options.maxBuffer ?? 67108864,
			windowsHide: true,
			encoding: "buffer"
		}, (error, stdout, stderr) => {
			if (error) {
				rejectPromise(cliError(options.errorCode ?? "device.tool.failed", `${path.basename(file)} failed: ${stderr?.toString()?.trim() || error.message}`));
				return;
			}
			resolvePromise({
				stdout,
				stderr
			});
		});
	});
}
async function runToolBackgroundPid(file, args, options = {}) {
	return new Promise((resolvePromise, rejectPromise) => {
		execFile(file, args, {
			timeout: options.timeoutMs ?? 15e3,
			maxBuffer: 4194304,
			windowsHide: true
		}, (error, stdout, stderr) => {
			if (error) {
				rejectPromise(cliError(options.errorCode ?? "device.tool.failed", `${path.basename(file)} failed: ${stderr?.toString()?.trim() || error.message}`));
				return;
			}
			const pid = Number.parseInt(String(stdout).trim().split(/\s+/).pop() ?? "", 10);
			resolvePromise({
				pid: Number.isInteger(pid) ? pid : void 0,
				stdout,
				stderr
			});
		});
	});
}
async function fileExists(candidate) {
	try {
		await access(candidate, constants.X_OK);
		return true;
	} catch {
		return false;
	}
}
async function firstExisting(candidates) {
	for (const candidate of candidates) if (candidate && await fileExists(candidate)) return candidate;
}
function sdkRoots(env = process.env) {
	const roots = [];
	if (env.ANDROID_HOME?.trim()) roots.push(env.ANDROID_HOME.trim());
	if (env.ANDROID_SDK_ROOT?.trim()) roots.push(env.ANDROID_SDK_ROOT.trim());
	const home = homedir();
	if (isWindows) {
		roots.push(path.join(home, "AppData", "Local", "Android", "Sdk"));
		roots.push(path.join("C:\\", "Android", "Sdk"));
		roots.push(path.join("D:\\", "Android", "Sdk"));
	} else if (platform() === "darwin") roots.push(path.join(home, "Library", "Android", "sdk"));
	else roots.push(path.join(home, "Android", "Sdk"));
	return [...new Set(roots)];
}
async function findAndroidSdk(env = process.env) {
	for (const root of sdkRoots(env)) {
		const adb = path.join(root, "platform-tools", `adb${exeSuffix}`);
		if (await fileExists(adb)) {
			const emulatorPath = path.join(root, "emulator", `emulator${exeSuffix}`);
			return Object.freeze({
				root,
				adb,
				emulator: await fileExists(emulatorPath) ? emulatorPath : void 0
			});
		}
	}
}
async function findHdc(env = process.env) {
	const home = homedir();
	const candidates = [];
	if (env.DEVECO_SDK_HOME?.trim()) {
		candidates.push(path.join(env.DEVECO_SDK_HOME.trim(), "sdk", "default", "openharmony", "toolchains", `hdc${exeSuffix}`));
		candidates.push(path.join(env.DEVECO_SDK_HOME.trim(), "toolchains", `hdc${exeSuffix}`));
	}
	if (env.HARMONYOS_SDK_HOME?.trim()) candidates.push(path.join(env.HARMONYOS_SDK_HOME.trim(), "toolchains", `hdc${exeSuffix}`));
	candidates.push(path.join(home, "AppData", "Local", "OpenHarmony", "Sdk", "toolchains", `hdc${exeSuffix}`));
	return firstExisting(candidates);
}
async function findXcrun() {
	if (platform() !== "darwin") return void 0;
	return firstExisting(["/usr/bin/xcrun"]);
}
function defaultArtifactDirectory(env = process.env) {
	return path.join(env.MOBILE_USE_ARTIFACT_DIR?.trim() || tmpdir(), "mobile-use-artifacts");
}
async function listDirectoryNames(directory) {
	try {
		return (await readdir(directory, { withFileTypes: true })).filter((entry) => entry.isDirectory()).map((entry) => entry.name);
	} catch {
		return [];
	}
}
//#endregion
//#region src/lib/uiautomator.ts
const INTERACTIVE_CLASSES = /button|edittext|checkbox|radio|switch|imagebutton|spinner|seekbar|tab|menuitem|link/i;
function parseUiAutomatorXml(xml) {
	const elements = [];
	let index = 0;
	const nodePattern = /<node\b([^>]*?)\/?>(?![\s\S]*?<\/node>)|<node\b([^>]*?)>/g;
	let match;
	while ((match = nodePattern.exec(xml)) !== null) {
		const element = elementFromAttributes(match[1] ?? match[2] ?? "", index);
		index += 1;
		if (element) elements.push(element);
	}
	return elements;
}
function elementFromAttributes(attrs, ordinal) {
	const read = (name) => {
		const found = new RegExp(`${name}="([^"]*)"`).exec(attrs);
		return found ? decodeXml(found[1]) : "";
	};
	const box = parseBounds(read("bounds"));
	if (!box) return void 0;
	const className = read("class");
	const identifier = read("resource-id");
	const label = read("text") || read("content-desc");
	const clickable = read("clickable") === "true";
	const enabled = read("enabled") !== "false";
	const interactive = clickable || INTERACTIVE_CLASSES.test(className) || Boolean(identifier) || Boolean(label);
	return Object.freeze({
		ref: `e${ordinal}`,
		identifier: identifier || void 0,
		label: label || void 0,
		contentDesc: read("content-desc") || void 0,
		text: read("text") || void 0,
		role: classToRole(className),
		type: className || void 0,
		clickable,
		enabled,
		center: Object.freeze({
			x: Math.round((box.left + box.right) / 2),
			y: Math.round((box.top + box.bottom) / 2)
		}),
		bounds: box,
		interactive
	});
}
function classToRole(className) {
	if (!className) return void 0;
	return (className.split(".").pop() ?? className).replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
}
function parseBounds(bounds) {
	const found = /\[(\d+),(\d+)\]\[(\d+),(\d+)\]/.exec(bounds);
	if (!found) return void 0;
	const [, left, top, right, bottom] = found.map(Number);
	return Object.freeze({
		left,
		top,
		right,
		bottom
	});
}
function decodeXml(value) {
	return value.replace(/&quot;/g, "\"").replace(/&apos;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}
function resolveSelector(elements, selector) {
	const matches = elements.filter((element) => matchesSelector(element, selector));
	if (matches.length === 0) throw cliError("phone.selector.not-found", "No element matched the selector. Re-observe and refine the selector.");
	if (matches.length > 1) {
		const actionable = matches.filter((element) => element.clickable);
		if (actionable.length === 1) return actionable[0];
		const error = cliError("phone.selector.ambiguous", `Selector matched ${matches.length} elements. Add an identifier or more constraints.`);
		error.details = Object.freeze({ candidates: matches.slice(0, 10).map(summarizeCandidate) });
		throw error;
	}
	return matches[0];
}
function matchesSelector(element, selector) {
	if (selector.ref) return element.ref === selector.ref;
	if (selector.identifier) {
		if (!(element.identifier === selector.identifier || element.identifier?.endsWith(`/${selector.identifier}`))) return false;
	}
	if (selector.label) {
		const needle = selector.label.toLowerCase();
		if (![
			element.label,
			element.text,
			element.contentDesc
		].filter(Boolean).map((value) => value.toLowerCase()).some((value) => value === needle || value.includes(needle))) return false;
	}
	if (selector.role) {
		if (!element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
	}
	if (selector.type) {
		if (!element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
	}
	return true;
}
function summarizeCandidate(element) {
	return Object.freeze({
		ref: element.ref,
		identifier: element.identifier,
		label: element.label,
		role: element.role,
		type: element.type
	});
}
function buildObservation(elements, platform, source) {
	return Object.freeze({
		uiRevision: Date.now(),
		snapshotId: `snap-${Date.now()}`,
		platform,
		source,
		elementCount: elements.length,
		truncated: false,
		elements: Object.freeze(elements.map((element) => Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type,
			clickable: element.clickable,
			enabled: element.enabled,
			center: element.center
		})))
	});
}
//#endregion
//#region src/lib/instrumentation.ts
function classifyInstrumentationOutcome(output) {
	const zeroTests = /OK\s+\(0\s+tests?\)/i.test(output) || /numtests=0/.test(output);
	const classLoadFailed = /ClassNotFoundException|No tests found|Test run failed to complete/i.test(output);
	if (zeroTests || classLoadFailed) return "runner_mismatch";
	if (/FAILURES!!!/i.test(output) || /AssertionError|AssertionFailedError/i.test(output)) return "assertion_failed";
	if (/OK\s+\([1-9]\d*\s+tests?\)/i.test(output)) return "passed";
	if (/Unable to find instrumentation|does not exist|No instrumentation/i.test(output)) return "runner_mismatch";
	if (/Process crashed|shortMsg=|INSTRUMENTATION_RESULT:.*shortMsg/i.test(output)) return "crashed_before_assertion";
	if (/INSTRUMENTATION_CODE:\s*-1/.test(output) && /OK\s+\([1-9]\d*\s+test/i.test(output)) return "passed";
	return "runner_mismatch";
}
//#endregion
//#region src/lib/android-backend.ts
var android_backend_exports = /* @__PURE__ */ __exportAll({
	invokePhoneUse: () => invokePhoneUse$3,
	invokeSessionOperation: () => invokeSessionOperation$3,
	invokeTargetOperation: () => invokeTargetOperation$3,
	isRecord: () => isRecord,
	listAndroidDevices: () => listAndroidDevices,
	listLiveSessions: () => listLiveSessions$3,
	listLiveTargets: () => listLiveTargets$3,
	shellQuoteInputText: () => shellQuoteInputText,
	startPhoneUseSession: () => startPhoneUseSession$3,
	stopPhoneUseSession: () => stopPhoneUseSession$3
});
const SURFACE_ID$2 = "adb-android";
const ADAPTER_ID = "android-adb";
const ANDROID_TARGET_CAPABILITIES = Object.freeze([
	"device.frame.screenshot",
	"device.app.list",
	"device.app.install",
	"device.app.launch",
	"device.app.terminate",
	"device.app.uninstall",
	"device.logs.read",
	"device.test.run",
	"device.recording.native"
]);
/** 校验一个值是安全整数（坐标、时长），否则抛 cli.argument。 */
function requireInt(value, name) {
	if (!Number.isInteger(value)) throw cliError("phone.cli.argument", `${name} must be an integer, got ${JSON.stringify(value)}.`);
	return value;
}
/** Android keyevent：仅接受 KEYCODE_ 名（字母数字下划线）或纯数字键码。 */
const KEYCODE_RE = /^(?:KEYCODE_[A-Z0-9_]+|\d+)$/;
function requireKeyCode(value) {
	if (typeof value !== "string" || !KEYCODE_RE.test(value)) throw cliError("phone.cli.argument", `key must be a KEYCODE_ name or a numeric key code, got ${JSON.stringify(value)}.`);
	return value;
}
/** Android 包名/组件：字母数字、点、下划线、斜杠、$、横线。拒绝 shell 元字符。 */
const PACKAGE_RE = /^[A-Za-z0-9._/$-]+$/;
function requirePackageName(value, name = "package") {
	if (typeof value !== "string" || !PACKAGE_RE.test(value)) throw cliError("phone.cli.argument", `${name} contains unsafe characters: ${JSON.stringify(value)}.`);
	return value;
}
/** instrumentation selector `pkg.Outer$Inner[#method]`：包名字符集加 `#`。 */
const TEST_SELECTOR_RE = /^[A-Za-z0-9._/$-]+(#[A-Za-z0-9_$-]+)?$/;
function requireTestSelector(value) {
	if (typeof value !== "string" || !TEST_SELECTOR_RE.test(value)) throw cliError("phone.cli.argument", `test selector contains unsafe characters: ${JSON.stringify(value)}.`);
	return value;
}
/**
* 把任意文本安全嵌入 `adb shell` 的单引号字符串。
* POSIX 单引号内无转义；正确形式是闭合引号 + `\'` + 重开引号（'\''）。
* 同时把空格转为 Android `input text` 要求的 `%s`。
*/
function shellQuoteInputText(text) {
	return `'${text.replace(/ /g, "%s").replace(/'/g, `'\\''`)}'`;
}
let sdkPromise;
async function sdk() {
	if (!sdkPromise) sdkPromise = findAndroidSdk();
	const resolved = await sdkPromise;
	if (!resolved) throw cliError("device.toolchain.missing", "Android SDK not found. Set ANDROID_HOME or install Android SDK platform-tools. Run `doctor` for setup guidance.");
	return resolved;
}
async function adb(args, options = {}) {
	const { adb: adbPath } = await sdk();
	return runTool(adbPath, args, {
		errorCode: "device.adb.failed",
		...options
	});
}
async function adbOnDevice(serial, args, options = {}) {
	return adb([
		"-s",
		serial,
		...args
	], options);
}
async function adbShell(serial, shellCommand, options = {}) {
	return adbOnDevice(serial, ["shell", shellCommand], options);
}
async function listAndroidDevices() {
	const { stdout } = await adb(["devices", "-l"]);
	const devices = [];
	for (const line of stdout.split("\n").slice(1)) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith("*")) continue;
		const [serial, state, ...rest] = trimmed.split(/\s+/);
		if (!serial || state !== "device") continue;
		const props = Object.fromEntries(rest.map((token) => {
			const splitAt = token.indexOf(":");
			return splitAt === -1 ? [token, ""] : [token.slice(0, splitAt), token.slice(splitAt + 1)];
		}));
		devices.push(Object.freeze({
			serial,
			state,
			model: props.model ?? serial,
			product: props.product,
			runtimeKind: /emulator|sdk_gphone|generic/i.test(props.model ?? serial) ? "emulator" : "physical"
		}));
	}
	return devices;
}
async function listLiveTargets$3() {
	return (await listAndroidDevices()).map((device) => Object.freeze({
		surfaceId: SURFACE_ID$2,
		adapterId: ADAPTER_ID,
		targetId: device.serial,
		platform: "android",
		targetName: device.model,
		runtimeKind: device.runtimeKind,
		state: "online",
		targetCapabilities: [...ANDROID_TARGET_CAPABILITIES]
	}));
}
async function listLiveSessions$3() {
	return (await listAndroidDevices()).map((device) => Object.freeze({
		surfaceId: SURFACE_ID$2,
		sessionId: device.serial,
		targetId: device.serial,
		platform: "android",
		targetName: device.model,
		runtimeKind: device.runtimeKind,
		state: "attached",
		capabilities: Object.freeze([
			Object.freeze({ id: "device.frame.screenshot" }),
			Object.freeze({ id: "device.logs.read" }),
			Object.freeze({ id: "device.test.run" }),
			Object.freeze({ id: "device.recording.native" })
		])
	}));
}
async function startPhoneUseSession$3(surfaceId, targetId) {
	const session = (await listLiveSessions$3()).find((candidate) => candidate.sessionId === targetId);
	if (!session) throw cliError("device.target.not-found", `Android device ${targetId} is not online. Run list-targets again.`);
	return session;
}
async function stopPhoneUseSession$3() {
	return Object.freeze({
		stopped: false,
		note: "ADB devices are not stopped by this skill."
	});
}
async function invokePhoneUse$3(surfaceId, sessionId, method, input) {
	if (method === "observe") return observe$1(sessionId, input);
	if (method === "perform") return perform$1(sessionId, input);
	if (method === "act") return act$1(sessionId, input);
	if (method === "wait") return waitFor$1(sessionId, input);
	if (method === "assert") return assert$1(sessionId, input);
	throw new TypeError(`Unsupported method: ${method}`);
}
async function dumpUi(serial) {
	const remote = `/sdcard/window_dump.xml`;
	await adbShell(serial, `uiautomator dump ${remote}`).catch(() => {});
	const { stdout } = await adbShell(serial, `cat ${remote}`, { timeoutMs: 3e4 });
	if (!stdout.includes("<hierarchy")) throw cliError("device.observe.failed", "uiautomator dump returned no hierarchy. The screen may be off or a secure surface is shown.");
	return stdout;
}
async function observe$1(serial, input = {}) {
	const all = parseUiAutomatorXml(await dumpUi(serial));
	return buildObservation(input?.mode === "full" ? all : all.filter((element) => element.interactive), "android", "uiautomator");
}
async function perform$1(serial, input = {}) {
	const action = input?.action ?? {};
	const element = resolveSelector(parseUiAutomatorXml(await dumpUi(serial)), action.selector ?? {});
	const { x, y } = element.center;
	if (action.kind === "long-press") await adbShell(serial, `input swipe ${x} ${y} ${x} ${y} ${requireInt(action.durationMs ?? 1e3, "long-press durationMs")}`);
	else await adbShell(serial, `input tap ${x} ${y}`);
	const after = await observe$1(serial, {});
	return Object.freeze({
		uiChanged: true,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation: after,
		receipt: Object.freeze({
			operationId: operationId$2("tap"),
			operation: "input.tap",
			status: "succeeded"
		})
	});
}
async function act$1(serial, input = {}) {
	const action = input?.action ?? {};
	const kind = action.kind;
	if (kind === "tap" || kind === "long-press") return perform$1(serial, input);
	if (kind === "swipe") {
		const from = action.from ?? {
			x: 0,
			y: 0
		};
		const to = action.to ?? {
			x: 0,
			y: 0
		};
		await adbShell(serial, `input swipe ${requireInt(from.x, "swipe from.x")} ${requireInt(from.y, "swipe from.y")} ${requireInt(to.x, "swipe to.x")} ${requireInt(to.y, "swipe to.y")} ${requireInt(action.durationMs ?? 300, "swipe durationMs")}`);
		return Object.freeze({
			uiChanged: true,
			observation: await observe$1(serial, {})
		});
	}
	if (kind === "text") {
		await adbShell(serial, `input text ${shellQuoteInputText(String(action.text ?? ""))}`);
		return Object.freeze({
			uiChanged: true,
			observation: await observe$1(serial, {})
		});
	}
	if (kind === "key") {
		await adbShell(serial, `input keyevent ${requireKeyCode(action.key)}`);
		return Object.freeze({
			uiChanged: true,
			observation: await observe$1(serial, {})
		});
	}
	throw new TypeError(`Unsupported act kind: ${kind}`);
}
async function waitFor$1(serial, input = {}) {
	const condition = input?.condition ?? {};
	const timeoutMs = input?.timeoutMs ?? 1e4;
	const pollIntervalMs = input?.pollIntervalMs ?? 500;
	const deadline = Date.now() + timeoutMs;
	let lastObservation;
	while (Date.now() < deadline) {
		lastObservation = await observe$1(serial, {});
		if (condition.kind === "stable") return lastObservation;
		const found = findQuietly(lastObservation, condition.selector);
		if (condition.kind === "present" && found) return lastObservation;
		if (condition.kind === "absent" && !found) return lastObservation;
		await sleep(pollIntervalMs);
	}
	throw cliError("phone.wait.timeout", `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`);
}
async function assert$1(serial, input = {}) {
	const all = parseUiAutomatorXml(await dumpUi(serial));
	const observation = buildObservation(all.filter((element) => element.interactive), "android", "uiautomator");
	let element;
	try {
		element = resolveSelector(all, input?.selector ?? {});
	} catch (error) {
		const code = error.code;
		if (input?.state === "absent" && code === "phone.selector.not-found") return Object.freeze({
			passed: true,
			observation
		});
		if (code?.startsWith("phone.selector")) return Object.freeze({
			passed: false,
			observation,
			reason: code
		});
		throw error;
	}
	const passed = input?.state === "absent" ? false : true;
	return Object.freeze({
		passed,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation
	});
}
function findQuietly(observation, selector = {}) {
	if (!selector || !observation?.elements) return false;
	return observation.elements.some((element) => {
		if (selector.identifier && !(element.identifier === selector.identifier || element.identifier?.endsWith(`/${selector.identifier}`))) return false;
		if (selector.label) {
			const needle = selector.label.toLowerCase();
			if (!element.label?.toLowerCase().includes(needle)) return false;
		}
		if (selector.role && !element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
		if (selector.type && !element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
		return true;
	});
}
async function invokeSessionOperation$3(surfaceId, sessionId, operation, capability, input = {}) {
	switch (operation) {
		case "device.capture.screenshot": return captureScreenshot$2(sessionId);
		case "device.logs.read": return readLogs(sessionId, input);
		case "device.test.run": return runNativeTest(sessionId, input);
		case "device.app.list": return manageApp(sessionId, "list", input);
		case "device.app.install": return manageApp(sessionId, "install", input);
		case "device.app.launch": return manageApp(sessionId, "launch", input);
		case "device.app.terminate": return manageApp(sessionId, "terminate", input);
		case "device.app.uninstall": return manageApp(sessionId, "uninstall", input);
		case "device.recording.start": return recordScreen(sessionId, "start");
		case "device.recording.status": return recordScreen(sessionId, "status");
		case "device.recording.stop": return recordScreen(sessionId, "stop");
		default: throw new TypeError(`Unsupported session operation: ${operation}`);
	}
}
async function invokeTargetOperation$3(surfaceId, targetId, operation) {
	if (operation === "device.target.restart") {
		await adb([
			"-s",
			targetId,
			"reboot"
		]);
		return Object.freeze({
			status: "succeeded",
			operation
		});
	}
	throw new TypeError(`Unsupported target operation: ${operation}`);
}
async function captureScreenshot$2(serial) {
	const { adb: adbPath } = await sdk();
	const { stdout } = await runToolRaw(adbPath, [
		"-s",
		serial,
		"exec-out",
		"screencap",
		"-p"
	], { timeoutMs: 3e4 });
	const artifact = await writeArtifact(serial, Buffer.from(stdout), "png", "image/png", "screenshot");
	return Object.freeze({
		operationId: operationId$2("screenshot"),
		operation: "device.capture.screenshot",
		status: "succeeded",
		completedAt: (/* @__PURE__ */ new Date()).toISOString(),
		output: Object.freeze({ artifact })
	});
}
async function readLogs(serial, input = {}) {
	const seconds = requireInt(input?.seconds ?? 5, "seconds");
	const limit = requireInt(input?.limit ?? 500, "limit");
	await adbShell(serial, "logcat -c").catch(() => {});
	await sleep(Math.min(seconds, 3) * 1e3);
	const { stdout } = await adbOnDevice(serial, [
		"logcat",
		"-d",
		"-t",
		String(limit)
	]);
	return Object.freeze({
		operationId: operationId$2("logs"),
		operation: "device.logs.read",
		status: "succeeded",
		output: Object.freeze({ lines: stdout.split("\n").filter(Boolean).slice(-limit) })
	});
}
async function runNativeTest(serial, input = {}) {
	const rawSelector = input?.selector;
	if (!rawSelector) throw new TypeError("run_native_test requires a selector like com.example.TestClass#testMethod.");
	const selector = requireTestSelector(rawSelector);
	const component = requirePackageName(await resolveInstrumentation(serial, input, selector), "runner");
	const instrumentArgs = [
		"shell",
		"am",
		"instrument",
		"-w",
		"-r"
	];
	if (selector.includes("#") || selector.includes(".")) instrumentArgs.push("-e", "class", selector);
	instrumentArgs.push(component);
	const { stdout, stderr } = await adbOnDevice(serial, instrumentArgs, { timeoutMs: input?.timeoutMs ?? 6e5 }).catch((error) => {
		throw cliError("device.test.failed", `instrumentation failed: ${error.message}`);
	});
	const output = `${stdout}\n${stderr}`;
	const outcome = classifyInstrumentationOutcome(output);
	return Object.freeze({
		operationId: operationId$2("native-test"),
		operation: "device.test.run",
		status: "succeeded",
		output: Object.freeze({
			outcome,
			selector,
			component,
			tail: output.split("\n").filter(Boolean).slice(-40)
		})
	});
}
async function resolveInstrumentation(serial, input, selector) {
	if (typeof input?.runner === "string" && input.runner.includes("/")) return input.runner;
	if (typeof input?.testPackage === "string") {
		const runner = await findRunnerForPackage(serial, input.testPackage);
		return `${input.testPackage}/${runner ?? "androidx.test.runner.AndroidJUnitRunner"}`;
	}
	const className = selector.split("#")[0];
	const instrumentations = await listInstrumentations(serial);
	const match = instrumentations.find((entry) => className.startsWith(entry.targetPackage) || className.startsWith(entry.package.replace(/\.test$/, "")));
	if (match) return `${match.package}/${match.runner}`;
	if (instrumentations.length === 1) return `${instrumentations[0].package}/${instrumentations[0].runner}`;
	throw cliError("device.test.runner-unresolved", `Could not resolve an instrumentation runner for ${className}. Install the androidTest APK or pass --runner <pkg>/<runner>. Found: ${instrumentations.map((i) => i.package).join(", ") || "none"}.`);
}
async function listInstrumentations(serial) {
	const { stdout } = await adbShell(serial, "pm list instrumentation");
	const entries = [];
	const pattern = /instrumentation:([^\s]+)\/([^\s]+)\s+\(target=([^)]+)\)/g;
	let match;
	while ((match = pattern.exec(stdout)) !== null) entries.push(Object.freeze({
		package: match[1],
		runner: match[2],
		targetPackage: match[3]
	}));
	return entries;
}
async function findRunnerForPackage(serial, testPackage) {
	return (await listInstrumentations(serial)).find((entry) => entry.package === testPackage)?.runner;
}
async function manageApp(serial, action, input = {}) {
	const rawBundleId = input?.bundleId;
	const bundleId = rawBundleId === void 0 ? void 0 : requirePackageName(rawBundleId, "bundle_id");
	switch (action) {
		case "list": {
			const { stdout } = await adbShell(serial, "pm list packages");
			const packages = stdout.split("\n").map((line) => line.replace("package:", "").trim()).filter(Boolean);
			return Object.freeze({
				operationId: operationId$2("app-list"),
				operation: "device.app.list",
				status: "succeeded",
				output: Object.freeze({ packages })
			});
		}
		case "install":
			if (!input?.path) throw new TypeError("manage_app install requires a path.");
			await adbOnDevice(serial, [
				"install",
				"-r",
				input.path
			], { timeoutMs: 3e5 });
			return Object.freeze({
				operationId: operationId$2("app-install"),
				operation: "device.app.install",
				status: "succeeded",
				output: Object.freeze({
					installed: true,
					path: input.path
				})
			});
		case "launch":
			if (!bundleId) throw new TypeError("manage_app launch requires bundle_id.");
			await adbShell(serial, `monkey -p ${bundleId} -c android.intent.category.LAUNCHER 1`).catch(async () => {
				await adbShell(serial, `am start -n ${bundleId}/.MainActivity`);
			});
			return Object.freeze({
				operationId: operationId$2("app-launch"),
				operation: "device.app.launch",
				status: "succeeded",
				output: Object.freeze({
					launched: true,
					bundleId
				})
			});
		case "terminate":
			if (!bundleId) throw new TypeError("manage_app terminate requires bundle_id.");
			await adbShell(serial, `am force-stop ${bundleId}`);
			return Object.freeze({
				operationId: operationId$2("app-terminate"),
				operation: "device.app.terminate",
				status: "succeeded",
				output: Object.freeze({
					terminated: true,
					bundleId
				})
			});
		case "uninstall":
			if (!bundleId) throw new TypeError("manage_app uninstall requires bundle_id.");
			if (input?.confirm !== true) throw new TypeError("manage_app uninstall requires confirm=true.");
			await adbOnDevice(serial, ["uninstall", bundleId], { timeoutMs: 12e4 });
			return Object.freeze({
				operationId: operationId$2("app-uninstall"),
				operation: "device.app.uninstall",
				status: "succeeded",
				output: Object.freeze({
					uninstalled: true,
					bundleId
				})
			});
		default: throw new TypeError(`Unsupported manage_app action: ${action}`);
	}
}
function recordingStatePath(serial) {
	return path.join(defaultArtifactDirectory(), serial.replace(/[^\w.-]/g, "_"), "active-recording.json");
}
async function saveRecordingState(serial, state) {
	const filePath = recordingStatePath(serial);
	await mkdir(path.dirname(filePath), { recursive: true });
	await writeFile(filePath, JSON.stringify(state));
}
async function loadRecordingState(serial) {
	try {
		const raw = await readFile(recordingStatePath(serial), "utf8");
		const parsed = JSON.parse(raw);
		if (typeof parsed?.remote === "string") return parsed;
	} catch {}
}
async function clearRecordingState(serial) {
	await unlink(recordingStatePath(serial)).catch(() => {});
}
async function recordScreen(serial, action) {
	if (action === "start") {
		if (await loadRecordingState(serial)) throw cliError("device.recording.active", "A recording is already active for this device. Stop it before starting another.");
		const remote = `/sdcard/mobile-use-recording-${Date.now()}.mp4`;
		const { adb: adbPath } = await sdk();
		const { pid } = await runToolBackgroundPid(adbPath, [
			"-s",
			serial,
			"shell",
			`nohup screenrecord ${remote} >/dev/null 2>&1 & echo $!`
		], { timeoutMs: 15e3 });
		const startedAt = (/* @__PURE__ */ new Date()).toISOString();
		await saveRecordingState(serial, {
			remote,
			pid,
			startedAt
		});
		await sleep(500);
		return Object.freeze({
			operationId: operationId$2("record-start"),
			operation: "device.recording.start",
			status: "succeeded",
			output: Object.freeze({
				active: true,
				startedAt
			})
		});
	}
	if (action === "status") {
		const record = await loadRecordingState(serial);
		return Object.freeze({
			operationId: operationId$2("record-status"),
			operation: "device.recording.status",
			status: "succeeded",
			output: Object.freeze({
				active: Boolean(record),
				...record ? { startedAt: record.startedAt } : {}
			})
		});
	}
	if (action === "stop") {
		const record = await loadRecordingState(serial);
		if (!record) throw cliError("device.recording.inactive", "No active recording for this device.");
		if (Number.isInteger(record.pid)) await adbShell(serial, `kill -INT ${record.pid}`).catch(() => adbShell(serial, `kill ${record.pid}`)).catch(() => {});
		else await adbShell(serial, "pkill -INT screenrecord").catch(() => adbShell(serial, "killall -INT screenrecord")).catch(() => {});
		await sleep(1500);
		const { adb: adbPath } = await sdk();
		const { stdout } = await runToolRaw(adbPath, [
			"-s",
			serial,
			"exec-out",
			"cat",
			record.remote
		], { timeoutMs: 6e4 });
		const buffer = Buffer.from(stdout);
		if (buffer.length === 0) throw cliError("device.recording.empty", "Recording file was empty after stop. screenrecord may not have started.");
		const artifact = await writeArtifact(serial, buffer, "mp4", "video/mp4", "recording");
		await clearRecordingState(serial);
		await adbShell(serial, `rm -f ${record.remote}`).catch(() => {});
		return Object.freeze({
			operationId: operationId$2("record-stop"),
			operation: "device.recording.stop",
			status: "succeeded",
			completedAt: (/* @__PURE__ */ new Date()).toISOString(),
			output: Object.freeze({
				active: false,
				startedAt: record.startedAt,
				artifact
			})
		});
	}
	throw new TypeError(`Unsupported record_screen action: ${action}`);
}
async function writeArtifact(serial, buffer, extension, mediaType, kind) {
	const directory = path.join(defaultArtifactDirectory(), serial.replace(/[^\w.-]/g, "_"));
	await mkdir(directory, { recursive: true });
	const digest = createHash("sha256").update(buffer).digest("hex");
	const fileName = `${kind}-${Date.now()}.${extension}`;
	const filePath = path.join(directory, fileName);
	await writeFile(filePath, buffer);
	return Object.freeze({
		artifactId: digest.slice(0, 16),
		createdAt: (/* @__PURE__ */ new Date()).toISOString(),
		mediaType,
		size: buffer.length,
		algorithm: "sha256",
		digest,
		uri: pathToFileURL(filePath).href,
		source: kind,
		platform: "android",
		targetId: serial
	});
}
function operationId$2(prefix) {
	return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
function sleep(ms) {
	return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}
//#endregion
//#region src/lib/ios-backend.ts
var ios_backend_exports = /* @__PURE__ */ __exportAll({
	invokePhoneUse: () => invokePhoneUse$2,
	invokeSessionOperation: () => invokeSessionOperation$2,
	invokeTargetOperation: () => invokeTargetOperation$2,
	listLiveSessions: () => listLiveSessions$2,
	listLiveTargets: () => listLiveTargets$2,
	startPhoneUseSession: () => startPhoneUseSession$2,
	stopPhoneUseSession: () => stopPhoneUseSession$2
});
const SURFACE_ID$1 = "simctl-ios";
async function requireDarwin() {
	if (hostPlatform() !== "darwin") throw cliError("device.platform.unsupported", "iOS Simulator control requires macOS with xcrun. This host is not supported.");
	const xcrun = await findXcrun();
	if (!xcrun) throw cliError("device.toolchain.missing", "xcrun not found. Install Xcode and its command-line tools.");
	return xcrun;
}
async function simctl(args, options = {}) {
	return runTool(await requireDarwin(), ["simctl", ...args], {
		errorCode: "device.simctl.failed",
		...options
	});
}
async function listLiveTargets$2() {
	const { stdout } = await simctl([
		"list",
		"devices",
		"-j",
		"available"
	]);
	const parsed = JSON.parse(stdout);
	const targets = [];
	for (const [runtime, devices] of Object.entries(parsed.devices ?? {})) for (const device of devices) targets.push(Object.freeze({
		surfaceId: SURFACE_ID$1,
		adapterId: "ios-simctl",
		targetId: device.udid,
		platform: "ios",
		targetName: device.name,
		runtimeKind: "simulator",
		state: device.state === "Booted" ? "online" : "shutdown",
		targetCapabilities: Object.freeze([
			"device.frame.screenshot",
			"device.app.launch",
			"device.app.terminate",
			"device.app.uninstall"
		]),
		runtime
	}));
	return targets;
}
async function listLiveSessions$2() {
	return (await listLiveTargets$2()).filter((target) => target.state === "online").map((target) => Object.freeze({
		surfaceId: SURFACE_ID$1,
		sessionId: target.targetId,
		targetId: target.targetId,
		platform: "ios",
		targetName: target.targetName,
		runtimeKind: "simulator",
		state: "attached",
		capabilities: Object.freeze([
			{ id: "device.frame.screenshot" },
			{ id: "device.app.launch" },
			{ id: "device.app.terminate" },
			{ id: "device.app.uninstall" }
		])
	}));
}
async function startPhoneUseSession$2(surfaceId, targetId) {
	await simctl(["boot", targetId]).catch(() => {});
	const session = (await listLiveSessions$2()).find((candidate) => candidate.sessionId === targetId);
	if (!session) throw cliError("device.target.not-found", `iOS Simulator ${targetId} did not boot.`);
	return session;
}
async function stopPhoneUseSession$2(surfaceId, sessionId) {
	await simctl(["shutdown", sessionId]).catch(() => {});
	return Object.freeze({ stopped: true });
}
async function invokePhoneUse$2(surfaceId, sessionId, method, input) {
	if (method === "observe") return wdaObserve(sessionId);
	if (method === "perform") return wdaPerform(sessionId, input);
	if (method === "act") return wdaAct(sessionId, input);
	if (method === "wait") return wdaWait(sessionId, input);
	if (method === "assert") return wdaAssert(sessionId, input);
	throw cliError("device.capability.unsupported", `iOS does not support method: ${method}.`);
}
function wdaBaseUrl() {
	return (process.env.MOBILE_USE_WDA_URL?.trim() || "http://localhost:8100").replace(/\/$/, "");
}
async function wdaRequest(sessionId, method, pathSuffix, body) {
	const url = `${wdaBaseUrl()}${pathSuffix}`;
	let response;
	try {
		response = await fetch(url, {
			method,
			headers: body === void 0 ? {} : { "content-type": "application/json" },
			...body === void 0 ? {} : { body: JSON.stringify(body) },
			signal: AbortSignal.timeout(15e3)
		});
	} catch (error) {
		throw cliError("device.driver.unavailable", `WebDriverAgent is not reachable at ${wdaBaseUrl()}. Start WebDriverAgent on the Simulator (or set MOBILE_USE_WDA_URL), then retry. (${error instanceof Error ? error.message : String(error)})`);
	}
	const payload = await response.json().catch(() => ({}));
	if (!response.ok) {
		const message = typeof payload?.value === "object" && payload.value !== null && "message" in payload.value ? String(payload.value.message) : `HTTP ${response.status}`;
		throw cliError("device.driver.failed", `WebDriverAgent ${method} ${pathSuffix} failed: ${message}`);
	}
	return payload;
}
let wdaSessionId;
async function wdaSession() {
	if (wdaSessionId) return wdaSessionId;
	const value = (await wdaRequest("", "POST", "/session", { capabilities: { alwaysMatch: { platformName: "iOS" } } })).value;
	if (!value?.sessionId) throw cliError("device.driver.failed", "WebDriverAgent did not return a sessionId.");
	wdaSessionId = value.sessionId;
	return wdaSessionId;
}
function flattenWdaSource(node, ordinal) {
	const elements = [];
	if (!node || typeof node !== "object") return elements;
	const ref = `e${ordinal.value}`;
	ordinal.value += 1;
	const rect = node.rect ?? {};
	const center = Number.isFinite(rect.x) && Number.isFinite(rect.width) ? {
		x: Math.round(rect.x + (rect.width || 0) / 2),
		y: Math.round(rect.y + (rect.height || 0) / 2)
	} : void 0;
	const label = node.label ?? node.value ?? node.name;
	const identifier = node.name !== label ? node.name : void 0;
	elements.push(Object.freeze({
		ref,
		identifier,
		label,
		role: node.type,
		type: node.type,
		center
	}));
	for (const child of node.children ?? []) elements.push(...flattenWdaSource(child, ordinal));
	return elements;
}
async function wdaObserve(sessionId) {
	const value = (await wdaRequest(sessionId, "GET", `/session/${await wdaSession()}/source`)).value;
	const elements = value ? flattenWdaSource(value, { value: 0 }) : [];
	return Object.freeze({
		uiRevision: Date.now(),
		snapshotId: `snap-${Date.now()}`,
		platform: "ios",
		source: "webdriveragent",
		elementCount: elements.length,
		truncated: false,
		elements: Object.freeze(elements)
	});
}
function matchesWdaSelector(element, selector) {
	if (typeof selector.identifier === "string") {
		if (!(element.identifier === selector.identifier || element.identifier?.endsWith(`/${selector.identifier}`))) return false;
	}
	if (typeof selector.label === "string") {
		const needle = selector.label.toLowerCase();
		if (!element.label?.toLowerCase().includes(needle)) return false;
	}
	if (typeof selector.role === "string") {
		if (!element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
	}
	if (typeof selector.type === "string") {
		if (!element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
	}
	return true;
}
async function wdaFindElement(sessionId, selector) {
	const matches = (await wdaObserve(sessionId)).elements.filter((el) => matchesWdaSelector(el, selector) && el.center);
	if (matches.length === 0) throw cliError("phone.selector.not-found", "No iOS element matched the selector.");
	if (matches.length > 1) throw cliError("phone.selector.ambiguous", `Selector matched ${matches.length} elements.`);
	return matches[0];
}
async function wdaTap(sessionId, point) {
	await wdaRequest(sessionId, "POST", `/session/${await wdaSession()}/actions`, { actions: [{
		type: "pointer",
		id: "finger1",
		parameters: { pointerType: "touch" },
		actions: [
			{
				type: "pointerMove",
				duration: 0,
				x: point.x,
				y: point.y
			},
			{
				type: "pointerDown",
				button: 0
			},
			{
				type: "pause",
				duration: 50
			},
			{
				type: "pointerUp",
				button: 0
			}
		]
	}] });
}
async function wdaPerform(sessionId, input = {}) {
	const action = input?.action ?? {};
	const element = await wdaFindElement(sessionId, action.selector ?? {});
	if (action.kind === "long-press") await wdaRequest(sessionId, "POST", `/session/${await wdaSession()}/actions`, { actions: [{
		type: "pointer",
		id: "finger1",
		parameters: { pointerType: "touch" },
		actions: [
			{
				type: "pointerMove",
				duration: 0,
				x: element.center?.x ?? 0,
				y: element.center?.y ?? 0
			},
			{
				type: "pointerDown",
				button: 0
			},
			{
				type: "pause",
				duration: action.durationMs ?? 1e3
			},
			{
				type: "pointerUp",
				button: 0
			}
		]
	}] });
	else await wdaTap(sessionId, element.center);
	const observation = await wdaObserve(sessionId);
	return Object.freeze({
		uiChanged: true,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation,
		receipt: Object.freeze({
			operationId: operationId$1("tap"),
			operation: "wda.actions.tap",
			status: "succeeded"
		})
	});
}
async function wdaAct(sessionId, input = {}) {
	const action = input?.action ?? {};
	const kind = action.kind;
	if (kind === "tap" || kind === "long-press") return wdaPerform(sessionId, input);
	if (kind === "swipe") {
		const sid = await wdaSession();
		const from = action.from ?? {
			x: 0,
			y: 0
		};
		const to = action.to ?? {
			x: 0,
			y: 0
		};
		const durationMs = Number.isInteger(action.durationMs) ? action.durationMs : 300;
		await wdaRequest(sessionId, "POST", `/session/${sid}/actions`, { actions: [{
			type: "pointer",
			id: "finger1",
			parameters: { pointerType: "touch" },
			actions: [
				{
					type: "pointerMove",
					duration: 0,
					x: from.x,
					y: from.y
				},
				{
					type: "pointerDown",
					button: 0
				},
				{
					type: "pointerMove",
					duration: durationMs,
					x: to.x,
					y: to.y
				},
				{
					type: "pointerUp",
					button: 0
				}
			]
		}] });
		return Object.freeze({
			uiChanged: true,
			observation: await wdaObserve(sessionId)
		});
	}
	if (kind === "text") {
		const element = await wdaFindElement(sessionId, action.selector ?? {});
		const text = String(action.text ?? "");
		if (!text) throw cliError("phone.cli.argument", "text must be non-empty.");
		await wdaRequest(sessionId, "POST", `/session/${await wdaSession()}/actions`, { actions: [{
			type: "key",
			id: "keyboard",
			actions: [{
				type: "keyDown",
				value: text
			}, {
				type: "keyUp",
				value: text
			}]
		}] }).catch(async () => {
			await wdaTap(sessionId, element.center);
		});
		return Object.freeze({
			uiChanged: true,
			observation: await wdaObserve(sessionId)
		});
	}
	throw cliError("device.capability.unsupported", `iOS does not support act kind: ${kind}.`);
}
async function wdaWait(sessionId, input = {}) {
	const condition = input?.condition ?? {};
	const timeoutMs = input?.timeoutMs ?? 1e4;
	const pollIntervalMs = input?.pollIntervalMs ?? 500;
	const deadline = Date.now() + timeoutMs;
	let lastObservation;
	while (Date.now() < deadline) {
		lastObservation = await wdaObserve(sessionId);
		if (condition.kind === "stable") return lastObservation;
		const found = lastObservation.elements.some((el) => matchesWdaSelector(el, condition.selector ?? {}));
		if (condition.kind === "present" && found) return lastObservation;
		if (condition.kind === "absent" && !found) return lastObservation;
		await iosSleep(pollIntervalMs);
	}
	throw cliError("phone.wait.timeout", `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`);
}
async function wdaAssert(sessionId, input = {}) {
	const observation = await wdaObserve(sessionId);
	const selector = input?.selector ?? {};
	const matches = observation.elements.filter((el) => matchesWdaSelector(el, selector));
	const element = matches[0];
	if (matches.length === 0) {
		if (input?.state === "absent") return Object.freeze({
			passed: true,
			observation
		});
		return Object.freeze({
			passed: false,
			observation,
			reason: "phone.selector.not-found"
		});
	}
	if (matches.length > 1) return Object.freeze({
		passed: false,
		observation,
		reason: "phone.selector.ambiguous"
	});
	const passed = input?.state === "absent" ? false : true;
	return Object.freeze({
		passed,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation
	});
}
function iosSleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}
async function invokeSessionOperation$2(surfaceId, sessionId, operation, capability, input = {}) {
	switch (operation) {
		case "device.capture.screenshot": return captureScreenshot$1(sessionId);
		case "device.app.launch":
			await simctl([
				"launch",
				sessionId,
				input?.bundleId ?? ""
			]);
			return Object.freeze({
				operationId: operationId$1("launch"),
				operation,
				status: "succeeded",
				output: Object.freeze({ launched: true })
			});
		case "device.app.terminate":
			await simctl([
				"terminate",
				sessionId,
				input?.bundleId ?? ""
			]);
			return Object.freeze({
				operationId: operationId$1("terminate"),
				operation,
				status: "succeeded",
				output: Object.freeze({ terminated: true })
			});
		case "device.app.uninstall":
			if (input?.confirm !== true) throw new TypeError("manage_app uninstall requires confirm=true.");
			await simctl([
				"uninstall",
				sessionId,
				input?.bundleId ?? ""
			]);
			return Object.freeze({
				operationId: operationId$1("uninstall"),
				operation,
				status: "succeeded",
				output: Object.freeze({ uninstalled: true })
			});
		default: throw cliError("device.capability.unsupported", `iOS operation not supported by this backend: ${operation}`);
	}
}
async function invokeTargetOperation$2() {
	throw cliError("device.capability.unsupported", "iOS target operations are not supported by this backend.");
}
async function captureScreenshot$1(udid) {
	const directory = path.join(defaultArtifactDirectory(), udid.replace(/[^\w.-]/g, "_"));
	await mkdir(directory, { recursive: true });
	const filePath = path.join(directory, `screenshot-${Date.now()}.png`);
	await simctl([
		"io",
		udid,
		"screenshot",
		filePath
	], { timeoutMs: 3e4 });
	const buffer = await import("node:fs/promises").then(({ readFile }) => readFile(filePath));
	const digest = createHash("sha256").update(buffer).digest("hex");
	return Object.freeze({
		operationId: operationId$1("screenshot"),
		operation: "device.capture.screenshot",
		status: "succeeded",
		completedAt: (/* @__PURE__ */ new Date()).toISOString(),
		output: Object.freeze({ artifact: Object.freeze({
			artifactId: digest.slice(0, 16),
			createdAt: (/* @__PURE__ */ new Date()).toISOString(),
			mediaType: "image/png",
			size: buffer.length,
			algorithm: "sha256",
			digest,
			uri: pathToFileURL(filePath).href,
			source: "screenshot",
			platform: "ios",
			targetId: udid
		}) })
	});
}
function operationId$1(prefix) {
	return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
//#endregion
//#region src/lib/harmony-backend.ts
var harmony_backend_exports = /* @__PURE__ */ __exportAll({
	invokePhoneUse: () => invokePhoneUse$1,
	invokeSessionOperation: () => invokeSessionOperation$1,
	invokeTargetOperation: () => invokeTargetOperation$1,
	listLiveSessions: () => listLiveSessions$1,
	listLiveTargets: () => listLiveTargets$1,
	startPhoneUseSession: () => startPhoneUseSession$1,
	stopPhoneUseSession: () => stopPhoneUseSession$1
});
const SURFACE_ID = "hdc-harmony";
let hdcPromise;
async function hdc(args, options = {}) {
	if (!hdcPromise) hdcPromise = findHdc();
	const binary = await hdcPromise;
	if (!binary) throw cliError("device.toolchain.missing", "OpenHarmony hdc not found. Set DEVECO_SDK_HOME or install DevEco Studio. Run `doctor` for guidance.");
	return runTool(binary, args, {
		errorCode: "device.hdc.failed",
		...options
	});
}
async function hdcOnDevice(connectKey, args, options = {}) {
	return hdc([
		"-t",
		connectKey,
		...args
	], options);
}
async function listLiveTargets$1() {
	const { stdout } = await hdc(["list", "targets"]);
	const targets = [];
	for (const line of stdout.split("\n")) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith("[") || trimmed.toLowerCase().includes("empty")) continue;
		targets.push(Object.freeze({
			surfaceId: SURFACE_ID,
			adapterId: "harmony-hdc",
			targetId: trimmed,
			platform: "harmony",
			targetName: trimmed,
			runtimeKind: "remote",
			state: "online",
			targetCapabilities: Object.freeze([
				"device.frame.screenshot",
				"device.app.launch",
				"device.app.terminate"
			])
		}));
	}
	return targets;
}
async function listLiveSessions$1() {
	return (await listLiveTargets$1()).map((target) => Object.freeze({
		surfaceId: SURFACE_ID,
		sessionId: target.targetId,
		targetId: target.targetId,
		platform: "harmony",
		targetName: target.targetName,
		runtimeKind: "remote",
		state: "attached",
		capabilities: Object.freeze([
			{ id: "device.frame.screenshot" },
			{ id: "device.app.launch" },
			{ id: "device.app.terminate" }
		])
	}));
}
async function startPhoneUseSession$1(surfaceId, targetId) {
	const session = (await listLiveSessions$1()).find((candidate) => candidate.sessionId === targetId);
	if (!session) throw cliError("device.target.not-found", `HarmonyOS device ${targetId} is not connected. Run list-targets again.`);
	return session;
}
async function stopPhoneUseSession$1() {
	return Object.freeze({
		stopped: false,
		note: "HDC targets are not stopped by this skill."
	});
}
async function invokePhoneUse$1(surfaceId, sessionId, method, input) {
	if (method === "observe") return observe(sessionId);
	if (method === "perform") return perform(sessionId, input);
	if (method === "act") return act(sessionId, input);
	if (method === "wait") return waitFor(sessionId, input);
	if (method === "assert") return assert(sessionId, input);
	throw cliError("device.capability.unsupported", `HarmonyOS does not support method: ${method}.`);
}
async function dumpUiTree(connectKey) {
	const remote = "/data/local/tmp/uitest-dump.json";
	await hdcOnDevice(connectKey, [
		"shell",
		"uitest",
		"dumpLayout",
		"-p",
		remote
	]).catch(() => {});
	const { stdout } = await hdcOnDevice(connectKey, [
		"shell",
		"cat",
		remote
	], { timeoutMs: 3e4 }).catch(() => ({
		stdout: "",
		stderr: ""
	}));
	try {
		return flattenUitest(JSON.parse(stdout));
	} catch {
		return [];
	}
}
async function observe(connectKey) {
	const elements = await dumpUiTree(connectKey);
	return Object.freeze({
		uiRevision: Date.now(),
		snapshotId: `snap-${Date.now()}`,
		platform: "harmony",
		source: "uitest",
		elementCount: elements.length,
		truncated: false,
		elements: Object.freeze(elements)
	});
}
function resolveHarmonyElement(elements, selector) {
	const matches = elements.filter((element) => matchesHarmonySelector(element, selector));
	if (matches.length === 0) throw cliError("phone.selector.not-found", "No HarmonyOS element matched the selector.");
	const withCenter = matches.filter((element) => element.center);
	const pool = withCenter.length > 0 ? withCenter : matches;
	if (pool.length > 1) throw cliError("phone.selector.ambiguous", `Selector matched ${pool.length} elements.`);
	const element = pool[0];
	if (!element.center) throw cliError("device.observe.failed", "Matched element has no bounds to tap.");
	return element;
}
function matchesHarmonySelector(element, selector) {
	if (typeof selector.identifier === "string") {
		if (!(element.identifier === selector.identifier || element.identifier?.endsWith(`/${selector.identifier}`))) return false;
	}
	if (typeof selector.label === "string") {
		const needle = selector.label.toLowerCase();
		if (!element.label?.toLowerCase().includes(needle)) return false;
	}
	if (typeof selector.role === "string") {
		if (!element.role?.toLowerCase().includes(selector.role.toLowerCase())) return false;
	}
	if (typeof selector.type === "string") {
		if (!element.type?.toLowerCase().includes(selector.type.toLowerCase())) return false;
	}
	return true;
}
async function perform(connectKey, input = {}) {
	const action = input?.action ?? {};
	const element = resolveHarmonyElement(await dumpUiTree(connectKey), action.selector ?? {});
	const { x, y } = element.center;
	if (action.kind === "long-press") await hdcOnDevice(connectKey, [
		"shell",
		"uitest",
		"uiInput",
		"longClick",
		String(x),
		String(y)
	]);
	else await hdcOnDevice(connectKey, [
		"shell",
		"uitest",
		"uiInput",
		"click",
		String(x),
		String(y)
	]);
	const observation = await observe(connectKey);
	return Object.freeze({
		uiChanged: true,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation,
		receipt: Object.freeze({
			operationId: operationId("tap"),
			operation: "uitest.uiInput.click",
			status: "succeeded"
		})
	});
}
async function act(connectKey, input = {}) {
	const action = input?.action ?? {};
	const kind = action.kind;
	if (kind === "tap" || kind === "long-press") return perform(connectKey, input);
	if (kind === "swipe") {
		const from = action.from ?? {
			x: 0,
			y: 0
		};
		const to = action.to ?? {
			x: 0,
			y: 0
		};
		const velocity = Math.max(200, Math.min(4e4, Math.round((action.durationMs ?? 300) / 300 * 600)));
		await hdcOnDevice(connectKey, [
			"shell",
			"uitest",
			"uiInput",
			"swipe",
			String(requireHarmonyInt(from.x, "from.x")),
			String(requireHarmonyInt(from.y, "from.y")),
			String(requireHarmonyInt(to.x, "to.x")),
			String(requireHarmonyInt(to.y, "to.y")),
			String(velocity)
		]);
		return Object.freeze({
			uiChanged: true,
			observation: await observe(connectKey)
		});
	}
	if (kind === "text") {
		const { x, y } = resolveHarmonyElement(await dumpUiTree(connectKey), action.selector ?? {}).center;
		const text = String(action.text ?? "");
		if (!text) throw cliError("phone.cli.argument", "text must be non-empty.");
		await hdcOnDevice(connectKey, [
			"shell",
			"uitest",
			"uiInput",
			"inputText",
			String(x),
			String(y),
			text
		]);
		return Object.freeze({
			uiChanged: true,
			observation: await observe(connectKey)
		});
	}
	if (kind === "key") {
		const key = String(action.key ?? "");
		if (!/^[A-Za-z0-9_]+$/.test(key)) throw cliError("phone.cli.argument", `key must be a key name (e.g. Home, Back), got ${JSON.stringify(action.key)}.`);
		await hdcOnDevice(connectKey, [
			"shell",
			"uitest",
			"uiInput",
			"keyEvent",
			key
		]);
		return Object.freeze({
			uiChanged: true,
			observation: await observe(connectKey)
		});
	}
	throw cliError("device.capability.unsupported", `HarmonyOS does not support act kind: ${kind}.`);
}
function requireHarmonyInt(value, name) {
	if (!Number.isInteger(value)) throw cliError("phone.cli.argument", `${name} must be an integer, got ${JSON.stringify(value)}.`);
	return value;
}
async function waitFor(connectKey, input = {}) {
	const condition = input?.condition ?? {};
	const timeoutMs = input?.timeoutMs ?? 1e4;
	const pollIntervalMs = input?.pollIntervalMs ?? 500;
	const deadline = Date.now() + timeoutMs;
	let lastObservation;
	while (Date.now() < deadline) {
		lastObservation = await observe(connectKey);
		if (condition.kind === "stable") return lastObservation;
		const found = lastObservation.elements.some((el) => matchesHarmonySelector(el, condition.selector ?? {}));
		if (condition.kind === "present" && found) return lastObservation;
		if (condition.kind === "absent" && !found) return lastObservation;
		await harmonySleep(pollIntervalMs);
	}
	throw cliError("phone.wait.timeout", `wait condition ${condition.kind} timed out after ${timeoutMs} ms.`);
}
async function assert(connectKey, input = {}) {
	const observation = await observe(connectKey);
	const elements = observation.elements;
	const selector = input?.selector ?? {};
	let element;
	try {
		element = resolveHarmonyElement(elements, selector);
	} catch (error) {
		const code = error.code;
		if (input?.state === "absent" && code === "phone.selector.not-found") return Object.freeze({
			passed: true,
			observation
		});
		if (code === "device.observe.failed") return Object.freeze({
			passed: false,
			observation,
			reason: "phone.selector.not-found"
		});
		if (code?.startsWith("phone.selector")) return Object.freeze({
			passed: false,
			observation,
			reason: code
		});
		throw error;
	}
	const passed = input?.state === "absent" ? false : true;
	return Object.freeze({
		passed,
		element: Object.freeze({
			ref: element.ref,
			identifier: element.identifier,
			label: element.label,
			role: element.role,
			type: element.type
		}),
		observation
	});
}
function harmonySleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}
function parseHarmonyBounds(bounds) {
	if (!bounds) return void 0;
	const found = /\[(\d+),(\d+)\]\[(\d+),(\d+)\]/.exec(bounds);
	if (!found) return void 0;
	const [, left, top, right, bottom] = found.map(Number);
	return {
		x: Math.round((left + right) / 2),
		y: Math.round((top + bottom) / 2)
	};
}
function flattenUitest(node, ordinal = { value: 0 }) {
	const elements = [];
	if (node && typeof node === "object") {
		const candidate = node;
		const ref = `e${ordinal.value}`;
		ordinal.value += 1;
		const bounds = candidate.attributes?.bounds ?? candidate.bounds;
		elements.push(Object.freeze({
			ref,
			identifier: candidate.attributes?.id ?? candidate.id,
			label: candidate.attributes?.text ?? candidate.text,
			role: candidate.attributes?.type ?? candidate.type,
			type: candidate.attributes?.type ?? candidate.type,
			center: parseHarmonyBounds(bounds)
		}));
		const children = candidate.children ?? candidate.child ?? [];
		for (const child of Array.isArray(children) ? children : []) elements.push(...flattenUitest(child, ordinal));
	}
	return elements;
}
async function invokeSessionOperation$1(surfaceId, sessionId, operation, _capability, input = {}) {
	if (operation === "device.capture.screenshot") return captureScreenshot(sessionId);
	if (operation === "device.app.launch") {
		const bundleId = requireHarmonyPackage(input?.bundleId, "bundle_id");
		await hdcOnDevice(sessionId, [
			"shell",
			"aa",
			"start",
			"-b",
			bundleId,
			"-a",
			"EntryAbility"
		]);
		return Object.freeze({
			operationId: operationId("app-launch"),
			operation: "device.app.launch",
			status: "succeeded",
			output: Object.freeze({
				launched: true,
				bundleId
			})
		});
	}
	if (operation === "device.app.terminate") {
		const bundleId = requireHarmonyPackage(input?.bundleId, "bundle_id");
		await hdcOnDevice(sessionId, [
			"shell",
			"aa",
			"force-stop",
			bundleId
		]);
		return Object.freeze({
			operationId: operationId("app-terminate"),
			operation: "device.app.terminate",
			status: "succeeded",
			output: Object.freeze({
				terminated: true,
				bundleId
			})
		});
	}
	throw cliError("device.capability.unsupported", `HarmonyOS operation not supported by this backend: ${operation}`);
}
function requireHarmonyPackage(value, name) {
	if (typeof value !== "string" || !/^[A-Za-z0-9._]+$/.test(value)) throw cliError("phone.cli.argument", `${name} contains unsafe characters: ${JSON.stringify(value)}.`);
	return value;
}
async function invokeTargetOperation$1() {
	throw cliError("device.capability.unsupported", "HarmonyOS target operations are not supported by this backend.");
}
async function captureScreenshot(connectKey) {
	const remote = `/data/local/tmp/mobile-use-shot-${Date.now()}.png`;
	await hdcOnDevice(connectKey, [
		"shell",
		"snapshot_display",
		"-f",
		remote
	], { timeoutMs: 3e4 });
	const directory = path.join(defaultArtifactDirectory(), connectKey.replace(/[^\w.-]/g, "_"));
	await mkdir(directory, { recursive: true });
	const filePath = path.join(directory, `screenshot-${Date.now()}.png`);
	await hdc([
		"file",
		"recv",
		remote,
		filePath
	], { timeoutMs: 6e4 });
	const { readFile } = await import("node:fs/promises");
	const buffer = await readFile(filePath);
	const digest = createHash("sha256").update(buffer).digest("hex");
	return Object.freeze({
		operationId: operationId("screenshot"),
		operation: "device.capture.screenshot",
		status: "succeeded",
		completedAt: (/* @__PURE__ */ new Date()).toISOString(),
		output: Object.freeze({ artifact: Object.freeze({
			artifactId: digest.slice(0, 16),
			createdAt: (/* @__PURE__ */ new Date()).toISOString(),
			mediaType: "image/png",
			size: buffer.length,
			algorithm: "sha256",
			digest,
			uri: pathToFileURL(filePath).href,
			source: "screenshot",
			platform: "harmony",
			targetId: connectKey
		}) })
	});
}
function operationId(prefix) {
	return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
//#endregion
//#region src/lib/device-backends.ts
const backends = Object.freeze([
	Object.freeze({
		platform: "android",
		impl: android_backend_exports
	}),
	Object.freeze({
		platform: "harmony",
		impl: harmony_backend_exports
	}),
	Object.freeze({
		platform: "ios",
		impl: ios_backend_exports
	})
]);
async function collect(fnName) {
	return (await Promise.all(backends.map(async ({ platform: _platform, impl }) => {
		try {
			const values = await impl[fnName]();
			return Array.isArray(values) ? values : [];
		} catch {
			return [];
		}
	}))).flat();
}
async function listLiveTargets() {
	return collect("listLiveTargets");
}
async function listLiveSessions() {
	return collect("listLiveSessions");
}
function backendForSurface(surfaceId) {
	if (surfaceId === "adb-android") return android_backend_exports;
	if (surfaceId === "simctl-ios") return ios_backend_exports;
	if (surfaceId === "hdc-harmony") return harmony_backend_exports;
	throw cliError("device.surface.stale", `Unknown surface ${surfaceId}. Run list-targets to discover live surfaces.`);
}
async function startPhoneUseSession(surfaceId, targetId) {
	return backendForSurface(surfaceId).startPhoneUseSession(surfaceId, targetId);
}
async function stopPhoneUseSession(surfaceId, sessionId) {
	return backendForSurface(surfaceId).stopPhoneUseSession(surfaceId, sessionId);
}
async function invokePhoneUse(surfaceId, sessionId, method, input) {
	return backendForSurface(surfaceId).invokePhoneUse(surfaceId, sessionId, method, input);
}
async function invokeSessionOperation(surfaceId, sessionId, operation, capability, input) {
	return backendForSurface(surfaceId).invokeSessionOperation(surfaceId, sessionId, operation, capability, input);
}
async function invokeTargetOperation(surfaceId, targetId, operation, capability, input) {
	return backendForSurface(surfaceId).invokeTargetOperation(surfaceId, targetId, operation, capability, input);
}
//#endregion
//#region src/lib/phone-arguments.ts
const SESSION_PROPERTIES = Object.freeze(["surface_id", "session_id"]);
const TARGET_OPERATION_COMMANDS = Object.freeze({ restart_target: Object.freeze({
	operation: "device.target.restart",
	capability: "device.target.restart"
}) });
const SESSION_OPERATION_COMMANDS = Object.freeze({
	manage_app: Object.freeze({ group: "app" }),
	read_logs: Object.freeze({
		operation: "device.logs.read",
		capability: "device.logs.read"
	}),
	run_native_test: Object.freeze({
		operation: "device.test.run",
		capability: "device.test.run"
	}),
	capture_screenshot: Object.freeze({
		operation: "device.capture.screenshot",
		capability: "device.frame.screenshot"
	}),
	record_screen: Object.freeze({ group: "recording" })
});
function targetAndInput(command, params) {
	const { surfaceId, sessionId } = sessionSelection(params);
	if (command === "observe") return {
		surfaceId,
		sessionId,
		input: { mode: params.mode === "full" ? "full" : "interactive" }
	};
	if (command === "act") {
		if (!Number.isInteger(params.ui_revision) || params.ui_revision < 1) throw new TypeError("ui_revision must be a positive integer from observe.");
		return {
			surfaceId,
			sessionId,
			input: {
				uiRevision: params.ui_revision,
				action: requiredRecord(params.action, "action")
			}
		};
	}
	if (command === "tap" || command === "long_press") return {
		surfaceId,
		sessionId,
		input: { action: {
			kind: command === "tap" ? "tap" : "long-press",
			selector: requiredRecord(params.selector, "selector"),
			...command === "long_press" && params.duration_ms !== void 0 ? { durationMs: boundedInteger$1(params.duration_ms, "duration_ms", 1, 6e4) } : {}
		} }
	};
	if (command === "wait") return {
		surfaceId,
		sessionId,
		input: {
			condition: requiredRecord(params.condition, "condition"),
			...typeof params.timeout_ms === "number" ? { timeoutMs: params.timeout_ms } : {},
			...typeof params.poll_interval_ms === "number" ? { pollIntervalMs: params.poll_interval_ms } : {}
		}
	};
	if (command === "assert") return {
		surfaceId,
		sessionId,
		input: {
			selector: requiredRecord(params.selector, "selector"),
			state: params.state === "absent" ? "absent" : "present"
		}
	};
	throw commandError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
}
function targetSelection(params) {
	return {
		surfaceId: requiredString$1(params.surface_id, "surface_id"),
		targetId: requiredString$1(params.target_id, "target_id")
	};
}
function operationAndInput(command, params) {
	const targetDefinition = TARGET_OPERATION_COMMANDS[command];
	if (targetDefinition) return {
		...targetSelection(params),
		...targetDefinition,
		input: {}
	};
	const selection = sessionSelection(params);
	if (command === "manage_app") {
		if (params.action === "list") return {
			...selection,
			operation: "device.app.list",
			capability: "device.app.list",
			input: {}
		};
		if (params.action === "install") return {
			...selection,
			operation: "device.app.install",
			capability: "device.app.install",
			input: { path: requiredString$1(params.path, "path") }
		};
		if (params.action === "launch") return {
			...selection,
			operation: "device.app.launch",
			capability: "device.app.launch",
			input: { bundleId: requiredString$1(params.bundle_id, "bundle_id") }
		};
		if (params.action === "terminate") return {
			...selection,
			operation: "device.app.terminate",
			capability: "device.app.terminate",
			input: { bundleId: requiredString$1(params.bundle_id, "bundle_id") }
		};
		if (params.action === "uninstall") return {
			...selection,
			operation: "device.app.uninstall",
			capability: "device.app.uninstall",
			input: {
				bundleId: requiredString$1(params.bundle_id, "bundle_id"),
				confirm: requireConfirmation(params.confirm)
			}
		};
		throw new TypeError("manage_app action must be list, install, launch, terminate, or uninstall.");
	}
	if (command === "record_screen") {
		const operation = {
			start: "device.recording.start",
			status: "device.recording.status",
			stop: "device.recording.stop"
		}[params.action];
		if (!operation) throw new TypeError("record_screen action must be start, status, or stop.");
		return {
			...selection,
			operation,
			capability: "device.recording.native",
			input: {}
		};
	}
	const sessionDefinition = SESSION_OPERATION_COMMANDS[command];
	if (!sessionDefinition?.operation) throw commandError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
	let input = {};
	if (command === "read_logs") input = {
		...params.bundle_id === void 0 ? {} : { bundleId: requiredString$1(params.bundle_id, "bundle_id") },
		...params.seconds === void 0 ? {} : { seconds: boundedInteger$1(params.seconds, "seconds", 1, 3600) },
		...params.limit === void 0 ? {} : { limit: boundedInteger$1(params.limit, "limit", 1, 5e3) }
	};
	else if (command === "run_native_test") input = {
		selector: requiredString$1(params.selector, "selector"),
		...params.timeout_ms === void 0 ? {} : { timeoutMs: boundedInteger$1(params.timeout_ms, "timeout_ms", 1e3, 12e5) },
		...params.test_target === void 0 ? {} : { testTarget: requiredString$1(params.test_target, "test_target") },
		...params.test_module === void 0 ? {} : { testModule: requiredString$1(params.test_module, "test_module") },
		...params.test_bundle_id === void 0 ? {} : { testBundleId: requiredString$1(params.test_bundle_id, "test_bundle_id") },
		...params.test_package === void 0 ? {} : { testPackage: requiredString$1(params.test_package, "test_package") },
		...params.runner === void 0 ? {} : { runner: requiredString$1(params.runner, "runner") }
	};
	return {
		...selection,
		...sessionDefinition,
		input
	};
}
function sessionSelection(params) {
	return Object.fromEntries(SESSION_PROPERTIES.map((name) => [toCamelCase(name), requiredString$1(params[name], name)]));
}
function requireConfirmation(value) {
	if (value !== true) throw new TypeError("manage_app uninstall requires confirm=true.");
	return true;
}
function requiredString$1(value, name) {
	if (typeof value !== "string" || !value.trim()) throw new TypeError(`${name} is required.`);
	return value.trim();
}
function requiredRecord(value, name) {
	if (!isRecord(value)) throw new TypeError(`${name} must be an object.`);
	return value;
}
function boundedInteger$1(value, name, minimum, maximum) {
	if (typeof value !== "number" || !Number.isInteger(value) || value < minimum || value > maximum) throw new TypeError(`${name} must be an integer from ${minimum} through ${maximum}.`);
	return value;
}
function toCamelCase(value) {
	return value.replace(/_([a-z])/gu, (_match, character) => character.toUpperCase());
}
function commandError(code, message) {
	return cliError(code, message);
}
//#endregion
//#region src/lib/phone-plan.ts
const PLATFORMS = /* @__PURE__ */ new Set([
	"android",
	"harmony",
	"ios"
]);
const SESSION_POLICIES = /* @__PURE__ */ new Set(["existing", "reuse-or-start"]);
const SCREENSHOT_POLICIES = /* @__PURE__ */ new Set(["off", "on-failure"]);
const RECORDING_POLICIES = /* @__PURE__ */ new Set(["off", "native"]);
const MAX_PLAN_STEPS = 64;
async function executePhoneInventory(invoke) {
	const [targetsEnvelope, sessionsEnvelope] = await Promise.all([invoke("list_targets", {}), invoke("list_sessions", {})]);
	const targets = arrayValue(targetsEnvelope, "list_targets");
	const sessions = arrayValue(sessionsEnvelope, "list_sessions");
	const surfaceMap = /* @__PURE__ */ new Map();
	for (const item of [...targets, ...sessions]) {
		if (!item?.surfaceId) continue;
		const surface = surfaceMap.get(item.surfaceId) ?? {
			surfaceId: item.surfaceId,
			platforms: /* @__PURE__ */ new Set(),
			runtimeKinds: /* @__PURE__ */ new Set(),
			targetCount: 0,
			sessionCount: 0
		};
		if (typeof item.platform === "string") surface.platforms.add(item.platform);
		if (typeof item.runtimeKind === "string") surface.runtimeKinds.add(item.runtimeKind);
		if ("sessionId" in item) surface.sessionCount += 1;
		else surface.targetCount += 1;
		surfaceMap.set(item.surfaceId, surface);
	}
	const surfaces = [...surfaceMap.values()].map((surface) => Object.freeze({
		surfaceId: surface.surfaceId,
		platforms: Object.freeze([...surface.platforms].sort()),
		runtimeKinds: Object.freeze([...surface.runtimeKinds].sort()),
		targetCount: surface.targetCount,
		sessionCount: surface.sessionCount
	})).sort((left, right) => left.surfaceId.localeCompare(right.surfaceId));
	const publishedPlatforms = [...new Set([...targets, ...sessions].map((item) => item?.platform).filter(Boolean))].sort();
	return Object.freeze({
		schemaVersion: 1,
		scope: "connected_devices",
		summary: Object.freeze({
			surfaceCount: surfaces.length,
			targetCount: targets.length,
			sessionCount: sessions.length,
			publishedPlatforms: Object.freeze(publishedPlatforms)
		}),
		surfaces: Object.freeze(surfaces),
		targets: Object.freeze(targets),
		sessions: Object.freeze(sessions),
		note: "This inventory contains devices reachable through the host toolchain (adb, hdc, simctl). It is not a machine-wide SDK or toolchain scan; run `doctor` for that."
	});
}
async function executePhonePlan(source, invoke) {
	const plan = normalizePlan(source);
	const selection = await selectSession(plan.session, invoke);
	const steps = [];
	const evidenceErrors = [];
	let primaryError;
	let failureScreenshot;
	let recordingStarted = false;
	let recording;
	let cleanup;
	try {
		if (plan.evidence.recording === "native") {
			requireSucceededReceipt(await invoke("record_screen", {
				surface_id: selection.session.surfaceId,
				session_id: selection.session.sessionId,
				action: "start"
			}), "record_screen start");
			recordingStarted = true;
		}
		for (let index = 0; index < plan.steps.length; index += 1) {
			const step = plan.steps[index];
			try {
				const data = await executeStep(step, selection.session, invoke);
				steps.push(Object.freeze({
					index,
					kind: step.kind,
					status: "succeeded",
					data: summarizeStep(step.kind, data)
				}));
			} catch (error) {
				primaryError = annotateStepError(error, index, step.kind);
				break;
			}
		}
	} catch (error) {
		primaryError = annotateEvidencePhase(error, "recording-start");
	} finally {
		if (primaryError && plan.evidence.screenshots === "on-failure") try {
			const captured = await invoke("capture_screenshot", {
				surface_id: selection.session.surfaceId,
				session_id: selection.session.sessionId
			});
			requireSucceededReceipt(captured, "capture_screenshot on failure");
			failureScreenshot = summarizeVisualReceipt(captured);
		} catch (error) {
			evidenceErrors.push(summarizeEvidenceError(error, "failure-screenshot"));
		}
		if (recordingStarted) try {
			const stopped = await invoke("record_screen", {
				surface_id: selection.session.surfaceId,
				session_id: selection.session.sessionId,
				action: "stop"
			});
			requireSucceededReceipt(stopped, "record_screen stop");
			recording = summarizeVisualReceipt(stopped);
		} catch (error) {
			if (!primaryError) primaryError = annotateEvidencePhase(error, "recording-stop");
			else evidenceErrors.push(summarizeEvidenceError(error, "recording-stop"));
		}
		if (selection.startedSession && !plan.keepSession) try {
			cleanup = await invoke("stop_session", {
				surface_id: selection.session.surfaceId,
				session_id: selection.session.sessionId
			});
		} catch (error) {
			if (!primaryError) primaryError = annotateStepError(error, plan.steps.length, "stop_session");
		}
	}
	const evidence = summarizePlanEvidence(failureScreenshot, recording, evidenceErrors);
	if (primaryError) {
		if (evidence) attachPlanEvidence(primaryError, evidence);
		throw primaryError;
	}
	return Object.freeze({
		schemaVersion: 1,
		session: selection.session,
		...selection.target ? { target: selection.target } : {},
		startedSession: selection.startedSession,
		keptSession: selection.startedSession ? plan.keepSession : true,
		steps: Object.freeze(steps),
		...evidence ? { evidence } : {},
		...cleanup ? { cleanup: summarizeStep("stop_session", cleanup) } : {}
	});
}
async function selectSession(criteria, invoke) {
	const sessions = arrayValue(await invoke("list_sessions", {}), "list_sessions");
	const matchingSessions = sessions.filter((session) => matchesSelection(session, criteria));
	if (matchingSessions.length === 1) return Object.freeze({
		session: matchingSessions[0],
		startedSession: false
	});
	if (matchingSessions.length > 1) throw selectionError("phone.plan.session-ambiguous", "Plan session selector matched multiple live sessions.", matchingSessions);
	if (criteria.policy === "existing") throw selectionError("phone.plan.session-not-found", "Plan session selector did not match a live session.", sessions);
	const targets = arrayValue(await invoke("list_targets", {}), "list_targets");
	const matchingTargets = targets.filter((target) => matchesSelection(target, criteria));
	if (matchingTargets.length !== 1) throw selectionError(matchingTargets.length === 0 ? "phone.plan.target-not-found" : "phone.plan.target-ambiguous", matchingTargets.length === 0 ? "Plan session selector did not match a live target to start." : "Plan session selector matched multiple live targets.", matchingTargets.length === 0 ? targets : matchingTargets);
	const target = matchingTargets[0];
	const session = await invoke("start_session", {
		surface_id: target.surfaceId,
		target_id: target.targetId
	});
	return Object.freeze({
		session,
		target,
		startedSession: true
	});
}
async function executeStep(step, session, invoke) {
	const selected = {
		surface_id: session.surfaceId,
		session_id: session.sessionId
	};
	if (step.kind === "observe") return invoke("observe", {
		...selected,
		mode: step.mode
	});
	if (step.kind === "tap") return invoke("tap", {
		...selected,
		selector: step.selector
	});
	if (step.kind === "long_press") return invoke("long_press", {
		...selected,
		selector: step.selector,
		duration_ms: step.durationMs
	});
	if (step.kind === "wait") return invoke("wait", {
		...selected,
		condition: step.condition,
		...step.timeoutMs === void 0 ? {} : { timeout_ms: step.timeoutMs },
		...step.pollIntervalMs === void 0 ? {} : { poll_interval_ms: step.pollIntervalMs }
	});
	if (step.kind === "assert") return invoke("assert", {
		...selected,
		selector: step.selector,
		state: step.state
	});
	if (step.kind === "launch_app") {
		const receipt = await invoke("manage_app", {
			...selected,
			action: "launch",
			bundle_id: step.bundleId
		});
		if (receipt?.status !== "succeeded" || receipt?.output?.launched !== true) throw planError("phone.plan.app-launch-failed", "Plan app launch did not report a successful launch.", {
			status: receipt?.status,
			launched: receipt?.output?.launched === true
		});
		return receipt;
	}
	if (step.kind === "capture_screenshot") {
		const receipt = await invoke("capture_screenshot", selected);
		requireSucceededReceipt(receipt, "capture_screenshot");
		return receipt;
	}
	if (step.kind === "run_native_test") {
		const receipt = await invoke("run_native_test", {
			...selected,
			selector: step.selector,
			...step.timeoutMs === void 0 ? {} : { timeout_ms: step.timeoutMs },
			...step.testTarget === void 0 ? {} : { test_target: step.testTarget },
			...step.testModule === void 0 ? {} : { test_module: step.testModule },
			...step.testBundleId === void 0 ? {} : { test_bundle_id: step.testBundleId },
			...step.runner === void 0 ? {} : { runner: step.runner }
		});
		requireSucceededReceipt(receipt, "run_native_test");
		if (receipt?.output?.outcome !== "passed") throw planError("phone.plan.native-test-not-passed", `Native test outcome is ${receipt?.output?.outcome ?? "missing"}, expected passed.`, { outcome: receipt?.output?.outcome ?? "missing" });
		return receipt;
	}
	throw planError("phone.plan.step-invalid", `Unsupported plan step: ${step.kind}`);
}
function normalizePlan(source) {
	if (!isRecord(source) || source.schemaVersion !== 1) throw planError("phone.plan.invalid", "Plan must be an object with schemaVersion: 1.");
	const session = normalizeSessionSelection(source.session);
	if (!Array.isArray(source.steps) || source.steps.length === 0 || source.steps.length > MAX_PLAN_STEPS) throw planError("phone.plan.invalid", `Plan steps must contain 1 through ${MAX_PLAN_STEPS} entries.`);
	if (source.keepSession !== void 0 && typeof source.keepSession !== "boolean") throw planError("phone.plan.invalid", "Plan keepSession must be a boolean.");
	return Object.freeze({
		session,
		steps: Object.freeze(source.steps.map((step, index) => normalizeStep(step, index))),
		keepSession: source.keepSession === true,
		evidence: normalizeEvidence(source.evidence)
	});
}
function normalizeEvidence(source) {
	if (source === void 0) return Object.freeze({
		screenshots: "off",
		recording: "off"
	});
	if (!isRecord(source)) throw planError("phone.plan.invalid", "Plan evidence must be an object.");
	const screenshots = source.screenshots ?? "off";
	const recording = source.recording ?? "off";
	if (!SCREENSHOT_POLICIES.has(screenshots)) throw planError("phone.plan.invalid", "Plan evidence.screenshots must be off or on-failure.");
	if (!RECORDING_POLICIES.has(recording)) throw planError("phone.plan.invalid", "Plan evidence.recording must be off or native.");
	return Object.freeze({
		screenshots,
		recording
	});
}
function normalizeSessionSelection(source) {
	if (!isRecord(source)) throw planError("phone.plan.invalid", "Plan session must be an object.");
	const policy = source.policy ?? "existing";
	if (!SESSION_POLICIES.has(policy)) throw planError("phone.plan.invalid", "Plan session policy must be existing or reuse-or-start.");
	const selection = Object.freeze({
		policy,
		...optionalString$1(source.surfaceId, "session.surfaceId"),
		...optionalString$1(source.sessionId, "session.sessionId"),
		...optionalString$1(source.targetId, "session.targetId"),
		...optionalString$1(source.targetName, "session.targetName"),
		...optionalString$1(source.runtimeKind, "session.runtimeKind"),
		...optionalString$1(source.platform, "session.platform")
	});
	if (selection.surfaceId === void 0 !== (selection.sessionId === void 0) && selection.sessionId !== void 0) throw planError("phone.plan.invalid", "session.sessionId requires session.surfaceId.");
	if (selection.sessionId === void 0 && selection.platform === void 0) throw planError("phone.plan.invalid", "Plan session requires exact surfaceId/sessionId or a platform selector.");
	if (selection.platform !== void 0 && !PLATFORMS.has(selection.platform)) throw planError("phone.plan.invalid", "session.platform must be android, harmony, or ios.");
	return selection;
}
function normalizeStep(source, index) {
	if (!isRecord(source) || typeof source.kind !== "string") throw planError("phone.plan.invalid", `Plan step ${index} requires a kind.`);
	if (source.kind === "observe") {
		if (source.mode !== void 0 && source.mode !== "interactive" && source.mode !== "full") throw planError("phone.plan.invalid", `steps[${index}].mode must be interactive or full.`);
		return Object.freeze({
			kind: source.kind,
			mode: source.mode === "full" ? "full" : "interactive"
		});
	}
	if (source.kind === "tap" || source.kind === "long_press") return Object.freeze({
		kind: source.kind,
		selector: requiredSelector(source.selector, index),
		...source.kind === "long_press" && source.durationMs !== void 0 ? { durationMs: boundedInteger(source.durationMs, `steps[${index}].durationMs`, 1, 6e4) } : {}
	});
	if (source.kind === "wait") return Object.freeze({
		kind: source.kind,
		condition: normalizeWaitCondition(source.condition, index),
		...source.timeoutMs === void 0 ? {} : { timeoutMs: boundedInteger(source.timeoutMs, `steps[${index}].timeoutMs`, 1, 12e5) },
		...source.pollIntervalMs === void 0 ? {} : { pollIntervalMs: boundedInteger(source.pollIntervalMs, `steps[${index}].pollIntervalMs`, 1, 6e4) }
	});
	if (source.kind === "assert") {
		if (source.state !== void 0 && source.state !== "present" && source.state !== "absent") throw planError("phone.plan.invalid", `steps[${index}].state must be present or absent.`);
		const state = source.state === "absent" ? "absent" : "present";
		return Object.freeze({
			kind: source.kind,
			selector: requiredSelector(source.selector, index),
			state
		});
	}
	if (source.kind === "launch_app") return Object.freeze({
		kind: source.kind,
		bundleId: requiredString(source.bundleId, `steps[${index}].bundleId`)
	});
	if (source.kind === "capture_screenshot") return Object.freeze({ kind: source.kind });
	if (source.kind === "run_native_test") return Object.freeze({
		kind: source.kind,
		selector: requiredString(source.selector, `steps[${index}].selector`),
		...source.timeoutMs === void 0 ? {} : { timeoutMs: boundedInteger(source.timeoutMs, `steps[${index}].timeoutMs`, 1e3, 12e5) },
		...optionalNamedString(source.testTarget, "testTarget", `steps[${index}].testTarget`),
		...optionalNamedString(source.testModule, "testModule", `steps[${index}].testModule`),
		...optionalNamedString(source.testBundleId, "testBundleId", `steps[${index}].testBundleId`),
		...optionalNamedString(source.runner, "runner", `steps[${index}].runner`)
	});
	throw planError("phone.plan.invalid", `Unsupported plan step kind at index ${index}: ${source.kind}`);
}
function normalizeWaitCondition(source, index) {
	if (!isRecord(source) || typeof source.kind !== "string") throw planError("phone.plan.invalid", `steps[${index}].condition must be an object with a kind.`);
	if (source.kind === "stable") return Object.freeze({
		kind: source.kind,
		...source.durationMs === void 0 ? {} : { durationMs: boundedInteger(source.durationMs, `steps[${index}].condition.durationMs`, 1, 12e5) }
	});
	if (source.kind === "present" || source.kind === "absent") return Object.freeze({
		kind: source.kind,
		selector: requiredSelector(source.selector, index)
	});
	throw planError("phone.plan.invalid", `Unsupported wait condition at step ${index}: ${source.kind}`);
}
function matchesSelection(item, selection) {
	const record = item;
	return [
		"surfaceId",
		"sessionId",
		"targetId",
		"targetName",
		"runtimeKind",
		"platform"
	].every((key) => selection[key] === void 0 || record?.[key] === selection[key]);
}
function summarizeStep(kind, value) {
	if (kind === "observe" || kind === "wait") return summarizeObservation(value);
	if (kind === "tap" || kind === "long_press") {
		const v = value ?? {};
		return Object.freeze({
			uiChanged: v.uiChanged === true,
			element: summarizeElement(v.element),
			observation: summarizeObservation(v.observation),
			receipt: summarizeReceipt(v.receipt)
		});
	}
	if (kind === "assert") {
		const v = value ?? {};
		return Object.freeze({
			passed: v.passed === true,
			...typeof v.reason === "string" ? { reason: v.reason } : {},
			...v.element ? { element: summarizeElement(v.element) } : {},
			observation: summarizeObservation(v.observation)
		});
	}
	if (kind === "capture_screenshot" || kind === "record_screen") return summarizeVisualReceipt(value);
	return value;
}
function summarizeVisualReceipt(value) {
	if (!isRecord(value)) return value;
	const artifact = summarizeArtifact(value.output?.artifact);
	return Object.freeze({
		operationId: value.operationId,
		operation: value.operation,
		status: value.status,
		...value.startedAt ? { startedAt: value.startedAt } : {},
		...value.completedAt ? { completedAt: value.completedAt } : {},
		...value.sessionId ? { sessionId: value.sessionId } : {},
		...value.revision ? { revision: value.revision } : {},
		...isRecord(value.output) ? { output: Object.freeze({
			...typeof value.output.active === "boolean" ? { active: value.output.active } : {},
			...typeof value.output.startedAt === "string" ? { startedAt: value.output.startedAt } : {},
			...artifact ? { artifact } : {}
		}) } : {},
		...Array.isArray(value.evidence) ? { evidence: Object.freeze(value.evidence.map(summarizeEvidenceRef).filter(Boolean)) } : {}
	});
}
function summarizeArtifact(value) {
	if (!isRecord(value)) return void 0;
	return Object.freeze(Object.fromEntries([
		"artifactId",
		"createdAt",
		"mediaType",
		"size",
		"algorithm",
		"digest",
		"uri",
		"source",
		"platform",
		"targetId",
		"sessionId",
		"revision"
	].flatMap((key) => value[key] === void 0 ? [] : [[key, value[key]]])));
}
function summarizeEvidenceRef(value) {
	if (!isRecord(value)) return void 0;
	return Object.freeze(Object.fromEntries([
		"algorithm",
		"digest",
		"mediaType",
		"size",
		"uri"
	].flatMap((key) => value[key] === void 0 ? [] : [[key, value[key]]])));
}
function summarizePlanEvidence(failureScreenshot, recording, errors) {
	if (!failureScreenshot && !recording && errors.length === 0) return void 0;
	return Object.freeze({
		...failureScreenshot ? { failureScreenshot } : {},
		...recording ? { recording } : {},
		...errors.length ? { errors: Object.freeze([...errors]) } : {}
	});
}
function summarizeEvidenceError(error, phase) {
	const e = error;
	return Object.freeze({
		phase,
		code: typeof e?.code === "string" ? e.code : "phone.plan.evidence-failed",
		message: error instanceof Error ? error.message : String(error)
	});
}
function summarizeObservation(value) {
	const v = value ?? {};
	return Object.freeze({
		uiRevision: v.uiRevision,
		snapshotId: v.snapshotId,
		platform: v.platform,
		source: v.source,
		screen: v.screen,
		truncated: v.truncated === true,
		elementCount: Number.isInteger(v.elementCount) ? v.elementCount : Array.isArray(v.elements) ? v.elements.length : 0
	});
}
function summarizeElement(value) {
	if (!isRecord(value)) return void 0;
	return Object.freeze({
		...typeof value.ref === "string" ? { ref: value.ref } : {},
		...typeof value.identifier === "string" ? { identifier: value.identifier } : {},
		...typeof value.label === "string" ? { label: value.label } : {},
		...typeof value.role === "string" ? { role: value.role } : {},
		...typeof value.type === "string" ? { type: value.type } : {}
	});
}
function summarizeReceipt(value) {
	if (!isRecord(value)) return void 0;
	return Object.freeze({
		operationId: value.operationId,
		operation: value.operation,
		status: value.status,
		...value.output === void 0 ? {} : { output: value.output }
	});
}
function arrayValue(value, command) {
	if (!Array.isArray(value)) throw planError("phone.plan.command-invalid", `${command} did not return an array.`);
	return value;
}
function requiredSelector(value, index) {
	if (!isRecord(value)) throw planError("phone.plan.invalid", `steps[${index}].selector must be an object.`);
	const keys = [
		"ref",
		"identifier",
		"label",
		"role",
		"type"
	];
	if (!keys.some((key) => typeof value[key] === "string" && value[key].trim())) throw planError("phone.plan.invalid", `steps[${index}].selector requires ref, identifier, label, role, or type.`);
	return Object.freeze(Object.fromEntries(keys.flatMap((key) => typeof value[key] === "string" && value[key].trim() ? [[key, value[key].trim()]] : [])));
}
function optionalString$1(value, name) {
	if (value === void 0) return {};
	return { [name.slice(name.lastIndexOf(".") + 1)]: requiredString(value, name) };
}
function optionalNamedString(value, key, name) {
	return value === void 0 ? {} : { [key]: requiredString(value, name) };
}
function requiredString(value, name) {
	if (typeof value !== "string" || !value.trim()) throw planError("phone.plan.invalid", `${name} must be a non-empty string.`);
	return value.trim();
}
function boundedInteger(value, name, minimum, maximum) {
	if (!Number.isInteger(value) || value < minimum || value > maximum) throw planError("phone.plan.invalid", `${name} must be an integer from ${minimum} through ${maximum}.`);
	return value;
}
function requireSucceededReceipt(receipt, stepKind) {
	const r = receipt;
	if (r?.status !== "succeeded") throw planError("phone.plan.operation-failed", `${stepKind} did not return a succeeded operation receipt.`, {
		stepKind,
		status: r?.status ?? "missing"
	});
}
function selectionError(code, message, candidates) {
	return planError(code, message, { candidates: candidates.slice(0, 20).map((item) => ({
		surfaceId: item?.surfaceId,
		..."sessionId" in item && item.sessionId ? { sessionId: item.sessionId } : {},
		..."targetId" in item && item.targetId ? { targetId: item.targetId } : {},
		platform: item?.platform,
		targetName: item?.targetName,
		runtimeKind: item?.runtimeKind,
		state: item?.state
	})) });
}
function annotateStepError(error, stepIndex, stepKind) {
	const normalized = error instanceof Error ? error : new Error(String(error));
	normalized.details = Object.freeze({
		...isRecord(normalized.details) ? normalized.details : {},
		stepIndex,
		stepKind
	});
	return normalized;
}
function annotateEvidencePhase(error, evidencePhase) {
	const normalized = error instanceof Error ? error : new Error(String(error));
	normalized.details = Object.freeze({
		...isRecord(normalized.details) ? normalized.details : {},
		evidencePhase
	});
	return normalized;
}
function attachPlanEvidence(error, evidence) {
	error.details = Object.freeze({
		...isRecord(error.details) ? error.details : {},
		evidence
	});
}
function planError(code, message, details) {
	const error = cliError(code, message);
	if (details !== void 0) error.details = Object.freeze(details);
	return error;
}
//#endregion
//#region src/lib/phone-command.ts
const CORE_PHONE_COMMANDS = Object.freeze([
	"inventory",
	"list_targets",
	"start_session",
	"stop_session",
	"list_sessions",
	"observe",
	"tap",
	"long_press",
	"act",
	"wait",
	"assert",
	"run_plan"
]);
const OPERATIONAL_PHONE_COMMANDS = Object.freeze([
	"restart_target",
	"manage_app",
	"read_logs",
	"run_native_test",
	"capture_screenshot",
	"record_screen"
]);
const PHONE_COMMANDS = Object.freeze([...CORE_PHONE_COMMANDS, ...OPERATIONAL_PHONE_COMMANDS]);
async function executePhoneCommand(command, args = {}, dependencies = {}) {
	if (!PHONE_COMMANDS.includes(command)) throw cliError("phone.command.unknown", `Unknown Mobile Use command: ${command}`);
	const listSessions = dependencies.listLiveSessions ?? listLiveSessions;
	const listTargets = dependencies.listLiveTargets ?? listLiveTargets;
	const startSession = dependencies.startPhoneUseSession ?? startPhoneUseSession;
	const stopSession = dependencies.stopPhoneUseSession ?? stopPhoneUseSession;
	const invoke = dependencies.invokePhoneUse ?? invokePhoneUse;
	const invokeSession = dependencies.invokeSessionOperation ?? invokeSessionOperation;
	const invokeTarget = dependencies.invokeTargetOperation ?? invokeTargetOperation;
	const invokeCommand = (nextCommand, nextArgs = {}) => executePhoneCommand(nextCommand, nextArgs, dependencies);
	if (command === "inventory") return executePhoneInventory(invokeCommand);
	if (command === "run_plan") return executePhonePlan(args.plan, invokeCommand);
	if (command === "list_targets") return listTargets();
	if (command === "start_session") {
		const target = targetSelection(args);
		return startSession(target.surfaceId, target.targetId);
	}
	if (command === "stop_session") {
		const target = sessionSelection(args);
		return stopSession(target.surfaceId, target.sessionId);
	}
	if (command === "list_sessions") return listSessions();
	if (TARGET_OPERATION_COMMANDS[command]) {
		const target = operationAndInput(command, args);
		return invokeTarget(target.surfaceId, target.targetId, target.operation, target.capability, target.input);
	}
	if (SESSION_OPERATION_COMMANDS[command]) {
		const target = operationAndInput(command, args);
		return invokeSession(target.surfaceId, target.sessionId, target.operation, target.capability, target.input);
	}
	const target = targetAndInput(command, args);
	if (command === "tap" || command === "long_press") return summarizePerformResult(await invoke(target.surfaceId, target.sessionId, "perform", target.input));
	return invoke(target.surfaceId, target.sessionId, command, target.input);
}
function summarizePerformResult(value) {
	const v = value ?? {};
	const observation = v.observation;
	const element = v.element;
	const receipt = v.receipt;
	return Object.freeze({
		uiChanged: v.uiChanged === true,
		...element && typeof element === "object" ? { element: Object.freeze({
			...typeof element.ref === "string" ? { ref: element.ref } : {},
			...typeof element.identifier === "string" ? { identifier: element.identifier } : {},
			...typeof element.label === "string" ? { label: element.label } : {},
			...typeof element.role === "string" ? { role: element.role } : {},
			...typeof element.type === "string" ? { type: element.type } : {}
		}) } : {},
		observation: Object.freeze({
			uiRevision: observation?.uiRevision,
			snapshotId: observation?.snapshotId,
			platform: observation?.platform,
			source: observation?.source,
			screen: observation?.screen,
			truncated: observation?.truncated === true,
			elementCount: Array.isArray(observation?.elements) ? observation.elements.length : 0
		}),
		...receipt && typeof receipt === "object" ? { receipt: Object.freeze({
			operationId: receipt.operationId,
			operation: receipt.operation,
			status: receipt.status,
			...receipt.output === void 0 ? {} : { output: receipt.output }
		}) } : {}
	});
}
//#endregion
//#region src/lib/swift-cache.ts
const DEFAULT_MAX_AGE_DAYS = 30;
const DEFAULT_MAX_SIZE_MB = 8192;
const MAX_CACHE_ENTRIES = 1024;
const SWIFT_CACHE_COMMANDS = Object.freeze([
	"swift_cache_status",
	"swift_cache_prune",
	"swift_cache_clean"
]);
async function executeSwiftCacheCommand(command, args = {}) {
	if (!SWIFT_CACHE_COMMANDS.includes(command)) throw cliError("swift.cache.command.unknown", `Unknown Swift cache command: ${command}`);
	const cacheRoot = resolveSwiftCacheRoot(args.cache_root);
	const entries = await scanSwiftCache(cacheRoot);
	if (command === "swift_cache_status") return summarizeCache(cacheRoot, entries);
	if (command === "swift_cache_prune") {
		const maxAgeDays = boundedNumber(args.max_age_days, "max_age_days", 1, 3650, DEFAULT_MAX_AGE_DAYS);
		const maxSizeMb = boundedNumber(args.max_size_mb, "max_size_mb", 128, 1048576, DEFAULT_MAX_SIZE_MB);
		const includeLegacy = args.include_legacy === true;
		const selected = selectPrunableEntries(entries, {
			includeLegacy,
			maxAgeDays,
			maxSizeBytes: maxSizeMb * 1024 * 1024
		});
		const applied = args.apply === true;
		if (applied) await removeCacheEntries(cacheRoot, selected);
		const candidateBytes = selected.reduce((total, entry) => total + entry.sizeBytes, 0);
		return Object.freeze({
			cacheRoot,
			applied,
			policy: {
				includeLegacy,
				maxAgeDays,
				maxSizeMb
			},
			candidateBytes,
			reclaimedBytes: applied ? candidateBytes : 0,
			candidates: selected.map(publicEntry),
			removed: applied ? selected.map(publicEntry) : [],
			skippedActive: entries.filter((entry) => entry.active).map(publicEntry),
			skippedLegacy: includeLegacy ? [] : entries.filter((entry) => entry.legacy).map(publicEntry)
		});
	}
	if (args.confirm !== true) throw cliError("swift.cache.confirmation.required", "swift_cache_clean requires --confirm.");
	const packageSwift = args.package_swift === void 0 ? void 0 : optionalAbsolutePath(args.package_swift, "package_swift");
	const cacheIdentity = optionalString(args.cache_identity);
	if (!packageSwift && !cacheIdentity) throw cliError("swift.cache.argument", "swift_cache_clean requires --package-swift or --cache-identity.");
	const selected = entries.filter((entry) => (!packageSwift || entry.packageSwift === packageSwift) && (!cacheIdentity || entry.cacheIdentity === cacheIdentity));
	const active = selected.filter((entry) => entry.active);
	if (active.length) throw cliError("swift.cache.active", `Refusing to remove ${active.length} active Swift preview cache entr${active.length === 1 ? "y" : "ies"}.`);
	await removeCacheEntries(cacheRoot, selected);
	return Object.freeze({
		cacheRoot,
		removed: selected.map(publicEntry),
		reclaimedBytes: selected.reduce((total, entry) => total + entry.sizeBytes, 0)
	});
}
async function scanSwiftCache(cacheRoot) {
	const packagesRoot = path.join(cacheRoot, "packages");
	const packageEntries = await readDirectories(packagesRoot);
	const cacheEntries = [];
	for (const packageEntry of packageEntries) {
		const entriesRoot = path.join(packagesRoot, packageEntry.name, "entries");
		for (const entry of await readDirectories(entriesRoot)) {
			if (cacheEntries.length >= MAX_CACHE_ENTRIES) throw cliError("swift.cache.too-many-entries", `Swift preview cache exceeds ${MAX_CACHE_ENTRIES} entries; clean it with an exact cache path before retrying.`);
			const entryRoot = path.join(entriesRoot, entry.name);
			const [metadata, entryStat, activity, sizeBytes] = await Promise.all([
				readJsonIfExists(path.join(entryRoot, "cache-metadata.json")),
				stat(entryRoot),
				inspectActivity(entryRoot),
				directorySize(entryRoot)
			]);
			const lastUsedAt = validDate(metadata?.lastUsedAt) ?? validDate(metadata?.createdAt) ?? entryStat.mtime.toISOString();
			cacheEntries.push(Object.freeze({
				active: activity.active,
				activePids: activity.activePids,
				cacheIdentity: typeof metadata?.cacheIdentity === "string" ? metadata.cacheIdentity : entry.name,
				entryRoot,
				healthy: metadata?.schemaVersion === 1 && metadata?.kind === "swiftui-package-preview",
				lastUsedAt,
				packageIdentity: typeof metadata?.packageIdentity === "string" ? metadata.packageIdentity : packageEntry.name,
				packageSwift: typeof metadata?.packageSwift === "string" ? path.resolve(metadata.packageSwift) : void 0,
				packageTarget: typeof metadata?.packageTarget === "string" ? metadata.packageTarget : void 0,
				sizeBytes,
				staleLeaseCount: activity.staleLeaseCount ?? 0
			}));
		}
	}
	const processTable = readProcessTable();
	for (const legacyEntry of await readDirectories(cacheRoot)) {
		if (legacyEntry.name === "packages") continue;
		const entryRoot = path.join(cacheRoot, legacyEntry.name);
		const childDirectories = new Set((await readDirectories(entryRoot)).map((entry) => entry.name));
		if (!childDirectories.has("GeneratedPreviewHost") || !childDirectories.has("Build") && !childDirectories.has("sessions")) continue;
		if (cacheEntries.length >= MAX_CACHE_ENTRIES) throw cliError("swift.cache.too-many-entries", `Swift preview cache exceeds ${MAX_CACHE_ENTRIES} entries; clean it with an exact cache path before retrying.`);
		const [entryStat, sizeBytes] = await Promise.all([stat(entryRoot), directorySize(entryRoot)]);
		const activity = inspectLegacyActivity(cacheRoot, entryRoot, processTable);
		cacheEntries.push(Object.freeze({
			active: activity.active,
			activePids: activity.activePids,
			activityKnown: activity.known,
			cacheIdentity: `legacy:${legacyEntry.name}`,
			entryRoot,
			healthy: true,
			lastUsedAt: entryStat.mtime.toISOString(),
			legacy: true,
			packageIdentity: legacyEntry.name,
			sizeBytes,
			staleLeaseCount: 0
		}));
	}
	return Object.freeze(cacheEntries.sort((left, right) => Date.parse(right.lastUsedAt) - Date.parse(left.lastUsedAt) || left.cacheIdentity.localeCompare(right.cacheIdentity)));
}
function summarizeCache(cacheRoot, entries) {
	const legacyEntries = entries.filter((entry) => entry.legacy);
	return Object.freeze({
		cacheRoot,
		entryCount: entries.length,
		activeCount: entries.filter((entry) => entry.active).length,
		totalBytes: entries.reduce((total, entry) => total + entry.sizeBytes, 0),
		legacyEntryCount: legacyEntries.length,
		legacyBytes: legacyEntries.reduce((total, entry) => total + entry.sizeBytes, 0),
		entries: entries.map(publicEntry)
	});
}
function selectPrunableEntries(entries, { includeLegacy, maxAgeDays, maxSizeBytes }) {
	const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1e3;
	const selected = /* @__PURE__ */ new Map();
	for (const entry of entries) if (!entry.active && (includeLegacy || !entry.legacy) && Date.parse(entry.lastUsedAt) < cutoff) selected.set(entry.entryRoot, entry);
	let retainedBytes = entries.reduce((total, entry) => total + entry.sizeBytes, 0) - [...selected.values()].reduce((total, entry) => total + entry.sizeBytes, 0);
	const oldestInactive = entries.filter((entry) => !entry.active && (includeLegacy || !entry.legacy) && !selected.has(entry.entryRoot)).sort((left, right) => Date.parse(left.lastUsedAt) - Date.parse(right.lastUsedAt));
	for (const entry of oldestInactive) {
		if (retainedBytes <= maxSizeBytes) break;
		selected.set(entry.entryRoot, entry);
		retainedBytes -= entry.sizeBytes;
	}
	return [...selected.values()].sort((left, right) => Date.parse(left.lastUsedAt) - Date.parse(right.lastUsedAt));
}
async function removeCacheEntries(cacheRoot, entries) {
	for (const entry of entries) {
		assertContainedEntry(cacheRoot, entry);
		await rm(entry.entryRoot, {
			recursive: true,
			force: true
		});
	}
}
function inspectLegacyActivity(cacheRoot, entryRoot, processTable) {
	if (!processTable) return Object.freeze({
		active: false,
		activePids: [],
		known: false
	});
	const matches = processTable.filter((record) => record.command.includes(entryRoot) || record.command.includes(cacheRoot) && record.command.includes("swift-package-preview.mjs"));
	const activePids = [...new Set(matches.map((record) => record.pid))].sort((left, right) => left - right);
	return Object.freeze({
		active: activePids.length > 0,
		activePids,
		known: true
	});
}
function readProcessTable() {
	if (process.platform !== "darwin") return void 0;
	try {
		return execFileSync("/bin/ps", [
			"-ax",
			"-o",
			"pid=,command="
		], {
			encoding: "utf8",
			stdio: [
				"ignore",
				"pipe",
				"ignore"
			]
		}).split("\n").flatMap((line) => {
			const match = /^\s*(\d+)\s+(.+)$/u.exec(line);
			return match ? [{
				pid: Number(match[1]),
				command: match[2]
			}] : [];
		});
	} catch {
		return;
	}
}
async function inspectActivity(entryRoot) {
	const records = [];
	for (const entry of await readFiles(path.join(entryRoot, "sessions"))) {
		const pid = (await readJsonIfExists(path.join(entryRoot, "sessions", entry.name)))?.pid;
		if (Number.isInteger(pid) && pid > 0) records.push(pid);
	}
	for (const deviceEntry of await readDirectories(path.join(entryRoot, "DerivedData"))) {
		const buildLockPid = (await readJsonIfExists(path.join(entryRoot, "DerivedData", deviceEntry.name, ".build.lock")))?.pid;
		if (Number.isInteger(buildLockPid) && buildLockPid > 0) records.push(buildLockPid);
	}
	const activeRecords = records.filter(processIsAlive);
	const activePids = [...new Set(activeRecords)].sort((left, right) => left - right);
	return Object.freeze({
		active: activePids.length > 0,
		activePids,
		staleLeaseCount: records.length - activeRecords.length
	});
}
async function directorySize(directory) {
	let total = 0;
	let entries;
	try {
		entries = await readdir(directory, { withFileTypes: true });
	} catch (error) {
		if (error?.code === "ENOENT") return 0;
		throw error;
	}
	for (const entry of entries) {
		const child = path.join(directory, entry.name);
		if (entry.isDirectory()) total += await directorySize(child);
		else if (entry.isFile()) total += (await stat(child)).size;
	}
	return total;
}
async function readDirectories(directory) {
	return (await readEntries(directory)).filter((entry) => entry.isDirectory());
}
async function readFiles(directory) {
	return (await readEntries(directory)).filter((entry) => entry.isFile() && entry.name.endsWith(".json"));
}
async function readEntries(directory) {
	try {
		return await readdir(directory, { withFileTypes: true });
	} catch (error) {
		if (error?.code === "ENOENT") return [];
		throw error;
	}
}
async function readJsonIfExists(filePath) {
	try {
		const value = JSON.parse(await readFile(filePath, "utf8"));
		return value && typeof value === "object" && !Array.isArray(value) ? value : void 0;
	} catch (error) {
		if (error?.code === "ENOENT" || error instanceof SyntaxError) return void 0;
		throw error;
	}
}
function publicEntry(entry) {
	return Object.freeze({
		active: entry.active,
		...entry.activityKnown === false ? { activityKnown: false } : {},
		cacheIdentity: entry.cacheIdentity,
		healthy: entry.healthy,
		lastUsedAt: entry.lastUsedAt,
		...entry.legacy ? { legacy: true } : {},
		packageIdentity: entry.packageIdentity,
		...entry.packageSwift ? { packageSwift: entry.packageSwift } : {},
		...entry.packageTarget ? { packageTarget: entry.packageTarget } : {},
		sizeBytes: entry.sizeBytes,
		staleLeaseCount: entry.staleLeaseCount
	});
}
function resolveSwiftCacheRoot(value) {
	if (value !== void 0) return optionalAbsolutePath(value, "cache_root");
	const dataRoot = process.env.AICODING_HOME || process.env.QODER_HOME || path.join(os.homedir(), ".qoder");
	return path.resolve(dataRoot, "canvas", "swiftui-package-preview");
}
function optionalAbsolutePath(value, name) {
	if (typeof value !== "string" || !value.trim()) throw cliError("swift.cache.argument", `${name} must be an absolute path.`);
	const resolved = path.resolve(value.trim());
	if (!path.isAbsolute(value.trim())) throw cliError("swift.cache.argument", `${name} must be an absolute path.`);
	return resolved;
}
function optionalString(value) {
	return typeof value === "string" && value.trim() ? value.trim() : void 0;
}
function boundedNumber(value, name, minimum, maximum, fallback) {
	if (value === void 0) return fallback;
	if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || value > maximum) throw cliError("swift.cache.argument", `${name} must be from ${minimum} through ${maximum}.`);
	return value;
}
function validDate(value) {
	return typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : void 0;
}
function assertContainedEntry(cacheRoot, entry) {
	const entryRoot = entry.entryRoot;
	if (entry.legacy) {
		const relative = path.relative(path.resolve(cacheRoot), path.resolve(entryRoot));
		if (!relative || relative === "packages" || relative.includes(path.sep) || relative.startsWith("..") || path.isAbsolute(relative)) throw cliError("swift.cache.path", `Refusing to remove a path outside the Swift preview cache: ${entryRoot}`);
		return;
	}
	const entriesRoot = path.resolve(cacheRoot, "packages");
	const relative = path.relative(entriesRoot, path.resolve(entryRoot));
	if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) throw cliError("swift.cache.path", `Refusing to remove a path outside the Swift preview cache: ${entryRoot}`);
}
function processIsAlive(pid) {
	if (!Number.isInteger(pid) || pid <= 0) return false;
	try {
		process.kill(pid, 0);
		return true;
	} catch (error) {
		return error?.code === "EPERM";
	}
}
//#endregion
//#region src/lib/doctor.ts
async function collectDoctorReport(requested = "all") {
	const host = hostPlatform();
	const checks = [];
	if (requested === "all" || requested === "android") checks.push(await checkAndroid());
	if (requested === "all" || requested === "harmony") checks.push(await checkHarmony());
	if (requested === "all" || requested === "ios") checks.push(await checkIos(host));
	return Object.freeze({
		schemaVersion: 1,
		host,
		platform: requested,
		checks: Object.freeze(checks),
		summary: Object.freeze({
			total: checks.length,
			ready: checks.filter((check) => check.status === "ready").length,
			missing: checks.filter((check) => check.status === "missing").length,
			unsupported: checks.filter((check) => check.status === "unsupported").length
		})
	});
}
async function checkAndroid() {
	const sdk = await findAndroidSdk();
	if (!sdk) return Object.freeze({
		platform: "android",
		status: "missing",
		tools: Object.freeze({
			adb: null,
			emulator: null
		}),
		guidance: "Install Android SDK platform-tools, or set ANDROID_HOME / ANDROID_SDK_ROOT to an existing SDK."
	});
	const adbVersion = await runTool(sdk.adb, ["version"], { timeoutMs: 15e3 }).then(({ stdout }) => stdout.split("\n")[0]?.trim()).catch(() => null);
	const avdHome = process.env.ANDROID_AVD_HOME;
	const avds = avdHome ? await listDirectoryNames(avdHome) : [];
	return Object.freeze({
		platform: "android",
		status: "ready",
		tools: Object.freeze({
			adb: Object.freeze({
				path: sdk.adb,
				version: adbVersion
			}),
			emulator: sdk.emulator ? Object.freeze({ path: sdk.emulator }) : null,
			sdkRoot: sdk.root
		}),
		avds: Object.freeze(avds),
		guidance: sdk.emulator ? null : "emulator component not found; install it via sdkmanager to boot virtual devices."
	});
}
async function checkHarmony() {
	const hdc = await findHdc();
	if (!hdc) return Object.freeze({
		platform: "harmony",
		status: "missing",
		tools: Object.freeze({ hdc: null }),
		guidance: "Install DevEco Studio and set DEVECO_SDK_HOME, or add OpenHarmony toolchains (hdc) to PATH."
	});
	const version = await runTool(hdc, ["-v"], { timeoutMs: 15e3 }).then(({ stdout }) => stdout.trim()).catch(() => null);
	return Object.freeze({
		platform: "harmony",
		status: "ready",
		tools: Object.freeze({ hdc: Object.freeze({
			path: hdc,
			version
		}) }),
		guidance: null
	});
}
async function checkIos(host) {
	if (host !== "darwin") return Object.freeze({
		platform: "ios",
		status: "unsupported",
		tools: Object.freeze({ xcrun: null }),
		guidance: "iOS Simulator control requires macOS with Xcode."
	});
	const xcrun = await findXcrun();
	if (!xcrun) return Object.freeze({
		platform: "ios",
		status: "missing",
		tools: Object.freeze({ xcrun: null }),
		guidance: "Install Xcode and run `xcode-select --install` for command-line tools."
	});
	const version = await runTool(xcrun, ["simctl", "help"], { timeoutMs: 15e3 }).then(() => "available").catch(() => null);
	return Object.freeze({
		platform: "ios",
		status: version ? "ready" : "missing",
		tools: Object.freeze({ xcrun: Object.freeze({
			path: xcrun,
			version
		}) }),
		guidance: null
	});
}
//#endregion
//#region src/bin/mobile-use.ts
const SCHEMA_VERSION = 1;
const CLI_VERSION = "1.0.0";
const JSON_FLAGS = /* @__PURE__ */ new Map([
	["action_json", "action"],
	["condition_json", "condition"],
	["params_json", void 0],
	["plan_json", "plan"],
	["selector_json", "selector"]
]);
const NUMBER_FLAGS = /* @__PURE__ */ new Set([
	"duration_ms",
	"limit",
	"max_age_days",
	"max_size_mb",
	"poll_interval_ms",
	"seconds",
	"timeout_ms",
	"ui_revision"
]);
const BOOLEAN_FLAGS = /* @__PURE__ */ new Set([
	"apply",
	"confirm",
	"include_legacy"
]);
const LOCAL_COMMANDS = ["doctor"];
async function runCli(argv, options = {}) {
	const stdout = options.stdout ?? process.stdout;
	const stderr = options.stderr ?? process.stderr;
	let command;
	try {
		const parsed = parseArguments(argv);
		command = parsed.command;
		if (parsed.help) {
			stdout.write(`${helpText()}\n`);
			return 0;
		}
		if (parsed.version) {
			stdout.write(`${CLI_VERSION}\n`);
			return 0;
		}
		let data;
		if (command === "doctor") data = await collectDoctorReport(typeof parsed.params.platform === "string" ? parsed.params.platform : "all");
		else if (command && SWIFT_CACHE_COMMANDS.includes(command)) {
			if ((options.platform ?? process.platform) !== "darwin") throw cliError("swift.cache.host.unsupported", "Swift preview cache commands are supported only on macOS hosts that can run iOS previews.");
			data = await executeSwiftCacheCommand(command, parsed.params);
		} else if (command) data = await executePhoneCommand(command, parsed.params, options.dependencies);
		const envelope = {
			schemaVersion: SCHEMA_VERSION,
			ok: true,
			command,
			data
		};
		stdout.write(`${JSON.stringify(envelope, null, parsed.pretty ? 2 : 0)}\n`);
		return 0;
	} catch (error) {
		const normalized = normalizeError(error);
		const envelope = {
			schemaVersion: SCHEMA_VERSION,
			ok: false,
			...command ? { command } : {},
			error: normalized
		};
		stderr.write(`${JSON.stringify(envelope)}\n`);
		return exitCodeFor(normalized.code);
	}
}
function parseArguments(argv) {
	const tokens = [...argv];
	if (tokens.length === 0 || tokens[0] === "--help" || tokens[0] === "-h" || tokens[0] === "help") return {
		help: true,
		params: {},
		pretty: true
	};
	if (tokens[0] === "--version" || tokens[0] === "-v") return {
		version: true,
		params: {},
		pretty: false
	};
	const rawCommand = tokens.shift();
	const command = rawCommand.replaceAll("-", "_");
	if (![
		...PHONE_COMMANDS,
		...SWIFT_CACHE_COMMANDS,
		...LOCAL_COMMANDS
	].includes(command)) throw cliError("phone.command.unknown", `Unknown command: ${rawCommand}. Run mobile-use --help.`);
	let params = {};
	let pretty = false;
	for (let index = 0; index < tokens.length; index += 1) {
		const token = tokens[index];
		if (token === "--json") continue;
		if (token === "--pretty") {
			pretty = true;
			continue;
		}
		if (!token.startsWith("--")) throw cliError("phone.cli.argument", `Unexpected argument: ${token}`);
		const separator = token.indexOf("=");
		const rawName = separator === -1 ? token.slice(2) : token.slice(2, separator);
		const name = rawName.replaceAll("-", "_");
		let value = separator === -1 ? void 0 : token.slice(separator + 1);
		if (BOOLEAN_FLAGS.has(name) && value === void 0) {
			params[name] = true;
			continue;
		}
		if (value === void 0) {
			index += 1;
			value = tokens[index];
		}
		if (value === void 0 || value.startsWith("--")) throw cliError("phone.cli.argument", `--${rawName} requires a value.`);
		if (JSON_FLAGS.has(name)) {
			const parsed = parseJson(value, rawName);
			const target = JSON_FLAGS.get(name);
			if (target === void 0) {
				if (!isRecord(parsed)) throw cliError("phone.cli.argument", `--${rawName} must contain a JSON object.`);
				params = {
					...params,
					...parsed
				};
			} else params[target] = parsed;
			continue;
		}
		if (NUMBER_FLAGS.has(name)) {
			const number = Number(value);
			if (!Number.isFinite(number)) throw cliError("phone.cli.argument", `--${rawName} must be a number.`);
			params[name] = number;
			continue;
		}
		if (BOOLEAN_FLAGS.has(name)) {
			if (value !== "true" && value !== "false") throw cliError("phone.cli.argument", `--${rawName} must be true or false.`);
			params[name] = value === "true";
			continue;
		}
		params[name] = value;
	}
	return {
		command,
		params,
		pretty
	};
}
function parseJson(value, name) {
	if (Buffer.byteLength(value) > 1048576) throw cliError("phone.cli.argument", `--${name} exceeds the 1 MiB limit.`);
	try {
		return JSON.parse(value);
	} catch (error) {
		throw cliError("phone.cli.argument", `--${name} is not valid JSON: ${error instanceof Error ? error.message : String(error)}`);
	}
}
function normalizeError(error) {
	const message = error instanceof Error ? error.message : String(error);
	const explicitCode = typeof error?.code === "string" ? error.code : void 0;
	let code = explicitCode ?? (error instanceof TypeError ? "phone.cli.argument" : "phone.command.failed");
	if (!explicitCode && !(error instanceof TypeError) && /stale|not found|does not belong|no live session/iu.test(message)) code = "phone.session.unavailable";
	if (!explicitCode && !(error instanceof TypeError) && /revision|assert/iu.test(message)) code = "phone.revision.failed";
	return {
		code,
		message,
		...code.includes("revision") ? { retry: "observe" } : {},
		...isRecord(error?.details) ? { details: error.details } : {}
	};
}
function exitCodeFor(code) {
	if (code === "swift.cache.argument" || code === "swift.cache.command.unknown" || code === "swift.cache.confirmation.required") return 2;
	if (code === "swift.cache.active") return 3;
	if (code === "phone.cli.argument" || code === "phone.command.unknown" || code === "phone.plan.invalid" || code === "phone.plan.step-invalid") return 2;
	if (code.includes("surface") || code.includes("session") || code.includes("target")) return 3;
	if (code.includes("revision") || code.includes("assert") || code.includes("selector")) return 4;
	if (code.includes("capability")) return 5;
	if (code.includes("broker")) return 6;
	return 1;
}
function helpText() {
	return [
		`Mobile Use CLI ${CLI_VERSION}`,
		"",
		"Usage:",
		"  mobile-use <command> [options] [--json]",
		"",
		"Environment:",
		"  doctor [--platform <android|harmony|ios|all>]",
		"",
		"Core commands:",
		"  inventory, list_targets, start_session, stop_session, list_sessions",
		"  observe, tap, long_press, act, wait, assert, run_plan",
		"",
		"Operational commands (CLI only):",
		"  restart_target, manage_app, read_logs, run_native_test, capture_screenshot, record_screen",
		"",
		"Local Swift build cache (macOS only):",
		"  swift_cache_status",
		"  swift_cache_prune [--max-age-days <days>] [--max-size-mb <MiB>] [--include-legacy] [--apply]",
		"  swift_cache_clean (--package-swift <absolute-path> | --cache-identity <id>) --confirm",
		"",
		"Common options:",
		"  --surface-id <id>        Surface returned by list_targets/list_sessions",
		"  --target-id <id>         Target returned by list_targets",
		"  --session-id <id>        Session returned by start_session/list_sessions",
		"  --platform <name>        doctor platform filter",
		"  --params-json <object>   Merge a complete JSON argument object",
		"  --action-json <object>   act action payload",
		"  --plan-json <object>     versioned run_plan workflow",
		"  --duration-ms <number>   long_press duration in milliseconds",
		"  --condition-json <object> wait condition payload",
		"  --selector-json <object> tap/long_press/assert selector payload",
		"  --selector <id>          Exact native test selector for run_native_test",
		"  --test-target <name>     Optional platform test target override",
		"  --test-module <name>     Optional HarmonyOS test module override",
		"  --test-bundle-id <id>    Optional HarmonyOS test bundle override",
		"  --runner <name>          Optional platform runner override",
		"  --pretty                 Pretty-print the JSON envelope",
		"",
		"Drives devices through the host toolchain (adb, hdc, simctl); no vendor plugin or broker required."
	].join("\n");
}
if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
	const exitCode = await runCli(process.argv.slice(2));
	process.exitCode = exitCode;
}
//#endregion
export { parseArguments, runCli };
