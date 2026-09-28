/**
 * 设计稿自动布局文本适配脚本
 *
 * 实现 SKILL.md 中的确定性算法：
 * 1. 第一章 硬性过滤（visible: false 整棵子树跳过）
 * 2. 第二章 扫描范围（普通文本 + INSTANCE 内部文本，分号路径格式）
 * 3. 第四章 分类判定（4.1 六策略 Match-First + 4.2 四级溢出分级 + 4.3 Gate 校验 + 4.4 表格输出）
 * 4. 第三章/5.1/6.2 Height 规则 + padding 补偿计算
 * 5. 6.1 容器链水平宽度检查（遍历 parent 链，INSTANCE 同等对待）
 * 6. 第六章 修复操作生成（外→内拓扑排序，Phase A 容器 / Phase B 文本，每批 ≤25）
 *
 * 数据获取方式（两步探活，探活接口与数据接口分离）：
 *   第一步：探活 http://127.0.0.1:50501/api/v1/health（GET）
 *           通了 → HTTP 数据接口 http://127.0.0.1:50501/api/v1/mcp（JSON-RPC batch_read）
 *   第二步（第一步不通时）：探活 http://127.0.0.1:19501/api/v1/health（GET）
 *           通了 → WebSocket 数据接口 ws://127.0.0.1:19501/ws/adapters（socket.io batch_read）
 *
 * 用法（CLI）：
 *   node layout-adaptation.js --detect
 *     两步探活检测可用接口
 *
 *   node layout-adaptation.js --fetch --fileId <文件ID> --nodeIds <id1,id2> [--output <out.json>] [--report <report.md>]
 *     未指定 --mcpUrl 时，脚本自动两步探活选择可用接口获取数据
 *     指定 --mcpUrl <url> 时，直接使用该 URL
 *
 * 用法（程序化调用）：
 *   const { executeLayoutAdaptation } = require('./layout-adaptation');
 *   const result = executeLayoutAdaptation(batchReadResult);
 *   // result.classification  → 分类表（4.4 格式）
 *   // result.chainCheck      → 容器链检查结果（6.1 格式）
 *   // result.operations      → 分批的 batch_edit U() 操作
 */

'use strict';

// ============================================================
// 常量
// ============================================================

const STRUCTURAL_CHILD_KEYS = ['children', 'nodes', 'items', 'rows', 'elements'];
const BATCH_SIZE = 25;

// ============================================================
// 基础工具：属性读取（兼容 Ardot 多种命名变体）
// ============================================================

function getNodeId(node) {
  return node?.id || node?.nodeId || null;
}

function getNodeType(node) {
  const t = node?.type || node?.nodeType || '';
  return typeof t === 'string' ? t.toUpperCase() : '';
}

function getNodeName(node) {
  return typeof node?.name === 'string' ? node.name : '';
}

