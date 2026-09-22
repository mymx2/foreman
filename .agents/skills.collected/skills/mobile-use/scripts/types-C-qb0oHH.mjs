//#region src/lib/types.ts
function cliError(code, message) {
	const error = new Error(message);
	error.code = code;
	return error;
}
function isRecord(value) {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}
//#endregion
export { isRecord as n, cliError as t };
