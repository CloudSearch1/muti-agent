"""配置模块测试"""

from src.config.settings import Settings, get_settings


class TestConfig:
    """配置测试类"""

    def test_settings_creation(self):
        """测试配置创建"""
        settings = Settings()
        assert settings is not None

    def test_settings_app_name(self):
        """测试应用名称"""
        settings = Settings()
        assert settings.app_name == "IntelliTeam"

    def test_get_settings_singleton(self):
        """测试配置单例"""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_debug(self):
        """测试调试模式"""
        settings = Settings()
        # Settings 有 debug 属性
        assert hasattr(settings, "debug")

    def test_settings_app_env(self):
        """测试应用环境"""
        settings = Settings()
        # Settings 有 app_env 属性
        assert hasattr(settings, "app_env")

    def test_settings_api_config(self):
        """测试 API 配置"""
        settings = Settings()
        assert hasattr(settings, "api_host")
        assert hasattr(settings, "api_port")

    def test_settings_database_config(self):
        """测试数据库配置"""
        settings = Settings()
        assert hasattr(settings, "database_url")

    def test_settings_redis_config(self):
        """测试 Redis 配置"""
        settings = Settings()
        assert hasattr(settings, "redis_url")

    def test_settings_agent_config(self):
        """测试 Agent 配置"""
        settings = Settings()
        assert hasattr(settings, "agent_timeout_seconds")
        assert hasattr(settings, "agent_temperature")
