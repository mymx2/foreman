---
name: jdbc-dsl
description: >
  使用基于 JdbcClient 扩展的 CRUD DSL 进行数据库操作，
  涵盖高层方法（insert/update/delete/select 等）及其自动行为、实体约定与底层 Builder SQL 生成规则。
license: MIT
metadata:
  origin: https://github.com/mymx2/skills/jdbc-dsl
  author: mymx2 <https://github.com/mymx2>
  version: 2026.05.06
compatibility: Requires Kotlin, JDK25
---

# JDBC CRUD 使用规则

文档分两层：

- `JdbcClient` 扩展方法：业务代码优先使用，包含读写库绑定、超时、SPI handler、逻辑删除、默认 limit、分页 count 等高层行为。
- `InsertBuilder` / `SelectBuilder` / `UpdateBuilder` / `DeleteBuilder` / `Where`：底层 SQL 生成规则，用来解释高层 DSL
  的行为，不作为业务代码的首选入口。

## 实体约定

CRUD DSL 依赖 `io.mybatis.provider.Entity` 元数据：

```kotlin
@Entity.Table(
  value = "user",
  props = [
    Entity.Prop(name = "tableMeta.dbType", value = "postgresql"),
    Entity.Prop(name = "tableLogic.isDelete", value = "delete_time is not null"),
    Entity.Prop(name = "tableLogic.notDelete", value = "delete_time is null"),
    Entity.Prop(name = "tableLogic.setDelete", value = "delete_time = now()"),
  ],
)
data class User(
  @Entity.Column(value = "id", id = true, nullable = false, updatable = false)
  var id: Long,
  @Entity.Column(value = "name", nullable = true)
  var name: String?,
)
```

常用表属性：

| 属性                   | 用途                                                |
| ---------------------- | --------------------------------------------------- |
| `tableMeta.db`         | 默认数据源                                          |
| `tableMeta.dbRead`     | 读数据源，多个值用逗号分隔，高层读操作会随机选择    |
| `tableMeta.dbWrite`    | 写数据源                                            |
| `tableMeta.dbType`     | 数据库类型，用于 `limit(pageNum, pageSize, dbType)` |
| `tableLogic.notDelete` | 查询、更新、删除时追加的未删除条件                  |
| `tableLogic.setDelete` | 默认删除时使用的逻辑删除 set 语句                   |

## JdbcClient 高层 DSL

高层 DSL 都是 `JdbcClient` 扩展方法，业务代码优先用这一层。查询、更新、删除条件一般从 lambda 参数 `s.where()` 进入，然后继续链式调用。

### 公共流程

高层方法会根据实体元数据做这些事：

- 通过 `JdbcOps.boundDb(...)` 绑定读库或写库。
- 通过 `JdbcOps.boundTimeout(...)` 绑定查询超时。
- 调用 `BeforeBuilderPrepare` SPI handler。
- 将 Builder 的参数 map 转成 `paramsMap.values.toList()` 后传给 `JdbcClient.params(...)`。

读写库绑定规则：

- 读操作：优先使用 `tableMeta.dbRead`，多个读库逗号分隔时随机选择；如果 `JdbcOps.ENTITY_PROP_DB_READ_CLOSE = true`
  ，读操作不使用读库配置。
- 写操作：优先使用 `tableMeta.dbWrite`。
- 未配置读写库时回退到 `tableMeta.db`。
- `JdbcOps.SCOPED_DB_TYPE` 已绑定时优先使用它，否则使用实体的 `tableMeta.dbType`。

### insert

```kotlin
val rows = jdbcClient.insert(user)
```

行为：

- 默认超时 `10m`。
- 写库绑定。
- 调用 `beforeInsertPrepare(insertBuilder)`。
- 使用 `InsertBuilder<T>().values(value).prepare()` 生成 SQL。
- 如果实体有可插入 id 列，且当前 id 为 `null`、`0`、`0L` 或空字符串，则使用 `GeneratedKeyHolder` 接收数据库生成的
  key，并尝试回写到实体 id 字段。
- 返回影响行数。

### insertBatch

```kotlin
val rows = jdbcClient.insertBatch(users)
```

参数：

- `batchSize = 1000`
- `batchTimeout = 20m`
- `autoTransaction = true`

行为：

