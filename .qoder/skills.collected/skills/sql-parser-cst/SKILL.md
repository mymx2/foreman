---
name: sql-parser-cst
description: >
  使用 sql-parser-cst 将 SQL 解析为具体语法树 (CST)，遍历/转换节点，从 DDL/DML 中提取元信息。
  当任务涉及解析 SQL 文件、从 DDL 提取表/列/索引元信息、分析 SQL 结构、构建 SQL linter 或格式化工具、
  或任何需要保留注释、空白和精确语法的 SQL 静态分析时，使用此技能。
  也适用于处理 sql-parser-cst 类型（如 Program、Statement、CreateTableStmt、ColumnDefinition），
  或用户提到 CST 解析、SQL 语法树、sql-parser-cst 时。
---

# sql-parser-cst 技能

sql-parser-cst 将 SQL 解析为**具体语法树** (CST) — 与 AST 解析器不同，它保留所有语法元素
（注释、空白、关键字大小写、引号），支持精确地还原为原始 SQL。

## 适用场景

- 从 DDL 文件提取表/列/索引元信息（CREATE TABLE、ALTER TABLE、CREATE INDEX）
- 构建 SQL linter、格式化工具或转换器
- 不依赖数据库连接的 SQL 静态分析
- 需要在操作结构的同时保留原始 SQL 格式的任何任务

## 安装与导入

```bash
npm install sql-parser-cst
```

```ts
import { parse, show, cstVisitor, cstTransformer, VisitorAction } from "sql-parser-cst";
import type {
  Program,
  Statement,
  Node,
  Expr,
  EntityName,
  CreateTableStmt,
  ColumnDefinition,
  AlterTableStmt,
  CreateIndexStmt,
  CommentStmt,
  DataType,
  Keyword,
} from "sql-parser-cst";
```

## 核心 API

### parse(sql, options) → Program

```ts
const cst: Program = parse(sql, {
  dialect: "postgresql", // 必填：sqlite | bigquery | mysql | mariadb | postgresql | plpgsql
  includeSpaces: true, // 保留水平空白（空格/制表符）
  includeNewlines: true, // 保留换行符
  includeComments: true, // 保留注释
  includeRange: true, // 为所有节点添加 range: [start, end] 位置信息
  paramTypes: ["?"], // 支持绑定参数："?" | "?nr" | "$nr" | ":name" | "$name" | "@name"
  filename: "schema.sql", // 用于错误报告中的文件名
});
```

所有 `include*` 选项默认为 `false`。要精确还原（`show(parse(sql)) === sql`），
需同时启用三项：`includeSpaces`、`includeNewlines`、`includeComments`。

解析失败时抛出 `FormattedSyntaxError`，错误信息包含意外 token 和期望的替代项。
可用条件注释跳过不支持的 SQL 片段：

```sql
/* sql-parser-cst-disable */
这里放不支持的 SQL;
/* sql-parser-cst-enable */
```

### show(node) → string

将任意 CST 节点序列化回 SQL 字符串。只有当解析时启用了所有 `include*` 空白选项时
才能生成有效 SQL — 否则 token 之间的空白会丢失。

### cstVisitor(map) → (node) => void

遍历整棵 CST，对遇到的每种节点类型调用匹配的函数。
返回 `VisitorAction.SKIP` 可跳过该节点的子节点。

```ts
// 将所有关键字转为大写
const toUpper = cstVisitor({
  keyword: (kw) => {
    kw.text = kw.text.toUpperCase();
  },
});
toUpper(cst);
```

### cstTransformer\<T\>(map) → (node) => T

将整棵 CST 转换为类型 `T`。map 中的每个条目接收一个节点并返回 `T`。
未覆盖的节点类型会在运行时报错 — 需覆盖所有预期遇到的节点类型。

```ts
const toString = cstTransformer<string>({
  program: (n) => n.statements.map(toString).join(";"),
  select_stmt: (n) => n.clauses.map(toString).join(" "),
  // ... 覆盖所有预期类型
});
```

