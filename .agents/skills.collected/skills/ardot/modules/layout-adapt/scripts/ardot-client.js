'use strict';

/**
 * Ardot 数据获取客户端
 *
 * 封装与 Ardot 服务交互的两步探活与 batch_read 数据获取逻辑。
 * 探活接口与数据接口分离，第一步用 HTTP，第二步用 WebSocket：
 *   第一步：ardot mcp 探活及获取数据
 *     探活接口：http://127.0.0.1:50501/api/v1/health（GET）
 *     数据接口：http://127.0.0.1:50501/api/v1/mcp（JSON-RPC tools/call batch_read）
 *     通了 → 用 HTTP mcp 接口获取数据
 *   第二步（第一步不通时）：ardot 沙箱探活
 *     探活接口：http://127.0.0.1:19501/api/v1/health（GET）
 *     数据接口：WebSocket ws://127.0.0.1:19501/ws/adapters（socket.io, tool_request batch_read）
 *     通了 → 用 WebSocket 获取数据（MCP 工具 batch_read）
 *
 * 用法：
 *   const ardot = require('./ardot-client');
 *
 *   // 两步探活（返回探活信息 + 数据获取配置）
 *   const probe = await ardot.probeService();
 *   if (probe) { console.log(probe.source, probe.mode); }
 *
 *   // 获取数据（传入 probe 结果，自动选择 HTTP 或 WebSocket）
 *   const nodes = await ardot.fetchBatchRead(fileId, nodeIds, 5, true, probe);
 *   // 也可以直接传 URL 字符串（HTTP 模式）
 *   const nodes2 = await ardot.fetchBatchRead(fileId, nodeIds, 5, true, 'http://127.0.0.1:50501/api/v1/mcp');
 *
 *   // 单独探活某 health 接口
 *   const ok = await ardot.probeHealth('http://127.0.0.1:50501/api/v1/health');
 */

const http = require('http');

// ============================================================
// 常量
// ============================================================

// 第一步：ardot mcp（端口 50501，HTTP）
const PRIMARY_HEALTH_URL = 'http://127.0.0.1:50501/api/v1/health';
const PRIMARY_MCP_URL = 'http://127.0.0.1:50501/api/v1/mcp';

// 第二步：ardot 沙箱（端口 19501，health 探活 + WebSocket 数据获取）
const SANDBOX_HEALTH_URL = 'http://127.0.0.1:19501/api/v1/health';
const SANDBOX_WS_URL = 'ws://127.0.0.1:19501';
const SANDBOX_WS_PATH = '/ws/adapters';

// 兼容旧引用
const DEFAULT_MCP_URL = PRIMARY_MCP_URL;
const SANDBOX_MCP_URL = SANDBOX_WS_URL; // 兼容：沙箱无 HTTP mcp 端点
const HEALTH_HOST = '127.0.0.1';
const HEALTH_PORT = '19501';
const HEALTH_PATH = '/api/v1/health';

const PROBE_TIMEOUT = 2000;
const WS_FETCH_TIMEOUT = 60000; // WebSocket 数据获取超时 60 秒

// batch_read 需要的属性列表（HTTP 和 WebSocket 共用）
const BATCH_READ_PROPERTIES = [
  'width', 'height', 'type', 'name',
  'layoutMode', 'layoutSizingHorizontal', 'layoutSizingVertical',
  'primaryAxisSizingMode', 'counterAxisSizingMode',
  'primaryAxisAlignItems', 'counterAxisAlignItems',
  'paddingLeft', 'paddingRight', 'paddingTop', 'paddingBottom',
  'itemSpacing', 'layoutAlign', 'layoutGrow',
  'textAutoResize', 'characters',
  'visible',
  'x', 'y',
  'parent'
];

// ============================================================
// URL 解析（字符串拼接方式，不使用 URL 对象）
// ============================================================

/**
 * 通过字符串拼接方式解析 HTTP URL，提取 host / port / path
 * 仅支持 http://host:port/path 格式，不使用 URL 对象
 *
 * @param {string} urlStr - 完整 URL，如 'http://127.0.0.1:50501/api/v1/mcp'
 * @returns {{host: string, port: string, path: string}}
 */