function getTextContent(node) {
  const text = node?.characters ?? node?.content ?? node?.text;
  return typeof text === 'string' ? text : '';
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function getNumericProp(node, key) {
  const v = node?.[key];
  return isFiniteNumber(v) ? v : 0;
}

function getNodeNumericWidth(node) {
  if (!node) return null;
  const w = node.width ?? node.absoluteBoundingBox?.width;
  return isFiniteNumber(w) ? w : null;
}

function getNodeNumericHeight(node) {
  if (!node) return null;
  const h = node.height ?? node.absoluteBoundingBox?.height;
  return isFiniteNumber(h) ? h : null;
}

function isNodeHidden(node) {
  if (!node || typeof node !== 'object') return false;
  return node.visible === false;
}

function isTextNode(node) {
  return getNodeType(node) === 'TEXT';
}

function isInstanceNode(node) {
  const t = getNodeType(node);
  return t === 'INSTANCE' || t === 'REF';
}

function scoreNode(node) {
  const childScore = STRUCTURAL_CHILD_KEYS.reduce(
    (sum, key) => sum + (Array.isArray(node?.[key]) ? node[key].length * 10 : 0),
    0
  );
  const keyScore = node && typeof node === 'object' ? Object.keys(node).length : 0;
  return childScore + keyScore;
}

// ============================================================
// 布局属性读取
// ============================================================

function normalizeLayoutMode(node) {
  const layout = node?.layoutMode ?? node?.layout;
  return typeof layout === 'string' ? layout.toUpperCase() : 'NONE';
}

function hasAutoLayout(node) {
  const m = normalizeLayoutMode(node);
  return m === 'HORIZONTAL' || m === 'VERTICAL' || m === 'WRAP';
}

/**
 * 将 Ardot 的 primaryAxisSizingMode/counterAxisSizingMode 值映射为标准 FIXED/FILL/HUG
 */
function mapSizingMode(mode) {
  if (!mode || typeof mode !== 'string') return null;
  const upper = mode.toUpperCase();
  if (upper === 'FIXED') return 'FIXED';
  if (upper.includes('RESIZE_TO_FIT') || upper === 'AUTO' || upper === 'HUG') return 'HUG';
  if (upper === 'FILL') return 'FILL';
  return null;
}

/**
 * 获取节点水平尺寸模式
 * 优先级：layoutSizingHorizontal > primaryAxisSizingMode/counterAxisSizingMode（按 layoutMode 判断） > layoutAlign=STRETCH > width 值
 */
function getSizingHorizontal(node) {
  if (!node) return 'UNKNOWN';

  // 1. 标准 layoutSizingHorizontal 属性
  if (node.layoutSizingHorizontal) return node.layoutSizingHorizontal;

  // 1.5. TEXT 节点：batch_read 不带 properties 时无 layoutSizingHorizontal，
  //      通过 textAutoResize + layoutGrow 推断
  if (isTextNode(node)) {
    const ar = getTextAutoResize(node);
    if (ar === 'WIDTH_AND_HEIGHT') return 'HUG';
    if (ar === 'HEIGHT') {
      // HEIGHT = 宽度受限、高度自适应；layoutGrow=1 → FILL，否则 FIXED
      return node.layoutGrow === 1 ? 'FILL' : 'FIXED';
    }
  }

  // 2. Ardot 的 primaryAxisSizingMode / counterAxisSizingMode（按 layoutMode 判断主次轴）
  const layoutMode = normalizeLayoutMode(node);
  if (layoutMode === 'HORIZONTAL') {
    // 水平布局：主轴=宽度 → primaryAxisSizingMode 控制宽度
    const mapped = mapSizingMode(node.primaryAxisSizingMode);
    if (mapped) return mapped;
  } else if (layoutMode === 'VERTICAL') {
    // 垂直布局：交叉轴=宽度 → counterAxisSizingMode 控制宽度
    const mapped = mapSizingMode(node.counterAxisSizingMode);
    if (mapped) return mapped;
  }

  // 3. layoutAlign: STRETCH 表示在父级 auto-layout 中水平拉伸（仅当父级为 VERTICAL 时）
  if (node.layoutAlign === 'STRETCH') return 'FILL';

  // 4. width 值推断
  if (node.width === 'fill_container') return 'FILL';
  if (node.width === 'hug_contents') return 'HUG';
  if (isFiniteNumber(node.width)) return 'FIXED';

  return 'UNKNOWN';
}

/**
 * 获取节点垂直尺寸模式
 */
function getSizingVertical(node) {
  if (!node) return 'UNKNOWN';

  // 1. 标准 layoutSizingVertical 属性
  if (node.layoutSizingVertical) return node.layoutSizingVertical;

  // 2. Ardot 的 primaryAxisSizingMode / counterAxisSizingMode（按 layoutMode 判断主次轴）
  const layoutMode = normalizeLayoutMode(node);
  if (layoutMode === 'HORIZONTAL') {
    // 水平布局：交叉轴=高度 → counterAxisSizingMode 控制高度
    const mapped = mapSizingMode(node.counterAxisSizingMode);
    if (mapped) return mapped;
  } else if (layoutMode === 'VERTICAL') {
    // 垂直布局：主轴=高度 → primaryAxisSizingMode 控制高度
    const mapped = mapSizingMode(node.primaryAxisSizingMode);
    if (mapped) return mapped;
  }

  // 3. height 值推断
  if (node.height === 'fill_container') return 'FILL';
  if (node.height === 'hug_contents') return 'HUG';
  if (isFiniteNumber(node.height)) return 'FIXED';

  return 'UNKNOWN';
}

function getTextAutoResize(node) {
  return node?.textAutoResize || 'NONE';
}

function isTextFixedWidth(node) {
  // 文本宽度固定 = textAutoResize 不是 WIDTH_AND_HEIGHT（即 HEIGHT 或 NONE）
  const ar = getTextAutoResize(node);
  return ar === 'HEIGHT' || ar === 'NONE';
}

/**
 * 推断父容器的左侧 padding。
 * batch_read 不总是返回 paddingLeft/paddingRight，需要从子节点位置推断。
 * HORIZONTAL 布局中，第一个子节点的 x = paddingLeft。
 */
function inferPaddingLeft(parentNode) {
  // 仅对 auto-layout 容器推断 padding；Group/NONE 为绝对定位，不推断
  const layoutMode = normalizeLayoutMode(parentNode);
  if (layoutMode === 'NONE') return 0;
  const children = getStructuralChildren(parentNode);
  if (children.length === 0) return 0;
  const firstX = getNumericProp(children[0], 'x');
  return firstX > 0 ? firstX : 0;
}

/**
 * 推断父容器的右侧 padding。
 * HORIZONTAL 布局中，最后一个子节点的右边界到父容器右边缘的距离 = paddingRight。
 */
function inferPaddingRight(parentNode) {
  // 仅对 auto-layout 容器推断 padding；Group/NONE 为绝对定位，不推断
  const layoutMode = normalizeLayoutMode(parentNode);
  if (layoutMode === 'NONE') return 0;
  const w = getNodeNumericWidth(parentNode);
  if (w == null) return 0;
  const children = getStructuralChildren(parentNode);
  if (children.length === 0) return 0;
  const last = children[children.length - 1];
  const lastRight = getNumericProp(last, 'x') + getNumericProp(last, 'width');
  const inferred = w - lastRight;
  return inferred > 0 ? inferred : 0;
}

function getParentAvailableWidth(parentNode) {
  const w = getNodeNumericWidth(parentNode);
  if (w == null) return 0;

  // 优先使用显式 paddingLeft/paddingRight；缺失时从子节点位置推断
  let padL;
  if (typeof parentNode?.paddingLeft === 'number') {
    padL = parentNode.paddingLeft;
  } else {
    padL = inferPaddingLeft(parentNode);
  }

  let padR;
  if (typeof parentNode?.paddingRight === 'number') {
    padR = parentNode.paddingRight;
  } else {
    padR = inferPaddingRight(parentNode);
  }

  return w - padL - padR;
}

/**
 * 计算文本在父容器中的实际可用宽度。
 *
 * 在 HORIZONTAL 布局中，文本与兄弟元素（如图标）共享水平空间，
 * 仅用 parentWidth - padding 会高估可用宽度，导致溢出漏检。
 * 本函数在 HORIZONTAL 布局时额外扣除兄弟元素宽度与 itemSpacing。
 *
 * @param {Object} parentNode - 父容器节点
 * @param {string} textId - 文本节点的完整 ID（分号路径）
 * @param {Map} index - 节点索引（buildNodeIndex 产物）
 * @returns {number} 文本实际可用宽度
 */
function getAvailableWidthForText(parentNode, textId, index) {
  const base = getParentAvailableWidth(parentNode);

  // 仅 HORIZONTAL 布局需扣除兄弟元素
  const layoutMode = normalizeLayoutMode(parentNode);
  if (layoutMode !== 'HORIZONTAL' || !index || !textId) {
    return base;
  }

  const textInfo = index.get(textId);
  const parentId = textInfo?.parentId;
  const parentInfo = parentId ? index.get(parentId) : null;
  if (!parentInfo || parentInfo.childIds.length <= 1) {
    return base;
  }

  const itemSpacing = getNumericProp(parentNode, 'itemSpacing');
  let siblingWidthsSum = 0;

  parentInfo.childIds.forEach(childId => {
    if (childId === textId) return; // 跳过文本自身
    const childInfo = index.get(childId);
    if (childInfo) {
      const childW = getNodeNumericWidth(childInfo.node);
      if (childW && childW > 0) {
        siblingWidthsSum += childW;
      }
    }
  });

  // SPACE_BETWEEN / SPACE_EVENLY 模式不使用 itemSpacing，间距由布局自动分配
  const primaryAxisAlign = parentNode?.primaryAxisAlignItems || parentNode?.primaryAxisAlignItems || '';
  const usesItemSpacing = primaryAxisAlign !== 'SPACE_BETWEEN' && primaryAxisAlign !== 'SPACE_EVENLY';

  // 间距数 = (子元素总数 - 1)，文本自身也参与间距排列
  const gapTotal = usesItemSpacing ? itemSpacing * (parentInfo.childIds.length - 1) : 0;

  return base - siblingWidthsSum - gapTotal;
}

function nonCJKRatio(text) {
  if (!text || !text.length) return 0;
  const cjk = (text.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || []).length;
  return (text.length - cjk) / text.length;
}

function hasParagraphPunctuation(text) {
  if (!text) return false;
  return /[。.]/.test(text) || text.includes('\n');
}

// ============================================================
// 节点遍历与索引（处理 INSTANCE 分号路径）
// ============================================================

function getStructuralChildren(node) {
  const children = [];
  STRUCTURAL_CHILD_KEYS.forEach(key => {
    const value = node?.[key];
    if (Array.isArray(value)) {
      value.forEach(item => children.push(item));
    }
  });
  return children;
}

/**
 * 构建完整路径 ID（INSTANCE 内部节点使用 instanceId;childId 格式）
 */
function buildFullId(rawId, instancePrefix) {
  if (!rawId) return null;
  if (!instancePrefix) return rawId;
  if (rawId.includes(';') || rawId.startsWith(instancePrefix + ';')) return rawId;
  return `${instancePrefix};${rawId}`;
}

function traverseNodes(data, visitor, parentHidden = false, parentId = null, instancePrefix = '') {
  if (!data || typeof data !== 'object') return;

  if (Array.isArray(data)) {
    data.forEach(item => traverseNodes(item, visitor, parentHidden, parentId, instancePrefix));
    return;
  }

  const currentHidden = parentHidden || isNodeHidden(data);
  const rawId = getNodeId(data);
  const fullId = buildFullId(rawId, instancePrefix);

  visitor(data, { hidden: currentHidden, parentId, fullId, instancePrefix });

  if (currentHidden) return;

  // INSTANCE 节点的子节点需要用 instance ID 作为路径前缀
  const childInstancePrefix = isInstanceNode(data) && fullId ? fullId : instancePrefix;

  getStructuralChildren(data).forEach(child => {
    traverseNodes(child, visitor, currentHidden, fullId, childInstancePrefix);
  });
}

function buildNodeIndex(data) {
  const index = new Map();

  traverseNodes(data, (node, meta) => {
    const id = meta.fullId;
    if (!id) return;

    const nextInfo = {
      id,
      node,
      parentId: meta.parentId,
      hidden: meta.hidden,
      childIds: []
    };

    const existing = index.get(id);
    if (!existing || scoreNode(node) >= scoreNode(existing.node)) {
      index.set(id, nextInfo);
    }
  });

  // 通过 parentId 反向构建 childIds
  index.forEach(info => {
    if (info.parentId && index.has(info.parentId)) {
      const parent = index.get(info.parentId);
      if (!parent.childIds.includes(info.id)) {
        parent.childIds.push(info.id);
      }
    }
  });

  return index;
}

function getNodeDepth(index, nodeId) {
  let depth = 0;
  let current = index.get(nodeId);
  while (current?.parentId && depth < 200) {
    depth += 1;
    current = index.get(current.parentId);
  }
  return depth;
}

// ============================================================
// 第一章 硬性过滤 + 第二章 扫描范围
// 提取所有可见文本节点（普通文本 + INSTANCE 内部文本）
// ============================================================

function extractAllTexts(data) {
  const results = [];
  const seen = new Set();

  traverseNodes(data, (node, meta) => {
    if (meta.hidden || !isTextNode(node)) return;
    const id = meta.fullId;
    if (!id || seen.has(id)) return;
    seen.add(id);
    results.push({ id, text: getTextContent(node), parentId: meta.parentId });
  });

  return results;
}

// ============================================================
// 压缩子节点检测与自动补充读取
// batch_read 返回数据中，子节点过多时 children 会压缩为 "..."
// 导致深层子树中的文本节点被遗漏
// ============================================================

/**
 * 遍历数据树，收集所有 children 被压缩为 "..." 的节点
 * 返回 fullId（含 INSTANCE 分号路径），以便 autoExpandCompressedNodes
 * 能正确提取 INSTANCE 根 ID 进行补充读取
 * @returns {Array<{id: string, node: Object}>}
 */
function findCompressedNodes(data) {
  const compressed = [];
  function walk(node, instancePrefix) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(item => walk(item, instancePrefix)); return; }

    const rawId = getNodeId(node);
    const fullId = buildFullId(rawId, instancePrefix);
    const isInst = isInstanceNode(node);
    const childPrefix = isInst && fullId ? fullId : instancePrefix;

    for (const key of STRUCTURAL_CHILD_KEYS) {
      const v = node[key];
      if (v === '...') {
        const idToUse = fullId || rawId;
        if (idToUse && !compressed.some(c => c.id === idToUse)) {
          compressed.push({ id: idToUse, node });
        }
      } else if (Array.isArray(v)) {
        v.forEach(child => walk(child, childPrefix));
      }
    }
  }
  walk(data, '');
  return compressed;
}

/**
 * 构建原始数据树中所有节点的 ID → 节点引用 Map（含分号路径节点）
 */
function buildNodeRefMap(data) {
  const map = new Map();
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    const id = getNodeId(node);
    if (id) map.set(id, node);
    for (const key of STRUCTURAL_CHILD_KEYS) {
      const v = node[key];
      if (Array.isArray(v)) v.forEach(walk);
    }
  }
  walk(data);
  return map;
}

/**
 * 将补充读取的节点数据合并到原始数据树中
 * 用补充读取的完整 children 替换原始节点中的 "..." 压缩标记
 */
