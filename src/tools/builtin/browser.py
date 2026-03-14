"""
浏览器工具

提供浏览器自动化能力，支持 snapshot/act 引用式交互。

功能特性:
- 浏览器生命周期管理 (start/stop/status)
- 引用式交互 (snapshot -> act by ref)
- 导航与标签页管理
- 截图与文件上传
- 对话框处理
- Profile 管理

使用示例:
    browser = BrowserTool()
    
    # 启动浏览器
    result = await browser(action="start")
    
    # 导航到页面
    result = await browser(action="navigate", url="https://example.com")
    
    # 获取快照（引用式交互基础）
    result = await browser(action="snapshot")
    refs = result.data["refs"]
    
    # 使用 ref 执行点击
    result = await browser(action="click", ref=refs[0]["ref"])
    
    # 截图
    result = await browser(action="screenshot")

规范依据:
- docs/tools-design.md - Browser 流程: status/start -> snapshot -> act -> screenshot
- docs/tools-interface-spec.md - 8.5 browser 接口规范
"""

import asyncio
import base64
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel, Field, field_validator

from ..base import BaseTool, OutputField, OutputSchema, ToolParameter, ToolResult, ToolStatus
from ..errors import ErrorCode, StandardError, ToolError

logger = structlog.get_logger(__name__)


# =============================================================================
# 浏览器状态枚举
# =============================================================================


class BrowserState(str, Enum):
    """浏览器状态"""
    
    IDLE = "idle"           # 未启动
    STARTING = "starting"   # 启动中
    RUNNING = "running"     # 运行中
    STOPPING = "stopping"   # 停止中
    ERROR = "error"         # 错误状态


class DialogAction(str, Enum):
    """对话框动作"""
    
    ACCEPT = "accept"   # 确认
    DISMISS = "dismiss" # 取消


# =============================================================================
# 数据模型
# =============================================================================


class NodeTarget(BaseModel):
    """节点目标配置（用于远程浏览器）"""
    
    id: str = Field(..., description="节点 ID")


class BrowserProfile(BaseModel):
    """浏览器 Profile 配置"""
    
    name: str = Field("default", description="Profile 名称")
    path: Optional[str] = Field(None, description="Profile 存储路径")
    proxy: Optional[str] = Field(None, description="代理服务器地址")


class ElementRef(BaseModel):
    """元素引用（snapshot 返回的可交互元素）"""
    
    ref: str = Field(..., description="元素引用 ID，用于 act 操作")
    role: str = Field(..., description="元素角色 (button, link, textbox, etc.)")
    name: Optional[str] = Field(None, description="元素名称")
    text: Optional[str] = Field(None, description="元素文本内容")
    tag: Optional[str] = Field(None, description="HTML 标签名")
    is_visible: bool = Field(True, description="是否可见")
    is_enabled: bool = Field(True, description="是否可用")
    is_focused: bool = Field(False, description="是否聚焦")
    bounding_box: Optional[Dict[str, float]] = Field(None, description="边界框坐标")


class TabInfo(BaseModel):
    """标签页信息"""
    
    id: str = Field(..., description="标签页 ID")
    url: str = Field(..., description="当前 URL")
    title: Optional[str] = Field(None, description="页面标题")
    active: bool = Field(False, description="是否为活动标签页")


# =============================================================================
# 请求模型
# =============================================================================


class BrowserCommonRequest(BaseModel):
    """浏览器请求通用字段"""
    
    target: str = Field("default", description="浏览器目标标识")
    profile: str = Field("default", description="浏览器 Profile 名称")
    node: Optional[NodeTarget] = Field(None, description="节点目标配置")


class BrowserStatusRequest(BrowserCommonRequest):
    """status 动作请求"""
    pass


class BrowserStartRequest(BrowserCommonRequest):
    """start 动作请求"""
    
    headless: bool = Field(True, description="是否使用无头模式")
    browser_type: str = Field("chromium", description="浏览器类型 (chromium/firefox/webkit)")
    viewport_width: int = Field(1280, description="视口宽度")
    viewport_height: int = Field(720, description="视口高度")
    proxy: Optional[str] = Field(None, description="代理服务器")
    user_data_dir: Optional[str] = Field(None, description="用户数据目录")


class BrowserStopRequest(BrowserCommonRequest):
    """stop 动作请求"""
    
    force: bool = Field(False, description="是否强制停止")


class BrowserSnapshotRequest(BrowserCommonRequest):
    """snapshot 动作请求"""
    
    include_hidden: bool = Field(False, description="是否包含隐藏元素")
    max_refs: int = Field(100, description="最大返回元素数量")


class BrowserActRequest(BrowserCommonRequest):
    """act 动作请求基类"""
    
    ref: str = Field(..., description="元素引用 ID（来自 snapshot）")
    timeout_ms: int = Field(30000, description="操作超时时间（毫秒）")


class BrowserClickRequest(BrowserActRequest):
    """click 动作请求"""
    
    button: str = Field("left", description="鼠标按钮 (left/right/middle)")
    click_count: int = Field(1, description="点击次数")
    delay_ms: int = Field(0, description="按下和释放之间的延迟（毫秒）")


class BrowserTypeRequest(BrowserActRequest):
    """type 动作请求"""
    
    text: str = Field(..., description="要输入的文本")
    clear: bool = Field(False, description="是否先清除现有内容")
    delay_ms: int = Field(0, description="按键之间的延迟（毫秒）")


class BrowserSelectRequest(BrowserActRequest):
    """select 动作请求"""
    
    value: Optional[str] = Field(None, description="选中的值")
    label: Optional[str] = Field(None, description="选中的标签文本")
    index: Optional[int] = Field(None, description="选中的索引")
    
    @field_validator("value", "label", "index")
    @classmethod
    def validate_select_option(cls, v, info):
        """至少需要提供 value, label 或 index 之一"""
        data = info.data
        if not any([data.get("value"), data.get("label"), data.get("index")]):
            raise ValueError("At least one of value, label, or index must be provided")
        return v


class BrowserHoverRequest(BrowserActRequest):
    """hover 动作请求"""
    
    pass


class BrowserPressRequest(BrowserCommonRequest):
    """press 动作请求（键盘按键）"""
    
    key: str = Field(..., description="要按下的键 (Enter, Escape, Tab, etc.)")
    modifiers: List[str] = Field(default_factory=list, description="修饰键 (Shift, Ctrl, Alt, Meta)")


