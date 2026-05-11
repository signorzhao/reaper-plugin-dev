# ReaPack 订阅说明

## 在 REAPER 中订阅此插件

1. 在 REAPER 中打开 **Extensions** → **ReaPack** → **Manage repositories**
2. 点击 **Import repositories**
3. 添加以下 URL：
   ```
   https://raw.githubusercontent.com/signorzhao/reapack_repo/main/index.xml
   ```
4. 点击 **OK** 保存
5. 在 ReaPack 包管理器中找到 **enz_ReaperTools** 插件
6. 右键点击插件，选择 **Install** 或 **Update**

UCS 自动重命名工具在同一个仓库中，包名为
**enz_UCS_Auto_Rename_Selected_Items.lua**。安装后先运行同目录下的
`start_ucs_service_windows.bat`，再在 REAPER 中运行脚本。

## 自动更新

订阅后，插件会自动检查更新。当有新版本发布时，ReaPack 会提示你更新插件。

## 手动更新

你也可以手动检查更新：
- **Extensions** → **ReaPack** → **Synchronize packages**

## 功能说明

**enz_ReaperTools** 插件提供以下功能：
- 切换静音轨道的可见性
- 支持轨道静音和项目静音两种模式
- 提供撤销支持

**enz_UCS_Auto_Rename_Selected_Items.lua** 提供以下功能：
- 中文自然语言输入
- UCS 官方 CatID 候选预览
- 选中 item 按时间线顺序批量命名
- 单个撤销块撤销整批重命名

## 版本历史

- **v1.0.0**: 初始版本，支持静音轨道可见性切换 