function mergeExpandedData(originalData, expandedNodes) {
  const refMap = buildNodeRefMap(originalData);
  for (const expanded of expandedNodes) {
    if (!expanded || typeof expanded !== 'object') continue;
    const id = getNodeId(expanded);
    if (!id) continue;
    const original = refMap.get(id);
    if (original) {
      for (const key of STRUCTURAL_CHILD_KEYS) {
        if (Array.isArray(expanded[key])) {
          original[key] = expanded[key];
        }
      }
    }
  }
}

/**
 * 自动展开被压缩的子节点（持续补充读取直到完全展开）
 * @param {Object[]} nodes - 原始 batch_read 返回的节点数组
 * @param {string} fileId - 文件 ID
 * @param {boolean} resolveInstances - 是否展开 INSTANCE
 * @param {string|Object} fetchConfig - 数据获取配置（URL 字符串或 probeService 结果）
 * @param {number} _maxRounds - 已废弃，保留兼容；实际无限轮次直到完全展开
 * @param {number} readDepth - 补充读取的初始深度（默认 5）
 */
async function autoExpandCompressedNodes(nodes, fileId, resolveInstances, fetchConfig, _maxRounds, readDepth) {
  const BATCH_SIZE = 20;
  const MAX_SAFETY_ROUNDS = 50;       // 安全上限
  const MAX_STALL = 5;                 // 最大停滞次数（连续无进展后放弃）
  const DEPTH_INCREMENT = 3;           // 停滞时每次递增的读取深度

  let currentReadDepth = readDepth || 5;
  let lastCompressedKey = '';
  let stallCount = 0;

  for (let round = 1; round <= MAX_SAFETY_ROUNDS; round++) {
    const compressed = findCompressedNodes(nodes);
    if (compressed.length === 0) {
      console.log(`  ✓ 所有压缩子节点已展开（共 ${round - 1} 轮）`);
      return;
    }

    // 用排序后的 ID 列表生成指纹，检测是否停滞
    const currentKey = compressed.map(c => c.id).sort().join(',');
    if (currentKey === lastCompressedKey) {
      stallCount++;
      currentReadDepth += DEPTH_INCREMENT;
      if (stallCount > MAX_STALL) {
        console.log(`  ⚠ 连续 ${MAX_STALL} 次无进展，放弃展开剩余 ${compressed.length} 个节点（已尝试读取深度 ${currentReadDepth}）`);
        compressed.forEach(c => {
          console.log(`    - ${c.id} (${c.node?.name || '?'}, type=${c.node?.type || '?'})`);
        });
        return;
      }
      console.log(`  第 ${round} 轮: 检测到 ${compressed.length} 个被压缩的子节点（停滞，提升读取深度至 ${currentReadDepth}）...`);
    } else {
      stallCount = 0;
      console.log(`  第 ${round} 轮: 检测到 ${compressed.length} 个被压缩的子节点，补充读取...`);
    }
    lastCompressedKey = currentKey;

    // 构建需要补充读取的节点 ID 列表
    // 分号路径节点（INSTANCE 内部）取分号前的 INSTANCE 实例 ID
    const readIdSet = new Set();
    for (const c of compressed) {
      const id = c.id.includes(';') ? c.id.split(';')[0] : c.id;
      readIdSet.add(id);
    }

    const readIds = Array.from(readIdSet);

    // 分批补充读取
    for (let i = 0; i < readIds.length; i += BATCH_SIZE) {
      const batch = readIds.slice(i, i + BATCH_SIZE);
      try {
        const expanded = await fetchBatchRead(fileId, batch, currentReadDepth, resolveInstances, fetchConfig);
        mergeExpandedData(nodes, expanded);
      } catch (e) {
        console.error(`  补充读取批次失败: ${e.message}`);
      }
    }
  }

  // 最终统计
  const remaining = findCompressedNodes(nodes);
  if (remaining.length > 0) {
    console.log(`  ⚠ 已达安全上限 ${MAX_SAFETY_ROUNDS} 轮，仍有 ${remaining.length} 个节点未完全展开`);
  } else {
    console.log(`  ✓ 所有压缩子节点已展开（共 ${MAX_SAFETY_ROUNDS} 轮）`);
  }
}

// ============================================================
// 第四章 分类判定
// ============================================================

/**
 * 4.1 策略分类（Match-First，按顺序匹配）
 */
/**
 * 检测父容器是否为按钮/标签类组件
 * 特征：HORIZONTAL auto-layout + 单文本子元素 + 有 padding + 宽度跟随内容
 * 这类组件的宽度应 hug 内容，不能改为 fill（否则按钮会撑满父容器）
 *
 * 排除条件（避免误判）：
 * 1. 文本内容过长（>30 字符）→ 段落描述，不是按钮/标签
 * 2. HUG 容器实际宽度已溢出父容器 → 按钮不应溢出父容器，溢出说明是描述性文本
 * 3. 兄弟节点一致性：祖父级为 auto-layout 列表，且兄弟中 FILL 占多数（≥2）→ 列表项，非按钮
 */
function isButtonOrTagContainer(parentNode, parentInfo, index) {
  if (!parentNode || !parentInfo) return false;

  // 必须是 HORIZONTAL auto-layout
  const layoutMode = normalizeLayoutMode(parentNode);
  if (layoutMode !== 'HORIZONTAL') return false;

  // 必须有 padding（按钮/标签通常有内边距，水平或垂直均可）
  // 某些 tab 按钮风格只有垂直 padding（靠 itemSpacing 控制水平间距），不能漏判
  const padL = getNumericProp(parentNode, 'paddingLeft') || 0;
  const padR = getNumericProp(parentNode, 'paddingRight') || 0;
  const padT = getNumericProp(parentNode, 'paddingTop') || 0;
  const padB = getNumericProp(parentNode, 'paddingBottom') || 0;
  if (padL === 0 && padR === 0 && padT === 0 && padB === 0) return false;

  // 子元素数量少（1-3个，典型为图标+文本 或 纯文本）
  if (!parentInfo.childIds || parentInfo.childIds.length === 0 || parentInfo.childIds.length > 3) return false;

  // 至少包含一个 TEXT 子元素
  const textChildInfo = parentInfo.childIds.map(id => index.get(id)).find(info =>
    info && info.node && info.node.type === 'TEXT'
  );
  if (!textChildInfo) return false;

  // 排除条件 1：文本内容过长（>30 字符）→ 段落描述，不是按钮/标签
  // 按钮/标签文本通常很短（如 "Save"、"Cancel"、"确定"、"+18909879088"）
  const textContent = getTextContent(textChildInfo.node);
  if (textContent.length > 30) return false;

  // 排除条件 2：HUG 容器实际宽度已溢出父容器 → 不是按钮
  // 按钮宽度 hug 内容后不应超出父容器，溢出说明是长描述文本撑破了容器
  const parentSizingH = getSizingHorizontal(parentNode);
  if (parentSizingH === 'HUG' && parentInfo.parentId) {
    const grandparentInfo = index.get(parentInfo.parentId);
    if (grandparentInfo) {
      const parentW = getNodeNumericWidth(parentNode);
      const grandparentAvailW = getAvailableWidthForText(grandparentInfo.node, parentInfo.id, index);
      if (parentW != null && grandparentAvailW > 0 && parentW > grandparentAvailW + 1) {
        return false; // HUG 容器溢出父容器，不是按钮
      }
    }
  }

  // 排除条件 3：兄弟节点一致性检查
  // 场景：侧边栏菜单、表格行等列表容器中，菜单子项/行容器结构与按钮相似
  // （HORIZONTAL + padding + 含 TEXT + 子元素≤3），但实际是列表项，宽度应 FILL
  // 判定：祖父级为 VERTICAL/HORIZONTAL auto-layout，且兄弟节点中 FILL 模式占多数（≥2）
  // 此时当前节点不是独立按钮，而是列表项 → 不应 hug，应跟随兄弟设为 FILL
  if (parentInfo.parentId) {
    const grandparentInfo = index.get(parentInfo.parentId);
    if (grandparentInfo && grandparentInfo.node) {
      const grandparentLayoutMode = normalizeLayoutMode(grandparentInfo.node);
      if (grandparentLayoutMode === 'VERTICAL' || grandparentLayoutMode === 'HORIZONTAL') {
        // 统计兄弟节点（排除自身）的水平 sizing 模式
        const siblings = (grandparentInfo.childIds || [])
          .filter(id => id !== parentInfo.id)
          .map(id => index.get(id))
          .filter(info => info && info.node);

        if (siblings.length >= 2) {
          const fillCount = siblings.filter(info =>
            getSizingHorizontal(info.node) === 'FILL'
          ).length;

          // FILL 兄弟占多数（≥2 个）→ 列表项场景，不是按钮
          if (fillCount >= 2) {
            return false;
          }
        }
      }
    }
  }

  // 满足结构特征即可判定为按钮/标签类组件
  return true;
}