- `values` 为 `null` 或空列表时返回 `0`。
- 按 `batchSize` 分批。
- 每批调用 `beforeInsertPrepare(insertBuilder)`。
- 默认自动包事务，事务超时按分批数量和单批超时计算。
- 对缺失 id 的实体使用 `GeneratedKeyHolder`，并尝试按返回顺序回写 id。

### update

```kotlin
val rows = jdbcClient.update<User> { s, t ->
  s.set(t::name, "Tom", true)
    .where()
    .eq(t::id, 1L)
}
```

行为：

- 默认超时 `10m`。
- 创建 `UpdateBuilder<T>` 和一个无参实体实例 `t`，用于属性引用。
- 委托给 `updateBatch(listOf(updateBuilder), batchTimeout = timeout, autoTransaction = false)`。

### updateBatch

```kotlin
val rows = jdbcClient.updateBatch(builders)
```

参数：

- `batchSize = 1000`
- `batchTimeout = 20m`
- `autoTransaction = true`

行为：

- `builders` 为 `null` 或空列表时返回 `0`。
- 会过滤掉 `setValues` 为空的 builder。
- 每个 builder 执行前依次调用：
  - `beforeUpdatePrepare(ub)`
  - `avoidNullCriteria(ub)`
  - `addLogicDelete(ub)`
  - `ub.prepare()`
- `avoidNullCriteria` 在 `addLogicDelete` 前执行，所以空 where 的更新会先注入 `1 = 0`，再追加逻辑删除条件，避免全表更新。
- SQL 为空时不执行。

### delete

```kotlin
val rows = jdbcClient.delete<User> { s, t ->
  s.where().eq(t::id, 1L)
}
```

行为：

- 默认超时 `10m`。
- 写库绑定。
- 默认逻辑删除；如果实体配置了 `tableLogic.setDelete`，底层生成 `update table set ...`。
- 显式调用 `s.physicalDelete()` 才生成物理删除。
- 执行前依次调用：
  - `beforeDeletePrepare(deleteBuilder)`
  - `avoidNullCriteria(deleteBuilder)`
  - `addLogicDelete(deleteBuilder)`
  - `deleteBuilder.prepare()`
- 空 where 会先注入 `1 = 0`，再追加逻辑删除条件，避免全表删除。

### selectList

```kotlin
val list = jdbcClient.selectList<User> { s, t ->
  s.where().eq(t::status, 1)
}
```

参数：

- `timeout = 10m`
- `limit = 100_000`

行为：

- 读库绑定。
- 执行前依次调用：
  - `beforeSelectPrepare(selectBuilder)`
  - `avoidNullCriteria(selectBuilder)`
  - `addLogicDelete(selectBuilder)`
  - `addSelectLimit(selectBuilder, pageSize = limit)`
- 如果 builder 中误设了 `countColumns`，会清空，确保返回实体列表。
- `JdbcClient.withMaxRows(limit)` 会同时限制最大返回行数。
- 空 where 会先注入 `1 = 0`，再追加逻辑删除条件，所以默认不会查询全表。

### selectOne

```kotlin
val one = jdbcClient.selectOne<User> { s, t ->
  s.where().eq(t::id, 1L)
}
```

参数：

- `timeout = 2m`
- `throwIfNotVolatile = false`
- `logIfNotVolatile = true`

行为：

- 内部调用 `selectList(timeout = timeout, limit = 2, builder = builder)`。
- 无结果返回 `null`。
- 多于 1 条时，`throwIfNotVolatile = true` 会抛错。
- 多于 1 条且不抛错时，默认记录 `TooManyResultsException` 日志，然后返回第一条。

### count

```kotlin
val total = jdbcClient.count<User> { s, t ->
  s.where().eq(t::status, 1)
}
```

行为：

- 默认超时 `2m`。
- 读库绑定。
- 执行前调用 `beforeSelectPrepare(selectBuilder)` 和 `addLogicDelete(selectBuilder)`。
- `count()` 不调用 `avoidNullCriteria`，空 where 时会统计符合逻辑删除条件的数据，而不是强制 `1 = 0`。
- 会清空 `orderByClause` 和 `limitClause`。
- 如果存在 `groupBy` 或 `having`，先把查询列设为 `1`，再把原 SQL 包成：

```sql
select count(*) as tableCount from (<原 SQL>) as t
```

### selectPage

```kotlin
val pageResult = jdbcClient.selectPage<User>(page) { s, t ->
  s.where().eq(t::status, 1).last {
    it.orderByDesc(t::id)
  }
}
```

