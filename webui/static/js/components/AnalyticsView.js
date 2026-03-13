/**
 * 数据分析视图组件
 */

export const AnalyticsView = {
    name: 'AnalyticsView',
    
    props: {
        stats: {
            type: Object,
            default: () => ({ totalTasks: 0, activeAgents: 0, completionRate: 0 })
        },
        agents: {
            type: Array,
            default: () => []
        },
        tasks: {
            type: Array,
            default: () => []
        }
    },
    
    data() {
        return {
            currentTime: new Date().toLocaleTimeString('zh-CN'),
            charts: {}
        };
    },
    
    mounted() {
        this.updateTime();
        setInterval(() => this.updateTime(), 1000);
        this.$nextTick(() => {
            this.initCharts();
        });
    },
    
    methods: {
        updateTime() {
            this.currentTime = new Date().toLocaleTimeString('zh-CN');
        },
        
        async initCharts() {
            // 延迟加载 Chart.js
            if (!window.Chart) {
                await this.loadChartJS();
            }
            this.renderCharts();
        },
        
        loadChartJS() {
            return new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        },
        
        renderCharts() {
            this.renderTaskTrendChart();
            this.renderAgentEfficiencyChart();
            this.renderTaskTypeChart();
            this.renderWeeklyActivityChart();
        },
        
        renderTaskTrendChart() {
            const ctx = document.getElementById('analyticsTaskTrend');
            if (!ctx) return;
            
            if (this.charts.taskTrend) {
                this.charts.taskTrend.destroy();
            }
            
            this.charts.taskTrend = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
                    datasets: [{
                        label: '完成任务数',
                        data: [12, 19, 15, 22, 18, 14, 20],
                        borderColor: '#33BB22',
                        backgroundColor: 'rgba(51, 187, 34, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#30363d' },
                            ticks: { color: '#6A737D' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#6A737D' }
                        }
                    }
                }
            });
        },
        
        renderAgentEfficiencyChart() {
            const ctx = document.getElementById('analyticsAgentEfficiency');
            if (!ctx) return;
            
            if (this.charts.agentEfficiency) {
                this.charts.agentEfficiency.destroy();
            }
            
            const agentNames = this.agents.map(a => a.name);
            const agentTasks = this.agents.map(a => a.tasksCompleted);
            
            this.charts.agentEfficiency = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: agentNames,
                    datasets: [{
                        label: '完成任务数',
                        data: agentTasks,
                        backgroundColor: [
                            'rgba(51, 187, 34, 0.8)',
                            'rgba(3, 102, 214, 0.8)',
                            'rgba(137, 87, 229, 0.8)',
                            'rgba(240, 199, 68, 0.8)',
                            'rgba(218, 54, 51, 0.8)',
                            'rgba(88, 166, 255, 0.8)',
                            'rgba(255, 121, 63, 0.8)'
                        ],
                        borderColor: [
                            '#33BB22',
                            '#0366D6',
                            '#8957e5',
                            '#F0C744',
                            '#DA3633',
                            '#58a6ff',
                            '#ff793f'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#30363d' },
                            ticks: { color: '#6A737D' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#6A737D' }
                        }
                    }
                }
            });
        },
        
        renderTaskTypeChart() {
            const ctx = document.getElementById('analyticsTaskType');
            if (!ctx) return;
            
            if (this.charts.taskType) {
                this.charts.taskType.destroy();
            }
            
            this.charts.taskType = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['开发', '测试', '设计', '文档', '其他'],
                    datasets: [{
                        data: [45, 25, 15, 10, 5],
                        backgroundColor: [
                            'rgba(51, 187, 34, 0.8)',
                            'rgba(3, 102, 214, 0.8)',
                            'rgba(137, 87, 229, 0.8)',
                            'rgba(240, 199, 68, 0.8)',
                            'rgba(110, 118, 129, 0.8)'
                        ],
                        borderColor: '#161b22',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: '#6A737D', padding: 15 }
                        }
                    }
                }
            });
        },
        
        renderWeeklyActivityChart() {
            const ctx = document.getElementById('analyticsWeeklyActivity');
            if (!ctx) return;
            
            if (this.charts.weeklyActivity) {
                this.charts.weeklyActivity.destroy();
            }
            
            this.charts.weeklyActivity = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: ['任务创建', '任务完成', 'Agent 活跃', '代码提交', '文档更新'],
                    datasets: [{
                        label: '本周',
                        data: [85, 78, 92, 65, 45],
                        backgroundColor: 'rgba(51, 187, 34, 0.2)',
                        borderColor: '#33BB22',
                        pointBackgroundColor: '#33BB22',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#33BB22'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            angleLines: { color: '#30363d' },
                            grid: { color: '#30363d' },
                            pointLabels: { color: '#6A737D' },
                            ticks: { display: false, backdropColor: 'transparent' }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
    },
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex items-center justify-between">
                <h1 class="text-2xl font-bold text-white flex items-center">
                    <i class="fas fa-chart-line mr-2 text-gh-text"></i>数据分析
                </h1>
                <span class="text-sm text-gh-text">{{ currentTime }}</span>
            </div>
            
            <!-- 统计概览 -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">总任务数</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ stats.totalTasks }}</p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-tasks text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">完成率</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ stats.completionRate }}%</p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-chart-pie text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">活跃 Agent</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ stats.activeAgents }}</p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-robot text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">平均效率</p>
                            <p class="text-3xl font-bold text-green-400 mt-1">94%</p>
                        </div>
                        <div class="w-12 h-12 bg-green-500/10 rounded-xl flex items-center justify-center border border-green-500/20">
                            <i class="fas fa-bolt text-green-400 text-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 图表区域 -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div class="gh-card">
                    <div class="gh-card-header">
                        <h3 class="font-semibold text-white text-sm">任务完成趋势</h3>
                    </div>
                    <div class="gh-card-body" style="height: 250px; position: relative;">
                        <canvas id="analyticsTaskTrend"></canvas>
                    </div>
                </div>
                
                <div class="gh-card">
                    <div class="gh-card-header">
                        <h3 class="font-semibold text-white text-sm">Agent 效率对比</h3>
                    </div>
                    <div class="gh-card-body" style="height: 250px; position: relative;">
                        <canvas id="analyticsAgentEfficiency"></canvas>
                    </div>
                </div>
                
                <div class="gh-card">
                    <div class="gh-card-header">
                        <h3 class="font-semibold text-white text-sm">任务类型分布</h3>
                    </div>
                    <div class="gh-card-body" style="height: 250px; position: relative;">
                        <canvas id="analyticsTaskType"></canvas>
                    </div>
                </div>
                
                <div class="gh-card">
                    <div class="gh-card-header">
                        <h3 class="font-semibold text-white text-sm">每周活跃度</h3>
                    </div>
                    <div class="gh-card-body" style="height: 250px; position: relative;">
                        <canvas id="analyticsWeeklyActivity"></canvas>
                    </div>
                </div>
            </div>
        </div>
    `
};