function classifyStrategy(textNode, parentNode, index, textId) {
  const textW = getNodeNumericWidth(textNode) || 0;
  const parentAvailW = getAvailableWidthForText(parentNode, textId, index);
  const textAR = getTextAutoResize(textNode);
  const parentSizingH = getSizingHorizontal(parentNode);
  const parentLayoutMode = normalizeLayoutMode(parentNode);
  const content = getTextContent(textNode);

  // 获取 siblingCount
  const parentInfo = index.get(getNodeId(parentNode)) || index.get(textNode?.id);
  let siblingCount = 0;
  if (parentInfo) {
    siblingCount = parentInfo.childIds.length;
  }

  // 0. BUTTON_TAG: 按钮/标签类组件 — 宽度应 hug 内容，不 fill
  //    优先级最高，避免被 CONTAINER_OVERFLOW 误判为 fill
  if (isButtonOrTagContainer(parentNode, parentInfo, index)) {
    return 'BUTTON_TAG';
  }

  // 1. CONTAINER_OVERFLOW
  if (textAR === 'WIDTH_AND_HEIGHT' && parentSizingH === 'FIXED' && textW > parentAvailW) {
    return 'CONTAINER_OVERFLOW';
  }

  // 2. SINGLE_LABEL: 父容器 HORIZONTAL + siblingCount=1 + text FIXED width
  if (parentLayoutMode === 'HORIZONTAL' && siblingCount === 1 && isTextFixedWidth(textNode)) {
    return 'SINGLE_LABEL';
  }

  // 3. HUG_PARENT: 父容器 FIXED + 所有直接子元素在主轴方向均非纯 FIXED + 子内容总宽度 > 父容器宽度
  //    「纯 FIXED」= sizingH === 'FIXED' 且 layoutGrow 不为 1
  if (parentSizingH === 'FIXED' && parentInfo) {
    const allChildrenNonPureFixed = parentInfo.childIds.every(childId => {
      const childInfo = index.get(childId);
      if (!childInfo) return true; // 无法判定，保守放行
      const sizingH = getSizingHorizontal(childInfo.node);
      if (sizingH === 'FIXED' && childInfo.node?.layoutGrow !== 1) {
        return false; // 纯 FIXED，子元素宽度是设计固定值，父容器不应该 HUG
      }
      return true; // HUG / FILL / FIXED+layoutGrow:1，宽度由内容或布局决定
    });
    if (allChildrenNonPureFixed) {
      // 计算子内容总宽度（递归计算，FIXED 容器取其子内容真实需要宽度）
      const totalChildContentWidth = computeTotalChildContentWidth(parentInfo, index);
      const parentW = getNodeNumericWidth(parentNode) || 0;
      if (totalChildContentWidth > parentW + 1) {
        return 'HUG_PARENT';
      }
    }
  }

  // 4. PREVENTIVE_FILL
  if (
    textAR === 'WIDTH_AND_HEIGHT' &&
    parentLayoutMode !== 'NONE' &&
    (parentSizingH === 'FIXED' || parentSizingH === 'FILL')
  ) {
    return 'PREVENTIVE_FILL';
  }

  // 4. PARAGRAPH: 含句号(。.) 且 字数>6
  if (hasParagraphPunctuation(content) && content.length > 6) {
    return 'PARAGRAPH';
  }

  // 5. TITLE: 无上述标点 + 字数≤10 + 父容器 NONE 或 HORIZONTAL；非CJK字符>50% 同样归入
  // 到这里说明：不含句号/\n 或 字数≤6（第4条未命中，AND 逻辑）
  // 字数≤6 必然 ≤10，无上述标点也必然满足
  if (parentLayoutMode === 'NONE' || parentLayoutMode === 'HORIZONTAL') {
    return 'TITLE';
  }
  if (nonCJKRatio(content) > 0.5) {
    return 'TITLE';
  }

  // 6. FALLBACK
  return 'FALLBACK';
}

/**
 * 4.2 溢出分级 — 双层溢出检测（前置门槛）
 *
 * 第一层：文本是否溢出父容器（textW > parentAvailableW）
 * 第二层：父容器是否溢出祖父容器（parentW > grandparentAvailableW）
 *
 * 两层都没溢出 → SAFE（跳过，不处理）
 * 任一层溢出 → 需处理（OVERFLOW 或 CONTAINER_OVERFLOW），后续进入策略匹配
 */
function classifyOverflowGrade(textNode, parentNode, _strategy, index, textId) {
  // 已适配的文本（fill_container）不会再溢出，直接 SAFE
  const textSizingH = getSizingHorizontal(textNode);
  if (textSizingH === 'FILL') {
    return 'SAFE';
  }

  const textW = getNodeNumericWidth(textNode) || 0;
  const parentAvailW = getAvailableWidthForText(parentNode, textId, index);

  // 第一层：文本溢出父容器（扣除兄弟元素后的实际可用宽度）
  if (textW > parentAvailW) {
    return 'OVERFLOW';
  }

  // 第二层：父容器溢出祖父容器
  if (checkParentOverflowsGrandparent(index, textId)) {
    return 'CONTAINER_OVERFLOW';
  }

  // 第三层：父容器 FIXED + 子内容总宽度溢出父容器（HUG_PARENT 场景）
  if (checkParentContentOverflow(index, textId)) {
    return 'CONTAINER_HUG_OVERFLOW';
  }

  // 三层都没溢出 → SAFE
  return 'SAFE';
}

/**
 * 递归计算容器子内容的真实需要宽度。
 *
 * 对每个子元素：
 *   - TEXT 节点：当前宽度（hug 状态下的实际宽度）
 *   - HUG 容器：当前宽度（已 hug 内容）
 *   - FILL 容器：当前宽度（由父容器决定）
 *   - FIXED 容器（无 layoutGrow）：递归计算其子内容需要宽度
 *   - FIXED+layoutGrow:1 容器：递归计算其子内容需要宽度（弹性填充，实际需要取决于内容）
 *
 * @param {Object} containerInfo - 容器在 index 中的 info 对象
 * @param {Map} index - 节点索引
 * @returns {number} 子内容总宽度（含 itemSpacing）
 */
function computeTotalChildContentWidth(containerInfo, index) {
  if (!containerInfo?.childIds?.length) return 0;

  const layoutMode = normalizeLayoutMode(containerInfo.node);
  const isHorizontal = layoutMode === 'HORIZONTAL';
  const itemSpacing = getNumericProp(containerInfo.node, 'itemSpacing');
  let total = 0;
  let count = 0;

  containerInfo.childIds.forEach(childId => {
    const childInfo = index.get(childId);
    if (!childInfo) return;

    const sizingH = getSizingHorizontal(childInfo.node);
    let childWidth;

    if (isTextNode(childInfo.node)) {
      // 文本节点：取当前 hug 宽度
      childWidth = getNodeNumericWidth(childInfo.node) || 0;
    } else if (sizingH === 'HUG' || sizingH === 'FILL') {
      // HUG/FILL：取当前宽度
      childWidth = getNodeNumericWidth(childInfo.node) || 0;
    } else if (sizingH === 'FIXED' && childInfo.node?.layoutGrow === 1) {
      // FIXED+layoutGrow:1：弹性填充，递归计算内容需要宽度
      childWidth = computeTotalChildContentWidth(childInfo, index);
      // 至少用当前实际宽度作为下限
      const actualW = getNodeNumericWidth(childInfo.node) || 0;
      childWidth = Math.max(childWidth, actualW);
    } else {
      // 纯 FIXED：取当前宽度
      childWidth = getNodeNumericWidth(childInfo.node) || 0;
    }

    if (isHorizontal) {
      total += childWidth;
      count++;
    } else {
      // VERTICAL/NONE：取最大宽度
      total = Math.max(total, childWidth);
    }
  });

  // 加上 itemSpacing
  if (isHorizontal && count > 1) {
    total += itemSpacing * (count - 1);
  }

  return total;
}

/**
 * 检测父容器 FIXED + 子内容总宽度溢出父容器（HUG_PARENT 场景）
 *
 * 条件：
 *   1. 父容器 FIXED
 *   2. 所有直接子元素在主轴方向均非纯 FIXED（HUG / FILL / FIXED+layoutGrow:1）
 *   3. 子内容总宽度 > 父容器宽度 + 1px
 */
function checkParentContentOverflow(index, textNodeId) {
  const textInfo = index.get(textNodeId);
  if (!textInfo?.parentId) return false;

  const parentInfo = index.get(textInfo.parentId);
  if (!parentInfo) return false;

  const parentSizingH = getSizingHorizontal(parentInfo.node);
  if (parentSizingH !== 'FIXED') return false;

  // 检查所有子元素是否均非纯 FIXED
  const allNonPureFixed = parentInfo.childIds.every(childId => {
    const childInfo = index.get(childId);
    if (!childInfo) return true;
    const sizingH = getSizingHorizontal(childInfo.node);
    if (sizingH === 'FIXED' && childInfo.node?.layoutGrow !== 1) {
      return false;
    }
    return true;
  });

  if (!allNonPureFixed) return false;

  // 计算子内容总宽度
  const totalContentWidth = computeTotalChildContentWidth(parentInfo, index);
  const parentW = getNodeNumericWidth(parentInfo.node) || 0;

  return totalContentWidth > parentW + 1;
}

/**
 * 容器级溢出扫描（4.2.1）
 *
 * 遍历所有 FIXED + auto-layout 容器，检测子内容总宽度是否溢出。
 * 补充文本级检测的盲区：当 FIXED 容器的直接子元素都是 HUG 时，
 * 每个子容器各自不溢出 FIXED 容器，文本也不溢出 HUG 父容器，
 * 但子内容总宽度溢出 FIXED 容器。
 *
 * @param {Map} index - 节点索引
 * @returns {Array} 需要修复的容器列表 [{ id, name, width, totalContentWidth, children }]
 */