参数：

- `timeout = 10m`
- `maxPageSize = 100_000`

行为：

- 要求 `page.pageNum > 0`。
- 要求 `page.pageSize > 0`。
- 要求 `page.pageSize <= maxPageSize`。
- 读库绑定。
- 执行前调用：
  - `beforeSelectPrepare(selectBuilder)`
  - `addLogicDelete(selectBuilder)`
  - `addSelectLimit(selectBuilder, pageNum, pageSize)`
- `selectPage` 不调用 `avoidNullCriteria`，空 where 时会查询符合逻辑删除条件的数据，并自动追加分页 limit。
- 主查询使用 `withMaxRows(pageNum * pageSize)`。
- count 在虚拟线程里并发执行。
- count 查询会清空 `orderByClause` 和 `limitClause`。
- 有 `groupBy` 或 `having` 时，count 使用子查询包裹统计。
- 返回 `OpPageResponse(records, total, size = pageSize, current = pageNum)`。

### 高层 DSL 自动附加逻辑删除

`addLogicDelete(builder)` 会读取 `tableLogic.notDelete`，并注入到 `lastCriteria`：

```sql
delete_time is null
```

会自动调用它的方法：

- `updateBatch`
- `delete`
- `selectList`
- `count`
- `selectPage`

`insert` 和 `insertBatch` 不追加逻辑删除条件。

### 高层 DSL 的空条件差异

需要特别注意：

| 方法          | 是否主动调用 `avoidNullCriteria` | 空 where 的效果                        |
| ------------- | -------------------------------- | -------------------------------------- |
| `selectList`  | 是                               | 注入 `1 = 0`，默认不查全表             |
| `selectOne`   | 是，来自 `selectList`            | 注入 `1 = 0`，默认不查全表             |
| `update`      | 是，来自 `updateBatch`           | 注入 `1 = 0`，默认不全表更新           |
| `updateBatch` | 是                               | 注入 `1 = 0`                           |
| `delete`      | 是                               | 注入 `1 = 0`，默认不全表删除           |
| `count`       | 否                               | 统计符合逻辑删除条件的数据             |
| `selectPage`  | 否                               | 查询符合逻辑删除条件的数据，并追加分页 |

## Builder 基本规则

本节是底层实现规则，用于理解高层 DSL 最终如何生成 SQL。以下示例主要来自测试和框架扩展场景，业务代码通常不直接 new Builder
并执行 `prepare()`。

底层 Builder 的 `prepare(placeholder = Placeholder.JDBC)` 返回：

```kotlin
Pair<String, MutableMap<String, Any?>>
```

默认占位符是 JDBC `?`。参数按 SQL 出现顺序写入 `LinkedHashMap`，执行时通常取：

```kotlin
val params = paramsMap.values.toList()
```

占位符类型：

| Placeholder | 渲染     |
| ----------- | -------- |
| `JDBC`      | `?`      |
| `NAMED`     | `:key`   |
| `MYBATIS`   | `#{key}` |

原始 SQL 入口：

- `join(...)`
- `having(...)`
- `orderBy(String)`
- `limit(String)`
- `inject(...)`
- `setInject(...)`
- `startSql`
- `endSql`

这些都不会做 SQL 注入防护，只能拼后端可信内容。

## 链式 Where 条件

条件一般写在 `JdbcClient` 高层 DSL 的 lambda 里，从 `s.where()` 进入。链式调用默认使用 `and` 连接：

```kotlin
jdbcClient.selectList<User> { s, t ->
  s.where()
    .eq(t::id, 1L)
    .like(t::name, "tom")
    .between(t::age, 18, 30)
}
```

生成：

```sql
where id = ? and name like ? and age between ? and ?
```

常用条件：

| 方法                                   | SQL                              |
| -------------------------------------- | -------------------------------- |
| `isNull(User::name)`                   | `name is null`                   |
| `isNotNull(User::age)`                 | `age is not null`                |
| `eq(User::id, 1L)`                     | `id = ?`                         |
| `ne(User::id, 1L)`                     | `id <> ?`                        |
| `gt/ge/lt/le`                          | `>` / `>=` / `<` / `<=`          |
| `` `in`(User::status, listOf(1, 2)) `` | `status in (?, ?)`               |
| `notIn(User::age, listOf(10, 20))`     | `age not in (?, ?)`              |
| `between(User::age, 18, 30)`           | `age between ? and ?`            |
| `notBetween(...)`                      | `not between ? and ?`            |
| `like(User::name, "tom")`              | `name like ?`，参数为 `%tom%`    |
| `notLike(User::name, "tom")`           | `name not like ?`                |
| `isNullOrBlank(User::name)`            | `((name is null) or (name = ?))` |
| `nonNullAndBlank(User::name)`          | `name is not null and name <> ?` |

