# 设备环境供给（可选章节）

本文件不在常规操控流程里——只在你或用户需要从零准备设备环境（Android SDK/AVD、鸿蒙 DevEco/HDC、iOS Xcode/Simulator）时读它。

mobile-use 的定位是"设备供给是用户的事"：日常只用 adb/hdc/simctl 直驱已就绪的设备。本文件补的是**供给这一段**，即没有可用设备时怎么把环境搭起来。

## 通用纪律（三平台共用）

- **先全部只读诊断，再请求任何变更**。诊断阶段不动系统。
- 安装 SDK、接受 license、下载运行时、创建虚拟设备、改 shell 配置、用 `sudo`、切换 Xcode 版本——**每一项都要先问用户**。
- 优先用官方安装器（Android Studio / DevEco Studio / Xcode）和它们的 SDK 管理器，不编造第三方下载地址。
- 不静默修改 `.zshrc`、`.bashrc`、IDE 设置、签名身份、Gradle 属性或项目文件。
- 不要在环境供给阶段启动模拟器/仿真器/预览器——列举目标就是最后一个只读检查。
- 区分三类事实：检查工具自身确认的 / 已应用到 IDE 配置的 / 仍未验证的实时行为。命令级环境变量覆盖不等于 IDE 进程继承了它。
- 供给完成后若目标列表仍为空，先重启一次 IDE 让插件宿主继承环境，再诊断。

## Android

逐项探测，缺什么补什么，不要一上来就重装 SDK。

macOS / Linux：

```bash
java -version 2>&1 | head -1
command -v gradle sdkmanager adb emulator || true
echo "ANDROID_HOME=$ANDROID_HOME"
echo "ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
```

Windows PowerShell：

```powershell
where.exe java 2>$null
where.exe gradle 2>$null
where.exe sdkmanager 2>$null
where.exe adb 2>$null
where.exe emulator 2>$null
Write-Output "ANDROID_HOME=$env:ANDROID_HOME"
```

诊断结论决定下一步：

| 现象 | 处理 |
|---|---|
| **只缺 Gradle** | 装 Gradle 即可，**不要重装 Android SDK** |
| 缺 Java | 装 JDK 17（Temurin 或 openjdk@17） |
| 缺 sdkmanager/adb/emulator | 装 Android 命令行工具 + platform-tools + emulator |
| 缺 AVD | 用 `avdmanager create avd` 建一个 |
| 都已就绪、但 `adb devices` 为空 | 正常——模拟器未启动，先启动再连 |

## 默认版本基线

不确定版本时用这组（太老会撞新 AGP/Compose 要求）：

- JDK major：`17`
- Android API level：`35`
- build-tools：`35.0.0`
- system image variant：`default`
- ABI：Apple Silicon → `arm64-v8a`；其余 → `x86_64`

### system image 变体怎么选

| 变体 | 体积 | 什么时候用 |
|---|---|---|
| `default` | 最小 | 普通构建/运行测试，默认选它 |
| `google_apis` | 中 | 需要 Google Play 服务以外的 Google API |
| `google_apis_playstore` | 最大 | 只有需要 Play Store 服务时才用 |

## 安装 SDK 包

```bash
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"   # macOS 示例
export ANDROID_SDK_ROOT="$ANDROID_HOME"
API=35; BT=35.0.0; VARIANT=default
case "$(uname -m)" in arm64) ABI=arm64-v8a ;; *) ABI=x86_64 ;; esac

sdkmanager --sdk_root="$ANDROID_HOME" --install \
  "cmdline-tools;latest" "platform-tools" "emulator" \
  "platforms;android-$API" "build-tools;$BT" \
  "system-images;android-$API;$VARIANT;$ABI"
```

Windows 用 `sdkmanager.bat`，SDK 根默认 `$env:LOCALAPPDATA\Android\Sdk`：

```powershell
$SdkRoot = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_HOME = $SdkRoot; $env:ANDROID_SDK_ROOT = $SdkRoot
& "$SdkRoot\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root="$SdkRoot" --install `
  "cmdline-tools;latest" "platform-tools" "emulator" `
  "platforms;android-35" "build-tools;35.0.0" `
  "system-images;android-35;default;x86_64"
```

**许可证**：`sdkmanager` 问 license 时停下，让用户确认：

```bash
sdkmanager --sdk_root="$ANDROID_HOME" --licenses
```

**超时**：系统镜像常达数 GB，命令要给足超时（10–30 分钟）。下载超时就原命令加长超时重试；**同一包别并发跑两个 sdkmanager**。不要在后台跑安装命令，也不要只 `| tail` 丢掉日志——留下完整输出便于排障。

## 创建 AVD

只在没有可用 USB 设备、且确实需要新模拟器目标时创建。

```bash
avdmanager create avd \
  --name medium_phone \
  --package "system-images;android-35;default;x86_64" \
  --device "medium_phone"