class BrowserScrollRequest(BrowserCommonRequest):
    """scroll 动作请求"""
    
    direction: str = Field("down", description="滚动方向 (up/down/left/right)")
    amount: int = Field(100, description="滚动像素数")
    ref: Optional[str] = Field(None, description="滚动到指定元素")


class BrowserNavigateRequest(BrowserCommonRequest):
    """navigate 动作请求"""
    
    url: str = Field(..., description="目标 URL")
    wait_until: str = Field("load", description="等待条件 (load/domcontentloaded/networkidle)")
    timeout_ms: int = Field(30000, description="导航超时时间（毫秒）")


class BrowserBackRequest(BrowserCommonRequest):
    """back 动作请求"""
    
    pass


class BrowserForwardRequest(BrowserCommonRequest):
    """forward 动作请求"""
    
    pass


class BrowserTabsRequest(BrowserCommonRequest):
    """tabs 动作请求"""
    
    action: str = Field("list", description="标签页操作 (list/new/close/activate)")
    tab_id: Optional[str] = Field(None, description="目标标签页 ID")
    url: Optional[str] = Field(None, description="新标签页 URL")


class BrowserScreenshotRequest(BrowserCommonRequest):
    """screenshot 动作请求"""
    
    full_page: bool = Field(False, description="是否截取整个页面")
    format: str = Field("png", description="图片格式 (png/jpeg)")
    quality: int = Field(80, description="JPEG 质量 (1-100)")
    selector: Optional[str] = Field(None, description="截图元素选择器")
    ref: Optional[str] = Field(None, description="截图元素引用")


class BrowserUploadRequest(BrowserCommonRequest):
    """upload 动作请求"""
    
    ref: str = Field(..., description="文件输入框元素引用")
    files: List[str] = Field(..., description="要上传的文件路径列表")


class BrowserDialogRequest(BrowserCommonRequest):
    """dialog 动作请求"""
    
    action: DialogAction = Field(..., description="对话框动作 (accept/dismiss)")
    prompt_text: Optional[str] = Field(None, description="prompt 对话框输入文本")


class BrowserProfileRequest(BrowserCommonRequest):
    """profile 动作请求"""
    
    action: str = Field("list", description="Profile 操作 (list/create/delete/switch)")
    name: Optional[str] = Field(None, description="Profile 名称")
    options: Optional[Dict[str, Any]] = Field(None, description="Profile 选项")


# =============================================================================
# 响应模型
# =============================================================================


class BrowserStatusResponse(BaseModel):
    """status 动作响应"""
    
    state: BrowserState = Field(..., description="浏览器状态")
    url: Optional[str] = Field(None, description="当前 URL")
    title: Optional[str] = Field(None, description="当前页面标题")
    tabs_count: int = Field(0, description="标签页数量")
    active_tab_id: Optional[str] = Field(None, description="活动标签页 ID")


class BrowserSnapshotResponse(BaseModel):
    """snapshot 动作响应"""
    
    url: str = Field(..., description="当前 URL")
    title: Optional[str] = Field(None, description="页面标题")
    refs: List[ElementRef] = Field(default_factory=list, description="可交互元素引用列表")
    html: Optional[str] = Field(None, description="页面 HTML（可选）")
    viewport: Optional[Dict[str, int]] = Field(None, description="视口尺寸")


class BrowserTabsResponse(BaseModel):
    """tabs 动作响应"""
    
    tabs: List[TabInfo] = Field(default_factory=list, description="标签页列表")
    active_tab_id: Optional[str] = Field(None, description="活动标签页 ID")


class BrowserScreenshotResponse(BaseModel):
    """screenshot 动作响应"""
    
    data: str = Field(..., description="Base64 编码的图片数据")
    format: str = Field(..., description="图片格式")
    width: int = Field(..., description="图片宽度")
    height: int = Field(..., description="图片高度")


class BrowserProfileResponse(BaseModel):
    """profile 动作响应"""
    
    profiles: List[Dict[str, Any]] = Field(default_factory=list, description="Profile 列表")
    active_profile: Optional[str] = Field(None, description="当前活动 Profile")


# =============================================================================
# 浏览器会话管理
# =============================================================================


class BrowserSession(BaseModel):
    """浏览器会话"""
    
    session_id: str = Field(..., description="会话 ID")
    target: str = Field("default", description="目标标识")
    profile: str = Field("default", description="Profile 名称")
    state: BrowserState = Field(BrowserState.IDLE, description="浏览器状态")
    browser_type: str = Field("chromium", description="浏览器类型")
    headless: bool = Field(True, description="是否无头模式")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_activity: datetime = Field(default_factory=datetime.now, description="最后活动时间")
    
    # 运行时状态
    current_url: Optional[str] = Field(None, description="当前 URL")
    current_title: Optional[str] = Field(None, description="当前标题")
    tabs: List[TabInfo] = Field(default_factory=list, description="标签页列表")
    active_tab_id: Optional[str] = Field(None, description="活动标签页 ID")
    
    # 最后一次 snapshot 的 refs 缓存
    last_refs: Dict[str, ElementRef] = Field(default_factory=dict, description="元素引用缓存")
    
    # Playwright 实例（运行时注入）
    browser: Any = Field(None, exclude=True)
    context: Any = Field(None, exclude=True)
    page: Any = Field(None, exclude=True)


