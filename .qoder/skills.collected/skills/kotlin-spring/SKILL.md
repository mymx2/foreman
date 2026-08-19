---
name: kotlin-spring
description: 'Router for the jetbrains/skills pack: maps 25 specialized skills to concrete Kotlin + Spring problems. Use when working on a Kotlin + Spring project and hitting build, dependency conflict, Spring container, API design, JPA, transaction, security, serialization, testing, performance, or version-upgrade issues. Not for non-Kotlin/Spring stacks or general programming Q&A.'
when_to_use: 'kotlin, spring boot, gradle 构建, jpa, spring security, kotlin 后端'
license: MIT
metadata:
  origin: https://github.com/mymx2/skills/skills/kotlin-spring
  author: mymx2 <https://github.com/mymx2>
  version: 2026.08.19
  source: https://github.com/jetbrains/skills
---

# Kotlin Backend Agent Skills

这是路由器，不是知识库：价值在于把症状映射到正确的子技能，而不是在这里复述 Spring 知识。

## Outcome Contract

- **Outcome**: 用户的问题被路由到正确的子技能（含安装命令），或确认子技能缺失后由你直接回答。
- **Done when**: 按症状在下方分类表中定位到具体子技能名；子技能未安装时给出对应安装命令。
- **Evidence**: 分类表中的症状描述与用户问题的匹配；`npx skills list` 的实际输出。
- **Authorization**: 路由和解答可以直接做；安装子技能前需用户确认。

## 使用流程

1. 确认项目确实是 Kotlin + Spring 技术栈；不是则不要动用本路由器。
2. 按症状在下方分类表中定位子技能——表内描述即触发条件。
3. 用 `npx skills list` 确认该子技能是否已安装。
4. 未安装则给出针对性安装命令（见下方"安装"），经用户确认后执行。
5. 子技能缺失且用户不打算安装时，直接凭通用能力回答，并说明跳过了哪个子技能。子技能被用户有意裁剪是正常情况，不是路由错误。

## 安装

全量安装（25 个）：