function parseUrlByString(urlStr) {
  // 去掉协议前缀
  let rest = urlStr;
  const proto = 'http://';
  if (rest.indexOf(proto) === 0) {
    rest = rest.slice(proto.length);
  } else if (rest.indexOf('https://') === 0) {
    rest = rest.slice(8);
  }

  // 分离 host:port 和 path
  let hostPort = rest;
  let pathStr = '/';
  const slashIdx = rest.indexOf('/');
  if (slashIdx >= 0) {
    hostPort = rest.slice(0, slashIdx);
    pathStr = rest.slice(slashIdx);
  }

  // 分离 host 和 port
  let host = hostPort;
  let port = '';
  const colonIdx = hostPort.indexOf(':');
  if (colonIdx >= 0) {
    host = hostPort.slice(0, colonIdx);
    port = hostPort.slice(colonIdx + 1);
  }

  return { host: host, port: port, path: pathStr };
}

/**
 * 通过字符串拼接构造请求 options（hostname/port/path）
 * 不使用 URL 对象
 *
 * @param {string} urlStr - 完整 URL
 * @param {string} method - HTTP 方法
 * @param {number} [timeout] - 超时毫秒
 * @param {Object} [headers] - 额外 headers
 * @returns {{hostname: string, port: string, path: string, method: string, timeout?: number, headers?: Object}}
 */
function buildRequestOptions(urlStr, method, timeout, headers) {
  const parsed = parseUrlByString(urlStr);
  const options = {
    hostname: parsed.host,
    port: parsed.port,
    path: parsed.path,
    method: method
  };
  if (typeof timeout === 'number') {
    options.timeout = timeout;
  }
  if (headers) {
    options.headers = headers;
  }
  return options;
}

// ============================================================
// 响应解析
// ============================================================

/**
 * 从 MCP 响应中提取 batch_read 的节点数据
 * 支持多种格式：
 *   - HTTP JSON-RPC: { result: { content: [{ type: "text", text: "..." }] } }
 *   - HTTP JSON-RPC: { result: { data: { nodes: [...] } } }
 *   - WebSocket tool_response: { data: { nodes: [...] } } 或 { data: [...] } 或 { data: { result: {...} } }
 *   - 直接节点数组
 */
function parseBatchReadResponse(jsonRpcResponse) {
  const result = jsonRpcResponse.result;

  // 格式1: 直接返回 data 对象
  if (result && result.data && result.data.nodes) {
    return result.data.nodes;
  }

  // 格式2: 返回 content 数组（MCP 标准格式）
  if (result && result.content && Array.isArray(result.content)) {
    for (const item of result.content) {
      if (item.type === 'text' && item.text) {
        try {
          const parsed = JSON.parse(item.text);
          if (parsed.data && parsed.data.nodes) {
            return parsed.data.nodes;
          }
          if (parsed.nodes) {
            return parsed.nodes;
          }
          if (Array.isArray(parsed)) {
            return parsed;
          }
          // 可能是单个节点对象
          if (parsed.id && parsed.type) {
            return [parsed];
          }
          return parsed;
        } catch (e) {
          // text 不是 JSON，继续
        }
      }
      if (item.type === 'resource' && item.resource) {
        return item.resource;
      }
    }
  }

  // 格式3: result 本身就是数据
  if (result && result.nodes) {
    return result.nodes;
  }

  // 格式4: result 本身就是节点数组
  if (Array.isArray(result)) {
    return result;
  }

  // 格式5: result 是单个节点
  if (result && result.id && result.type) {
    return [result];
  }

  throw new Error(`无法解析 batch_read 响应格式。响应结构: ${JSON.stringify(Object.keys(result || {}))}`);
}

/**
 * 从 WebSocket tool_response 的 data 字段中提取节点数据
 * WebSocket 响应格式可能多种：msg.data 直接是数组、含 nodes、或嵌套 result
 *
 * @param {*} data - WebSocket tool_response 的 data 字段
 * @returns {Object[]} - 节点数据数组
 */
function parseWsBatchReadData(data) {
  if (!data) {
    throw new Error('WebSocket tool_response data 为空');
  }

  // data 本身就是节点数组
  if (Array.isArray(data)) {
    return data;
  }

  // data.data.nodes
  if (data.data && data.data.nodes) {
    return data.data.nodes;
  }

  // data.nodes
  if (data.nodes) {
    return data.nodes;
  }

  // data.data 是数组
  if (Array.isArray(data.data)) {
    return data.data;
  }

  // data.data 是单个节点
  if (data.data && data.data.id && data.data.type) {
    return [data.data];
  }

  // data.result（兼容 JSON-RPC 包装格式）
  if (data.result) {
    return parseBatchReadResponse(data);
  }

  // data 本身是单个节点
  if (data.id && data.type) {
    return [data];
  }

  // 尝试当作 JSON-RPC 响应解析
  try {
    return parseBatchReadResponse(data);
  } catch (e) {
    throw new Error(`无法解析 WebSocket batch_read 数据。data 结构: ${JSON.stringify(Object.keys(data))}`);
  }
}