function scanFixedContainerOverflow(index) {
  const results = [];

  index.forEach(info => {
    const node = info.node;
    if (!node) return;

    // 1. 容器水平尺寸模式为 FIXED
    const sizingH = getSizingHorizontal(node);
    if (sizingH !== 'FIXED') return;

    // 2. 容器有 auto-layout
    const layoutMode = normalizeLayoutMode(node);
    if (layoutMode !== 'HORIZONTAL' && layoutMode !== 'VERTICAL') return;

    // 2.1 跳过按钮/标签类容器（由 BUTTON_TAG 策略处理，避免重复报告）
    if (isButtonOrTagContainer(node, info, index)) return;

    // 3. 有子元素
    if (!info.childIds || info.childIds.length === 0) return;

    // 4. 所有直接子元素在主轴方向均非纯 FIXED
    const allNonPureFixed = info.childIds.every(childId => {
      const childInfo = index.get(childId);
      if (!childInfo) return true;
      const childSizingH = getSizingHorizontal(childInfo.node);
      if (childSizingH === 'FIXED' && childInfo.node?.layoutGrow !== 1) {
        return false;
      }
      return true;
    });
    if (!allNonPureFixed) return;

    // 5. 子内容总宽度 > 容器宽度 + 1px
    const totalContentWidth = computeTotalChildContentWidth(info, index);
    const containerW = getNodeNumericWidth(node) || 0;

    if (totalContentWidth > containerW + 1) {
      results.push({
        id: info.id,
        name: getNodeName(node),
        width: containerW,
        totalContentWidth,
        overflow: totalContentWidth - containerW,
        childCount: info.childIds.length,
        action: 'hug_contents'
      });
    }
  });

  return results;
}

/**
 * 检测父容器是否溢出祖父容器
 * parentW > grandparentAvailableW（含 1px 容差）
 */
function checkParentOverflowsGrandparent(index, textNodeId) {
  const textInfo = index.get(textNodeId);
  if (!textInfo?.parentId) return false;

  const parentInfo = index.get(textInfo.parentId);
  if (!parentInfo?.parentId) return false;

  // 父容器已是 fill_container → 宽度即等于可用空间，不会溢出祖父
  const parentSizingH = getSizingHorizontal(parentInfo.node);
  if (parentSizingH === 'FILL') return false;

  const grandparentInfo = index.get(parentInfo.parentId);
  if (!grandparentInfo) return false;

  const parentW = getNodeNumericWidth(parentInfo.node);
  const grandparentAvailW = getAvailableWidthForText(grandparentInfo.node, parentInfo.id, index);

  if (parentW == null || grandparentAvailW === 0) return false;

  return parentW > grandparentAvailW + 1; // 1px 容差
}

/**
 * 4.3 分类阶段 Gate 校验
 */
function validateGate(classifiedNodes) {
  const issues = [];

  for (const item of classifiedNodes) {
    if (!item.strategy || !item.overflowGrade) {
      issues.push(`节点 ${item.id}：strategy 或 overflowGrade 缺失`);
    }
    if (item.siblingCount == null || item.parentLayoutMode == null) {
      issues.push(`节点 ${item.id}：siblingCount 或父容器 layoutMode 未获取`);
    }
    if (item.overflowCheck !== true) {
      issues.push(`节点 ${item.id}：双层溢出检测未完成`);
    }
    if (item.source !== 'batch_read') {
      issues.push(`节点 ${item.id}：属性值可能来自推断而非 batch_read 实际值`);
    }
  }

  return {
    passed: issues.length === 0,
    issues
  };
}

/**
 * 4.4 分类输出格式（Markdown 表格）
 */
function formatClassificationTable(classifiedNodes) {
  const header =
    '| TEXT ID | 内容（前20字） | 父容器名称 | Strategy | 父容器宽(实际值) | 文本宽 | 溢出级别 | 来源 |';
  const separator = '|---------|--------------|-----------|----------|----------------|-------|---------|------|';

  const rows = classifiedNodes.map(item => {
    const preview = (item.content || '').slice(0, 20).replace(/\|/g, '\\|').replace(/\n/g, ' ');
    return `| ${item.id} | ${preview} | ${item.parentName || '-'} | ${item.strategy} | ${item.parentWidth ?? '-'} | ${item.textWidth ?? '-'} | ${item.overflowGrade} | ${item.source} |`;
  });

  return [header, separator, ...rows].join('\n');
}

// ============================================================
// 第三章/5.1/6.2 Height 规则 + padding 补偿计算
// ============================================================

/**
 * 估算容器 hug 后的内容高度
 */
function estimateContentHeight(index, containerInfo) {
  if (!containerInfo?.childIds?.length) return 0;

  const children = containerInfo.childIds.map(id => index.get(id)).filter(Boolean);
  const layoutMode = normalizeLayoutMode(containerInfo.node);
  const gap = getNumericProp(containerInfo.node, 'itemSpacing');

  if (children.length === 1 && isTextNode(children[0].node)) {
    // 单文本容器：hug 后内容高度 ≈ 文本高度
    return getNodeNumericHeight(children[0].node) || 0;
  }

  if (layoutMode === 'VERTICAL') {
    return children.reduce((sum, c) => sum + (getNodeNumericHeight(c.node) || 0), 0) + gap * Math.max(0, children.length - 1);
  }

  // 水平或无布局：取最大子元素高度
  return Math.max(0, ...children.map(c => getNodeNumericHeight(c.node) || 0));
}

/**
 * 计算 padding 补偿
 * 返回 { height, paddingTop, paddingBottom } 或 null（无需修改）
 */
function computePaddingCompensation(index, containerInfo) {
  const node = containerInfo.node;
  const sizingV = getSizingVertical(node);

  // 已是 HUG → 无需修改
  if (sizingV === 'HUG') return null;

  // 已有 padding → 保留不变，只改高度模式
  if (getNumericProp(node, 'paddingTop') > 0) {
    return { height: 'hug_contents' };
  }

  // 原 FIXED → 需要 padding 补偿
  if (sizingV === 'FIXED') {
    const originalHeight = getNodeNumericHeight(node) || 0;
    const contentHeight = estimateContentHeight(index, containerInfo);
    const padding = Math.max(0, (originalHeight - contentHeight) / 2);
    return {
      height: 'hug_contents',
      paddingTop: Math.round(padding),
      paddingBottom: Math.round(padding)
    };
  }

  // FILL → 改为 hug，无需 padding 补偿
  return { height: 'hug_contents' };
}

// ============================================================
// 6.1 容器链水平宽度检查
// ============================================================

/**
 * 从文本的直接父容器开始，沿 parent 链逐层向上检查
 * 返回需要修复的容器列表
 */
function checkContainerChainHorizontal(textNodeId, index) {
  const results = [];
  let current = index.get(textNodeId);
  if (!current?.parentId) return results;

  // 跳过直接父容器（由策略修复处理），从祖父容器开始检查
  current = index.get(current.parentId); // 直接父容器
  if (!current?.parentId) return results;
  current = index.get(current.parentId); // 祖父容器

  while (current) {
    const node = current.node;
    const sizingH = getSizingHorizontal(node);

    // FILL → 停止向上遍历
    if (sizingH === 'FILL') break;

    // 检查父级是否有 auto-layout
    const parentInfo = current.parentId ? index.get(current.parentId) : null;
    const parentHasAutoLayout = parentInfo ? hasAutoLayout(parentInfo.node) : false;

    if (sizingH === 'FIXED') {
      // FIXED 容器宽度是设计决定的，文本 fill 后在其中折行是 textAutoResize: HEIGHT 的预期行为
      // 不修改 FIXED 面板容器，避免误改布局结构（如侧边栏、面板宽度）
      // 继续向上遍历检查更外层容器
    } else if (sizingH === 'HUG') {
      if (parentHasAutoLayout) {
        // 判断父级对齐方式：SPACE_BETWEEN / SPACE_EVENLY 模式下，子容器靠分布算法定位
        // 此时 HUG 容器应保持原状，改 fill 会破坏两端分布（如顶栏左 logo + 右账号区）
        const parentAlign = parentInfo.node?.primaryAxisAlignItems || '';
        const isDistributedLayout = parentAlign === 'SPACE_BETWEEN' || parentAlign === 'SPACE_EVENLY';

        // 还需检查当前 HUG 容器在父级中的 layoutGrow：若为 0 且父级是分布模式，说明是靠分布定位的"端点容器"
        const ownLayoutGrow = node?.layoutGrow;
        const isEndpointByDistribution = isDistributedLayout && (ownLayoutGrow === 0 || ownLayoutGrow === undefined);

        if (isEndpointByDistribution) {
          // 父级 SPACE_BETWEEN/SPACE_EVENLY + 本容器 layoutGrow=0 → 靠分布定位，保持 HUG，停止向上遍历
          break;
        }

        // HUG + 父级有 auto-layout（非分布模式）→ 改为 fill_container
        results.push({
          textId: textNodeId,
          containerId: current.id,
          containerType: getNodeType(node) || 'FRAME',
          originalMode: 'HUG',
          action: 'fill_container',
          parentLayoutMode: parentInfo ? normalizeLayoutMode(parentInfo.node) : 'NONE'
        });
      }
      // HUG + 父级无 auto-layout → 不处理，继续向上
    }

    current = current.parentId ? index.get(current.parentId) : null;
  }

  return results;
}