class BrowserSessionManager:
    """
    浏览器会话管理器（单例）
    
    管理所有浏览器会话，提供 Agent 隔离。
    """
    
    _instance: Optional["BrowserSessionManager"] = None
    _sessions: Dict[str, BrowserSession] = {}
    
    def __new__(cls) -> "BrowserSessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def create_session(
        self,
        target: str,
        profile: str,
        browser_type: str = "chromium",
        headless: bool = True,
    ) -> str:
        """
        创建浏览器会话
        
        Args:
            target: 目标标识
            profile: Profile 名称
            browser_type: 浏览器类型
            headless: 是否无头模式
            
        Returns:
            session_id: 会话 ID
        """
        session_id = str(uuid.uuid4())
        
        session = BrowserSession(
            session_id=session_id,
            target=target,
            profile=profile,
            browser_type=browser_type,
            headless=headless,
            state=BrowserState.IDLE,
        )
        
        self._sessions[session_id] = session
        
        logger.info(
            "Browser session created",
            session_id=session_id,
            target=target,
            profile=profile,
        )
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """
        获取会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话对象，不存在则返回 None
        """
        return self._sessions.get(session_id)
    
    async def get_session_by_target(self, target: str) -> Optional[BrowserSession]:
        """
        根据目标标识获取会话
        
        Args:
            target: 目标标识
            
        Returns:
            会话对象
        """
        for session in self._sessions.values():
            if session.target == target:
                return session
        return None
    
    async def update_session(
        self,
        session_id: str,
        **updates,
    ) -> bool:
        """
        更新会话状态
        
        Args:
            session_id: 会话 ID
            **updates: 要更新的字段
            
        Returns:
            是否更新成功
        """
        session = self._sessions.get(session_id)
        
        if not session:
            return False
        
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.last_activity = datetime.now()
        
        logger.debug(
            "Browser session updated",
            session_id=session_id,
            updates=list(updates.keys()),
        )
        
        return True
    
    async def remove_session(self, session_id: str) -> bool:
        """
        移除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否移除成功
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            
            # 如果浏览器还在运行，尝试关闭
            if session.state == BrowserState.RUNNING:
                try:
                    if session.browser:
                        await session.browser.close()
                        logger.info(
                            "Browser closed during session removal",
                            session_id=session_id,
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to close browser during session removal",
                        session_id=session_id,
                        error=str(e),
                    )
            
            del self._sessions[session_id]
            
            logger.info(
                "Browser session removed",
                session_id=session_id,
            )
            
            return True
        
        return False
    
    async def list_sessions(self) -> List[BrowserSession]:
        """
        列出所有会话
        
        Returns:
            会话列表
        """
        return list(self._sessions.values())


# 全局会话管理器实例
_session_manager: Optional[BrowserSessionManager] = None


def get_browser_session_manager() -> BrowserSessionManager:
    """获取全局浏览器会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = BrowserSessionManager()
    return _session_manager


# =============================================================================
# Browser 工具
# =============================================================================