空值处理：

- `like(..., null)` 不生成条件。
- `in/notIn` 会过滤集合里的 `null`；过滤后为空则不生成条件。
- `inject(condition, value)` 的 `value` 只能是 Spring 判定的 simple value，集合参数也只能包含 simple value，否则抛
  `IllegalArgumentException`。

### OR 条件

顶层 `or { ... }` 会新增一组 Criteria：

```kotlin
jdbcClient.selectList<User> { s, t ->
  s.where().eq(t::id, 1L).or {
    it.eq(t::id, 2L)
    it.eq(t::status, 1)
  }
}
```

生成：

```sql
where id = ? or (id = ? and status = ?)
```

`and({ ... }, { ... })` 会在当前 AND 链里追加一组 OR：

```kotlin
jdbcClient.selectList<User> { s, t ->
  s.where()
    .eq(t::status, 1)
    .and(
      { it.eq(t::age, 18).like(t::name, "tom") },
      { it.eq(t::age, 20).like(t::name, "jack") },
    )
}
```

生成：

```sql
where status = ? and ((age = ? and name like ?) or (age = ? and name like ?))
```

### last 尾部条件

`last { ... }` 用于附加最后一组条件和 SQL 尾部子句：

```kotlin
jdbcClient.selectList<User> { s, t ->
  s.where().eq(t::status, 1).last {
    it.gt(t::age, 18)
    it.orderByAsc(t::id)
  }
}
```

生成：

```sql
where status = ? and age > ? order by id ASC
```

支持：

- `groupBy(User::status)` 或 `groupBy("status")`
- `having("count(*) > 1")`
- `orderByAsc(...)` / `orderByDesc(...)`
- `orderBy(orders, orderPositions)`
- `limit("limit 0, 10")`
- `limit(pageNum, pageSize, dbType)`

只有分组条件时，`SelectBuilder` 可以生成不带 `where` 的尾部 SQL：

```sql
select status from user
group by status having count(*) > 1
```

### 原始条件和子查询

原始条件也优先在高层 lambda 中链式调用。能参数化时用 `inject(condition, value)`，不要把用户输入拼进 SQL 字符串：

```kotlin
jdbcClient.selectList<User> { s, t ->
  s.where()
    .eq(t::status, 1)
    .inject("length(name) >", 3)
}
```

生成：

```sql
where status = ? and length(name) > ?
```

只有后端固定常量 SQL 才使用 `inject("length(name) > 3")` 这种无参数写法。

子查询也在高层 lambda 里链式挂到外层条件上。优先用 `SelectBuilder` 表达子查询，因为它能明确 select 列、join、distinct 等查询结构：

```kotlin
jdbcClient.selectList<User> { s, t ->
  val subQuery = SelectBuilder(User::class).apply {
    select(User::id).where().eq(User::status, 1)
  }

  s.where().`in`(t::id, subQuery)
}
```

生成：

```sql
where id in (select id from user
where status = ?)
```

`exists(subQuery)` 默认生成 `select 1`：

```kotlin
jdbcClient.selectList<User> { s, _ ->
  val subQuery = SelectBuilder(User::class).apply {
    where().eq(User::status, 1)
  }

  s.where().exists(subQuery)
}
```

```sql
where exists (select 1 from user
where status = ?)
```

还支持：

- `notIn(t::id, subQuery)`
- `notExists(subQuery)`

子查询参数会合并到外层参数 map，顺序跟 SQL 渲染顺序一致。普通业务查询不要单独 new `Where` 作为入口；需要复用子查询时，把可复用片段封装成返回
`SelectBuilder` 的方法，再链式挂到 `s.where()`。原始 `inject(condition, subQuery)` 保留给框架扩展或固定 SQL 片段，不作为业务优先写法。

## SelectBuilder

默认查询实体所有可查询列，列名和属性名不一致时会自动加别名：

```kotlin
val qb = SelectBuilder(User::class)
qb.where().eq(User::id, 1L)
```