// ============================================================
// 探活
// ============================================================

/**
 * 通过 health 接口探活（GET 请求，2秒超时）
 * 2xx 状态码即视为健康
 *
 * @param {string} healthUrl - health 接口完整 URL，如 'http://127.0.0.1:50501/api/v1/health'
 * @returns {Promise<boolean>} - 是否可达
 */
function probeHealth(healthUrl) {
  return new Promise((resolve) => {
    const options = buildRequestOptions(healthUrl, 'GET', PROBE_TIMEOUT, {
      'Accept': 'application/json'
    });

    const req = http.request(options, (res) => {
      // 消费响应体，避免内存泄漏
      res.resume();
      res.on('end', () => {
        resolve(res.statusCode >= 200 && res.statusCode < 300);
      });
      res.on('error', () => {
        resolve(false);
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });

    req.on('error', () => {
      resolve(false);
    });

    req.end();
  });
}

/**
 * 探测主 MCP health 端点是否可用（GET /api/v1/health，2秒超时）
 * 仅用于探活，数据获取使用 HTTP mcp 端点
 *
 * @param {string} [healthUrl] - health 端点地址，默认 http://127.0.0.1:50501/api/v1/health
 * @returns {Promise<boolean>} - 是否可达
 */
async function detectMcpAvailable(healthUrl) {
  const targetUrl = healthUrl || PRIMARY_HEALTH_URL;
  return probeHealth(targetUrl);
}

/**
 * 探测沙箱 health 端点是否可用（GET /api/v1/health，2秒超时）
 * 返回 health 接口可用状态及 WebSocket 数据获取配置
 *
 * @param {string} [host] - 主机地址，默认 127.0.0.1
 * @param {string} [port] - 端口，默认 19501
 * @returns {Promise<{available: boolean, healthUrl: string, wsConfig: {url: string, path: string}}>}
 */
async function checkHealthEndpoint(host, port) {
  const h = host || HEALTH_HOST;
  const p = port || HEALTH_PORT;
  const healthUrl = 'http://' + h + ':' + p + HEALTH_PATH;
  const wsConfig = {
    url: 'ws://' + h + ':' + p,
    path: SANDBOX_WS_PATH
  };
  const available = await probeHealth(healthUrl);
  return { available, healthUrl, wsConfig };
}

/**
 * 两步探活，返回探活信息和数据获取配置：
 *   第一步：探测 http://127.0.0.1:50501/api/v1/health
 *           通了 → HTTP 模式，数据接口 http://127.0.0.1:50501/api/v1/mcp
 *   第二步（第一步不通时）：探测 http://127.0.0.1:19501/api/v1/health
 *           通了 → WebSocket 模式，数据接口 ws://127.0.0.1:19501/ws/adapters
 *   都不通 → 返回 null
 *
 * @returns {Promise<Object | null>}
 *   HTTP 模式: { healthUrl, dataUrl, source: 'mcp', mode: 'http' }
 *   WS 模式:   { healthUrl, wsConfig: {url, path}, source: 'sandbox', mode: 'ws' }
 */
async function probeService() {
  // 第一步：探测主 MCP health 端点（50501），通了即用 HTTP mcp 接口获取数据
  const primaryOk = await probeHealth(PRIMARY_HEALTH_URL);
  if (primaryOk) {
    return {
      healthUrl: PRIMARY_HEALTH_URL,
      dataUrl: PRIMARY_MCP_URL,
      source: 'mcp',
      mode: 'http'
    };
  }

  // 第二步：探测沙箱 health 端点（19501），通了即用 WebSocket 获取数据
  const sandboxOk = await probeHealth(SANDBOX_HEALTH_URL);
  if (sandboxOk) {
    return {
      healthUrl: SANDBOX_HEALTH_URL,
      wsConfig: { url: SANDBOX_WS_URL, path: SANDBOX_WS_PATH },
      source: 'sandbox',
      mode: 'ws'
    };
  }

  return null;
}

// ============================================================
// 数据获取 — HTTP 模式
// ============================================================

/**
 * 通过 HTTP 调用 batch_read 获取设计稿节点数据
 * 向 MCP 接口发送 JSON-RPC tools/call 请求
 *
 * @param {string} fileId - 设计稿文件 ID
 * @param {string[]} nodeIds - 要读取的节点 ID 列表
 * @param {number} readDepth - 读取深度
 * @param {boolean} resolveInstances - 是否展开 INSTANCE
 * @param {string} [fetchUrl] - 数据接口地址（mcp 端点），默认 http://127.0.0.1:50501/api/v1/mcp
 * @returns {Promise<Object[]>} - 节点数据数组
 */
function fetchBatchReadViaHttp(fileId, nodeIds, readDepth, resolveInstances, fetchUrl) {
  const targetUrl = fetchUrl || PRIMARY_MCP_URL;

  return new Promise((resolve, reject) => {
    const requestBody = JSON.stringify({
      jsonrpc: '2.0',
      method: 'tools/call',
      params: {
        name: 'batch_read',
        arguments: {
          fileId: fileId,
          nodeIds: nodeIds,
          readDepth: readDepth || 5,
          resolveInstances: resolveInstances !== false,
          properties: BATCH_READ_PROPERTIES
        }
      },
      id: 1
    });

    const options = buildRequestOptions(targetUrl, 'POST', null, {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'Content-Length': Buffer.byteLength(requestBody)
    });

    const req = http.request(options, (res) => {
      let data = '';

      // 处理 SSE 流式响应
      if (res.headers['content-type'] && res.headers['content-type'].includes('text/event-stream')) {
        res.on('data', (chunk) => {
          data += chunk.toString();
        });
        res.on('end', () => {
          // 从 SSE 数据中提取 JSON-RPC 响应
          const lines = data.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonRpcResponse = JSON.parse(line.slice(6));
                if (jsonRpcResponse.result) {
                  resolve(parseBatchReadResponse(jsonRpcResponse));
                  return;
                }
              } catch (e) {
                // 继续尝试下一行
              }
            }
          }
          reject(new Error('无法从 SSE 响应中解析 batch_read 结果'));
        });
      } else {
        // 普通 JSON 响应
        res.on('data', (chunk) => {
          data += chunk.toString();
        });
        res.on('end', () => {
          try {
            const jsonRpcResponse = JSON.parse(data);
            if (jsonRpcResponse.error) {
              reject(new Error(`MCP 错误: ${JSON.stringify(jsonRpcResponse.error)}`));
              return;
            }
            resolve(parseBatchReadResponse(jsonRpcResponse));
          } catch (e) {
            reject(new Error(`解析响应失败: ${e.message}\n响应内容: ${data.slice(0, 500)}`));
          }
        });
      }
    });

    req.on('error', (e) => {
      reject(new Error(`HTTP 请求失败: ${e.message}\n请确认 Ardot 编辑器已打开且服务正在运行 (${targetUrl})`));
    });

    req.write(requestBody);
    req.end();
  });
}

