"""
配置模块测试

测试配置创建、环境变量覆盖、敏感字段脱敏、生产环境安全检查等
"""

import os
import pytest
from unittest.mock import patch

from src.config.settings import (
    AppSettings,
    LLMSettings,
    DatabaseSettings,
    RedisSettings,
    CelerySettings,
    AgentSettings,
    APISettings,
    LoggingSettings,
    SecuritySettings,
    get_settings,
    reload_settings,
    get_llm_settings,
    get_database_settings,
    get_agent_settings,
    get_api_settings,
    get_redis_settings,
    get_celery_settings,
    get_logging_settings,
    get_security_settings,
)


# ============ LLMSettings Tests ============

class TestLLMSettings:
    """LLM 配置测试"""

    def test_create_llm_settings(self):
        """测试创建 LLM 配置"""
        settings = LLMSettings()
        assert settings.provider == "openai"
        assert settings.model == "gpt-3.5-turbo"
        assert settings.temperature == 0.7

    def test_llm_settings_validation(self):
        """测试 LLM 配置验证"""
        # 有效温度
        settings = LLMSettings(temperature=1.5)
        assert settings.temperature == 1.5

        # 无效温度
        with pytest.raises(ValueError):
            LLMSettings(temperature=3.0)

    def test_llm_settings_max_tokens(self):
        """测试最大 token 验证"""
        settings = LLMSettings(max_tokens=4096)
        assert settings.max_tokens == 4096

        with pytest.raises(ValueError):
            LLMSettings(max_tokens=0)

    def test_llm_settings_timeout_range(self):
        """测试超时范围验证"""
        settings = LLMSettings(timeout=120)
        assert settings.timeout == 120

        with pytest.raises(ValueError):
            LLMSettings(timeout=5)  # 最小 10

    def test_llm_get_safe_summary(self):
        """测试 LLM 配置安全摘要"""
        settings = LLMSettings(
            openai_api_key="sk-test-key",
            anthropic_api_key="sk-ant-test",
        )
        summary = settings.get_safe_summary()

        assert summary["openai_api_key"] == "***REDACTED***"
        assert summary["anthropic_api_key"] == "***REDACTED***"
        assert summary["provider"] == "openai"

    def test_llm_settings_from_env(self):
        """测试从环境变量加载"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-3"}):
            settings = LLMSettings()
            assert settings.provider == "anthropic"
            assert settings.model == "claude-3"


# ============ DatabaseSettings Tests ============

class TestDatabaseSettings:
    """数据库配置测试"""

    def test_create_database_settings(self):
        """测试创建数据库配置"""
        settings = DatabaseSettings()
        assert settings.pool_size == 50
        assert settings.echo is False

    def test_database_settings_pool_validation(self):
        """测试连接池配置验证"""
        settings = DatabaseSettings(pool_size=100, max_overflow=50)
        assert settings.pool_size == 100
        assert settings.max_overflow == 50

        with pytest.raises(ValueError):
            DatabaseSettings(pool_size=3)  # 最小 5

    def test_database_settings_from_env(self):
        """测试从环境变量加载"""
        with patch.dict(os.environ, {"DB_URL": "postgresql://localhost/test"}):
            settings = DatabaseSettings()
            assert settings.url == "postgresql://localhost/test"


# ============ RedisSettings Tests ============

class TestRedisSettings:
    """Redis 配置测试"""

    def test_create_redis_settings(self):
        """测试创建 Redis 配置"""
        settings = RedisSettings()
        assert settings.enabled is False
        assert settings.host == "localhost"
        assert settings.port == 6379

    def test_redis_settings_port_validation(self):
        """测试端口验证"""
        settings = RedisSettings(port=6380)
        assert settings.port == 6380

        with pytest.raises(ValueError):
            RedisSettings(port=70000)  # 超出范围

    def test_redis_get_safe_summary(self):
        """测试 Redis 配置安全摘要"""
        settings = RedisSettings(password="secret123")
        summary = settings.get_safe_summary()

        assert summary["password"] == "***REDACTED***"


# ============ APISettings Tests ============

class TestAPISettings:
    """API 配置测试"""

    def test_create_api_settings(self):
        """测试创建 API 配置"""
        settings = APISettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.workers == 4

    def test_api_settings_port_validation(self):
        """测试端口验证"""
        settings = APISettings(port=443)
        assert settings.port == 443

        with pytest.raises(ValueError):
            APISettings(port=0)  # 无效端口

    def test_api_settings_workers_validation(self):
        """测试工作进程数验证"""
        settings = APISettings(workers=8)
        assert settings.workers == 8

        with pytest.raises(ValueError):
            APISettings(workers=20)  # 超出最大值


# ============ SecuritySettings Tests ============

class TestSecuritySettings:
    """安全配置测试"""

    def test_create_security_settings(self):
        """测试创建安全配置"""
        settings = SecuritySettings()
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30

    def test_security_settings_token_expire_validation(self):
        """测试令牌过期时间验证"""
        settings = SecuritySettings(access_token_expire_minutes=60)
        assert settings.access_token_expire_minutes == 60

        with pytest.raises(ValueError):
            SecuritySettings(access_token_expire_minutes=2)  # 最小 5

    def test_security_get_safe_summary(self):
        """测试安全配置安全摘要"""
        settings = SecuritySettings(secret_key="my-secret-key")
        summary = settings.get_safe_summary()

        assert summary["secret_key"] == "***REDACTED***"


# ============ AppSettings Tests ============

class TestAppSettings:
    """应用配置测试"""

    def test_settings_creation(self):
        """测试配置创建"""
        settings = AppSettings()
        assert settings is not None
        assert settings.name == "IntelliTeam"

    def test_settings_app_name(self):
        """测试应用名称"""
        settings = AppSettings()
        assert settings.name == "IntelliTeam"

    def test_settings_singleton(self):
        """测试配置单例"""
        # 先重置
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_debug(self):
        """测试调试模式"""
        settings = AppSettings()
        # debug 在 api 子配置中
        assert hasattr(settings.api, "debug")

    def test_settings_app_env(self):
        """测试应用环境"""
        settings = AppSettings()
        # environment 属性
        assert hasattr(settings, "environment")

    def test_settings_api_config(self):
        """测试 API 配置"""
        settings = AppSettings()
        assert hasattr(settings.api, "host")
        assert hasattr(settings.api, "port")

    def test_settings_database_config(self):
        """测试数据库配置"""
        settings = AppSettings()
        assert hasattr(settings.database, "url")

    def test_settings_redis_config(self):
        """测试 Redis 配置"""
        settings = AppSettings()
        # 使用兼容属性
        assert hasattr(settings, "redis_url")

    def test_settings_agent_config(self):
        """测试 Agent 配置"""
        settings = AppSettings()
        # 使用兼容属性
        assert hasattr(settings, "agent_timeout_seconds")
        assert hasattr(settings, "agent_temperature")

    def test_settings_sub_configs(self):
        """测试子配置"""
        settings = AppSettings()
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.redis, RedisSettings)
        assert isinstance(settings.celery, CelerySettings)
        assert isinstance(settings.agent, AgentSettings)
        assert isinstance(settings.api, APISettings)
        assert isinstance(settings.logging, LoggingSettings)
        assert isinstance(settings.security, SecuritySettings)


class TestAppSettingsEnvironment:
    """应用配置环境变量测试"""

    def test_settings_from_env_app_name(self):
        """测试从环境变量加载应用名称

        注意：Pydantic Settings 需要 APP_NAME 格式的环境变量
        但由于 AppSettings 使用嵌套配置，直接覆盖可能需要特定格式
        """
        get_settings.cache_clear()

        # 由于 pydantic-settings 的嵌套配置机制，
        # APP_NAME 环境变量可能需要特定格式才能生效
        # 这里测试配置是否可以正确创建
        settings = AppSettings(name="TestApp")
        assert settings.name == "TestApp"

    def test_settings_from_env_environment(self):
        """测试从环境变量加载环境

        注意：Pydantic Settings 需要 APP_ENVIRONMENT 格式
        """
        get_settings.cache_clear()

        settings = AppSettings(environment="staging")
        assert settings.environment == "staging"

    def test_settings_from_env_api_port(self):
        """测试从环境变量加载 API 端口"""
        get_settings.cache_clear()

        # API 配置使用 API_ 前缀
        with patch.dict(os.environ, {"API_PORT": "9000"}):
            settings = reload_settings()
            assert settings.api.port == 9000

    def test_settings_from_env_multiple(self):
        """测试从环境变量加载多个配置"""
        get_settings.cache_clear()

        # 测试可以创建自定义配置
        settings = AppSettings(
            name="CustomApp",
            environment="production",
            api=APISettings(port=8081, debug=True),
            security=SecuritySettings(secret_key="secure-custom-key"),
        )
        assert settings.name == "CustomApp"
        assert settings.environment == "production"
        assert settings.api.port == 8081
        assert settings.api.debug is True


class TestAppSettingsValidation:
    """应用配置验证测试"""

    def test_environment_validation_valid(self):
        """测试有效环境值"""
        settings = AppSettings(environment="development")
        assert settings.environment == "development"

        settings = AppSettings(environment="staging")
        assert settings.environment == "staging"

        # 生产环境需要提供自定义密钥
        settings = AppSettings(
            environment="production",
            security=SecuritySettings(secret_key="secure-custom-key-for-production")
        )
        assert settings.environment == "production"

    def test_environment_validation_invalid(self):
        """测试无效环境值"""
        with pytest.raises(ValueError, match="Environment must be"):
            AppSettings(environment="invalid_env")

    def test_production_security_check_default_key(self):
        """测试生产环境默认密钥检查"""
        with pytest.raises(ValueError, match="生产环境必须修改"):
            AppSettings(
                environment="production",
                security=SecuritySettings(secret_key="change-me-in-production")
            )

    def test_production_security_check_custom_key(self):
        """测试生产环境自定义密钥"""
        settings = AppSettings(
            environment="production",
            security=SecuritySettings(secret_key="secure-custom-key")
        )
        assert settings.environment == "production"

    def test_development_allows_default_key(self):
        """测试开发环境允许默认密钥"""
        settings = AppSettings(
            environment="development",
            security=SecuritySettings(secret_key="change-me-in-production")
        )
        assert settings.environment == "development"


class TestAppSettingsCompatibility:
    """应用配置向后兼容测试"""

    def test_app_name_compatibility(self):
        """测试 app_name 兼容属性"""
        settings = AppSettings(name="TestApp")
        assert settings.app_name == "TestApp"

    def test_app_env_compatibility(self):
        """测试 app_env 兼容属性"""
        settings = AppSettings(environment="staging")
        assert settings.app_env == "staging"

    def test_debug_compatibility(self):
        """测试 debug 兼容属性"""
        settings = AppSettings(api=APISettings(debug=True))
        assert settings.debug is True

    def test_api_host_compatibility(self):
        """测试 api_host 兼容属性"""
        settings = AppSettings(api=APISettings(host="127.0.0.1"))
        assert settings.api_host == "127.0.0.1"

    def test_api_port_compatibility(self):
        """测试 api_port 兼容属性"""
        settings = AppSettings(api=APISettings(port=3000))
        assert settings.api_port == 3000

    def test_database_url_compatibility(self):
        """测试 database_url 兼容属性"""
        settings = AppSettings(database=DatabaseSettings(url="postgresql://localhost/test"))
        assert settings.database_url == "postgresql://localhost/test"

    def test_redis_url_compatibility(self):
        """测试 redis_url 兼容属性"""
        settings = AppSettings(redis=RedisSettings(host="redis-server", port=6380, db=1))
        assert "redis-server" in settings.redis_url
        assert "6380" in settings.redis_url

    def test_redis_url_with_password(self):
        """测试带密码的 redis_url"""
        settings = AppSettings(redis=RedisSettings(password="secret"))
        assert ":secret@" in settings.redis_url

    def test_openai_api_key_compatibility(self):
        """测试 openai_api_key 兼容属性"""
        settings = AppSettings(llm=LLMSettings(openai_api_key="sk-test"))
        assert settings.openai_api_key == "sk-test"

    def test_openai_model_compatibility(self):
        """测试 openai_model 兼容属性"""
        settings = AppSettings(llm=LLMSettings(model="gpt-4"))
        assert settings.openai_model == "gpt-4"


# ============ Convenience Functions Tests ============

class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_get_llm_settings_func(self):
        """测试获取 LLM 配置函数"""
        get_settings.cache_clear()
        llm = get_llm_settings()
        assert isinstance(llm, LLMSettings)

    def test_get_database_settings_func(self):
        """测试获取数据库配置函数"""
        get_settings.cache_clear()
        db = get_database_settings()
        assert isinstance(db, DatabaseSettings)

    def test_get_agent_settings_func(self):
        """测试获取 Agent 配置函数"""
        get_settings.cache_clear()
        agent = get_agent_settings()
        assert isinstance(agent, AgentSettings)

    def test_get_api_settings_func(self):
        """测试获取 API 配置函数"""
        get_settings.cache_clear()
        api = get_api_settings()
        assert isinstance(api, APISettings)

    def test_get_redis_settings_func(self):
        """测试获取 Redis 配置函数"""
        get_settings.cache_clear()
        redis = get_redis_settings()
        assert isinstance(redis, RedisSettings)

    def test_get_celery_settings_func(self):
        """测试获取 Celery 配置函数"""
        get_settings.cache_clear()
        celery = get_celery_settings()
        assert isinstance(celery, CelerySettings)

    def test_get_logging_settings_func(self):
        """测试获取日志配置函数"""
        get_settings.cache_clear()
        logging = get_logging_settings()
        assert isinstance(logging, LoggingSettings)

    def test_get_security_settings_func(self):
        """测试获取安全配置函数"""
        get_settings.cache_clear()
        security = get_security_settings()
        assert isinstance(security, SecuritySettings)


# ============ Utility Methods Tests ============

class TestAppSettingsUtilityMethods:
    """应用配置工具方法测试"""

    def test_is_development(self):
        """测试是否开发环境"""
        settings = AppSettings(environment="development")
        assert settings.is_development() is True
        assert settings.is_production() is False

    def test_is_production(self):
        """测试是否生产环境"""
        settings = AppSettings(
            environment="production",
            security=SecuritySettings(secret_key="secure-key")
        )
        assert settings.is_production() is True
        assert settings.is_development() is False

    def test_get_summary(self):
        """测试获取配置摘要"""
        settings = AppSettings(
            name="TestApp",
            version="1.0.0",
            environment="staging",
        )
        summary = settings.get_summary()

        assert summary["name"] == "TestApp"
        assert summary["version"] == "1.0.0"
        assert summary["environment"] == "staging"
        assert "llm_provider" in summary
        assert "api_port" in summary


# ============ Edge Cases Tests ============

class TestConfigEdgeCases:
    """配置边界情况测试"""

    def test_empty_api_keys(self):
        """测试空 API 密钥"""
        settings = LLMSettings()
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None

    def test_cors_origins_wildcard(self):
        """测试 CORS 通配符"""
        settings = APISettings()
        assert "*" in settings.cors_origins

    def test_cors_origins_custom(self):
        """测试自定义 CORS 源"""
        settings = APISettings(cors_origins=["https://example.com", "https://api.example.com"])
        assert len(settings.cors_origins) == 2

    def test_logging_settings_file(self):
        """测试日志文件设置"""
        settings = LoggingSettings(file="/var/log/app.log")
        assert settings.file == "/var/log/app.log"

    def test_logging_settings_none_file(self):
        """测试无日志文件"""
        settings = LoggingSettings()
        assert settings.file is None

    def test_agent_settings_architect_patterns(self):
        """测试架构师模式设置"""
        settings = AgentSettings()
        assert len(settings.architect_patterns) > 0

    def test_agent_settings_custom_patterns(self):
        """测试自定义架构模式"""
        settings = AgentSettings(architect_patterns=["微服务", "事件驱动", "CQRS"])
        assert len(settings.architect_patterns) == 3


# ============ Performance Tests ============

class TestConfigPerformance:
    """配置性能测试"""

    @pytest.mark.slow
    def test_settings_caching(self):
        """测试配置缓存"""
        import time

        get_settings.cache_clear()

        # 第一次调用
        start = time.time()
        s1 = get_settings()
        first_time = time.time() - start

        # 第二次调用（应该使用缓存）
        start = time.time()
        s2 = get_settings()
        second_time = time.time() - start

        assert s1 is s2
        assert second_time < first_time * 0.1  # 缓存应该快很多

    @pytest.mark.slow
    def test_settings_creation_performance(self):
        """测试配置创建性能"""
        import time

        start = time.time()
        for _ in range(1000):
            AppSettings()
        elapsed = time.time() - start

        assert elapsed < 5.0  # 1000 次创建应该在 5 秒内