class BrowserTool(BaseTool):
    """
    浏览器工具
    
    提供浏览器自动化能力，支持 snapshot/act 引用式交互。
    
    核心概念:
    - snapshot: 获取页面可交互元素的引用列表
    - act: 使用 snapshot 返回的 ref 执行操作
    
    推荐工作流:
    status/start -> snapshot -> act -> screenshot
    
    动作列表:
    - status: 查询浏览器状态
    - start: 启动浏览器
    - stop: 停止浏览器
    - snapshot: 获取页面元素引用
    - click: 点击元素
    - type: 输入文本
    - select: 选择下拉选项
    - hover: 悬停元素
    - press: 按下键盘按键
    - scroll: 滚动页面
    - navigate: 导航到 URL
    - back: 后退
    - forward: 前进
    - tabs: 标签页管理
    - screenshot: 截图
    - upload: 上传文件
    - dialog: 处理对话框
    - profile: 管理 Profile
    """
    
    NAME = "browser"
    DESCRIPTION = "Browser automation tool with snapshot/act reference-based interaction"
    SCHEMA_VERSION = "1.0.0"
    
    # 支持的动作
    ACTIONS = [
        "status", "start", "stop",
        "snapshot",
        "click", "type", "select", "hover", "press", "scroll",
        "navigate", "back", "forward", "tabs",
        "screenshot", "upload", "dialog", "profile",
    ]
    
    # 默认超时
    DEFAULT_TIMEOUT_MS = 30000
    
    # 最大截图尺寸
    MAX_SCREENSHOT_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 会话管理器
        self.session_manager = get_browser_session_manager()
        
        # Playwright 实例（延迟加载）
        self._playwright: Optional[Any] = None
        self._browser_launcher: Optional[Any] = None
    
    @property
    def parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        return [
            ToolParameter(
                name="action",
                description="Action to perform",
                type="string",
                required=True,
                enum=self.ACTIONS,
            ),
            # 通用字段
            ToolParameter(
                name="target",
                description="Browser target identifier",
                type="string",
                required=False,
                default="default",
            ),
            ToolParameter(
                name="profile",
                description="Browser profile name",
                type="string",
                required=False,
                default="default",
            ),
            ToolParameter(
                name="node",
                description="Node target configuration for remote browser",
                type="object",
                required=False,
            ),
            # start 参数
            ToolParameter(
                name="headless",
                description="Run in headless mode",
                type="boolean",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="browser_type",
                description="Browser type (chromium/firefox/webkit)",
                type="string",
                required=False,
                default="chromium",
            ),
            # snapshot 参数
            ToolParameter(
                name="include_hidden",
                description="Include hidden elements in snapshot",
                type="boolean",
                required=False,
                default=False,
            ),
            # act 参数
            ToolParameter(
                name="ref",
                description="Element reference ID from snapshot",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="timeout_ms",
                description="Operation timeout in milliseconds",
                type="integer",
                required=False,
                default=self.DEFAULT_TIMEOUT_MS,
            ),
            # click 参数
            ToolParameter(
                name="button",
                description="Mouse button (left/right/middle)",
                type="string",
                required=False,
                default="left",
            ),
            ToolParameter(
                name="click_count",
                description="Number of clicks",
                type="integer",
                required=False,
                default=1,
            ),
            # type 参数
            ToolParameter(
                name="text",
                description="Text to type or URL to navigate",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="clear",
                description="Clear existing text before typing",
                type="boolean",
                required=False,
                default=False,
            ),
            # select 参数
            ToolParameter(
                name="value",
                description="Select value or scroll direction",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="label",
                description="Select label",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="index",
                description="Select index",
                type="integer",
                required=False,
            ),
            # press 参数
            ToolParameter(
                name="key",
                description="Key to press",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="modifiers",
                description="Key modifiers (Shift/Ctrl/Alt/Meta)",
                type="array",
                required=False,
            ),
            # scroll 参数
            ToolParameter(
                name="direction",
                description="Scroll direction (up/down/left/right)",
                type="string",
                required=False,
                default="down",
            ),
            ToolParameter(
                name="amount",
                description="Scroll amount in pixels",
                type="integer",
                required=False,
                default=100,
            ),
            # navigate 参数
            ToolParameter(
                name="url",
                description="URL to navigate to",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="wait_until",
                description="Wait condition (load/domcontentloaded/networkidle)",
                type="string",
                required=False,
                default="load",
            ),
            # tabs 参数
            ToolParameter(
                name="tab_action",
                description="Tab action (list/new/close/activate)",
                type="string",
                required=False,
                default="list",
            ),
            ToolParameter(
                name="tab_id",
                description="Target tab ID",
                type="string",
                required=False,
            ),
            # screenshot 参数
            ToolParameter(
                name="full_page",
                description="Capture full page screenshot",
                type="boolean",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="format",
                description="Screenshot format (png/jpeg)",
                type="string",
                required=False,
                default="png",
            ),
            # upload 参数
            ToolParameter(
                name="files",
                description="Files to upload (array of paths)",
                type="array",
                required=False,
            ),
            # dialog 参数
            ToolParameter(
                name="dialog_action",
                description="Dialog action (accept/dismiss)",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="prompt_text",
                description="Text for prompt dialog",
                type="string",
                required=False,
            ),
            # profile 参数
            ToolParameter(
                name="profile_action",
                description="Profile action (list/create/delete/switch)",
                type="string",
                required=False,
                default="list",
            ),
            ToolParameter(
                name="profile_name",
                description="Profile name",
                type="string",
                required=False,
            ),
            # stop 参数
            ToolParameter(
                name="force",
                description="Force stop browser",
                type="boolean",
                required=False,
                default=False,
            ),
        ]
    
    @property
    def output_schema(self) -> OutputSchema:
        """
        获取工具输出模式定义
        
        Returns:
            Browser 工具的输出模式
        """
        return OutputSchema(
            description="Browser tool response",
            fields=[
                OutputField(
                    name="state",
                    type="string",
                    description="Browser state (idle/starting/running/stopping/error)",
                    required=False,
                ),
                OutputField(
                    name="url",
                    type="string",
                    description="Current page URL",
                    required=False,
                ),
                OutputField(
                    name="title",
                    type="string",
                    description="Current page title",
                    required=False,
                ),
                OutputField(
                    name="refs",
                    type="array",
                    description="Element references from snapshot",
                    required=False,
                ),
                OutputField(
                    name="data",
                    type="string",
                    description="Base64 encoded screenshot data",
                    required=False,
                ),
                OutputField(
                    name="tabs",
                    type="array",
                    description="Tab information list",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行浏览器动作
        
        Args:
            **kwargs: 动作参数
            
        Returns:
            执行结果
        """
        # 获取动作
        action = kwargs.get("action")
        if not action:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="Missing required parameter: action",
                hint=f"Action must be one of: {', '.join(self.ACTIONS)}",
            )
        
        if action not in self.ACTIONS:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid action: {action}",
                hint=f"Action must be one of: {', '.join(self.ACTIONS)}",
            )
        
        # 分发到具体动作处理器
        handler = getattr(self, f"_handle_{action}", None)
        if not handler:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Action handler not implemented: {action}",
            )
        
        try:
            return await handler(**kwargs)
        except Exception as e:
            logger.error(
                "Browser action failed",
                action=action,
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Browser action '{action}' failed: {e}",
                details={"action": action, "error": str(e)},
            )
    
    # =========================================================================
    # 动作处理器 - 状态与生命周期
    # =========================================================================
    
    async def _handle_status(self, **kwargs) -> ToolResult:
        """处理 status 动作"""
        request = BrowserStatusRequest(**kwargs)
        
        # 查找目标会话
        session = await self.session_manager.get_session_by_target(request.target)
        
        if not session:
            # 没有会话，返回 idle 状态
            response = BrowserStatusResponse(
                state=BrowserState.IDLE,
            )
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
        
        # 返回会话状态
        response = BrowserStatusResponse(
            state=session.state,
            url=session.current_url,
            title=session.current_title,
            tabs_count=len(session.tabs),
            active_tab_id=session.active_tab_id,
        )
        
        return ToolResult.ok(data=response.model_dump(exclude_none=True))
    
    async def _handle_start(self, **kwargs) -> ToolResult:
        """处理 start 动作"""
        request = BrowserStartRequest(**kwargs)
        
        # 检查是否已有会话
        existing = await self.session_manager.get_session_by_target(request.target)
        if existing and existing.state == BrowserState.RUNNING:
            return ToolResult.ok(
                data=BrowserStatusResponse(
                    state=existing.state,
                    url=existing.current_url,
                    title=existing.current_title,
                ).model_dump(exclude_none=True),
                message=f"Browser already running for target '{request.target}'",
            )
        
        # 如果有旧会话但不在运行，先清理
        if existing:
            await self.session_manager.remove_session(existing.session_id)
        
        # 创建新会话
        session_id = await self.session_manager.create_session(
            target=request.target,
            profile=request.profile,
            browser_type=request.browser_type,
            headless=request.headless,
        )
        
        session = await self.session_manager.get_session(session_id)
        
        try:
            # 更新状态为启动中
            await self.session_manager.update_session(
                session_id,
                state=BrowserState.STARTING,
            )
            
            # 初始化 Playwright
            await self._init_playwright()
            
            # 启动浏览器
            if request.browser_type == "chromium":
                browser = await self._playwright.chromium.launch(
                    headless=request.headless,
                )
            elif request.browser_type == "firefox":
                browser = await self._playwright.firefox.launch(
                    headless=request.headless,
                )
            elif request.browser_type == "webkit":
                browser = await self._playwright.webkit.launch(
                    headless=request.headless,
                )
            else:
                raise ValueError(f"Unsupported browser type: {request.browser_type}")
            
            # 创建浏览器上下文
            context = await browser.new_context(
                viewport={
                    "width": request.viewport_width,
                    "height": request.viewport_height,
                },
            )
            
            # 创建页面
            page = await context.new_page()
            
            # 更新会话
            await self.session_manager.update_session(
                session_id,
                state=BrowserState.RUNNING,
                browser=browser,
                context=context,
                page=page,
                tabs=[TabInfo(id="default", url="about:blank", active=True)],
                active_tab_id="default",
            )
            
            response = BrowserStatusResponse(
                state=BrowserState.RUNNING,
            )
            
            logger.info(
                "Browser started",
                session_id=session_id,
                target=request.target,
                browser_type=request.browser_type,
            )
            
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
            
        except Exception as e:
            # 启动失败，更新状态
            await self.session_manager.update_session(
                session_id,
                state=BrowserState.ERROR,
            )
            
            logger.error(
                "Failed to start browser",
                session_id=session_id,
                error=str(e),
            )
            
            return ToolResult.error(
                code=ErrorCode.DEPENDENCY_ERROR,
                message=f"Failed to start browser: {e}",
                hint="Ensure Playwright is installed and browser binaries are available",
                retryable=True,
            )
    
    async def _handle_stop(self, **kwargs) -> ToolResult:
        """处理 stop 动作"""
        request = BrowserStopRequest(**kwargs)
        
        # 查找目标会话
        session = await self.session_manager.get_session_by_target(request.target)
        
        if not session:
            return ToolResult.ok(
                data=BrowserStatusResponse(state=BrowserState.IDLE).model_dump(),
                message="Browser not running",
            )
        
        try:
            # 更新状态
            await self.session_manager.update_session(
                session.session_id,
                state=BrowserState.STOPPING,
            )
            
            # 关闭浏览器
            if session.browser:
                await session.browser.close()
            
            # 移除会话
            await self.session_manager.remove_session(session.session_id)
            
            response = BrowserStatusResponse(state=BrowserState.IDLE)
            
            logger.info(
                "Browser stopped",
                session_id=session.session_id,
                target=request.target,
            )
            
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
            
        except Exception as e:
            logger.error(
                "Failed to stop browser",
                session_id=session.session_id,
                error=str(e),
            )
            
            if request.force:
                # 强制停止，直接移除会话
                await self.session_manager.remove_session(session.session_id)
                return ToolResult.ok(
                    data=BrowserStatusResponse(state=BrowserState.IDLE).model_dump(),
                    message="Browser force stopped",
                )
            
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to stop browser: {e}",
                retryable=True,
            )
    
    # =========================================================================
    # 动作处理器 - Snapshot
    # =========================================================================
    
    async def _handle_snapshot(self, **kwargs) -> ToolResult:
        """处理 snapshot 动作"""
        request = BrowserSnapshotRequest(**kwargs)
        
        # 获取会话
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        page = session.page
        
        try:
            # 获取页面信息
            url = page.url
            title = await page.title()
            
            # 获取可交互元素
            refs = await self._get_element_refs(page, request.include_hidden, request.max_refs)
            
            # 缓存 refs
            refs_dict = {ref.ref: ref for ref in refs}
            await self.session_manager.update_session(
                session.session_id,
                current_url=url,
                current_title=title,
                last_refs=refs_dict,
            )
            
            response = BrowserSnapshotResponse(
                url=url,
                title=title,
                refs=refs,
                viewport={"width": page.viewport_size["width"], "height": page.viewport_size["height"]},
            )
            
            logger.debug(
                "Snapshot taken",
                session_id=session.session_id,
                url=url,
                refs_count=len(refs),
            )
            
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
            
        except Exception as e:
            logger.error(
                "Failed to take snapshot",
                session_id=session.session_id,
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to take snapshot: {e}",
            )
    
    # =========================================================================
    # 动作处理器 - Act 类操作
    # =========================================================================
    
    async def _handle_click(self, **kwargs) -> ToolResult:
        """处理 click 动作"""
        request = BrowserClickRequest(**kwargs)
        
        # 验证 ref
        session, element = await self._validate_ref(request.target, request.ref)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 执行点击
            await session.page.click(
                f'[data-ref="{request.ref}"]',
                button=request.button,
                click_count=request.click_count,
                delay=request.delay_ms,
                timeout=request.timeout_ms,
            )
            
            logger.info(
                "Click performed",
                session_id=session.session_id,
                ref=request.ref,
                button=request.button,
            )
            
            return ToolResult.ok(message="Click performed successfully")
            
        except Exception as e:
            # 如果 ref 定位失败，尝试备用方案
            logger.warning(
                "Click by ref failed, trying fallback",
                ref=request.ref,
                error=str(e),
            )
            
            # 使用缓存的元素信息尝试定位
            if element:
                try:
                    # 尝试通过文本定位
                    if element.text:
                        await session.page.get_by_text(element.text).first.click(
                            timeout=request.timeout_ms,
                        )
                        logger.info(
                            "Click performed via text fallback",
                            text=element.text[:50],
                        )
                        return ToolResult.ok(
                            message="Click performed via text fallback",
                            warnings=["Used text-based fallback instead of ref"],
                        )
                except Exception as fallback_error:
                    logger.error(
                        "Click fallback also failed",
                        error=str(fallback_error),
                    )
            
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"Failed to click element: {e}",
                hint="Element may not be visible or interactable. Try taking a new snapshot.",
            )
    
    async def _handle_type(self, **kwargs) -> ToolResult:
        """处理 type 动作"""
        request = BrowserTypeRequest(**kwargs)
        
        # 验证 ref
        session, element = await self._validate_ref(request.target, request.ref)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 清除现有内容
            if request.clear:
                await session.page.fill(
                    f'[data-ref="{request.ref}"]',
                    "",
                    timeout=request.timeout_ms,
                )
            
            # 输入文本
            await session.page.type(
                f'[data-ref="{request.ref}"]',
                request.text,
                delay=request.delay_ms,
                timeout=request.timeout_ms,
            )
            
            logger.info(
                "Type performed",
                session_id=session.session_id,
                ref=request.ref,
                text_length=len(request.text),
            )
            
            return ToolResult.ok(message="Text typed successfully")
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"Failed to type text: {e}",
                hint="Element may not be an input field or not visible",
            )
    
    async def _handle_select(self, **kwargs) -> ToolResult:
        """处理 select 动作"""
        request = BrowserSelectRequest(**kwargs)
        
        # 验证 ref
        session, element = await self._validate_ref(request.target, request.ref)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 执行选择
            if request.value:
                await session.page.select_option(
                    f'[data-ref="{request.ref}"]',
                    value=request.value,
                    timeout=request.timeout_ms,
                )
            elif request.label:
                await session.page.select_option(
                    f'[data-ref="{request.ref}"]',
                    label=request.label,
                    timeout=request.timeout_ms,
                )
            elif request.index is not None:
                await session.page.select_option(
                    f'[data-ref="{request.ref}"]',
                    index=request.index,
                    timeout=request.timeout_ms,
                )
            
            logger.info(
                "Select performed",
                session_id=session.session_id,
                ref=request.ref,
            )
            
            return ToolResult.ok(message="Option selected successfully")
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"Failed to select option: {e}",
                hint="Element may not be a select element or option not found",
            )
    
    async def _handle_hover(self, **kwargs) -> ToolResult:
        """处理 hover 动作"""
        request = BrowserHoverRequest(**kwargs)
        
        # 验证 ref
        session, element = await self._validate_ref(request.target, request.ref)
        if isinstance(session, ToolResult):
            return session
        
        try:
            await session.page.hover(
                f'[data-ref="{request.ref}"]',
                timeout=request.timeout_ms,
            )
            
            logger.info(
                "Hover performed",
                session_id=session.session_id,
                ref=request.ref,
            )
            
            return ToolResult.ok(message="Hover performed successfully")
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"Failed to hover element: {e}",
            )
    
    async def _handle_press(self, **kwargs) -> ToolResult:
        """处理 press 动作"""
        request = BrowserPressRequest(**kwargs)
        
        # 获取会话
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 构建按键组合
            if request.modifiers:
                key_combo = "+".join([*request.modifiers, request.key])
            else:
                key_combo = request.key
            
            await session.page.keyboard.press(key_combo)
            
            logger.info(
                "Key press performed",
                session_id=session.session_id,
                key=key_combo,
            )
            
            return ToolResult.ok(message=f"Key '{key_combo}' pressed successfully")
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Failed to press key: {e}",
                hint=f"Key '{request.key}' may not be valid",
            )
    
    async def _handle_scroll(self, **kwargs) -> ToolResult:
        """处理 scroll 动作"""
        request = BrowserScrollRequest(**kwargs)
        
        # 获取会话
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            if request.ref:
                # 滚动到指定元素
                await session.page.locator(f'[data-ref="{request.ref}"]').scroll_into_view_if_needed()
                logger.info(
                    "Scrolled to element",
                    session_id=session.session_id,
                    ref=request.ref,
                )
            else:
                # 按方向滚动
                direction = request.direction.lower()
                if direction == "up":
                    await session.page.mouse.wheel(0, -request.amount)
                elif direction == "down":
                    await session.page.mouse.wheel(0, request.amount)
                elif direction == "left":
                    await session.page.mouse.wheel(-request.amount, 0)
                elif direction == "right":
                    await session.page.mouse.wheel(request.amount, 0)
                else:
                    return ToolResult.error(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid scroll direction: {direction}",
                        hint="Direction must be one of: up, down, left, right",
                    )
                
                logger.info(
                    "Page scrolled",
                    session_id=session.session_id,
                    direction=direction,
                    amount=request.amount,
                )
            
            return ToolResult.ok(message="Scroll performed successfully")
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to scroll: {e}",
            )
    
    # =========================================================================
    # 动作处理器 - 导航
    # =========================================================================
    
    async def _handle_navigate(self, **kwargs) -> ToolResult:
        """处理 navigate 动作"""
        request = BrowserNavigateRequest(**kwargs)
        
        # 获取会话
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 导航到 URL
            await session.page.goto(
                request.url,
                wait_until=request.wait_until,
                timeout=request.timeout_ms,
            )
            
            # 更新会话信息
            url = session.page.url
            title = await session.page.title()
            
            await self.session_manager.update_session(
                session.session_id,
                current_url=url,
                current_title=title,
            )
            
            logger.info(
                "Navigated to URL",
                session_id=session.session_id,
                url=url,
            )
            
            return ToolResult.ok(
                data={"url": url, "title": title},
                message="Navigation completed",
            )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.DEPENDENCY_ERROR,
                message=f"Failed to navigate to URL: {e}",
                hint=f"Check if URL '{request.url}' is valid and accessible",
            )
    
    async def _handle_back(self, **kwargs) -> ToolResult:
        """处理 back 动作"""
        request = BrowserBackRequest(**kwargs)
        
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            await session.page.go_back()
            
            url = session.page.url
            title = await session.page.title()
            
            await self.session_manager.update_session(
                session.session_id,
                current_url=url,
                current_title=title,
            )
            
            return ToolResult.ok(
                data={"url": url, "title": title},
                message="Navigated back",
            )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to navigate back: {e}",
            )
    
    async def _handle_forward(self, **kwargs) -> ToolResult:
        """处理 forward 动作"""
        request = BrowserForwardRequest(**kwargs)
        
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            await session.page.go_forward()
            
            url = session.page.url
            title = await session.page.title()
            
            await self.session_manager.update_session(
                session.session_id,
                current_url=url,
                current_title=title,
            )
            
            return ToolResult.ok(
                data={"url": url, "title": title},
                message="Navigated forward",
            )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to navigate forward: {e}",
            )
    
    async def _handle_tabs(self, **kwargs) -> ToolResult:
        """处理 tabs 动作"""
        request = BrowserTabsRequest(**kwargs)
        
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            if request.action == "list":
                # 列出所有标签页
                context = session.context
                pages = context.pages
                
                tabs = []
                for i, page in enumerate(pages):
                    tabs.append(TabInfo(
                        id=str(i),
                        url=page.url,
                        title=await page.title(),
                        active=page == session.page,
                    ))
                
                response = BrowserTabsResponse(tabs=tabs)
                return ToolResult.ok(data=response.model_dump(exclude_none=True))
            
            elif request.action == "new":
                # 创建新标签页
                new_page = await session.context.new_page()
                
                if request.url:
                    await new_page.goto(request.url)
                
                tabs = session.tabs + [TabInfo(
                    id=str(len(session.tabs)),
                    url=request.url or "about:blank",
                    active=True,
                )]
                
                await self.session_manager.update_session(
                    session.session_id,
                    page=new_page,
                    tabs=tabs,
                    active_tab_id=str(len(session.tabs) - 1),
                )
                
                return ToolResult.ok(message="New tab created")
            
            elif request.action == "close":
                # 关闭标签页
                if request.tab_id:
                    context = session.context
                    pages = context.pages
                    idx = int(request.tab_id)
                    if 0 <= idx < len(pages):
                        await pages[idx].close()
                    else:
                        return ToolResult.error(
                            code=ErrorCode.NOT_FOUND,
                            message=f"Tab not found: {request.tab_id}",
                        )
                else:
                    await session.page.close()
                
                return ToolResult.ok(message="Tab closed")
            
            elif request.action == "activate":
                # 激活标签页
                if not request.tab_id:
                    return ToolResult.error(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="tab_id is required for activate action",
                    )
                
                context = session.context
                pages = context.pages
                idx = int(request.tab_id)
                
                if 0 <= idx < len(pages):
                    await self.session_manager.update_session(
                        session.session_id,
                        page=pages[idx],
                        active_tab_id=request.tab_id,
                    )
                    return ToolResult.ok(message=f"Tab {request.tab_id} activated")
                else:
                    return ToolResult.error(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Tab not found: {request.tab_id}",
                    )
            
            else:
                return ToolResult.error(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid tab action: {request.action}",
                    hint="Action must be one of: list, new, close, activate",
                )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to manage tabs: {e}",
            )
    
    # =========================================================================
    # 动作处理器 - 高级功能
    # =========================================================================
    
    async def _handle_screenshot(self, **kwargs) -> ToolResult:
        """处理 screenshot 动作"""
        request = BrowserScreenshotRequest(**kwargs)
        
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 获取截图
            if request.ref:
                # 截取特定元素
                element = session.page.locator(f'[data-ref="{request.ref}"]')
                screenshot_bytes = await element.screenshot(
                    type=request.format,
                    quality=request.quality if request.format == "jpeg" else None,
                )
            elif request.selector:
                # 通过选择器截取
                element = session.page.locator(request.selector)
                screenshot_bytes = await element.screenshot(
                    type=request.format,
                    quality=request.quality if request.format == "jpeg" else None,
                )
            else:
                # 全页面截图
                screenshot_bytes = await session.page.screenshot(
                    full_page=request.full_page,
                    type=request.format,
                    quality=request.quality if request.format == "jpeg" else None,
                )
            
            # 转换为 Base64
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            # 检查大小
            if len(screenshot_base64) > self.MAX_SCREENSHOT_SIZE:
                return ToolResult.error(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Screenshot too large: {len(screenshot_base64)} bytes",
                    hint="Try reducing quality or using full_page=false",
                )
            
            response = BrowserScreenshotResponse(
                data=screenshot_base64,
                format=request.format,
                width=session.page.viewport_size["width"],
                height=session.page.viewport_size["height"],
            )
            
            logger.info(
                "Screenshot taken",
                session_id=session.session_id,
                format=request.format,
                full_page=request.full_page,
                size=len(screenshot_base64),
            )
            
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to take screenshot: {e}",
            )
    
    async def _handle_upload(self, **kwargs) -> ToolResult:
        """处理 upload 动作"""
        request = BrowserUploadRequest(**kwargs)
        
        # 验证 ref
        session, element = await self._validate_ref(request.target, request.ref)
        if isinstance(session, ToolResult):
            return session
        
        # 验证文件路径
        files_to_upload = []
        for file_path in request.files:
            path = Path(file_path)
            if not path.exists():
                return ToolResult.error(
                    code=ErrorCode.NOT_FOUND,
                    message=f"File not found: {file_path}",
                )
            files_to_upload.append(str(path.absolute()))
        
        try:
            # 设置文件输入
            await session.page.set_input_files(
                f'[data-ref="{request.ref}"]',
                files_to_upload,
            )
            
            logger.info(
                "Files uploaded",
                session_id=session.session_id,
                ref=request.ref,
                files_count=len(files_to_upload),
            )
            
            return ToolResult.ok(
                data={"files_uploaded": len(files_to_upload)},
                message="Files uploaded successfully",
            )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to upload files: {e}",
                hint="Element may not be a file input field",
            )
    
    async def _handle_dialog(self, **kwargs) -> ToolResult:
        """处理 dialog 动作"""
        request = BrowserDialogRequest(**kwargs)
        
        session = await self._get_running_session(request.target)
        if isinstance(session, ToolResult):
            return session
        
        try:
            # 设置对话框处理器
            async def handle_dialog(dialog):
                if request.action == DialogAction.ACCEPT:
                    await dialog.accept(request.prompt_text)
                else:
                    await dialog.dismiss()
            
            # 注册一次性处理器
            session.page.once("dialog", handle_dialog)
            
            logger.info(
                "Dialog handler set",
                session_id=session.session_id,
                action=request.action.value,
            )
            
            return ToolResult.ok(
                message=f"Dialog handler set to {request.action.value}",
                note="Handler will be triggered on next dialog",
            )
            
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to set dialog handler: {e}",
            )
    
    async def _handle_profile(self, **kwargs) -> ToolResult:
        """处理 profile 动作"""
        request = BrowserProfileRequest(**kwargs)
        
        # Profile 管理是简化实现
        # 实际应用中可能需要更复杂的持久化逻辑
        
        if request.action == "list":
            # 返回可用 Profile 列表
            response = BrowserProfileResponse(
                profiles=[
                    {"name": "default", "description": "Default browser profile"},
                ],
                active_profile="default",
            )
            return ToolResult.ok(data=response.model_dump(exclude_none=True))
        
        elif request.action == "create":
            if not request.name:
                return ToolResult.error(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Profile name is required for create action",
                )
            
            response = BrowserProfileResponse(
                profiles=[{"name": request.name}],
                active_profile=request.name,
            )
            return ToolResult.ok(
                data=response.model_dump(exclude_none=True),
                message=f"Profile '{request.name}' created",
            )
        
        elif request.action == "delete":
            if not request.name:
                return ToolResult.error(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Profile name is required for delete action",
                )
            
            return ToolResult.ok(message=f"Profile '{request.name}' deleted")
        
        elif request.action == "switch":
            if not request.name:
                return ToolResult.error(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Profile name is required for switch action",
                )
            
            response = BrowserProfileResponse(
                active_profile=request.name,
            )
            return ToolResult.ok(
                data=response.model_dump(exclude_none=True),
                message=f"Switched to profile '{request.name}'",
            )
        
        else:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid profile action: {request.action}",
                hint="Action must be one of: list, create, delete, switch",
            )
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    async def _init_playwright(self) -> None:
        """
        初始化 Playwright（延迟加载）
        """
        if self._playwright is None:
            try:
                from playwright.async_api import async_playwright
                self._browser_launcher = await async_playwright().start()
                self._playwright = self._browser_launcher
            except ImportError:
                raise ToolError(
                    code=ErrorCode.DEPENDENCY_ERROR,
                    message="Playwright is not installed",
                    hint="Install Playwright: pip install playwright && playwright install",
                )
    
    async def _get_running_session(self, target: str) -> Union[BrowserSession, ToolResult]:
        """
        获取运行中的会话
        
        Args:
            target: 目标标识
            
        Returns:
            会话对象或错误结果
        """
        session = await self.session_manager.get_session_by_target(target)
        
        if not session:
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"No browser session for target '{target}'",
                hint="Start a browser first with action='start'",
            )
        
        if session.state != BrowserState.RUNNING:
            return ToolResult.error(
                code=ErrorCode.CONFLICT,
                message=f"Browser is not running (state: {session.state.value})",
                hint="Wait for browser to be ready or restart it",
            )
        
        return session
    
    async def _validate_ref(self, target: str, ref: str) -> tuple:
        """
        验证元素引用
        
        Args:
            target: 目标标识
            ref: 元素引用 ID
            
        Returns:
            (session, element) 或 (error_result, None)
        """
        session = await self._get_running_session(target)
        if isinstance(session, ToolResult):
            return session, None
        
        if not ref:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="Element reference (ref) is required",
                hint="Get element refs from snapshot action first",
            ), None
        
        # 检查 ref 是否在缓存中
        element = session.last_refs.get(ref)
        
        if not element:
            logger.warning(
                "Element ref not found in cache",
                session_id=session.session_id,
                ref=ref,
            )
            # 不阻止操作，因为可能在其他 session 中
            # 返回 None 让后续逻辑尝试定位
        
        return session, element
    
    async def _get_element_refs(
        self,
        page: Any,
        include_hidden: bool = False,
        max_refs: int = 100,
    ) -> List[ElementRef]:
        """
        获取页面可交互元素引用列表
        
        Args:
            page: Playwright Page 对象
            include_hidden: 是否包含隐藏元素
            max_refs: 最大返回数量
            
        Returns:
            元素引用列表
        """
        refs = []
        
        # 定义可交互元素选择器
        selectors = [
            'a[href]', 'button', 'input', 'select', 'textarea',
            '[role="button"]', '[role="link"]', '[role="checkbox"]',
            '[role="radio"]', '[role="tab"]', '[role="menuitem"]',
            '[onclick]', '[tabindex]:not([tabindex="-1"])',
        ]
        
        # 执行 JavaScript 获取元素信息
        script = f"""
        () => {{
            const refs = [];
            const selectors = {selectors!r};
            
            for (const selector of selectors) {{
                try {{
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {{
                        // 跳过隐藏元素
                        const style = window.getComputedStyle(el);
                        if (!{include_hidden!r} && (style.display === 'none' || style.visibility === 'hidden')) {{
                            continue;
                        }}
                        
                        // 生成唯一 ref
                        const ref = 'r_' + Math.random().toString(36).substr(2, 9);
                        el.setAttribute('data-ref', ref);
                        
                        // 获取边界框
                        const rect = el.getBoundingClientRect();
                        
                        refs.push({{
                            ref: ref,
                            role: el.getAttribute('role') || el.tagName.toLowerCase(),
                            name: el.getAttribute('name') || el.getAttribute('aria-label'),
                            text: el.innerText?.trim().slice(0, 100),
                            tag: el.tagName.toLowerCase(),
                            is_visible: style.display !== 'none' && style.visibility !== 'hidden',
                            is_enabled: !el.disabled,
                            is_focused: document.activeElement === el,
                            bounding_box: {{
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            }}
                        }});
                        
                        if (refs.length >= {max_refs}) {{
                            return refs;
                        }}
                    }}
                }} catch (e) {{
                    // 忽略选择器错误
                }}
            }}
            
            return refs;
        }}
        """
        
        try:
            elements_data = await page.evaluate(script)
            
            for data in elements_data:
                refs.append(ElementRef(**data))
                
        except Exception as e:
            logger.warning(
                "Failed to get element refs",
                error=str(e),
            )
        
        return refs


# =============================================================================
# 便捷函数
# =============================================================================


async def browser_action(
    action: str,
    target: str = "default",
    **kwargs,
) -> ToolResult:
    """
    便捷函数：执行浏览器动作
    
    Args:
        action: 动作名称
        target: 目标标识
        **kwargs: 其他参数
        
    Returns:
        执行结果
    """
    tool = BrowserTool()
    return await tool(action=action, target=target, **kwargs)


async def start_browser(
    target: str = "default",
    headless: bool = True,
    browser_type: str = "chromium",
) -> ToolResult:
    """
    便捷函数：启动浏览器
    
    Args:
        target: 目标标识
        headless: 是否无头模式
        browser_type: 浏览器类型
        
    Returns:
        执行结果
    """
    return await browser_action(
        action="start",
        target=target,
        headless=headless,
        browser_type=browser_type,
    )


async def browser_snapshot(target: str = "default") -> ToolResult:
    """
    便捷函数：获取浏览器快照
    
    Args:
        target: 目标标识
        
    Returns:
        执行结果
    """
    return await browser_action(action="snapshot", target=target)


async def browser_click(
    ref: str,
    target: str = "default",
) -> ToolResult:
    """
    便捷函数：点击元素
    
    Args:
        ref: 元素引用 ID
        target: 目标标识
        
    Returns:
        执行结果
    """
    return await browser_action(action="click", target=target, ref=ref)


async def browser_type(
    ref: str,
    text: str,
    target: str = "default",
    clear: bool = False,
) -> ToolResult:
    """
    便捷函数：输入文本
    
    Args:
        ref: 元素引用 ID
        text: 要输入的文本
        target: 目标标识
        clear: 是否先清除
        
    Returns:
        执行结果
    """
    return await browser_action(
        action="type",
        target=target,
        ref=ref,
        text=text,
        clear=clear,
    )


async def browser_navigate(
    url: str,
    target: str = "default",
) -> ToolResult:
    """
    便捷函数：导航到 URL
    
    Args:
        url: 目标 URL
        target: 目标标识
        
    Returns:
        执行结果
    """
    return await browser_action(action="navigate", target=target, url=url)


async def browser_screenshot(
    target: str = "default",
    full_page: bool = False,
) -> ToolResult:
    """
    便捷函数：截图
    
    Args:
        target: 目标标识
        full_page: 是否截取整个页面
        
    Returns:
        执行结果
    """
    return await browser_action(
        action="screenshot",
        target=target,
        full_page=full_page,
    )


async def stop_browser(target: str = "default") -> ToolResult:
    """
    便捷函数：停止浏览器
    
    Args:
        target: 目标标识
        
    Returns:
        执行结果
    """
    return await browser_action(action="stop", target=target)