// ============================================================
// 数据获取 — WebSocket 模式（沙箱）
// ============================================================

/**
 * 通过 WebSocket (socket.io) 调用 batch_read 获取设计稿节点数据
 *
 * 流程：
 *   1. 连接 ws://127.0.0.1:19501，path=/ws/adapters
 *   2. 连接成功后发送 register（role: mcp-relay）
 *   3. 收到 register_ack 后发送 tool_request（method: batch_read）
 *   4. 收到 tool_response 后解析 data 并返回
 *
 * @param {string} fileId - 设计稿文件 ID
 * @param {string[]} nodeIds - 要读取的节点 ID 列表
 * @param {number} readDepth - 读取深度
 * @param {boolean} resolveInstances - 是否展开 INSTANCE
 * @param {{url: string, path: string}} [wsConfig] - WebSocket 配置，默认沙箱配置
 * @returns {Promise<Object[]>} - 节点数据数组
 */
function fetchBatchReadViaWs(fileId, nodeIds, readDepth, resolveInstances, wsConfig) {
  const config = wsConfig || { url: SANDBOX_WS_URL, path: SANDBOX_WS_PATH };

  // 动态 require socket.io-client，避免未安装时模块加载失败
  let io;
  try {
    io = require('socket.io-client').io;
  } catch (e) {
    return Promise.reject(new Error(
      'socket.io-client 未安装，无法使用 WebSocket 模式获取数据。\n' +
      '请在 scripts 目录执行: npm install'
    ));
  }

  return new Promise((resolve, reject) => {
    const socket = io(config.url, {
      path: config.path,
      transports: ['websocket'],
      reconnection: false,
      timeout: PROBE_TIMEOUT
    });

    let settled = false;

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { socket.disconnect(); } catch (e) {}
      reject(new Error(`WebSocket batch_read 超时（${WS_FETCH_TIMEOUT / 1000}秒）`));
    }, WS_FETCH_TIMEOUT);

    socket.on('connect', () => {
      // 注册为 mcp-relay
      socket.emit('message', {
        type: 'register',
        role: 'mcp-relay'
      });
    });

    socket.on('message', (msg) => {
      // 收到注册确认 → 发送 batch_read 请求
      if (msg.type === 'register_ack') {
        socket.emit('message', {
          type: 'tool_request',
          id: 1,
          method: 'batch_read',
          params: {
            fileId: fileId,
            nodeIds: nodeIds,
            readDepth: readDepth || 5,
            resolveInstances: resolveInstances !== false,
            properties: BATCH_READ_PROPERTIES
          }
        });
        return;
      }

      // 收到工具响应 → 解析并返回
      if (msg.type === 'tool_response') {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        try { socket.disconnect(); } catch (e) {}

        try {
          const nodes = parseWsBatchReadData(msg.data);
          resolve(nodes);
        } catch (e) {
          reject(new Error(`WebSocket batch_read 响应解析失败: ${e.message}`));
        }
        return;
      }

      // 错误响应
      if (msg.type === 'error' || msg.type === 'tool_error') {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        try { socket.disconnect(); } catch (e) {}
        reject(new Error(`WebSocket batch_read 错误: ${JSON.stringify(msg.error || msg.message || msg)}`));
        return;
      }
    });

    socket.on('connect_error', (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(new Error(`WebSocket 连接失败: ${err.message}`));
    });

    socket.on('disconnect', (reason) => {
      if (settled) return;
      // 如果是服务端主动断开且未收到响应，视为错误
      if (reason === 'io server disconnect' || reason === 'transport close') {
        settled = true;
        clearTimeout(timeout);
        reject(new Error(`WebSocket 连接断开（未收到响应）: ${reason}`));
      }
    });
  });
}

