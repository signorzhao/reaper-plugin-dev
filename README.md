# REAPER Plugin Repository

这是一个REAPER插件仓库，支持自动更新和订阅功能。

## 如何在REAPER中订阅此插件

### 方法1：通过REAPER的插件管理器

1. 在REAPER中，打开 **Actions** → **Show action list**
2. 搜索 "ReaPack" 并运行 **ReaPack: Browse packages**
3. 点击 **Import repositories**
4. 添加以下URL：
   ```
   https://raw.githubusercontent.com/signorzhao/reaper-plugin-repo/main/reaper_plugin_list.txt
   ```

### 方法2：手动安装

1. 下载对应平台的插件文件：
   - **Windows**: `plugin-win64.dll`
   - **macOS Intel**: `plugin-macosx.dylib`
   - **macOS Apple Silicon**: `plugin-macosx-arm64.dylib`
   - **Linux**: `plugin-linux-x86_64.so`

2. 将文件复制到REAPER的插件目录：
   - **Windows**: `%APPDATA%\REAPER\Plugins\`
   - **macOS**: `~/Library/Application Support/REAPER/Plugins/`
   - **Linux**: `~/.config/REAPER/Plugins/`

## 自动更新

当您通过ReaPack订阅此插件后，REAPER会自动检查更新。每次发布新版本时，插件会自动更新。

## 构建

本项目使用CMake构建系统。要本地构建：

```bash
mkdir build
cd build
cmake ..
make
```

## 发布新版本

要发布新版本：

1. 更新版本号
2. 创建git标签：
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
3. GitHub Actions会自动构建并发布到Releases页面

## 许可证

[在此添加您的许可证信息] 