/**
 * 6.1 输出格式（Markdown 表格）
 */
function formatChainCheckTable(chainResults) {
  if (!chainResults.length) return '无需容器链修复。';

  const header = '| 文本 ID | 路径上的容器 ID | 容器类型 | 原宽度模式 | 修复动作 |';
  const separator = '|---------|---------------|---------|-----------|---------|';

  const rows = chainResults.map(item =>
    `| ${item.textId} | ${item.containerId} | ${item.containerType} | ${item.originalMode} | ${item.action} |`
  );

  return [header, separator, ...rows].join('\n');
}

// ============================================================
// 第六章 修复操作生成
// ============================================================

/**
 * 保护 SPACE_BETWEEN 布局属性
 * Ardot 在应用 height: "hug_contents" 时，若容器 primaryAxisAlignItems 为 SPACE_BETWEEN，
 * 会自动将其改为 MIN，导致 itemSpacing 从 auto（忽略）变为实际值生效，破坏布局。
 * 此函数在修改 height 时显式保留原始的 primaryAxisAlignItems 和 layoutGrow。
 */
function protectSpaceBetween(node, props) {
  if (!node || !props.height) return;

  const primaryAxisAlignItems = node.primaryAxisAlignItems;
  if (primaryAxisAlignItems === 'SPACE_BETWEEN') {
    props.primaryAxisAlignItems = 'SPACE_BETWEEN';
    if (node.layoutGrow !== undefined) {
      props.layoutGrow = node.layoutGrow;
    }
  }
}

/**
 * 根据策略生成容器修复属性（Phase A）
 */
function getContainerFixProps(strategy, index, parentInfo) {
  const props = {};

  // 5.3 容器布局校验：已是目标值则跳过
  const sizingH = getSizingHorizontal(parentInfo.node);
  const targetFill = ['CONTAINER_OVERFLOW', 'PREVENTIVE_FILL', 'PARAGRAPH', 'TITLE', 'FALLBACK'].includes(strategy);
  const targetHug = strategy === 'SINGLE_LABEL' || strategy === 'HUG_PARENT' || strategy === 'BUTTON_TAG';

  // HUG 容器已自动适应内容宽度，不需要 fill；仅 FIXED 容器才需改为 fill（可能限制文本）
  if (targetFill && sizingH !== 'FILL') {
    props.width = 'fill_container';
  }
  if (targetHug && sizingH !== 'HUG') {
    props.width = 'hug_contents';
    // 清除 layoutAlign: STRETCH，否则即使设置了 hug_contents，节点仍会在父级 auto-layout 中水平拉伸
    // 注意：INHERIT 不是有效值，使用 AUTO 代替
    if (parentInfo.node.layoutAlign === 'STRETCH') {
      props.layoutAlign = 'AUTO';
    }
  }

  // Height → hug_contents + padding 补偿（HUG_PARENT 和 BUTTON_TAG 策略不执行高度修改）
  if (strategy !== 'HUG_PARENT' && strategy !== 'BUTTON_TAG') {
    const heightFix = computePaddingCompensation(index, parentInfo);
    if (heightFix) {
      Object.assign(props, heightFix);
      // 保护 SPACE_BETWEEN 布局，防止 Ardot 副作用
      protectSpaceBetween(parentInfo.node, props);
    }
  }

  return props;
}

/**
 * 根据策略生成文本修复属性（Phase B）
 */
function getTextFixProps(strategy) {
  switch (strategy) {
    case 'CONTAINER_OVERFLOW':
    case 'PREVENTIVE_FILL':
    case 'PARAGRAPH':
      return { width: 'fill_container', textAutoResize: 'HEIGHT' };

    case 'SINGLE_LABEL':
      return { width: 'fill_container' }; // textAutoResize 保留原值

    case 'BUTTON_TAG':
      // 按钮/标签文本不应折行，保留 HUG + WIDTH_AND_HEIGHT
      return null;

    case 'TITLE':
      return { width: 'fill_container' }; // 保留 WIDTH_AND_HEIGHT

    case 'HUG_PARENT':
    case 'FALLBACK':
      return null; // 不修改文本

    default:
      return null;
  }
}

function addFix(fixesMap, nodeId, props, reason) {
  if (!nodeId || !props || !Object.keys(props).length) return;

  const existing = fixesMap.get(nodeId) || { id: nodeId, props: {}, reasons: new Set() };
  Object.assign(existing.props, props);
  if (reason) existing.reasons.add(reason);
  fixesMap.set(nodeId, existing);
}

function serializeValue(value) {
  if (Array.isArray(value)) {
    return `[${value.map(serializeValue).join(', ')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.entries(value).map(([k, v]) => `${k}: ${serializeValue(v)}`).join(', ')}}`;
  }
  return JSON.stringify(value);
}

function chunkOperations(operations, batchSize = BATCH_SIZE) {
  const batches = [];
  for (let i = 0; i < operations.length; i += batchSize) {
    batches.push(operations.slice(i, i + batchSize).join('\n'));
  }
  return batches;
}

/**
 * 生成所有修复操作
 */
function generateFixOperations(classifiedNodes, index) {
  const containerFixes = new Map(); // Phase A
  const textFixes = new Map(); // Phase B
  const chainFixes = new Map(); // 6.1 容器链修复（合并到 Phase A）

  for (const item of classifiedNodes) {
    // SAFE 不修复
    if (item.overflowGrade === 'SAFE') continue;

    const textInfo = index.get(item.id);
    if (!textInfo?.parentId) continue;

    const parentInfo = index.get(textInfo.parentId);
    if (!parentInfo) continue;

    // Phase A: 容器操作
    const containerProps = getContainerFixProps(item.strategy, index, parentInfo);
    if (containerProps && Object.keys(containerProps).length) {
      addFix(containerFixes, parentInfo.id, containerProps, `${item.strategy} 策略容器修复`);
    }

    // Phase B: 文本操作
    const textProps = getTextFixProps(item.strategy);
    if (textProps) {
      addFix(textFixes, item.id, textProps, `${item.strategy} 策略文本修复`);
    }

    // 6.1 容器链水平宽度检查
    const chainResults = checkContainerChainHorizontal(item.id, index);
    for (const chain of chainResults) {
      if (chain.action === 'fill_container') {
        // 容器链检查仅修改宽度，不自动执行高度修改（参见 5.2 高度规则）
        // 高度修改仅对溢出文本的直接父容器执行（在 getContainerFixProps 中处理）
        const chainProps = { width: 'fill_container' };

        addFix(chainFixes, chain.containerId, chainProps, `6.1 容器链检查: ${chain.originalMode} → fill_container`);
      }
    }
  }

  // 合并容器修复（仅策略修复，容器链检查仅作检测报告不自动修复）
  const allContainerFixes = new Map();
  containerFixes.forEach((fix, id) => {
    const existing = allContainerFixes.get(id) || { id, props: {}, reasons: new Set() };
    Object.assign(existing.props, fix.props);
    fix.reasons.forEach(r => existing.reasons.add(r));
    allContainerFixes.set(id, existing);
  });
  // 容器链检查（6.1）仅输出检测表格，不生成自动修复操作
  // HUG 容器随内容伸缩不限制文本，FIXED 容器宽度是设计决定，均不应被容器链检查自动修改

  // 转数组并按深度排序（外→内）
  const sortedContainers = Array.from(allContainerFixes.values()).sort((a, b) => {
    const depthA = getNodeDepth(index, a.id);
    const depthB = getNodeDepth(index, b.id);
    if (depthA !== depthB) return depthA - depthB; // 外层（深度小）在前
    return a.id.localeCompare(b.id);
  });

  const sortedTexts = Array.from(textFixes.values()).sort((a, b) => {
    return getNodeDepth(index, a.id) - getNodeDepth(index, b.id);
  });

  // 生成 U() 操作字符串
  const containerOps = sortedContainers.map(item => `U("${item.id}", ${serializeValue(item.props)})`);
  const textOps = sortedTexts.map(item => `U("${item.id}", ${serializeValue(item.props)})`);

  // 分批
  const phaseA = chunkOperations(containerOps);
  const phaseB = chunkOperations(textOps);

  return {
    phaseA,
    phaseB,
    containerFixes: sortedContainers,
    textFixes: sortedTexts
  };
}

// ============================================================
// 主入口
// ============================================================