生成：

```sql
select id, name, age, status, delete_time as deleteTime from user
where id = ?
```

常用方法：

- `select(User::id, User::name)`：覆盖默认查询列。
- `exclude(...)`：从默认查询列中排除指定列。
- `distinct()`：生成 `select distinct ...`。
- `count()`：生成 `select count(*) as tableCount ...`。
- `count(User::id)`：生成 `select count(id) as tableCount ...`。
- `join("left join ...")`：在 `from table` 后追加 JOIN 原始 SQL。
- `where()`：进入链式条件；业务代码通常通过高层 lambda 里的 `s.where()` 使用。
- `last { ... }`：追加 group/order/limit 等尾部子句。

示例：

```kotlin
SelectBuilder(User::class).apply {
  select(User::id, User::name)
  join("left join dept d on d.id = user.dept_id")
  where().eq(User::status, 1)
}
```

生成：

```sql
select id, name from user
left join dept d on d.id = user.dept_id
where status = ?
```

空 where 默认安全返回：

```sql
select id, name, age, status, delete_time as deleteTime from user
where 1 = 0
```

## InsertBuilder

单条插入：

```kotlin
val user = User(id = 1L, name = "Tom", age = 18, status = 1, deleteTime = null)

val ib = InsertBuilder<User>()
ib.values(user)
```

生成：

```sql
insert into user (id, name, age, status, delete_time) values (?, ?, ?, ?, ?)
```

批量插入：

```kotlin
val users = listOf(
  User(1L, "Tom", 18, 1, null),
  User(2L, "Jerry", 20, 1, null),
)

InsertBuilder<User>().values(users)
```

生成：

```sql
insert into user (id, name, age, status, delete_time) values (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
```

没有调用 `values(...)` 时：

```kotlin
InsertBuilder<User>().prepare()
```

返回空 SQL 和空参数。

## UpdateBuilder

普通更新：

```kotlin
val ub = UpdateBuilder(User::class)
ub.set(User::name, "Tom", true)
  .set(User::age, 18, true)
ub.where().eq(User::id, 1L)
```

生成：

```sql
update user set name = ?, age = ?
where id = ?
```

参数顺序是 set 值在前，where 值在后。

写入 null：

```kotlin
ub.set(User::name, null, setNullIfNullValue = true)
```

如果 `setNullIfNullValue = false`，null set 会被忽略；如果没有任何有效 set，`prepare()` 返回空 SQL 和空参数。

表达式更新：

```kotlin
ub.setInject(User::age, "age + 1")
ub.where().eq(User::id, 1L)
```

生成：

```sql
update user set age = age + 1
where id = ?
```

`setInject` 不生成参数，表达式必须由后端保证安全。

有 set 但没有 where 时，底层 Builder 默认安全生成：

```sql
update user set name = ?
where 1 = 0
```

## DeleteBuilder

默认优先逻辑删除。实体配置了 `tableLogic.setDelete` 时：

```kotlin
val db = DeleteBuilder(User::class)
db.where().eq(User::id, 1L)
```

生成：

```sql
update user set delete_time = now()
where id = ?
```

物理删除：

```kotlin
val db = DeleteBuilder(User::class).physicalDelete()
db.where().eq(User::id, 2L)
```

生成：

```sql
delete from user
where id = ?
```

没有 where 时仍然走 `where 1 = 0`：

```sql
update user set delete_time = now()
where 1 = 0
```

或：

```sql
delete from user
where 1 = 0
```

## 推荐写法

- 业务代码优先用 `JdbcClient` 高层 DSL，在 lambda 中链式调用，不直接执行 Builder 生成的 SQL。
- 查询列、条件列、更新列尽量使用属性引用，不手写列名。
- 用户输入只能作为参数值传入，不要拼进 `inject`、`join`、`having`、`orderBy(String)`、`limit(String)`、`setInject`。
- 批量值、IN 值使用集合参数，让 Builder 生成占位符。
- 写更新和删除时保留默认空条件保护；只有非常明确的场景才关闭 `avoidNullCriteria`。
- 需要子查询时优先在高层 lambda 里创建 `SelectBuilder` 并链式挂到 `s.where()`；不要把直接构造 `Where` 当作业务入口。
- `selectList` 默认不查全表；`selectPage` 和 `count` 的空条件语义不同，使用时要明确是否只依赖逻辑删除条件。