// ============================================================
// 数据获取 — 统一入口（自动选择 HTTP 或 WebSocket）
// ============================================================

/**
 * 调用 batch_read 获取设计稿节点数据（统一入口）
 *
 * 根据第 5 个参数自动选择传输方式：
 *   - 字符串 URL → HTTP 模式
 *   - probeService() 返回的对象（含 mode 字段）→ 按 mode 选择
 *   - 未传或 null → 默认 HTTP 模式（主 MCP 端点）
 *
 * @param {string} fileId - 设计稿文件 ID
 * @param {string[]} nodeIds - 要读取的节点 ID 列表
 * @param {number} readDepth - 读取深度
 * @param {boolean} resolveInstances - 是否展开 INSTANCE
 * @param {string|Object} [fetchConfig] - 数据获取配置：
 *   - 字符串: HTTP mcp 端点 URL
 *   - 对象: probeService() 返回值，含 mode/dataUrl/wsConfig
 * @returns {Promise<Object[]>} - 节点数据数组
 */
async function fetchBatchRead(fileId, nodeIds, readDepth, resolveInstances, fetchConfig) {
  // 字符串 → HTTP 模式（向后兼容）
  if (typeof fetchConfig === 'string') {
    return fetchBatchReadViaHttp(fileId, nodeIds, readDepth, resolveInstances, fetchConfig);
  }

  // 对象 → 按 mode 分发
  if (fetchConfig && typeof fetchConfig === 'object') {
    if (fetchConfig.mode === 'ws') {
      return fetchBatchReadViaWs(fileId, nodeIds, readDepth, resolveInstances, fetchConfig.wsConfig);
    }
    // mode === 'http' 或其他 → HTTP
    const url = fetchConfig.dataUrl || fetchConfig.url || PRIMARY_MCP_URL;
    return fetchBatchReadViaHttp(fileId, nodeIds, readDepth, resolveInstances, url);
  }

  // 默认 HTTP 模式
  return fetchBatchReadViaHttp(fileId, nodeIds, readDepth, resolveInstances, PRIMARY_MCP_URL);
}

// ============================================================
// 导出
// ============================================================

module.exports = {
  // 常量
  PRIMARY_HEALTH_URL,
  PRIMARY_MCP_URL,
  SANDBOX_HEALTH_URL,
  SANDBOX_WS_URL,
  SANDBOX_WS_PATH,
  // 兼容旧引用
  DEFAULT_MCP_URL,
  SANDBOX_MCP_URL,
  HEALTH_HOST,
  HEALTH_PORT,
  HEALTH_PATH,
  BATCH_READ_PROPERTIES,
  // URL 解析（字符串拼接）
  parseUrlByString,
  buildRequestOptions,
  // 探活
  probeHealth,
  detectMcpAvailable,
  checkHealthEndpoint,
  probeService,
  // 数据获取
  fetchBatchRead,
  fetchBatchReadViaHttp,
  fetchBatchReadViaWs,
  // 响应解析
  parseBatchReadResponse,
  parseWsBatchReadData
};