function executeLayoutAdaptation(batchReadResult) {
  if (!batchReadResult) {
    console.error('错误：未提供 batch_read 结果数据');
    return null;
  }

  // 构建节点索引
  const index = buildNodeIndex(batchReadResult);

  // 第二章：提取所有可见文本节点
  const textNodes = extractAllTexts(batchReadResult);

  if (!textNodes.length) {
    console.log('未找到文本节点');
    return {
      totalTexts: 0,
      classification: [],
      gate: { passed: true, issues: [] },
      chainCheck: [],
      operations: { phaseA: [], phaseB: [], containerFixes: [], textFixes: [] }
    };
  }

  console.log(`扫描到 ${textNodes.length} 个可见文本节点（含 INSTANCE 内部文本）\n`);

  // 第四章：分类判定（先溢出检测，溢出才做策略匹配）
  const classifiedNodes = textNodes.map(textNode => {
    const textInfo = index.get(textNode.id);
    const parentNode = textInfo?.parentId ? index.get(textInfo.parentId)?.node : null;

    if (!parentNode) {
      return {
        id: textNode.id,
        content: textNode.text,
        parentName: '-',
        strategy: 'FALLBACK',
        parentWidth: null,
        textWidth: getNodeNumericWidth(textInfo?.node),
        siblingCount: null,
        parentLayoutMode: null,
        overflowGrade: 'SAFE',
        overflowCheck: true,
        source: 'batch_read'
      };
    }

    const parentInfo = index.get(textInfo.parentId);

    // 先做双层溢出检测（前置门槛）
    const overflowGrade = classifyOverflowGrade(textInfo.node, parentNode, null, index, textNode.id);

    // 仅当溢出时才进行策略匹配（决定如何修复）；SAFE 节点策略标记为 FALLBACK（不使用）
    const strategy = overflowGrade !== 'SAFE'
      ? classifyStrategy(textInfo.node, parentNode, index, textNode.id)
      : 'FALLBACK';

    return {
      id: textNode.id,
      content: textNode.text,
      parentName: getNodeName(parentNode),
      strategy,
      parentWidth: getNodeNumericWidth(parentNode),
      textWidth: getNodeNumericWidth(textInfo.node),
      siblingCount: parentInfo?.childIds?.length ?? null,
      parentLayoutMode: normalizeLayoutMode(parentNode),
      overflowGrade,
      overflowCheck: true,
      source: 'batch_read'
    };
  });

  // 4.3 Gate 校验
  const gate = validateGate(classifiedNodes);

  // 6.1 容器链检查（对所有需修复的节点）
  const allChainResults = [];
  classifiedNodes.forEach(item => {
    if (item.overflowGrade === 'SAFE') return;
    const chainResults = checkContainerChainHorizontal(item.id, index);
    allChainResults.push(...chainResults);
  });

  // 第六章：生成修复操作
  const operations = generateFixOperations(classifiedNodes, index);

  // 4.2.1 容器级溢出扫描（补充文本级检测盲区）
  const containerOverflowScan = scanFixedContainerOverflow(index);

  // 将容器级扫描结果合并到 Phase A
  if (containerOverflowScan.length > 0) {
    // 收集已有的容器修复 ID，避免重复
    const existingFixIds = new Set(operations.containerFixes.map(f => f.id));

    // 生成新的容器修复
    const scanFixes = containerOverflowScan
      .filter(item => !existingFixIds.has(item.id))
      .map(item => ({
        id: item.id,
        props: { width: 'hug_contents' },
        reasons: new Set([`4.2.1 容器级溢出扫描: FIXED ${item.width}px → hug (子内容 ${item.totalContentWidth}px)`])
      }));

    // 合并到 containerFixes
    scanFixes.forEach(fix => operations.containerFixes.push(fix));

    // 重新按深度排序（外→内）
    operations.containerFixes.sort((a, b) => {
      return getNodeDepth(index, a.id) - getNodeDepth(index, b.id);
    });

    // 重新生成 Phase A 批次
    const allContainerOps = operations.containerFixes.map(item =>
      `U("${item.id}", ${serializeValue(item.props)})`
    );
    operations.phaseA = chunkOperations(allContainerOps);
  }

  // 统计
  const stats = {
    total: classifiedNodes.length,
    byStrategy: {},
    byGrade: {}
  };
  classifiedNodes.forEach(item => {
    stats.byStrategy[item.strategy] = (stats.byStrategy[item.strategy] || 0) + 1;
    stats.byGrade[item.overflowGrade] = (stats.byGrade[item.overflowGrade] || 0) + 1;
  });
  const fixCount = classifiedNodes.filter(n => n.overflowGrade !== 'SAFE').length;

  // 输出
  console.log('========== 分类结果（4.4）==========');
  console.log(formatClassificationTable(classifiedNodes));
  console.log('');

  console.log('========== Gate 校验（4.3）==========');
  if (gate.passed) {
    console.log('✓ 全部通过');
  } else {
    gate.issues.forEach(issue => console.log(`✗ ${issue}`));
  }
  console.log('');

  console.log('========== 容器链检查（6.1）==========');
  console.log(formatChainCheckTable(allChainResults));
  console.log('');

  // 容器级溢出扫描输出
  if (containerOverflowScan.length > 0) {
    console.log('========== 容器级溢出扫描（4.2.1）==========');
    console.log('| 容器 ID | 容器名称 | 容器宽 | 子内容总宽 | 溢出量 | 子元素数 | 修复动作 |');
    console.log('|---------|---------|--------|-----------|--------|---------|---------|');
    containerOverflowScan.forEach(item => {
      console.log(`| ${item.id} | ${item.name || '-'} | ${item.width} | ${item.totalContentWidth} | ${Math.round(item.overflow)} | ${item.childCount} | ${item.action} |`);
    });
    console.log('');
  } else {
    console.log('========== 容器级溢出扫描（4.2.1）==========\n无需容器级修复\n');
  }

  console.log('========== 统计 ==========');
  console.log(`文本节点总数: ${stats.total}`);
  console.log(`策略分布: ${JSON.stringify(stats.byStrategy)}`);
  console.log(`溢出分级: ${JSON.stringify(stats.byGrade)}`);
  console.log(`需修复节点: ${fixCount}`);
  console.log(`容器修复操作: ${operations.containerFixes.length}`);
  console.log(`文本修复操作: ${operations.textFixes.length}`);
  console.log(`容器级溢出扫描: ${containerOverflowScan.length} 个容器`);
  console.log('');

  if (operations.phaseA.length) {
    console.log(`========== Phase A — 容器操作（${operations.phaseA.length} 批，外→内拓扑排序）==========`);
    operations.phaseA.forEach((batch, i) => {
      console.log(`\n--- 容器批次 ${i + 1} ---\n${batch}`);
    });
    console.log('');
  } else {
    console.log('========== Phase A — 容器操作 ==========\n无需容器修复\n');
  }

  if (operations.phaseB.length) {
    console.log(`========== Phase B — 文本操作（${operations.phaseB.length} 批，Phase A 完成后执行）==========`);
    operations.phaseB.forEach((batch, i) => {
      console.log(`\n--- 文本批次 ${i + 1} ---\n${batch}`);
    });
    console.log('');
  } else {
    console.log('========== Phase B — 文本操作 ==========\n无需文本修复\n');
  }

  console.log('========== 执行顺序提醒 ==========');
  console.log('1. 先执行 Phase A 所有批次（容器操作，外→内）');
  console.log('2. Phase A 全部完成后，再执行 Phase B 所有批次（文本操作）');
  console.log('3. 每批 ≤25 个 U() 操作');
  console.log('4. INSTANCE 内部节点使用分号路径格式（instanceId;childId）');
  console.log('5. 执行完成后按第七章分模块截图验证');

  return {
    totalTexts: textNodes.length,
    classification: classifiedNodes,
    gate,
    chainCheck: allChainResults,
    containerOverflowScan,
    operations,
    stats
  };
}

// ============================================================
// 文件 I/O + CLI 入口（支持大设计稿文件模式 + fetch 模式）
// ============================================================

const fs = require('fs');
const ardotClient = require('./ardot-client');
// 从 ardot-client 引入探活与数据获取函数（探活接口与数据接口分离，支持 HTTP 和 WebSocket）
const fetchBatchRead = ardotClient.fetchBatchRead;
const fetchBatchReadViaHttp = ardotClient.fetchBatchReadViaHttp;
const fetchBatchReadViaWs = ardotClient.fetchBatchReadViaWs;
const parseBatchReadResponse = ardotClient.parseBatchReadResponse;
const parseWsBatchReadData = ardotClient.parseWsBatchReadData;
const probeHealth = ardotClient.probeHealth;
const detectMcpAvailable = ardotClient.detectMcpAvailable;
const checkHealthEndpoint = ardotClient.checkHealthEndpoint;
const probeService = ardotClient.probeService;

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--output' || arg === '--report' ||
        arg === '--fileId' || arg === '--readDepth' || arg === '--mcpUrl') {
      args[arg.slice(2)] = argv[++i];
    } else if (arg === '--fetch') {
      args.fetch = true;
    } else if (arg === '--nodeIds') {
      args.nodeIds = argv[++i].split(',').map(s => s.trim());
    } else if (arg === '--no-resolveInstances') {
      args.resolveInstances = false;
    } else if (arg === '--detect') {
      args.detect = true;
    }
  }
  return args;
}

/**
 * 生成人类可读报告（Markdown）
 */
