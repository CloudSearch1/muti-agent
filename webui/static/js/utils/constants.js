/**
 * 全局常量定义
 * 统一管理和复用常量，避免硬编码
 */

// 导航标签
export const TABS = [
    { id: 'dashboard', name: '仪表盘', icon: 'fas fa-home' },
    { id: 'tasks', name: '任务', icon: 'fas fa-tasks' },
    { id: 'agents', name: 'Agent', icon: 'fas fa-users' },
    { id: 'workflows', name: '工作流', icon: 'fas fa-project-diagram' },
    { id: 'analytics', name: '分析', icon: 'fas fa-chart-line' },
    { id: 'skills', name: '技能', icon: 'fas fa-puzzle-piece' },
    { id: 'ai-assistant', name: 'AI助手', icon: 'fas fa-robot' }
];

// 任务优先级
export const PRIORITIES = {
    low: { label: '低优先级', color: 'badge-neutral', value: 'low' },
    normal: { label: '中优先级', color: 'badge-info', value: 'normal' },
    high: { label: '高优先级', color: 'badge-warning', value: 'high' },
    critical: { label: '紧急', color: 'badge-danger', value: 'critical' }
};

// 任务状态
export const TASK_STATUS = {
    pending: { label: '待处理', color: 'badge-neutral', icon: 'fas fa-clock' },
    in_progress: { label: '进行中', color: 'badge-info', icon: 'fas fa-spinner fa-spin' },
    completed: { label: '已完成', color: 'badge-success', icon: 'fas fa-check-circle' }
};

// Agent状态
export const AGENT_STATUS = {
    idle: { label: '空闲', color: 'text-gh-green', bgColor: 'bg-gh-green/10', icon: 'fas fa-circle' },
    busy: { label: '工作中', color: 'text-gh-yellow', bgColor: 'bg-gh-yellow/10', icon: 'fas fa-circle' },
    offline: { label: '离线', color: 'text-gh-text', bgColor: 'bg-gh-text/10', icon: 'fas fa-circle' }
};

// 技能分类
export const SKILL_CATEGORIES = [
    { value: 'general', label: '通用' },
    { value: 'code_review', label: '代码审查' },
    { value: 'api', label: 'API' },
    { value: 'generation', label: '生成' },
    { value: 'docs', label: '文档' },
    { value: 'testing', label: '测试' }
];

// AI提供商
export const AI_PROVIDERS = {
    bailian: { 
        name: '阿里云百炼', 
        models: ['qwen3.5-plus', 'qwen3-max-2026-01-23', 'qwen3-coder-next', 'qwen3-coder-plus', 'MiniMax-M2.5', 'glm-5', 'glm-4.7', 'kimi-k2.5']
    },
    anthropic: { 
        name: 'Anthropic', 
        models: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5']
    },
    openai: { 
        name: 'OpenAI', 
        models: ['gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']
    },
    deepseek: { 
        name: 'DeepSeek', 
        models: ['deepseek-chat', 'deepseek-coder']
    }
};

// 模型详细信息
export const MODEL_DETAILS = {
    'qwen3.5-plus': { 
        name: 'Qwen3.5 Plus', 
        description: '通义千问3.5增强版，性价比最优',
        inputCost: '¥0.0004/千tokens',
        outputCost: '¥0.002/千tokens',
        contextWindow: 131072,
        maxTokens: 8192,
        reasoning: true
    },
    'qwen3-max-2026-01-23': { 
        name: 'Qwen3 Max', 
        description: '通义千问3最强版，适合复杂任务',
        inputCost: '¥0.002/千tokens',
        outputCost: '¥0.006/千tokens',
        contextWindow: 131072,
        maxTokens: 8192,
        reasoning: true
    },
    'qwen3-coder-next': { 
        name: 'Qwen3 Coder Next', 
        description: '代码专用模型，最新版',
        inputCost: '¥0.0004/千tokens',
        outputCost: '¥0.002/千tokens',
        contextWindow: 131072,
        maxTokens: 8192,
        reasoning: false
    },
    'qwen3-coder-plus': { 
        name: 'Qwen3 Coder Plus', 
        description: '代码专用模型，增强版',
        inputCost: '¥0.0004/千tokens',
        outputCost: '¥0.002/千tokens',
        contextWindow: 131072,
        maxTokens: 8192,
        reasoning: false
    }
};

// 默认设置
export const DEFAULT_SETTINGS = {
    aiProvider: 'bailian',
    apiKey: '',
    apiEndpoint: '',
    model: 'qwen3.5-plus',
    temperature: 0.7,
    maxTokens: 4096,
    contextWindow: null,
    autoSave: true,
    theme: 'dark',
    language: 'zh-CN'
};

