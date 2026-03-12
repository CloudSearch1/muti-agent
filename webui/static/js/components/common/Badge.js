/**
 * 徽章组件
 * 用于状态、标签等展示
 */

export const Badge = {
    name: 'Badge',
    
    props: {
        type: {
            type: String,
            default: 'neutral',
            validator: (value) => ['success', 'warning', 'danger', 'info', 'neutral'].includes(value)
        },
        text: {
            type: String,
            required: true
        },
        size: {
            type: String,
            default: 'md', // sm, md, lg
            validator: (value) => ['sm', 'md', 'lg'].includes(value)
        },
        dot: {
            type: Boolean,
            default: false
        },
        pulse: {
            type: Boolean,
            default: false
        }
    },
    
    template: `
        <span :class="badgeClass">
            <span v-if="dot" :class="['w-2 h-2 rounded-full mr-1.5', dotClass, { 'animate-pulse': pulse }]"></span>
            {{ text }}
        </span>
    `,
    
    computed: {
        badgeClass() {
            const baseClasses = 'inline-flex items-center font-medium rounded-full';
            
            const typeClasses = {
                success: 'bg-green-500/10 text-green-400 border border-green-500/20',
                warning: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
                danger: 'bg-red-500/10 text-red-400 border border-red-500/20',
                info: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
                neutral: 'bg-gh-elevated text-gh-text border border-gh-border'
            };
            
            const sizeClasses = {
                sm: 'px-2 py-0.5 text-xs',
                md: 'px-2.5 py-1 text-xs',
                lg: 'px-3 py-1.5 text-sm'
            };
            
            return [baseClasses, typeClasses[this.type], sizeClasses[this.size]];
        },
        
        dotClass() {
            const classes = {
                success: 'bg-green-400',
                warning: 'bg-yellow-400',
                danger: 'bg-red-400',
                info: 'bg-blue-400',
                neutral: 'bg-gh-text'
            };
            return classes[this.type];
        }
    }
};

export default Badge;