```

- AVD 已存在时**不要删除**，除非用户明确确认
- 用 `emulator -list-avds` / `avdmanager list avd` 先查已有
- 启动：`emulator -avd <name>`（首次启动较慢，给足超时）

## Windows 模拟器加速

命令流程能装好 SDK 和 AVD，但加速常需用户或管理员动作。

先检查：

```powershell
emulator.exe -accel-check
```

不通过时依次排查：

1. BIOS/UEFI 里是否开了 CPU 虚拟化（没开需用户自己进 BIOS）
2. 优先启用 Windows Hypervisor Platform（WHPX）
3. 仍缺驱动时装 Android Studio，让用户走完 Device Manager / 驱动提示

加速检查不通过时不要硬启模拟器。

## 工程侧修复

`gradle.properties`（项目用了 AndroidX 或 Compose 时需要）：

```properties
android.useAndroidX=true
android.nonTransitiveRClass=true
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
```

`local.properties`（告诉 Gradle SDK 在哪）——macOS：

```bash
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
```

Windows：

```powershell
"sdk.dir=$($env:ANDROID_HOME -replace '\\','/')" | Set-Content local.properties
```

Gradle wrapper 缺失且有全局 Gradle 时：

```bash
gradle wrapper --gradle-version 8.9
```

## 构建安装管线

环境就绪后的标准链路：

```bash
./gradlew assembleDebug          # 或 assemble<Flaver><Variant>
adb install -r path/to/app-debug.apk
adb shell am start -n <pkg>/.MainActivity
adb logcat -d > log.txt          # 抓日志
```

找 APK 位置：

```bash
find app/build/outputs/apk -name "*.apk" -type f
```

UI 自动化测试：

```bash
./gradlew connectedAndroidTest   # 跑已就绪设备上的 androidTest
```

## 完成判据（Android）

环境算就绪的条件：

- `adb`、`sdkmanager`、`java`、`gradle` 都能执行
- 至少有一个可用目标：USB 设备，或（模拟器流程）`emulator` + `avdmanager` + 至少一个 AVD
- Windows 下模拟器流程还要 `emulator -accel-check` 通过
- `adb devices` 在模拟器启动前为空是**正常**的，不算失败

## HarmonyOS

### 依赖组成

DevEco Studio 自带整套工具链：Hvigor 构建、内嵌 Node.js、OpenHarmony SDK、Previewer 运行时、HDC。通常是**做一个预览**而不是 `hdc list targets` 就能判断可用。

### 诊断

```bash
command -v hdc || true
hdc list targets
echo "DEVECO_STUDIO_HOME=$DEVECO_STUDIO_HOME"
```

macOS 默认安装路径：`DEVECO_STUDIO_HOME=/Applications/DevEco-Studio.app/Contents`

### 供给步骤

1. 从华为官方 DevEco Studio 资源页下载**完整安装包**（不是单独的 SDK）。
2. 完成首次启动的 SDK 配置，确认默认 OpenHarmony SDK 与 Previewer 组件都在。
3. 在 DevEco Studio 里打开鸿蒙工程，**先渲染一次手机预览**——部分 DevEco 版本需要这一步才会生成 `.idea/previewer/phone/phoneSettingConfig_rd.json`。
4. 在 DevEco 里启动或连接目标设备，然后确认 `hdc list targets` 返回它的**准确 ID**。

### 平台边界

- macOS / Windows：可用 Previewer + HDC 两条路径
- Linux：DevEco Previewer 未作为宿主运行时发布，只能以 attach-only 模式连 HDC 目标——**不自动构建、不安装、不启动**
- **不要从产品字符串推断目标是模拟器还是真机**，也不要把未声明的录屏/日志能力当成有

### 完成判据（HarmonyOS）

- `hdc` 可执行且 `hdc list targets` 返回至少一个准确 ID
- Previewer 路径下：工程在 DevEco 中成功渲染过一次预览
- 目标发现**永远不隐式选第一个设备**，必须按 ID 显式指定

## iOS

仅 macOS。需要完整 Xcode（只有 Command Line Tools 不够），且只针对 iPhone 模拟器，不面向真机。

### 诊断

```bash
xcode-select -p
xcodebuild -version 2>&1 | head -3
xcrun simctl list devices available | head -20
command -v node npx || true
```

存在多个 Xcode 时先看当前选择；切换是系统级变更，需先问用户。

### 供给步骤

1. 安装完整 Xcode（App Store 或 Apple 开发者下载页）。
2. 打开一次 Xcode，接受 license，等首次启动的组件装完。
3. **Xcode > Settings > Components** 里安装一个 iOS Simulator runtime。
4. **Window > Devices and Simulators > Simulators** 里创建 iPhone 设备（没有可用设备时）。
5. 需要交互能力时还要 Node.js 20+ 与可用的 `npx`。

### 平台边界

- 只在 macOS 上可用；Windows/Linux 明确不可用
- `xcrun simctl` 能列设备不代表交互能力就绪——语义操作还依赖 WebDriverAgent / serve-sim 这类运行时

### 完成判据（iOS）

- `xcode-select -p` 指向完整 Xcode（不是 CommandLineTools）
- `xcrun simctl list devices available` 至少有一个 iPhone 设备
- 需要语义交互时，Node 20+ 与 `npx` 均可解析到绝对路径

## 三平台供给后的统一收尾

1. 报告：检测到了什么、缺的具体是哪一项、每个工具链根目录来自哪个环境变量或默认路径。
2. 只在只读诊断全部完成后，才逐项请求变更授权。
3. 变更后重新验证。注意：验证通过只证明工具链与目标发现，**不证明** IDE 环境继承、工程构建成功、实时画面或输入注入。
4. 把"检查器确认的事实"、"已写入 IDE 配置的"、"仍未验证的实时行为"分开陈述。