## CST 结构约定

理解这些模式对于操作任何 CST 节点至关重要：

1. **关键字** → `Keyword<T>` 节点，含 `text`（原始大小写）和 `name`（规范化的大写形式）。
   存储在名为 `selectKw`、`fromKw`、`asKw` 等的字段中。

2. **括号表达式** → `paren_expr` 包裹内部表达式。
   例如 `CREATE TABLE t (col INT)` 的 `columns: ParenExpr<ListExpr<ColumnDefinition>>`。

3. **逗号分隔列表** → `list_expr`，含 `items: T[]`。

4. **末尾分号** → 在 `program.statements` 末尾以 `empty` 节点表示。

5. **空白/注释** → 存储在每个节点的 `leading` 和 `trailing` 数组中。
   类型包括：`block_comment`、`line_comment`、`newline`、`space`。

6. **标识符** → `identifier` 节点，含 `text`（原始引号形式）和 `name`（去引号后的值）。
   `EntityName = Identifier | MemberExpr | BigQueryQuotedMemberExpr`，用于 schema 限定名。

7. **字面量** → 带类型的节点：`string_literal`（有 `value`）、`number_literal`（有 `value`）、
   `boolean_literal`、`null_literal` 等。

## 常见模式：提取 DDL 元信息

最常见的用途是解析 DDL 文件提取结构化元信息。
采用多遍遍历模式：每种语句类型一遍，累积到共享 map 中。

```ts
const tableMap = new Map<string, TableMeta>();

for (const stmt of cst.statements) {
  switch (stmt.type) {
    case "create_table_stmt":
      // 提取表名、列定义、约束
      break;
    case "comment_stmt":
      // 提取 COMMENT ON TABLE/COLUMN
      break;
    case "alter_table_stmt":
      // 提取 ADD PRIMARY KEY、ADD UNIQUE 等
      break;
    case "create_index_stmt":
      // 提取索引名、列、唯一性
      break;
  }
}
```

### 提取 EntityName（schema.table）

```ts
function entityName(node: EntityName): string {
  if (node.type === "identifier") return node.name;
  if (node.type === "member_expr") {
    const obj =
      node.object.type === "identifier" ? node.object.name : entityName(node.object as EntityName);
    const prop = node.property.type === "identifier" ? node.property.name : "";
    return prop ? `${obj}.${prop}` : obj;
  }
  return "";
}

// 只取最后一段标识符（表名或列名）：
function lastSegment(node: EntityName): string {
  if (node.type === "identifier") return node.name;
  if (node.type === "member_expr" && node.property.type === "identifier") return node.property.name;
  return "";
}
```

### 从 DataType 提取列类型

DataType 是判别联合类型（discriminated union），常见分支：

| DataType.type        | 含义       | 示例                           |
| -------------------- | ---------- | ------------------------------ |
| `data_type_name`     | 简单类型   | `bigint`、`text`、`boolean`    |
| `modified_data_type` | 带参数类型 | `varchar(32)`、`numeric(10,2)` |
| `time_data_type`     | 时间类型   | `timestamp`、`date`、`time`    |
| `interval_data_type` | 间隔类型   | `interval`                     |
| `array_data_type`    | 数组包装   | `integer[]`                    |

`modified_data_type` 的修饰符在 `paren_expr` → `list_expr` → items 中：

```ts
if (dt.type === "modified_data_type") {
  const inner = extractColumnType(dt.dataType);
  if (dt.modifiers?.type === "paren_expr") {
    const list = dt.modifiers.expr;
    if (list.type === "list_expr") {
      // items[0] = 长度，items[1] = 精度/小数位
    }
  }
}
```

未知类型使用 `show(node).trim().toLowerCase()` 兜底。

### 提取表达式文本（DEFAULT 值等）

简单字面量直接访问 `.value` 或 `.text`。复杂表达式（函数调用、类型转换）使用 `show(node)`：

