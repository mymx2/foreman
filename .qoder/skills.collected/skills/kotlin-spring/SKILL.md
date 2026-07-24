---
name: kotlin-spring
description: >
  Provides a comprehensive suite of 25 specialized skills for Kotlin + Spring backend development, covering the full lifecycle from project analysis, build management, Spring framework core, API design, persistence, transactions, security, serialization, testing, observability, performance tuning, code quality, architecture, CI/CD, to upgrade migration.
  Use when building or maintaining Kotlin + Spring Boot backend projects, diagnosing Spring container or proxy issues, designing REST/WebFlux APIs, configuring Spring Security or JPA, resolving Gradle dependency conflicts, planning database migrations, writing layered tests, analyzing performance bottlenecks, reviewing Kotlin + Spring code, refactoring Java to Kotlin, designing microservice boundaries, containerizing deployments, or navigating major version upgrades (Spring Boot, Kotlin, JDK, javax → jakarta).
license: MIT
metadata:
  origin: https://github.com/mymx2/skills/skills/kotlin-spring
  author: mymx2 <https://github.com/mymx2>
  version: 2026.06.12
  source: https://github.com/jetbrains/skills
---

# Kotlin Backend Agent Skills

面向 **Kotlin + Spring** 后端开发的 AI Agent 技能集合，包含 **25 个专业技能**，覆盖从项目分析、编码、测试到部署和事故响应的完整生命周期。

每个技能是一个结构化的 Markdown 文件，教 AI Agent 如何以深厚的领域专业知识执行特定任务，遵循经过验证的诊断工作流和安全护栏。

---

## 技能分类总览

