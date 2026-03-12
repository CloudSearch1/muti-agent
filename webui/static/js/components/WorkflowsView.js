/**
 * 工作流视图组件
 */

import { DEFAULT_WORKFLOWS } from '../utils/constants.js';

export const WorkflowsView = {
    name: 'WorkflowsView',
    
    props: {
        workflows: {
            type: Array,
            default: () => DEFAULT_WORKFLOWS
        }
    },
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-white">工作流</h1>
                    <p class="text-gh-text mt-1">管理和监控自动化工作流</p>
                </div>
                <button class="btn-primary flex items-center justify-center gap-2">
                    <i class="fas fa-plus"></i>新建工作流
                </button>
            </div>
            
            <!-- 工作流列表 -->
            <div class="space-y-4">
                <div v-for="workflow in workflows" :key="workflow.id" class="gh-card">
                    <div class="gh-card-header flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-gh-blue/10 flex items-center justify-center">
                                <i class="fas fa-project-diagram text-gh-blue"></i>
                            </div>
                            <div>
                                <h3 class="font-semibold text-white">{{ workflow.name }}</h3>
                                <p class="text-sm text-gh-text">{{ workflow.steps.length }} 个步骤</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="badge badge-success">运行中</span>
                            <button class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- 步骤流程 -->
                    <div class="gh-card-body">
                        <div class="flex flex-wrap items-center gap-2">
                            <template v-for="(step, index) in workflow.steps" :key="step.name">
                                <div class="flex items-center gap-3 px-4 py-3 rounded-lg bg-gh-elevated border border-gh-border">
                                    <div class="w-8 h-8 rounded-lg bg-gh-bg flex items-center justify-center">
                                        <i :class="[step.icon, 'text-gh-text']"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-medium text-white">{{ step.name }}</p>
                                        <p class="text-xs text-gh-text">{{ step.agent }}</p>
                                    </div>
                                </div>
                                <div v-if="index < workflow.steps.length - 1" class="text-gh-text">
                                    <i class="fas fa-arrow-right"></i>
                                </div>
                            </template>
                        </div>
                    </div>
                    
                    <!-- 统计 -->
                    <div class="px-6 py-4 border-t border-gh-border bg-gh-elevated/30">
                        <div class="flex items-center gap-8 text-sm">
                            <span class="text-gh-text">
                                <i class="fas fa-check-circle text-gh-green mr-1"></i>
                                已完成: 145
                            </span>
                            <span class="text-gh-text">
                                <i class="fas fa-clock text-gh-blue mr-1"></i>
                                平均耗时: 4.2h
                            </span>
                            <span class="text-gh-text">
                                <i class="fas fa-percentage text-gh-purple mr-1"></i>
                                成功率: 96%
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 模板推荐 -->
            <div class="gh-card">
                <div class="gh-card-header">
                    <h2 class="text-lg font-semibold text-white">工作流模板</h2>
                </div>
                <div class="gh-card-body">
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div v-for="template in workflowTemplates" :key="template.name"
                             class="p-4 rounded-xl border border-gh-border hover:border-gh-blue hover:bg-gh-blue/5 transition cursor-pointer group">
                            <div class="flex items-center gap-3 mb-3">
                                <div :class="['w-10 h-10 rounded-lg flex items-center justify-center', template.bgColor]">
                                    <i :class="[template.icon, template.iconColor]"></i>
                                </div>
                                <h4 class="font-medium text-white group-hover:text-gh-blue transition">{{ template.name }}</h4>
                            </div>
                            <p class="text-sm text-gh-text">{{ template.description }}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            workflowTemplates: [
                { 
                    name: 'Bug修复流程', 
                    description: '从发现问题到修复完成的完整流程',
                    icon: 'fas fa-bug',
                    bgColor: 'bg-red-500/10',
                    iconColor: 'text-red-400'
                },
                { 
                    name: '功能开发流程', 
                    description: '新功能从需求到上线的标准流程',
                    icon: 'fas fa-code',
                    bgColor: 'bg-blue-500/10',
                    iconColor: 'text-blue-400'
                },
                { 
                    name: '代码审查流程', 
                    description: '自动化代码审查和质量检查',
                    icon: 'fas fa-eye',
                    bgColor: 'bg-green-500/10',
                    iconColor: 'text-green-400'
                },
                { 
                    name: '文档生成流程', 
                    description: '自动从代码生成技术文档',
                    icon: 'fas fa-file-alt',
                    bgColor: 'bg-yellow-500/10',
                    iconColor: 'text-yellow-400'
                },
                { 
                    name: '测试执行流程', 
                    description: '自动化测试执行和报告生成',
                    icon: 'fas fa-vial',
                    bgColor: 'bg-purple-500/10',
                    iconColor: 'text-purple-400'
                },
                { 
                    name: '部署发布流程', 
                    description: '自动化部署和发布管理',
                    icon: 'fas fa-rocket',
                    bgColor: 'bg-cyan-500/10',
                    iconColor: 'text-cyan-400'
                }
            ]
        };
    }
};

export default WorkflowsView;