```ts
function exprToText(node: Expr): string {
  if (node.type === "string_literal") return node.value;
  if (node.type === "number_literal") return node.text;
  if (node.type === "boolean_literal") return String(node.value);
  if (node.type === "null_literal") return "null";
  if (node.type === "identifier") return node.text;
  return show(node as Node).trim(); // 复杂表达式的兜底
}
```

### 提取列约束

ColumnDefinition 有 `constraints: (ColumnConstraint | Constraint<ColumnConstraint>)[]`。
`Constraint<T>` 包装器内含 `constraint` 字段指向实际约束节点。

常见约束类型：

- `constraint_not_null` → NOT NULL
- `constraint_default` → DEFAULT expr（有 `expr` 字段）
- `constraint_primary_key` → PRIMARY KEY
- `constraint_unique` → UNIQUE
- `constraint_auto_increment` → 自增（SERIAL、AUTO_INCREMENT）
- `constraint_references` → 外键引用

## 关键语句类型

| 语句类型            | 关键字段                                                             |
| ------------------- | -------------------------------------------------------------------- |
| `create_table_stmt` | `name: EntityName`、`columns: ParenExpr<ListExpr<ColumnDefinition>>` |
| `alter_table_stmt`  | `table`、`actions: ListExpr<AlterAction>`                            |
| `create_index_stmt` | `name`、`table`、`columns: ParenExpr<ListExpr<...>>`、`indexTypeKw`  |
| `comment_stmt`      | `target: CommentTarget`、`message: StringLiteral`                    |
| `select_stmt`       | `clauses: (SelectClause \| FromClause \| WhereClause \| ...)[]`      |
| `insert_stmt`       | `table`、`columns`、`values`                                         |
| `update_stmt`       | `table`、`set`、`where`                                              |
| `delete_stmt`       | `from`、`where`                                                      |
| `drop_table_stmt`   | `name`、`ifExistsKw`                                                 |

## 关键字导出

库为每个方言导出保留关键字集合：
`sqliteKeywords`、`bigqueryKeywords`、`mysqlKeywords`、`mariadbKeywords`、`postgresqlKeywords`。

```ts
import { postgresqlKeywords } from "sql-parser-cst";
postgresqlKeywords["SELECT"]; // true
```

## 源码参考

完整 CST 类型定义在克隆仓库的 `.tmp/sql-parser-cst/src/cst/` 目录下。
需要了解特定节点类型时查阅以下文件：

| 文件                     | 内容                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------- |
| `Base.ts`                | BaseNode、Keyword、Whitespace、Empty                                                        |
| `Program.ts`             | Program（顶层节点）                                                                         |
| `Statement.ts`           | Statement 联合类型                                                                          |
| `Expr.ts`                | 所有表达式类型（Expr、ListExpr、ParenExpr、BinaryExpr、Identifier、MemberExpr、EntityName） |
| `Literal.ts`             | StringLiteral、NumberLiteral、BooleanLiteral、NullLiteral 等                                |
| `CreateTable.ts`         | CreateTableStmt、ColumnDefinition、TableOption                                              |
| `Select.ts`              | SelectStmt、SelectClause、FromClause、WhereClause、JoinExpr 等                              |
| `Constraint.ts`          | 列约束和表约束                                                                              |
| `DataType.ts`            | DataType 联合（data_type_name、modified_data_type、time_data_type 等）                      |
| `AlterTable.ts`          | AlterTableStmt 和 AlterAction 类型                                                          |
| `Index.ts`               | CreateIndexStmt、IndexSpecification                                                         |
| `Comment.ts`             | CommentStmt、CommentTarget                                                                  |
| `dialects/Postgresql.ts` | PostgreSQL 专有节点                                                                         |
| `dialects/Mysql.ts`      | MySQL 专有节点                                                                              |
| `dialects/Bigquery.ts`   | BigQuery 专有节点                                                                           |