function generateReport(result) {
  const lines = [];

  lines.push('# 设计稿自动布局适配报告\n');

  // 统计
  lines.push('## 统计\n');
  lines.push(`- 文本节点总数: ${result.totalTexts}`);
  lines.push(`- 策略分布: ${JSON.stringify(result.stats.byStrategy)}`);
  lines.push(`- 溢出分级: ${JSON.stringify(result.stats.byGrade)}`);
  const fixCount = result.classification.filter(n => n.overflowGrade !== 'SAFE').length;
  lines.push(`- 需修复节点: ${fixCount}`);
  lines.push(`- 容器修复操作: ${result.operations.containerFixes.length}`);
  lines.push(`- 文本修复操作: ${result.operations.textFixes.length}`);
  lines.push('');

  // Gate 校验
  lines.push('## Gate 校验（4.3）\n');
  if (result.gate.passed) {
    lines.push('✓ 全部通过\n');
  } else {
    result.gate.issues.forEach(issue => lines.push(`- ✗ ${issue}`));
    lines.push('');
  }

  // 分类表
  lines.push('## 分类结果（4.4）\n');
  lines.push(formatClassificationTable(result.classification));
  lines.push('');

  // 容器链检查
  lines.push('## 容器链检查（6.1）\n');
  lines.push(formatChainCheckTable(result.chainCheck));
  lines.push('');

  // Phase A
  lines.push(`## Phase A — 容器操作（${result.operations.phaseA.length} 批）\n`);
  if (result.operations.phaseA.length) {
    result.operations.phaseA.forEach((batch, i) => {
      lines.push(`### 容器批次 ${i + 1}\n`);
      lines.push('```javascript');
      lines.push(batch);
      lines.push('```\n');
    });
  } else {
    lines.push('无需容器修复\n');
  }

  // Phase B
  lines.push(`## Phase B — 文本操作（${result.operations.phaseB.length} 批）\n`);
  if (result.operations.phaseB.length) {
    result.operations.phaseB.forEach((batch, i) => {
      lines.push(`### 文本批次 ${i + 1}\n`);
      lines.push('```javascript');
      lines.push(batch);
      lines.push('```\n');
    });
  } else {
    lines.push('无需文本修复\n');
  }

  lines.push('## 执行顺序\n');
  lines.push('1. 先执行 Phase A 所有批次（容器操作，外→内）');
  lines.push('2. Phase A 全部完成后，再执行 Phase B 所有批次（文本操作）');
  lines.push('3. 每批 ≤25 个 U() 操作');
  lines.push('4. INSTANCE 内部节点使用分号路径格式（instanceId;childId）');
  lines.push('5. 执行完成后按第七章分模块截图验证');

  return lines.join('\n');
}

/**
 * CLI 主函数
 */
async function runCLI() {
  const args = parseArgs(process.argv);

  // ===== --detect 模式：两步探活检测可用接口 =====
  if (args.detect) {
    // 第一步：探测主 MCP health 端点（50501）
    const primaryHealthUrl = 'http://127.0.0.1:50501/api/v1/health';
    const primaryDataUrl = 'http://127.0.0.1:50501/api/v1/mcp';
    console.log(`[1/2] 正在探测主 health 接口: ${primaryHealthUrl}`);
    const primaryAvailable = await detectMcpAvailable(primaryHealthUrl);

    if (primaryAvailable) {
      // 第一步通了 → 用 mcp 接口获取数据
      console.log('MCP_AVAILABLE');
      console.log(`✓ 主 health 接口可达: ${primaryHealthUrl}`);
      console.log(`  数据接口: ${primaryDataUrl}`);
      console.log('  使用 --fetch 即可（--mcpUrl 可省略，脚本会自动选中此接口）');
    } else {
      // 第一步不通 → 探测沙箱 health 接口（19501）
      console.log(`✗ 主 health 接口不可达`);
      console.log(`[2/2] 正在探测沙箱 health 接口: http://127.0.0.1:19501/api/v1/health`);
      const healthResult = await checkHealthEndpoint('127.0.0.1', '19501');

      if (healthResult.available) {
        console.log('MCP_AVAILABLE');
        console.log(`✓ 沙箱 health 接口可达: ${healthResult.healthUrl}`);
        console.log(`  数据接口: ${healthResult.wsConfig.url}${healthResult.wsConfig.path} (WebSocket)`);
        console.log('  使用 --fetch 即可（--mcpUrl 可省略，脚本会自动选中此接口）');
      } else {
        console.log('MCP_UNAVAILABLE');
        console.log('✗ 两步探活均失败，请确认 Ardot 编辑器或沙箱服务是否运行');
      }
    }
    return;
  }

  // ===== --fetch 模式：脚本直接从 Ardot API 获取数据 =====
  if (args.fetch) {
    if (!args.fileId || !args.nodeIds || !args.nodeIds.length) {
      console.error('fetch 模式需要: --fileId <文件ID> --nodeIds <节点ID1,节点ID2,...>');
      console.error('用法: node layout-adaptation.js --fetch --fileId <id> --nodeIds <id1,id2> [--readDepth 5] [--output <out.json>] [--report <report.md>]');
      process.exit(1);
    }

    console.log(`正在从 Ardot API 获取数据...`);
    try {
      // 未指定 --mcpUrl 时，脚本内自动两步探活（先 50501 health，后 19501 health）
      let fetchConfig = args.mcpUrl;
      if (!fetchConfig) {
        console.log('未指定 --mcpUrl，正在自动探活...');
        const probeResult = await probeService();
        if (!probeResult) {
          throw new Error('所有探活均失败（端口 50501 和 19501 health 接口均不可达）');
        }
        fetchConfig = probeResult;
        if (probeResult.mode === 'ws') {
          console.log(`✓ 探活成功（来源: ${probeResult.source}，WebSocket 模式）`);
          console.log(`  数据接口: ${probeResult.wsConfig.url}${probeResult.wsConfig.path}`);
        } else {
          console.log(`✓ 探活成功（来源: ${probeResult.source}，HTTP 模式），数据接口: ${probeResult.dataUrl}`);
        }
      }

      const nodes = await fetchBatchRead(
        args.fileId,
        args.nodeIds,
        parseInt(args.readDepth) || 5,
        args.resolveInstances !== false,
        fetchConfig
      );

      console.log(`✓ 获取到 ${nodes.length} 个顶层节点`);

      // 自动检测并补充读取被压缩的子节点（children: "..."）
      // batch_read 在子节点过多时会压缩深层子树，导致文本节点遗漏
      console.log('检测压缩子节点...');
      await autoExpandCompressedNodes(
        nodes,
        args.fileId,
        args.resolveInstances !== false,
        fetchConfig,
        0,              // maxRounds 已废弃，0 表示使用安全上限
        5               // 补充读取深度（适中，避免 SSE 响应过大）
      );

      const result = executeLayoutAdaptation(nodes);
      if (!result) process.exit(1);

      if (args.output) {
        fs.writeFileSync(args.output, JSON.stringify(result, null, 2), 'utf-8');
        console.log(`结果已写入: ${args.output}`);
      }
      if (args.report) {
        fs.writeFileSync(args.report, generateReport(result), 'utf-8');
        console.log(`报告已写入: ${args.report}`);
      }

    } catch (e) {
      console.error(`✗ --fetch 模式失败: ${e.message}`);
      console.error('');
      console.error('可能原因：两步探活均失败（端口 50501 和 19501 health 接口均不可达）。');
      console.error('请确认 Ardot 编辑器或沙箱服务是否运行，然后重试。');
      process.exit(1);
    }
    return;
  }

  // 未指定 --fetch 或 --detect → 显示用法
  console.error('用法:');
  console.error('  环境检测: node layout-adaptation.js --detect');
  console.error('  fetch 模式: node layout-adaptation.js --fetch --fileId <id> --nodeIds <id1,id2> [--output <out.json>] [--report <report.md>]');
  console.error('');
  console.error('提示: 可先运行 --detect 检测当前环境，--fetch 模式会自动两步探活选择可用接口');
  process.exit(1);
}

// ============================================================
// 执行入口
// ============================================================

// CLI 模式：通过 --fetch 或 --detect 参数触发
if (process.argv.includes('--fetch') || process.argv.includes('--detect')) {
  runCLI();
}

module.exports = {
  // 基础工具
  getNodeId,
  getNodeType,
  getTextContent,
  isNodeHidden,
  isTextNode,
  isInstanceNode,
  isFiniteNumber,
  getNodeNumericWidth,
  getNodeNumericHeight,
  // 布局属性
  normalizeLayoutMode,
  hasAutoLayout,
  mapSizingMode,
  getSizingHorizontal,
  getSizingVertical,
  getTextAutoResize,
  isTextFixedWidth,
  getParentAvailableWidth,
  getAvailableWidthForText,
  nonCJKRatio,
  hasParagraphPunctuation,
  // 遍历与索引
  buildNodeIndex,
  traverseNodes,
  getNodeDepth,
  // 文本提取
  extractAllTexts,
  // 分类判定
  classifyStrategy,
  classifyOverflowGrade,
  checkParentOverflowsGrandparent,
  computeTotalChildContentWidth,
  checkParentContentOverflow,
  scanFixedContainerOverflow,
  validateGate,
  formatClassificationTable,
  // padding 补偿
  computePaddingCompensation,
  estimateContentHeight,
  // 容器链检查
  checkContainerChainHorizontal,
  formatChainCheckTable,
  // 修复操作生成
  protectSpaceBetween,
  getContainerFixProps,
  getTextFixProps,
  generateFixOperations,
  serializeValue,
  chunkOperations,
  // 文件 I/O + CLI
  parseArgs,
  generateReport,
  runCLI,
  // 探活与数据获取（抽离至 ardot-client.js，这里转出以便外部统一引用）
  ardotClient,
  fetchBatchRead,
  fetchBatchReadViaHttp,
  fetchBatchReadViaWs,
  parseBatchReadResponse,
  parseWsBatchReadData,
  probeHealth,
  detectMcpAvailable,
  checkHealthEndpoint,
  probeService,
  // 主入口
  executeLayoutAdaptation
};