```bash
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

只需个别技能时，保留对应 `--skill` 参数即可。

## 🔍 项目分析

| 技能                      | 说明                                                                                                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| project-context-ingestion | 在对仓库做任何改动之前进行全面检查——模块结构、Spring Boot / Kotlin / Gradle / JDK 版本、编译器插件、Profile 配置、依赖关系和架构边界。**所有其他技能的默认第一步。** |

## 🏗️ 构建与依赖管理

| 技能                         | 说明                                                                                                                                                     |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| gradle-kotlin-dsl-doctor     | 生成、调试和修复 `build.gradle.kts` / `settings.gradle.kts`，以最小兼容改动解决插件冲突、BOM 版本漂移、JDK 工具链不匹配、KAPT/KSP 配置和编译器插件问题。 |
| dependency-conflict-resolver | 诊断和解决 Gradle 类路径冲突、版本漂移和二进制不兼容（`NoSuchMethodError`、`ClassNotFoundException`、链接错误、重复日志绑定等）。                        |

## 🧩 Spring 框架核心

| 技能                                          | 说明                                                                                                                                                 |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| spring-context-di-reasoning                   | 诊断 Spring 容器启动失败、Bean 缺失/重复、循环依赖、条件化自动配置不匹配和 Profile 相关的装配问题。                                                  |
| kotlin-spring-proxy-compatibility             | 诊断和预防 Kotlin + Spring 代理失败：`@Transactional`、`@Cacheable`、`@Async`、方法级安全、JPA 实体要求——特别是 AOP 注解"看起来生效了但实际没有"时。 |
| configuration-properties-profiles-kotlin-safe | 设计和诊断 `@ConfigurationProperties` 绑定、Profile 分层、环境特定覆盖和密钥管理。                                                                   |

## 🌐 API 设计与 Web 层

| 技能                             | 说明                                                                                                                   |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| spring-mvc-webflux-api-builder   | 设计和生成 Kotlin Spring HTTP API：控制器签名、DTO、参数校验、序列化约定、错误处理和 Web 测试，MVC 和 WebFlux 均覆盖。 |
| error-model-validation-architect | 设计一致的 API 校验和错误处理：错误分类体系、`@ControllerAdvice`、HTTP 状态码映射、机器可读错误语义。                  |

## 💾 持久化与数据

| 技能                          | 说明                                                                                                                          |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| jpa-spring-data-kotlin-mapper | 为 Spring Data JPA 和 Hibernate 建模 Kotlin 持久化代码：实体设计、标识/相等性、抓取计划、N+1 诊断、懒加载陷阱和仓库查询优化。 |
| schema-migration-planner      | 规划安全的数据库 Schema 演进和零停机发布：Flyway/Liquibase 分阶段扩展/收缩迁移、回填策略、跨版本向后兼容。                    |

## 🔄 事务与集成

| 技能                             | 说明                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| transaction-consistency-designer | 为跨仓库、消息队列和外部系统的工作流设计事务边界、回滚行为、幂等性、锁策略和一致性策略。 |
| integration-resilience-engineer  | 设计弹性 HTTP、消息和定时集成：超时预算、重试、断路器、死信队列、幂等性和失败可观测性。  |

## 🔐 安全

| 技能                                 | 说明                                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| spring-security-configurator-auditor | 设计和审计 Spring Security 配置：过滤器链、JWT/OAuth2 资源服务器、方法级安全、CORS、CSRF 和公开端点暴露检查。 |

## 📊 序列化

| 技能                                    | 说明                                                                                                                 |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| jackson-kotlin-serialization-specialist | 诊断和设计 Kotlin + Jackson 序列化行为：DTO 反序列化失败、默认参数、空安全、多态载荷、PATCH 语义和日期时间格式漂移。 |

## 🧪 测试

| 技能               | 说明                                                                                                                                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| test-suite-builder | 设计分层测试：单元、切片（`@WebMvcTest`、`@DataJpaTest`）和集成（`@SpringBootTest` + Testcontainers）间的速度/真实性平衡，MockK 和协程测试惯用法。 |

## 📈 可观测性与运维

| 技能                          | 说明                                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| observability-integrator      | 设计可操作的可观测性方案：日志、指标、链路追踪和健康端点，SLO 驱动的指标设计、基数控制和协程流中的追踪传播。 |
| stacktrace-log-triage         | 从堆栈跟踪和日志中诊断故障：区分根因与包装异常、对假设排序，同时给出快速缓解和长期修复。                     |
| production-incident-responder | 指导生产事故响应：从首次告警到缓解、诊断和复盘，优先可逆操作、证据保全和爆炸半径控制。                       |

## ⚡ 性能与并发

| 技能                            | 说明                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------- |
| performance-concurrency-advisor | 基于真实证据分析和改进性能：N+1 查询、连接池饱和、协程/响应式阻塞、锁竞争、缓存策略和并行化决策。 |

## ♻️ 代码质量与迁移

| 技能                                     | 说明                                                                                                 |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| spring-kotlin-code-review                | 审查 Kotlin + Spring 变更的行为回归、事务/代理 Bug、API/序列化错误、持久化风险、安全问题和缺失测试。 |
| kotlin-idiomatic-refactorer-spring-aware | 把"Java 风格 Kotlin"重构为地道写法，同时不破坏 Spring 行为、序列化、持久化或公开契约。               |
| java-kotlin-migration-assistant          | 将 Java 代码迁移到 Kotlin：行为、公开契约、框架兼容性不变的增量转换，含 Lombok 替代和平台类型处理。  |

## 🏛️ 架构与设计

| 技能                                    | 说明                                                                                              |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| domain-decomposition-api-design-advisor | 在实现之前把业务需求分解为限界上下文、模块/服务边界、工作流和 API 契约，提供 ADR 级别的权衡推理。 |

## 🚀 CI/CD 与部署

| 技能                           | 说明                                                                                                              |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| ci-cd-containerization-advisor | 设计可重复的构建、容器镜像和部署流水线：多阶段 Dockerfile、CI 验证门禁、镜像加固、Kubernetes 探针和滚动发布策略。 |

## ⬆️ 升级管理

| 技能                              | 说明                                                                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| upgrade-breaking-change-navigator | 规划和执行高风险的 Spring Boot、Kotlin、Gradle、JDK 及主要依赖升级：显式兼容性检查点和回退策略，覆盖 `javax` → `jakarta`、K2 采用、自动配置漂移。 |

## 许可证

[源仓库](https://github.com/yalishevant/kotlin-backend-agent-skills)，基于 `MIT License` 开源。