| 分类                                        | 技能数量 |
| ------------------------------------------- | -------- |
| [🔍 项目分析](#-项目分析)                   | 1        |
| [🏗️ 构建与依赖管理](#️-构建与依赖管理)       | 2        |
| [🧩 Spring 框架核心](#-spring-框架核心)     | 3        |
| [🌐 API 设计与 Web 层](#-api-设计与-web-层) | 2        |
| [💾 持久化与数据](#-持久化与数据)           | 2        |
| [🔄 事务与集成](#-事务与集成)               | 2        |
| [🔐 安全](#-安全)                           | 1        |
| [📊 序列化](#-序列化)                       | 1        |
| [🧪 测试](#-测试)                           | 1        |
| [📈 可观测性与运维](#-可观测性与运维)       | 3        |
| [⚡ 性能与并发](#-性能与并发)               | 1        |
| [♻️ 代码质量与迁移](#️-代码质量与迁移)       | 3        |
| [🏛️ 架构与设计](#️-架构与设计)               | 1        |
| [🚀 CI/CD 与部署](#-cicd-与部署)            | 1        |
| [⬆️ 升级管理](#️-升级管理)                   | 1        |

安装：

```
npx skills add jetbrains/skills \
  --skill project-context-ingestion \
  --skill gradle-kotlin-dsl-doctor \
  --skill dependency-conflict-resolver \
  --skill spring-context-di-reasoning \
  --skill kotlin-spring-proxy-compatibility \
  --skill configuration-properties-profiles-kotlin-safe \
  --skill spring-mvc-webflux-api-builder \
  --skill error-model-validation-architect \
  --skill jpa-spring-data-kotlin-mapper \
  --skill schema-migration-planner \
  --skill transaction-consistency-designer \
  --skill integration-resilience-engineer \
  --skill spring-security-configurator-auditor \
  --skill jackson-kotlin-serialization-specialist \
  --skill test-suite-builder \
  --skill observability-integrator \
  --skill stacktrace-log-triage \
  --skill production-incident-responder \
  --skill performance-concurrency-advisor \
  --skill spring-kotlin-code-review \
  --skill kotlin-idiomatic-refactorer-spring-aware \
  --skill java-kotlin-migration-assistant \
  --skill domain-decomposition-api-design-advisor \
  --skill ci-cd-containerization-advisor \
  --skill upgrade-breaking-change-navigator
```

若下属对应技能不存在，可能是用户有意去除，你可忽略使用对应技能，非本技能指导错误。

---

## 🔍 项目分析

| 技能                      | 说明                                                                                                                                                                                                              |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| project-context-ingestion | 在对仓库做任何改动之前进行全面检查 — 映射模块结构、Spring Boot / Kotlin / Gradle / JDK 版本、编译器插件、Profile 配置、依赖关系和架构边界，确保后续所有建议都与项目实际技术栈兼容。**所有其他技能的默认第一步。** |

## 🏗️ 构建与依赖管理

| 技能                         | 说明                                                                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| gradle-kotlin-dsl-doctor     | 生成、调试和修复 `build.gradle.kts` / `settings.gradle.kts`，以最小兼容改动解决插件冲突、BOM 版本漂移、JDK 工具链不匹配、KAPT/KSP 配置和编译器插件问题。      |
| dependency-conflict-resolver | 诊断和解决 Gradle 类路径冲突、版本漂移和二进制不兼容（`NoSuchMethodError`、`ClassNotFoundException`、链接错误、重复日志绑定等），尊重仓库的真实版本权威来源。 |

## 🧩 Spring 框架核心

| 技能                                          | 说明                                                                                                                                                             |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| spring-context-di-reasoning                   | 诊断 Spring 容器启动失败、Bean 缺失/重复、循环依赖、条件化自动配置不匹配和 Profile 相关的装配问题。                                                              |
| kotlin-spring-proxy-compatibility             | 诊断和预防 Kotlin + Spring 代理失败，涵盖 `@Transactional`、`@Cacheable`、`@Async`、方法级安全、JPA 实体要求 — 特别是当 AOP 注解"看起来生效了但实际没有生效"时。 |
| configuration-properties-profiles-kotlin-safe | 设计和诊断 `@ConfigurationProperties` 绑定、Profile 分层、环境特定覆盖和密钥管理，利用 Kotlin 空安全特性进行安全的配置建模。                                     |

## 🌐 API 设计与 Web 层

| 技能                             | 说明                                                                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| spring-mvc-webflux-api-builder   | 设计和生成 Kotlin Spring HTTP API，包含正确的控制器签名、DTO、参数校验、序列化约定、错误处理和 Web 测试 — 同时支持 MVC 和 WebFlux 技术栈。 |
| error-model-validation-architect | 设计一致的 API 校验和错误处理行为 — 错误分类体系、`@ControllerAdvice`、HTTP 状态码映射、机器可读错误语义，防止内部细节泄露到客户端。       |

## 💾 持久化与数据

| 技能                          | 说明                                                                                                                               |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| jpa-spring-data-kotlin-mapper | 为 Spring Data JPA 和 Hibernate 正确建模 Kotlin 持久化代码 — 实体设计、标识/相等性、抓取计划、N+1 诊断、懒加载陷阱和仓库查询优化。 |
| schema-migration-planner      | 规划安全的数据库 Schema 演进和零停机变更发布 — 使用 Flyway/Liquibase 实现分阶段扩展/收缩迁移、回填策略和应用版本间的向后兼容。     |

## 🔄 事务与集成

| 技能                             | 说明                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------ |
| transaction-consistency-designer | 为跨多个仓库、消息队列和外部系统的业务工作流设计安全的事务边界、回滚行为、幂等性、锁策略和一致性策略。 |
| integration-resilience-engineer  | 设计弹性 HTTP、消息和定时集成 — 显式的超时预算、重试策略、断路器、死信队列行为、幂等性和失败可观测性。 |

## 🔐 安全

| 技能                                 | 说明                                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| spring-security-configurator-auditor | 设计和审计 Spring Security 配置 — 过滤器链、JWT/OAuth2 资源服务器设置、方法级安全、CORS、CSRF 分析和公开端点暴露检查。 |

## 📊 序列化

| 技能                                    | 说明                                                                                                                                                       |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| jackson-kotlin-serialization-specialist | 诊断和设计 Kotlin + Jackson 的 JSON 序列化/反序列化行为 — DTO 反序列化失败、默认参数、空安全、多态载荷、PATCH 语义（区分 null 与缺失）和日期时间格式漂移。 |

## 🧪 测试

| 技能               | 说明                                                                                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| test-suite-builder | 设计和生成分层测试，在单元、切片（`@WebMvcTest`、`@DataJpaTest`）和集成（`@SpringBootTest` + Testcontainers）级别间平衡速度、真实性和回归价值，使用 MockK 和协程测试惯用法。 |

## 📈 可观测性与运维

| 技能                          | 说明                                                                                                               |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| observability-integrator      | 设计可操作的可观测性方案 — 日志、指标、链路追踪和健康端点，SLO 驱动的指标设计、基数控制和异步/协程流中的追踪传播。 |
| stacktrace-log-triage         | 从堆栈跟踪、启动日志和运行时日志中诊断故障 — 区分根因与包装异常、对假设进行排序，同时提出快速缓解和长期修复方案。  |
| production-incident-responder | 指导生产事故响应 — 从首次告警到缓解、诊断和复盘，优先采用可逆操作、证据保全和爆炸半径控制。                        |

## ⚡ 性能与并发

| 技能                            | 说明                                                                                                                       |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| performance-concurrency-advisor | 基于真实证据分析和改进性能、吞吐量、延迟和并发行为 — N+1 查询、连接池饱和、协程/响应式阻塞、锁竞争、缓存策略和并行化决策。 |

## ♻️ 代码质量与迁移

| 技能                                     | 说明                                                                                                                                          |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| spring-kotlin-code-review                | 审查 Kotlin + Spring 变更的行为回归、事务/代理 Bug、API/序列化错误、持久化风险、安全问题和缺失测试 — 行为优先、风险优先的审查方式。           |
| kotlin-idiomatic-refactorer-spring-aware | 将 Kotlin 代码重构为更清晰、更地道的写法，同时不破坏 Spring 行为、序列化、持久化或公开契约。适用于"Java 风格 Kotlin"的清理和领域建模改进。    |
| java-kotlin-migration-assistant          | 将 Java 代码迁移到 Kotlin，不改变行为、公开契约、框架兼容性或二进制假设 — 安全的增量转换，包括 Lombok 替代、平台类型处理和 JPA/代理行为保持。 |

## 🏛️ 架构与设计

| 技能                                    | 说明                                                                                               |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| domain-decomposition-api-design-advisor | 在实现之前将业务需求分解为限界上下文、模块/服务边界、工作流和 API 契约 — 提供 ADR 级别的权衡推理。 |

## 🚀 CI/CD 与部署

| 技能                           | 说明                                                                                                                         |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| ci-cd-containerization-advisor | 设计可重复的构建、容器镜像和部署流水线 — 多阶段 Dockerfile、CI 验证门禁、镜像加固、Kubernetes 探针、滚动发布策略和迁移协调。 |

## ⬆️ 升级管理

| 技能                              | 说明                                                                                                                                                                          |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| upgrade-breaking-change-navigator | 规划和执行高风险的 Spring Boot、Spring Framework、Kotlin、Gradle、JDK 及主要依赖升级 — 显式的兼容性检查点和回退策略，覆盖 `javax` → `jakarta` 迁移、K2 采用、自动配置漂移等。 |

---

## 许可证

[源仓库](https://github.com/yalishevant/kotlin-backend-agent-skills)，基于 `MIT License` 开源。