// 默认Agent数据
export const DEFAULT_AGENTS = [
    { name: 'Planner', role: '任务规划师', icon: 'fas fa-clipboard-list', description: '负责任务分解和优先级排序', status: 'idle', tasksCompleted: 45, avgTime: 2.3, successRate: 98 },
    { name: 'Architect', role: '系统架构师', icon: 'fas fa-building', description: '负责系统架构设计和技术选型', status: 'busy', tasksCompleted: 38, avgTime: 5.7, successRate: 96 },
    { name: 'Coder', role: '代码工程师', icon: 'fas fa-laptop-code', description: '负责代码实现和功能开发', status: 'busy', tasksCompleted: 89, avgTime: 8.2, successRate: 94 },
    { name: 'Tester', role: '测试工程师', icon: 'fas fa-vial', description: '负责测试用例和质量保障', status: 'idle', tasksCompleted: 67, avgTime: 4.5, successRate: 97 },
    { name: 'DocWriter', role: '文档工程师', icon: 'fas fa-file-alt', description: '负责技术文档编写', status: 'idle', tasksCompleted: 52, avgTime: 3.8, successRate: 99 },
    { name: 'SeniorArchitect', role: '资深架构师', icon: 'fas fa-chess', description: '负责复杂系统设计和代码审查', status: 'idle', tasksCompleted: 23, avgTime: 12.5, successRate: 98 },
    { name: 'ResearchAgent', role: '研究助手', icon: 'fas fa-search', description: '负责文献调研和技术分析', status: 'idle', tasksCompleted: 15, avgTime: 6.8, successRate: 95 }
];

// 默认任务数据
export const DEFAULT_TASKS = [
    { id: 1, title: '创建用户管理 API', description: '实现用户注册、登录、权限管理等功能', priority: 'high', status: 'in_progress', assignee: '张三', agent: 'Coder', createdAt: '2026-03-03 10:30', time: '2 小时前' },
    { id: 2, title: '数据库设计', description: '设计用户表和权限表结构', priority: 'normal', status: 'completed', assignee: '李四', agent: 'Architect', createdAt: '2026-03-03 09:15', time: '3 小时前' },
    { id: 3, title: '编写测试用例', description: '为 API 接口编写单元测试', priority: 'normal', status: 'pending', assignee: '王五', agent: 'Tester', createdAt: '2026-03-03 11:00', time: '1 小时前' },
    { id: 4, title: '性能优化', description: '优化系统响应速度', priority: 'critical', status: 'in_progress', assignee: '张三', agent: 'SeniorArchitect', createdAt: '2026-03-04 14:20', time: '30 分钟前' },
    { id: 5, title: '文档更新', description: '更新 API 文档和使用说明', priority: 'low', status: 'pending', assignee: '李四', agent: 'DocWriter', createdAt: '2026-03-04 16:45', time: '15 分钟前' }
];

// 默认工作流
export const DEFAULT_WORKFLOWS = [
    {
        id: 1,
        name: '标准研发流程',
        steps: [
            { name: '需求分析', agent: 'Planner', icon: 'fas fa-clipboard-list' },
            { name: '架构设计', agent: 'Architect', icon: 'fas fa-building' },
            { name: '代码开发', agent: 'Coder', icon: 'fas fa-laptop-code' },
            { name: '测试', agent: 'Tester', icon: 'fas fa-vial' },
            { name: '文档', agent: 'DocWriter', icon: 'fas fa-file-alt' }
        ]
    }
];

// 默认技能数据
export const DEFAULT_SKILLS = [
    { id: 1, name: 'simplify', description: 'Review code for reuse, quality, and efficiency', category: 'code_review', version: '1.0.0', config: { auto_fix: true }, enabled: true, createdAt: '2026-03-01 10:00' },
    { id: 2, name: 'claude-api', description: 'Build apps with Claude API or Anthropic SDK', category: 'api', version: '1.0.0', config: { model: 'claude-sonnet-4-6' }, enabled: true, createdAt: '2026-03-01 10:00' },
    { id: 3, name: 'code-generation', description: 'Generate code from natural language', category: 'generation', version: '1.2.0', config: { language: 'python' }, enabled: true, createdAt: '2026-03-02 14:30' },
    { id: 4, name: 'documentation', description: 'Generate documentation for code files', category: 'docs', version: '1.0.0', config: { format: 'markdown' }, enabled: true, createdAt: '2026-03-02 14:30' },
    { id: 5, name: 'testing', description: 'Generate and run tests for code', category: 'testing', version: '1.1.0', config: { framework: 'pytest' }, enabled: false, createdAt: '2026-03-03 09:15' }
];
