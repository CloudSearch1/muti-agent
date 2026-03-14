# Windows 依赖安装指南

## 问题说明

在 Windows 系统上，当 `requirements.txt` 文件包含中文注释时，直接使用 `pip install -r requirements.txt` 可能会遇到编码错误：

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x93 in position 146: illegal multibyte sequence
```

这是因为 pip 在 Windows 上默认使用 GBK 编码读取文件，而文件实际使用 UTF-8 编码。

## 解决方案

本项目提供了三种在 Windows 上安装依赖的方法。

### 方法一：使用批处理脚本（推荐）

最简单的方法，双击运行或在命令行执行：

```cmd
install_windows.bat
```

或者在 PowerShell 中：

```powershell
.\install_windows.bat
```

### 方法二：使用 PowerShell 脚本

PowerShell 脚本提供了更多选项：

```powershell
# 基本安装
.\install_windows.ps1

# 强制安装（跳过确认）
.\install_windows.ps1 -Force

# 升级已安装的包
.\install_windows.ps1 -Upgrade
```

如果遇到执行策略限制，可以先运行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 方法三：使用 Python 脚本

如果上述方法不可用，可以直接运行 Python 脚本：

```bash
python scripts\install_requirements.py
```

## 手动解决方案

如果不想使用提供的脚本，也可以手动解决编码问题：

### 方案 A：逐个安装

```bash
python -m pip install fastapi>=0.109.0 uvicorn[standard]>=0.27.0 pydantic>=2.5.0 ...
```

### 方案 B：创建临时文件

```powershell
# 读取 UTF-8 编码的文件并转换为系统默认编码
$content = Get-Content -Path requirements.txt -Encoding UTF8
$content | Out-File -FilePath requirements_temp.txt -Encoding Default
pip install -r requirements_temp.txt
Remove-Item requirements_temp.txt
```

### 方案 C：使用环境变量

在 Python 3.10+ 版本中，可以设置环境变量：

```cmd
set PYTHONUTF8=1
pip install -r requirements.txt
```

## 预防措施

为避免此类问题，建议：

1. **保持 requirements.txt 为纯英文**：移除或替换中文注释
2. **使用标准编码声明**：在 requirements.txt 文件头部不适用编码声明（requirements.txt 不支持编码声明）
3. **升级 pip 到最新版本**：新版本的 pip 对编码问题处理更好

```bash
python -m pip install --upgrade pip
```

## 验证安装

安装完成后，可以验证是否成功：

```bash
# 检查已安装的包
pip list

# 或使用项目的健康检查脚本
python scripts\health_check.py
```

## 常见问题

### Q: 提示 "python 不是内部或外部命令"

**A:** 确保 Python 已正确安装并添加到系统 PATH。可以：
1. 重新安装 Python，勾选 "Add Python to PATH" 选项
2. 或手动添加 Python 安装目录到系统环境变量

### Q: 安装过程中出现权限错误

**A:** 尝试以下方法：
1. 以管理员身份运行脚本
2. 使用 `--user` 参数：`pip install --user package_name`
3. 使用虚拟环境（推荐）

### Q: 某些包安装失败

**A:** 可能是网络问题或包的依赖问题，尝试：
1. 使用国内镜像源：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple package_name
```

2. 升级 pip 和 setuptools：

```bash
python -m pip install --upgrade pip setuptools wheel
```

## 虚拟环境设置（推荐）

建议在虚拟环境中安装依赖：

```cmd
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 运行安装脚本
install_windows.bat
```

## 需要帮助？

如果以上方法都无法解决问题，请：
1. 检查 Python 版本（建议 3.8+）
2. 检查 pip 版本
3. 查看完整错误日志
4. 提交 Issue 到项目仓库
